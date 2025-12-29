# guna kamu apa?
#
# data verif
#	- minta dan parsing data dari pesan user
#	- ngecek ke db mengenai keabsahan data
#
# buat tiket
#	- call api ticketing
#
# tindak lanjut
# 	- masukin ke sebuah db scheduling yang akan dieksekusi oleh cron
#	- eskalasi ke live agent (cs orang)
# 
# yg harus dibikin:
# - state
# - 1 contoh node
# - 1 main graph
#
# consideration:
# - pattern sekarang mengharuskan hasil dari sub-graph dikembalikan ke main-graph
# - opsi lainnya adalah node terakhir dari main graph diekstraksi menjadi node modular 
# 	yang bisa dipanggil ke masing2 sub-graph 
# - subgraph harusnya bisa early exit


from typing import Optional
from uuid import uuid4
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END
from langchain.messages import HumanMessage, SystemMessage

from model import llm
from config import CHAT_INTENT, STEPS


# -------------------------------------------------------------------------------------
# STATE DEFINITION
# -------------------------------------------------------------------------------------

class Sop1State(BaseModel):
	# input
	user_input: Optional[str] = None,
	user_email: Optional[str] = None,
	user_phone: Optional[str] = None,
	intent: Optional[CHAT_INTENT] = None
	
	# process
	current_step: Optional[STEPS] = None
	is_early_exit: bool = False

	# transaction data
	reference_id: Optional[str] = None
	transaction_date: Optional[str] = None
	transaction_time: Optional[str] = None
	destination_bank: Optional[str] = None
	destination_account: Optional[str] = None
	amount: Optional[int] = None

	# result
	ticket_id: Optional[str] = None
	ticket_title: Optional[str] = None
	addtitional_prompt: Optional[str] = None


# -------------------------------------------------------------------------------------
# NODE DEFINITION
# -------------------------------------------------------------------------------------

def node_transaction_verification(state: Sop1State) -> Sop1State:
	state.current_step = "TRANSACTION_VERIF"
	
	prompt = """tugas kamu adalah mengambil informasi tentang data transaksi dari pesan user."""

	conversation = [
		SystemMessage(prompt),
		HumanMessage(state.user_input)
	]

	class TransactionInfo(BaseModel):
		reference_id		: Optional[str] = Field(..., description="reference id dari sebuah transaksi.")
		transaction_date	: Optional[str] = Field(..., description="tanggal transaksi tanpa jam nya, contoh 2024-12-28.")
		transaction_time	: Optional[str] = Field(..., description="jam dan menit dari transaksi, contoh 08:30.")
		destination_bank	: Optional[str] = Field(..., description="nama bank penerima.")
		destination_account	: Optional[str] = Field(..., description="nomor rekening penerima.")
		amount				: Optional[int] = Field(..., description="nominal uang pada transaksi tersebut.")

	llm_structured_output = llm.with_structured_output(TransactionInfo)
	llm_result = llm_structured_output.invoke(conversation)


	if llm_result.reference_id:
		state.reference_id = llm_result.reference_id

	if llm_result.transaction_date:
		state.transaction_date = llm_result.transaction_date

	if llm_result.transaction_time:
		state.transaction_time = llm_result.transaction_time

	if llm_result.destination_bank:
		state.destination_bank = llm_result.destination_bank

	if llm_result.destination_account:
		state.destination_account = llm_result.destination_account

	if llm_result.amount:
		state.amount = llm_result.amount


	if any(x is None for x in [
		state.reference_id,
		state.transaction_date,
		state.transaction_time,
		state.destination_bank,
		state.destination_account,
		state.amount,
	]):
		state.is_early_exit = True
	else:
		state.is_early_exit = False

	print(f"""-> node_transaction_verification
		- state.reference_id = {state.reference_id}
		- state.transaction_date = {state.transaction_date}
		- state.transaction_time = {state.transaction_time}
		- state.destination_bank = {state.destination_bank}
		- state.destination_account = {state.destination_account}
		- state.amount = {state.amount}""")
	return state


def node_create_ticket(state: Sop1State) -> Sop1State:
	state.current_step = "TICKETING"
	state.ticket_id = str(uuid4())
	state.ticket_title = "lorem ipsum"

	print('-> node_transaction_verification', state.ticket_id)
	return state


def node_process_additional_prompt(state: Sop1State) -> Sop1State:
	print("-> node_process_additional_prompt")

	if state.is_early_exit and state.current_step == "TRANSACTION_VERIF":
		state.addtitional_prompt = f"""
		Jawab pesan dari user sesuai dengan informasi berikut.
		- support type: {state.intent}

		berikut informasi data diri yang harus dilengkapi oleh user:
		- email: {state.user_email}
		- nomor handphone: {state.user_phone}

		berikut informasi transaksi yang harus dilengkapi oleh user:
		- reference ID: {state.reference_id}
		- tanggal transaksi: {state.transaction_date}
		- waktu / jam transaksi: {state.transaction_time}
		- nama bank penerima: {state.destination_bank}
		- nomor rekening penerima: {state.destination_account}
		- nominal transaksi: {state.amount}

		jika salah satu dari informasi tersebut tidak ada (None), maka minta user untuk melengkapinya.
		jangan meminta untuk melengkapi diluar hal tersebut.
		"""

	elif state.current_step == "TICKETING":
		state.addtitional_prompt = f"""
		Jawab pesan dari user sesuai dengan informasi berikut.
		- support type: {state.intent}

		berikut informasi data diri user:
		- email: {state.user_email}
		- nomor handphone: {state.user_phone}

		berikut informasi transaksi dari user:
		- reference ID: {state.reference_id}
		- tanggal transaksi: {state.transaction_date}
		- waktu / jam transaksi: {state.transaction_time}
		- nama bank penerima: {state.destination_bank}
		- nomor rekening penerima: {state.destination_account}
		- nominal transaksi: {state.amount}

		berikut informasi customer support ticket yang telah dibuat:
		- ticket ID: {state.ticket_id}

		informasikan kepada user bahwa support ticket telah dibuat, 
		dan proses refund telah dilakukan dengan estimasi 1-3 hari kerja.
		"""

	return state

# -------------------------------------------------------------------------------------
# GATE DEFINITION
# -------------------------------------------------------------------------------------

def gate_entry_routing (state: Sop1State) -> str:
	entry_step: STEPS
	
	if state.is_early_exit:
		entry_step = state.current_step
	else:
		entry_step = "TRANSACTION_VERIF"

	print('-> gate_entry_routing', entry_step)
	return entry_step


def gate_is_early_exit (state: Sop1State) -> bool:
	print(f"""-> gate_is_early_exit
	   - state.is_early_exit: {state.is_early_exit}
	   - state.current_step: {state.current_step}""")
	return state.is_early_exit


# -------------------------------------------------------------------------------------
# LANGGRAPH EXECUTION
# -------------------------------------------------------------------------------------

def construct_graph():
	graph = StateGraph(Sop1State)

	# main nodes definition
	graph.add_node(node_transaction_verification)
	graph.add_node(node_create_ticket)
	graph.add_node(node_process_additional_prompt)

	# edges definition
	graph.add_conditional_edges(START, gate_entry_routing, {
		"TRANSACTION_VERIF"	: 'node_transaction_verification',
		"TICKETING"			: 'node_create_ticket'
	})
	graph.add_conditional_edges('node_transaction_verification', gate_is_early_exit, {
		True: 'node_process_additional_prompt',
		False: 'node_create_ticket'
	})
	graph.add_edge('node_create_ticket', 'node_process_additional_prompt')
	graph.add_edge('node_process_additional_prompt', END)

	return graph.compile()