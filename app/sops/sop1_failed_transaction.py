from textwrap import dedent 
from typing import Optional, List
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END
from langchain.messages import SystemMessage, AnyMessage

import tools
from model import llm
from config import CHAT_INTENT, TRX_STATUS, SOP1_GRAPH_STATUS


# -------------------------------------------------------------------------------------
# STATE DEFINITION
# -------------------------------------------------------------------------------------

class Sop1State(BaseModel):
	# input
	user_input: Optional[str] = None,
	user_email: Optional[str] = None,
	user_phone: Optional[str] = None,
	intent: Optional[CHAT_INTENT] = None
	conversation: List[AnyMessage] = []
	
	# process
	graph_status: Optional[SOP1_GRAPH_STATUS] = None
	is_early_exit: bool = False
	is_transaction_gathered: bool = False
	is_transaction_verified: bool = False
	is_ticket_created: bool = False
	is_escalated_to_agent: bool = False
	is_good_faith_confirmed: bool = False

	# transaction data
	reference_id: Optional[str] = None
	transaction_date: Optional[str] = None
	transaction_time: Optional[str] = None
	destination_bank: Optional[str] = None
	destination_account: Optional[str] = None
	transaction_status: Optional[TRX_STATUS] = None
	amount: Optional[int] = None

	# result
	ticket_id: Optional[str] = None
	ticket_title: Optional[str] = None
	addtitional_prompt: Optional[str] = None


# -------------------------------------------------------------------------------------
# UTILS FUNCTION
# -------------------------------------------------------------------------------------

def __construct_user_info_prompt(state: Sop1State) -> str:
	return dedent(f"""\
		- email: {state.user_email}
		- nomor handphone: {state.user_phone}""")


def __construct_transaction_info_prompt(state: Sop1State, with_status = False) -> str:
	trx_info = dedent(f"""\
		- reference ID: {state.reference_id}
		- tanggal transaksi: {state.transaction_date}
		- waktu / jam transaksi: {state.transaction_time}
		- nama bank penerima: {state.destination_bank}
		- nomor rekening penerima: {state.destination_account}
		- nominal transaksi: {state.amount}""")
	
	if with_status:
		trx_info += f"\n- status transaksi: {state.transaction_status}"

	return trx_info


# -------------------------------------------------------------------------------------
# NODE DEFINITION
# -------------------------------------------------------------------------------------

def node_transaction_info_gathering (state: Sop1State) -> Sop1State:
	state.graph_status = "TRANSACTION_GATHERING"
	
	prompt = """tugas kamu adalah mengambil informasi tentang data transaksi dari pesan user."""

	conversation = [ SystemMessage(prompt) ] + state.conversation

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
		state.is_transaction_gathered = True


	print(f"""-> node_transaction_info_gathering
		- state.reference_id 		= {state.reference_id}
		- state.transaction_date 	= {state.transaction_date}
		- state.transaction_time 	= {state.transaction_time}
		- state.destination_bank 	= {state.destination_bank}
		- state.destination_account	= {state.destination_account}
		- state.amount 				= {state.amount}
		- state.transaction_status 	= {state.transaction_status}""")
	return state


def node_transaction_verification (state: Sop1State) -> Sop1State:
	state.graph_status = "TRANSACTION_VERIF"
	
	verified_transaction = tools.verify_transaction(
		reference_id=state.reference_id,
		transaction_date=state.transaction_date,
		transaction_time=state.transaction_time,
		destination_bank=state.destination_bank,
		destination_account=state.destination_account,
		amount=state.amount
	)

	if not verified_transaction:
		state.is_early_exit = True
	else:
		state.is_early_exit = False 
		state.is_transaction_verified = True
		state.transaction_status = verified_transaction['status']

	return state


def node_create_ticket(state: Sop1State) -> Sop1State:
	new_ticket = tools.create_ticket(state.transaction_status)
	
	state.ticket_id = new_ticket['ticket_id']
	state.ticket_title = new_ticket['ticket_title']

	state.is_ticket_created = True

	print('-> node_transaction_info_gathering', state.ticket_id)
	return state


def node_good_faith_check(state: Sop1State) -> Sop1State:
	print("-> node_good_faith_check")
	
	state.graph_status = "GOOD_FAITH_CHECK"
	state.is_early_exit = True

	return state


def node_good_faith_confirmation(state: Sop1State) -> Sop1State:
	print("-> node_good_faith_confirmation")

	prompt = """tugas kamu adalah menentukan apakah user menyetujui opsi good faith refund atau menolaknya."""
	conversation = [SystemMessage(prompt)] + state.conversation[-2:]

	class GoodFaithConfirmation(BaseModel):
		is_confirmed: Optional[bool] = Field(..., description="True jika user menyetujui opsi good faith refund, False jika menolak.")

	llm_structured_output = llm.with_structured_output(GoodFaithConfirmation)
	llm_result = llm_structured_output.invoke(conversation)

	state.is_good_faith_confirmed = llm_result.is_confirmed
	state.is_early_exit = False
	
	return state


def node_agent_ecalation_check(state: Sop1State) -> Sop1State:
	print("-> node_live_agent_ecalation")

	if state.amount > 1_672_000_000: # 100.000 USD
		state.is_escalated_to_agent = True
		print("ESCALATED", "FRAUD")

	if state.is_good_faith_confirmed:
		state.is_escalated_to_agent = True
		print("ESCALATED", "GOOD FAITH")

	return state


def node_process_additional_prompt(state: Sop1State) -> Sop1State:
	print("-> node_process_additional_prompt")
	
	if state.is_early_exit and not state.is_transaction_gathered:
		print("CASE: incomplete transaction info")

		state.addtitional_prompt = dedent(f"""\
		Jawab pesan dari user sesuai dengan informasi berikut.
		- support type: {state.intent}

		berikut informasi data diri yang harus dilengkapi oleh user:
		{__construct_user_info_prompt(state)}

		berikut informasi transaksi yang harus dilengkapi oleh user:
		{__construct_transaction_info_prompt(state)}

		jika salah satu dari informasi tersebut tidak ada (None), maka minta user untuk melengkapinya.
		jangan meminta untuk melengkapi diluar hal tersebut.
		""")

	elif state.is_early_exit and not state.is_transaction_verified:
		print("CASE: invalid transaction info")

		state.addtitional_prompt = dedent(f"""\
		Jawab pesan dari user sesuai dengan informasi berikut.
		- support type: {state.intent}

		berikut informasi data diri user:
		{__construct_user_info_prompt(state)}

		berikut informasi transaksi diberikan oleh user, tapi tidak ditemukan di database:
		{__construct_transaction_info_prompt(state)}

		beritahu ke user bahwa data transaksinya tidak ditemukan di database,
		dan minta untuk memeriksa ulang data transaksi yang diinputkan.
		jangan konfirmasi diluar hal tersebut.
		""")

	elif state.is_ticket_created:
		print("CASE: ticket created successfully")

		state.addtitional_prompt = dedent(f"""\
		Jawab pesan dari user sesuai dengan informasi berikut.
		- support type: {state.intent}

		berikut informasi data diri user:
		{__construct_user_info_prompt(state)}

		berikut informasi transaksi dari user:
		{__construct_transaction_info_prompt(state, with_status=True)}

		berikut informasi customer support ticket yang telah dibuat:
		- ticket ID: {state.ticket_id}

		""")

		if state.transaction_status == "FAILED":
			print("CASE: transaction status FAILED")

			state.addtitional_prompt += dedent("""\
			informasikan kepada user bahwa support ticket telah dibuat, 
			dan proses refund telah dilakukan dengan estimasi 1-3 hari kerja.
			jangan menjanjikan sesuatu selain hal di atas.
			""")

		elif state.transaction_status == "PENDING":
			print("CASE: transaction status PENDING")

			state.addtitional_prompt += dedent("""\
			informasikan kepada user bahwa transaksi sedang diproses, 
			dan akan dilakukan pengecekan lagi setelah 24 jam.
			jangan menjanjikan sesuatu selain hal di atas.
			""")

		elif state.transaction_status == "COMPLETED":
			print("CASE: transaction status COMPLETED")

			if state.is_early_exit and state.graph_status == "GOOD_FAITH_CHECK":
				print("CASE: need to confirm good faith")

				state.addtitional_prompt += dedent("""\
				informasikan kepada user bahwa transaksi telah settled, 
				dan pihak bank memiliki batasan tidak dapat menarik balik dana.

				Tawarkan opsi Good Faith Refund Request: Bank mengirim permintaan resmi ke bank penerima. 
				Biasanya memerlukan waktu dan biaya admin serta persetujuan dari kedua belah pihak.
				di akhir jawaban, Eksplisit tanyakan ke user apakah ingin mengajukan opsi Good Faith Refund atau tidak?
				jangan menjanjikan sesuatu selain hal di atas.
				""")

			elif state.is_good_faith_confirmed:
				print("CASE: good faith accepted")

				state.addtitional_prompt += dedent("""\
				informasikan kepada user bahwa request Good Faith Refund-nya telah diterima,
				dan telah dieskalasi ke live agent. beberapa saat lagi live agent akan menghubungi user.
				jangan menjanjikan sesuatu selain hal di atas.
				""")
			
			elif not state.is_good_faith_confirmed:
				print("CASE: good faith rejected")

				state.addtitional_prompt += dedent("""\
				user telah menolak opsi Good Faith Refund.
				informasikan kepada user bahwa walaupun tidak menerima opsi Good Faith Refund,
				user tetap memiliki opsi untuk menghubungi langsung bank penerima. 
				jangan menjanjikan sesuatu selain hal di atas.
				""")

	return state


def node_complete_subgraph(state: Sop1State) -> Sop1State:
	state.graph_status = 'COMPLETED'
	print('-> node_complete_subgraph', state.graph_status)
	return state


# -------------------------------------------------------------------------------------
# GATE DEFINITION
# -------------------------------------------------------------------------------------

def gate_entry_routing (state: Sop1State) -> str:
	entry_step: SOP1_GRAPH_STATUS
	
	if state.is_early_exit:
		entry_step = state.graph_status
	else:
		entry_step = "TRANSACTION_GATHERING"

	print('-> gate_entry_routing', entry_step)
	return entry_step


def gate_is_early_exit (state: Sop1State) -> bool:
	print(f"""-> gate_is_early_exit
	   - state.is_early_exit: {state.is_early_exit}
	   - state.graph_status: {state.graph_status}""")
	return state.is_early_exit


def gate_is_need_good_faith (state: Sop1State) -> bool:
	is_need_good_faith = state.transaction_status == "COMPLETED" 
	print('-> gate_is_need_good_faith', is_need_good_faith)
	return is_need_good_faith


# -------------------------------------------------------------------------------------
# LANGGRAPH EXECUTION
# -------------------------------------------------------------------------------------

def construct_graph():
	graph = StateGraph(Sop1State)

	# main nodes definition
	graph.add_node(node_transaction_info_gathering)
	graph.add_node(node_transaction_verification)
	graph.add_node(node_create_ticket)
	graph.add_node(node_good_faith_check)
	graph.add_node(node_good_faith_confirmation)
	graph.add_node(node_agent_ecalation_check)
	graph.add_node(node_process_additional_prompt)
	graph.add_node(node_complete_subgraph)

	# edges definition
	graph.add_conditional_edges(START, gate_entry_routing, {
		"COMPLETED"				: 'node_transaction_info_gathering',
		"TRANSACTION_GATHERING"	: 'node_transaction_info_gathering',
		"TRANSACTION_VERIF"		: 'node_transaction_info_gathering',
		"GOOD_FAITH_CHECK"		: 'node_good_faith_confirmation'
	})
	graph.add_conditional_edges('node_transaction_info_gathering', gate_is_early_exit, {
		False: 'node_transaction_verification',
		True: 'node_process_additional_prompt'
	})
	graph.add_conditional_edges('node_transaction_verification', gate_is_early_exit, {
		False: 'node_create_ticket',
		True: 'node_process_additional_prompt',
	})
	graph.add_conditional_edges('node_create_ticket', gate_is_need_good_faith, {
		True: 'node_good_faith_check',
		False: 'node_agent_ecalation_check',
	})
	graph.add_conditional_edges('node_good_faith_check', gate_is_early_exit, {
		False: 'node_good_faith_confirmation',
		True: 'node_process_additional_prompt',
	})
	graph.add_edge('node_good_faith_confirmation', 'node_agent_ecalation_check')
	graph.add_edge('node_agent_ecalation_check', 'node_process_additional_prompt')
	graph.add_conditional_edges('node_process_additional_prompt', gate_is_early_exit, {
		False: 'node_complete_subgraph',
		True: END
	})
	graph.add_edge('node_complete_subgraph', END)

	return graph.compile()