# - sebuah graph hanya bisa melayani 1 sop
# - ketika dia sudah masuk ke 1 sop, maka akan terkunci sampai sop tersebut selesai
# - apakah proses permintaan status tiket bisa disebut sebagai sop? butuh kepastian ini karena ada intent check di awal
# - early exit terjadi bukan hanya ketika data tidak cukup (post parsing, pre db call), 
# 	tapi juga ketika data tidak valid (post db call)
# - parsing menggunakan structured output llm, dengan description di setiap fieldnya
# - invalid data (post db call) harus dihandle dengan benar
# - technical error juga harus dihandle dengan benar
# - is_early_exit tidak boleh dicleanup, hanya boleh dihapus oleh node penyebabnya
from textwrap import dedent
from dotenv import load_dotenv
load_dotenv()


from typing import List, Literal, Optional
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END
from langchain.messages import HumanMessage, AIMessage, SystemMessage, AnyMessage

from model import llm
from config import CHAT_INTENT, MAIN_GRAPH_STATUS
import tools

from sops.sop1_failed_transaction import construct_graph as sop1_construct_graph, Sop1State


# -------------------------------------------------------------------------------------
# STATE DEFINITION
# -------------------------------------------------------------------------------------

class MainState(BaseModel):
	# input
	user_input: Optional[str] = None
	conversation: List[AnyMessage] = []
	
	# process
	intent: Optional[CHAT_INTENT] = None
	graph_status: Optional[MAIN_GRAPH_STATUS] = None
	is_early_exit: bool = False
	is_user_gathered: bool = False
	is_user_verified: bool = False
	is_sop_complete: bool = False
	
	# user verification data
	user_email: Optional[str] = None
	user_phone: Optional[str] = None

	# subgraph states
	sop1_state: Optional[Sop1State] = None

	# output
	sop_additional_prompt: Optional[str] = None
	result: Optional[str] = None


# -------------------------------------------------------------------------------------
# IN-MEMORY DATABASE
# -------------------------------------------------------------------------------------

saved_state: Optional[MainState] = None
saved_conversation: List[AnyMessage] = []


# -------------------------------------------------------------------------------------
# NODE DEFINITION
# -------------------------------------------------------------------------------------

def node_check_user_intent (state: MainState) -> MainState:
	state.graph_status = "INTENT_CHECK"
	
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
			- UNSUPPORTED_COMPLAIN: jika komplainnya tidak memenuhi kriteria di atas  
			"""
		)
	
	llm_structured_output = llm.with_structured_output(ChatIntent)
	llm_result = llm_structured_output.invoke(conversation)

	state.intent = llm_result.intent

	print("-> node_check_user_intent", state.intent)
	return state


def node_user_info_gathering (state: MainState) -> MainState:
	state.graph_status = "USER_GATHERING"
	
	prompt = """tugas kamu adalah mengambil informasi tentang email dan nomor hp dari pesan user."""

	conversation = [ SystemMessage(prompt) ] + state.conversation


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
		state.is_user_gathered = True

	print(f"""-> node_user_info_gathering
		user_email = {state.user_email}
		user_phone = {state.user_phone}""")
	return state


def node_user_verification (state: MainState) -> MainState:
	state.graph_status = "USER_VERIF"
	
	is_verified = tools.verify_user(
		email=state.user_email,
		phone=state.user_phone,
	)

	if not is_verified:
		state.is_early_exit = True
	else:
		state.is_early_exit = False
		state.is_user_verified = True

	return state


def node_call_subgraph (state: MainState) -> MainState:
	print("-> node_call_subgraph", state.intent)
	state.graph_status = "SUBGRAPH"
	return state


def node_process_final_answer (state: MainState) -> MainState:
	print("-> node_process_final_answer")
	prompt="""Kamu adalah customer support agent.\n\n"""
	

	if state.intent == "UNSUPPORTED_COMPLAIN":
		print("CASE: unsupported complain")

		prompt += dedent(f"""\
		Jawab pesan dari user sesuai dengan informasi berikut.
		- support type: UNSUPPORTED_COMPLAIN.

		karena komplain dari user belum dapat diselesaikan, sampaikan permohonan maaf.
		jangan tawarkan penyelesaian lain.
		""")

	elif state.is_early_exit and not state.is_user_gathered:
		print("CASE: incomplete user information")

		prompt += dedent(f"""\
		Jawab pesan dari user sesuai dengan informasi berikut.
		- support type: {state.intent}

		user harus memiliki informasi EMAIL dan PHONE, berikut informasi yang sekarang dimiliki user.
		- EMAIL: {state.user_email}
		- PHONE: {state.user_phone}

		jika salah satu atau kedua dari informasi tersebut tidak ada, maka minta user untuk melengkapi email dan nomor hp.
		jangan meminta untuk melengkapi diluar hal tersebut.
		""")

	elif state.is_early_exit and not state.is_user_verified:
		print("CASE: invalid user information")

		prompt += dedent(f"""\
		Jawab pesan dari user sesuai dengan informasi berikut.
		- support type: {state.intent}

		berikut informasi yang user berikan, tapi tidak ditemukan di database:
		- EMAIL: {state.user_email}
		- PHONE: {state.user_phone}

		beritahu ke user bahwa datanya tidak ditemukan di database,
		dan minta untuk memeriksa ulang data yang diinputkan.
		jangan konfirmasi diluar hal tersebut.
		""")

	elif state.graph_status == "SUBGRAPH":
		prompt += state.sop_additional_prompt

	
	print('\n')
	print(prompt)

	conversation = [ SystemMessage(prompt) ] + state.conversation
	llm_result = llm.invoke(conversation)

	state.result = llm_result.content
	state.conversation.append(AIMessage(state.result))
	
	return state


def node_complete_graph (state: MainState) -> MainState:
	if state.is_sop_complete:
		state.graph_status = 'COMPLETED'
		
	print('-> node_complete_graph', state.graph_status)
	return state


def node_save_conversation_and_state (state: MainState) -> MainState:
	print("-> node_save_conversation_and_state")
	global saved_conversation
	global saved_state
	saved_conversation = state.conversation
	saved_state = state
	return state


# -------------------------------------------------------------------------------------
# SUB-GRAPH DEFINITION
# -------------------------------------------------------------------------------------

def call_sop1 (state: MainState) -> MainState:
	print("-> call_sop1")

	sop_state = state.sop1_state if state.sop1_state else Sop1State()
	sop_state.user_input = state.user_input
	sop_state.user_email = state.user_email
	sop_state.user_phone = state.user_phone
	sop_state.intent = state.intent
	sop_state.conversation = state.conversation

	subgraph = sop1_construct_graph()
	subgraph_result = subgraph.invoke(sop_state)
	
	state.sop1_state = Sop1State(**subgraph_result)

	state.is_early_exit = state.sop1_state.is_early_exit
	state.sop_additional_prompt = state.sop1_state.addtitional_prompt
	state.is_sop_complete = state.sop1_state.graph_status == "COMPLETED"

	return state


# -------------------------------------------------------------------------------------
# GATE DEFINITION
# -------------------------------------------------------------------------------------

def gate_entry_routing (state: MainState) -> str:
	entry_step: MAIN_GRAPH_STATUS
	
	if state.is_early_exit:
		entry_step = state.graph_status
	else:
		entry_step = "INTENT_CHECK"

	print('-> gate_entry_routing', entry_step)
	return entry_step


def gate_is_valid_complain (state: MainState) -> bool:
	is_valid_complain = state.intent not in ["GENERAL_CHAT", "UNSUPPORTED_COMPLAIN"]

	print('-> gate_is_valid_complain', state.intent, is_valid_complain)
	return is_valid_complain


def gate_is_early_exit (state: MainState) -> bool:
	print(f"""-> gate_is_early_exit
	   - state.is_early_exit: {state.is_early_exit}
	   - state.graph_status: {state.graph_status}
	   - state.intent: {state.intent}""")
	return state.is_early_exit


# -------------------------------------------------------------------------------------
# LANGGRAPH EXECUTION
# -------------------------------------------------------------------------------------

def prepare_state (user_input: str) -> MainState:
	state = MainState() if not saved_state else saved_state

	state.user_input = user_input
	state.result = None
	
	state.conversation = saved_conversation
	state.conversation.append(HumanMessage(user_input))

	return state


def construct_graph():
	graph = StateGraph(MainState)
	
	# main nodes definition
	graph.add_node(node_check_user_intent)
	graph.add_node(node_user_info_gathering)
	graph.add_node(node_user_verification)
	graph.add_node(node_call_subgraph)
	graph.add_node(node_process_final_answer)
	graph.add_node(node_complete_graph)
	graph.add_node(node_save_conversation_and_state)

	# subgraph nodes definition
	graph.add_node(call_sop1)

	# edges definition
	graph.add_conditional_edges(START, gate_entry_routing, {
		"COMPLETED"			: 'node_check_user_intent',
		"INTENT_CHECK"		: 'node_check_user_intent',
		"USER_GATHERING"	: 'node_user_info_gathering',
		"USER_VERIF"		: 'node_user_info_gathering',
		"SUBGRAPH"			: 'node_call_subgraph',
	})
	graph.add_conditional_edges('node_check_user_intent', gate_is_valid_complain, {
		True: 'node_user_info_gathering', 
		False: 'node_process_final_answer'
	})
	graph.add_conditional_edges('node_user_info_gathering', gate_is_early_exit, {
		True: 'node_process_final_answer',
		False: 'node_user_verification'
	})
	graph.add_conditional_edges('node_user_verification', gate_is_early_exit, {
		True: 'node_process_final_answer',
		False: 'node_call_subgraph'
	})
	graph.add_conditional_edges('node_call_subgraph', lambda state: state.intent, {
		'FAILED_TRANSACTION'	: 'call_sop1',
	})
	
	graph.add_edge('call_sop1', 'node_process_final_answer')

	graph.add_conditional_edges('node_process_final_answer', gate_is_early_exit, {
		False: 'node_complete_graph',
		True: 'node_save_conversation_and_state'
	})
	graph.add_edge('node_complete_graph', 'node_save_conversation_and_state')
	graph.add_edge('node_save_conversation_and_state', END)

	return graph.compile()


# -------------------------------------------------------------------------------------
# MAIN LOOP
# -------------------------------------------------------------------------------------

while True:
	print('\n')
	user_input = input('[User]: ')
	print('\n')

	if not user_input:
		print('\ntolong tulis sesuatu.\n')
		continue
	
	state = prepare_state(user_input)
	graph = construct_graph()
	# print(graph.get_graph().draw_ascii())
	
	graph_result = graph.invoke(state)

	print('\n')
	print(f"[AI]: {graph_result["result"]}")
