# - sebuah graph hanya bisa melayani 1 sop
# - ketika dia sudah masuk ke 1 sop, maka akan terkunci sampai sop tersebut selesai
# - apakah proses permintaan status tiket bisa disebut sebagai sop? butuh kepastian ini karena ada intent check di awal
# - early exit terjadi bukan hanya ketika data tidak cukup (post parsing, pre db call), 
# 	tapi juga ketika data tidak valid (post db call)
# - parsing menggunakan structured output llm, dengan description di setiap fieldnya
# - invalid data (post db call) harus dihandle dengan benar
# - technical error juga harus dihandle dengan benar

from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from langgraph.graph import StateGraph, START, END
from langchain.chat_models import init_chat_model 
from langchain.messages import HumanMessage, AIMessage, SystemMessage, AnyMessage
from sops.sop1_failed_transaction import construct_graph as sop1_construct_graph, Sop1State
from sops.sop2_double_digit import construct_graph as sop2_construct_graph, Sop2State

# -------------------------------------------------------------------------------------
# CONFIG & CONSTANTS
# -------------------------------------------------------------------------------------

load_dotenv()

llm = init_chat_model("gpt-5-mini")

CHAT_INTENT = Literal[
	"GENERAL_CHAT",
	"FAILED_TRANSACTION",
	"DOUBLE_DIGIT",
	"UNSUPPORTED_COMPLAIN"
]


# -------------------------------------------------------------------------------------
# STATE DEFINITION
# -------------------------------------------------------------------------------------

class CoreState(BaseModel):
	# input
	user_input: Optional[str] = None
	conversation: List[AnyMessage] = []
	
	# process
	intent: Optional[CHAT_INTENT] = None
	early_exit_node: Optional[str] = None
	
	# user verification data
	user_email: Optional[str] = None
	user_phone: Optional[str] = None

	# subgraph states
	sop1_state: Optional[Sop1State] = None

	# output
	result: Optional[str] = None


# -------------------------------------------------------------------------------------
# IN-MEMORY DATABASE
# -------------------------------------------------------------------------------------

saved_state: Optional[CoreState] = None
saved_conversation: List[AnyMessage] = []


# -------------------------------------------------------------------------------------
# NODE DEFINITION
# -------------------------------------------------------------------------------------

def node_check_user_intent (state: CoreState) -> CoreState:
	prompt = "kamu adalah intent clasifier yang bertugas untuk mengecek intent dari sebuah pesan."

	conversation = [
		SystemMessage(prompt),
		HumanMessage(state.user_input)
	]

	class ChatIntent(BaseModel):
		intent: Literal[CHAT_INTENT] = Field(...,
			description="""
			jika pesan user seperti percakapan kasual, maka return GENERAL_CHAT.
			jika pesan user seperti komplain, maka klasifikasikan berdasarkan jenis komplain berikut:
			- FAILED_TRANSACTION: berkaitan dengan transaksi gagal, transfer uang gagal
			- DOUBLE_DIGIT: berkaitan dengan transaksi yang tercatat lebih dari sekali padahal cuma dilakukan sekali
			- UNSUPPORTED_COMPLAIN: jika komplainnya tidak memenuhi kriteria di atas  
			"""
		)
	
	llm_structured_output = llm.with_structured_output(ChatIntent)
	llm_result = llm_structured_output.invoke(conversation)

	state.intent = llm_result.intent

	print("-> node_check_user_intent", state.intent)
	return state


def node_user_verification (state: CoreState) -> CoreState:
	prompt = """tugas kamu adalah mengambil informasi tentang email dan nomor hp dari pesan user."""

	conversation = [
		SystemMessage(prompt),
		HumanMessage(state.user_input)
	]

	class UserInfo(BaseModel):
		user_email: Optional[str] = Field(..., description="email dari user")
		user_phone: Optional[str] = Field(..., description="nomor hp dari user")

	llm_structured_output = llm.with_structured_output(UserInfo)
	llm_result = llm_structured_output.invoke(conversation)
	
	if llm_result.user_email:
		state.user_email = llm_result.user_email

	if llm_result.user_phone:
		state.user_phone = llm_result.user_phone

	if not state.user_email or not state.user_phone:
		state.early_exit_node = 'node_user_verification'
	else:
		state.early_exit_node = None

	print(f"""-> node_user_verification
		user_email = {state.user_email}
		user_phone = {state.user_phone}
		early_exit_node = {state.early_exit_node}""")
	return state


def node_call_subgraph (state: CoreState) -> CoreState:
	print("-> node_call_subgraph")
	return state


def node_process_final_answer (state: CoreState) -> CoreState:
	print("-> node_process_final_answer")
	prompt="""Kamu adalah customer support agent."""
	

	if state.intent == "UNSUPPORTED_COMPLAIN":
		prompt += f"""
		Jawab pesan dari user sesuai dengan informasi berikut.
		- support type: UNSUPPORTED_COMPLAIN.

		karena komplain dari user belum dapat diselesaikan, sampaikan permohonan maaf.
		"""

	elif state.intent != "GENERAL_CHAT":
		prompt += f"""
		Jawab pesan dari user sesuai dengan informasi berikut.
		- support type: {state.intent}

		user harus memiliki informasi EMAIL dan PHONE, berikut informasi yang sekarang dimiliki user.
		- EMAIL: {state.user_email}
		- PHONE: {state.user_phone}

		jika salah satu atau kedua dari informasi tersebut tidak ada, maka minta user untuk melengkapi email dan nomor hp.
		tapi jika keduanya tersedia, sampaikan ke user bahwa komplainnya sedang ditindaklanjuti.
		jangan meminta untuk melengkapi diluar hal tersebut.
		"""


	conversation = [ SystemMessage(prompt) ] + state.conversation
	llm_result = llm.invoke(conversation)

	state.result = llm_result.content
	state.conversation.append(AIMessage(state.result))
	
	return state


def node_save_conversation_and_state (state: CoreState) -> CoreState:
	print("-> node_save_conversation_and_state")
	global saved_conversation
	global saved_state
	saved_conversation = state.conversation
	saved_state = state
	return state


# -------------------------------------------------------------------------------------
# SUB-GRAPH DEFINITION
# -------------------------------------------------------------------------------------

def call_sop1 (state: CoreState) -> CoreState:
	
	subgraph = sop1_construct_graph()
	subgraph_result = subgraph.invoke(Sop1State(
		user_input=state.user_input,
		user_email=state.user_email,
		user_phone=state.user_phone,
	))
	
	state.sop1_state = Sop1State(**subgraph_result)

	print("-> call_sop1", state.sop1_state.contoh_result)
	return state


def call_sop2 (state: CoreState) -> CoreState:
	
	subgraph = sop2_construct_graph()
	subgraph_result = subgraph.invoke(Sop2State(
		user_input=state.user_input,
		user_email=state.user_email,
		user_phone=state.user_phone,
	))
	
	state.sop1_state = Sop1State(**subgraph_result)

	print("-> call_sop2", state.sop1_state.contoh_result)
	return state


# -------------------------------------------------------------------------------------
# GATE DEFINITION
# -------------------------------------------------------------------------------------

def gate_entry_routing (state: CoreState) -> str:
	if state.early_exit_node:
		entry_route = state.early_exit_node
	else:
		entry_route = 'node_check_user_intent' 

	print('-> gate_entry_routing', entry_route)
	return entry_route


def gate_is_valid_complain (state: CoreState) -> bool:
	is_valid_complain = state.intent not in ["GENERAL_CHAT", "UNSUPPORTED_COMPLAIN"]

	print('-> gate_is_valid_complain', state.intent, is_valid_complain)
	return is_valid_complain


def gate_is_early_exit (state: CoreState) -> bool:
	is_early_exit = bool(state.early_exit_node)

	print('-> gate_is_early_exit', is_early_exit)
	return is_early_exit


# -------------------------------------------------------------------------------------
# LANGGRAPH EXECUTION
# -------------------------------------------------------------------------------------

def prepare_state (user_input: str) -> CoreState:
	state = CoreState() if not saved_state else saved_state

	state.user_input = user_input
	state.result = None
	
	state.conversation = saved_conversation
	state.conversation.append(HumanMessage(user_input))

	return state


def construct_graph():
	graph = StateGraph(CoreState)
	
	# main nodes
	graph.add_node(node_check_user_intent)
	graph.add_node(node_user_verification)
	graph.add_node(node_call_subgraph)
	graph.add_node(node_process_final_answer)
	graph.add_node(node_save_conversation_and_state)

	# subgraph nodes
	graph.add_node(call_sop1)
	graph.add_node(call_sop2)

	graph.add_conditional_edges(START, gate_entry_routing, {
		'node_check_user_intent': 'node_check_user_intent',
		'node_user_verification': 'node_user_verification',
	})
	graph.add_conditional_edges('node_check_user_intent', gate_is_valid_complain, {
		True: 'node_user_verification',
		False: 'node_process_final_answer'
	})
	graph.add_conditional_edges('node_user_verification', gate_is_early_exit, {
		True: 'node_process_final_answer',
		False: 'node_call_subgraph'
	})
	graph.add_conditional_edges('node_call_subgraph', lambda state: state.intent, {
		'FAILED_TRANSACTION'	: 'call_sop1',
		'DOUBLE_DIGIT'			: 'call_sop2'
	})
	
	graph.add_edge('call_sop1', 'node_process_final_answer')
	graph.add_edge('call_sop2', 'node_process_final_answer')

	graph.add_edge('node_process_final_answer', 'node_save_conversation_and_state')
	graph.add_edge('node_save_conversation_and_state', END)

	return graph.compile()


# -------------------------------------------------------------------------------------
# MAIN LOOP
# -------------------------------------------------------------------------------------

while True:
	user_input = input('[User]: ')

	if not user_input:
		print('\ntolong tulis sesuatu.\n')
		continue
	
	state = prepare_state(user_input)
	graph = construct_graph()
	# print(graph.get_graph().draw_ascii())
	
	graph_result = graph.invoke(state)

	print(f"[AI]: {graph_result["result"]}")