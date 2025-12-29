# - sebuah graph hanya bisa melayani 1 sop
# - ketika dia sudah masuk ke 1 sop, maka akan terkunci sampai sop tersebut selesai
# - apakah proses permintaan status tiket bisa disebut sebagai sop? butuh kepastian ini karena ada intent check di awal
# - early exit terjadi bukan hanya ketika data tidak cukup (post parsing, pre db call), 
# 	tapi juga ketika data tidak valid (post db call)
# - parsing menggunakan structured output llm, dengan description di setiap fieldnya
# - invalid data (post db call) harus dihandle dengan benar
# - technical error juga harus dihandle dengan benar
# - is_early_exit tidak boleh dicleanup, hanya boleh dihapus oleh node penyebabnya

from dotenv import load_dotenv
load_dotenv()


from typing import List, Literal, Optional
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END
from langchain.messages import HumanMessage, AIMessage, SystemMessage, AnyMessage

from model import llm
from config import CHAT_INTENT, STEPS
from sops.sop1_failed_transaction import construct_graph as sop1_construct_graph, Sop1State
from sops.sop2_double_debit import construct_graph as sop2_construct_graph, Sop2State


# -------------------------------------------------------------------------------------
# STATE DEFINITION
# -------------------------------------------------------------------------------------

class CoreState(BaseModel):
	# input
	user_input: Optional[str] = None
	conversation: List[AnyMessage] = []
	
	# process
	intent: Optional[CHAT_INTENT] = None
	current_step: Optional[STEPS] = None
	is_early_exit: bool = False
	
	# user verification data
	user_email: Optional[str] = None
	user_phone: Optional[str] = None

	# subgraph states
	sop1_state: Optional[Sop1State] = None
	sop2_state: Optional[Sop2State] = None

	# output
	sop_additional_prompt: Optional[str] = None
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
	state.current_step = "INTENT_CHECK"
	
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
			- DOUBLE_DEBIT: berkaitan dengan transaksi yang tercatat lebih dari sekali padahal cuma dilakukan sekali
			- UNSUPPORTED_COMPLAIN: jika komplainnya tidak memenuhi kriteria di atas  
			"""
		)
	
	llm_structured_output = llm.with_structured_output(ChatIntent)
	llm_result = llm_structured_output.invoke(conversation)

	state.intent = llm_result.intent

	print("-> node_check_user_intent", state.intent)
	return state


def node_user_verification (state: CoreState) -> CoreState:
	state.current_step = "USER_VERIF"
	
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
		state.is_early_exit = True
	else:
		state.is_early_exit = False

	print(f"""-> node_user_verification
		user_email = {state.user_email}
		user_phone = {state.user_phone}""")
	return state


def node_call_subgraph (state: CoreState) -> CoreState:
	print("-> node_call_subgraph", state.intent)
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

	elif state.is_early_exit and state.current_step == "USER_VERIF":
		prompt += f"""
		Jawab pesan dari user sesuai dengan informasi berikut.
		- support type: {state.intent}

		user harus memiliki informasi EMAIL dan PHONE, berikut informasi yang sekarang dimiliki user.
		- EMAIL: {state.user_email}
		- PHONE: {state.user_phone}

		jika salah satu atau kedua dari informasi tersebut tidak ada, maka minta user untuk melengkapi email dan nomor hp.
		jangan meminta untuk melengkapi diluar hal tersebut.
		"""

	elif state.current_step in ["TRANSACTION_VERIF", "TICKETING"]:
		prompt += state.sop_additional_prompt


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
	print("-> call_sop1")

	sop_state = state.sop1_state if state.sop1_state else Sop1State()
	sop_state.user_input = state.user_input
	sop_state.user_email = state.user_email
	sop_state.user_phone = state.user_phone
	sop_state.intent = state.intent

	subgraph = sop1_construct_graph()
	subgraph_result = subgraph.invoke(sop_state)
	
	state.sop1_state = Sop1State(**subgraph_result)
	state.is_early_exit = state.sop1_state.is_early_exit
	state.current_step = state.sop1_state.current_step
	state.sop_additional_prompt = state.sop1_state.addtitional_prompt

	return state


def call_sop2 (state: CoreState) -> CoreState:
	print("-> call_sop2")

	sop_state = Sop2State(**state.sop2_state) if state.sop2_state else Sop2State()
	sop_state.user_input=state.user_input,
	sop_state.user_email=state.user_email,
	sop_state.user_phone=state.user_phone,
	sop_state.intent=state.intent,

	subgraph = sop2_construct_graph()
	subgraph_result = subgraph.invoke(sop_state)
	
	state.sop2_state = Sop2State(**subgraph_result)
	state.is_early_exit = state.sop2_state.is_early_exit
	state.current_step = state.sop2_state.current_step
	state.sop_additional_prompt = state.sop2_state.addtitional_prompt

	return state


# -------------------------------------------------------------------------------------
# GATE DEFINITION
# -------------------------------------------------------------------------------------

def gate_entry_routing (state: CoreState) -> str:
	entry_step: STEPS
	
	if state.is_early_exit:
		entry_step = state.current_step
	else:
		entry_step = "INTENT_CHECK"

	print('-> gate_entry_routing', entry_step)
	return entry_step


def gate_is_valid_complain (state: CoreState) -> bool:
	is_valid_complain = state.intent not in ["GENERAL_CHAT", "UNSUPPORTED_COMPLAIN"]

	print('-> gate_is_valid_complain', state.intent, is_valid_complain)
	return is_valid_complain


def gate_is_early_exit (state: CoreState) -> bool:
	print(f"""-> gate_is_early_exit
	   - state.is_early_exit: {state.is_early_exit}
	   - state.current_step: {state.current_step}
	   - state.intent: {state.intent}""")
	return state.is_early_exit


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
	
	# main nodes definition
	graph.add_node(node_check_user_intent)
	graph.add_node(node_user_verification)
	graph.add_node(node_call_subgraph)
	graph.add_node(node_process_final_answer)
	graph.add_node(node_save_conversation_and_state)

	# subgraph nodes definition
	graph.add_node(call_sop1)
	graph.add_node(call_sop2)

	# edges definition
	graph.add_conditional_edges(START, gate_entry_routing, {
		"INTENT_CHECK"		: 'node_check_user_intent',
		"USER_VERIF"		: 'node_user_verification',
		"TRANSACTION_VERIF"	: 'node_call_subgraph',
		"TICKETING"			: 'node_call_subgraph',
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
		'DOUBLE_DEBIT'			: 'call_sop2'
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