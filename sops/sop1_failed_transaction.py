# guna kamu apa?
# data verif
#	- minta dan parsing data dari pesan user
#	- ngecek ke db mengenai keabsahan data
# buat tiket
#	- call api ticketing
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
from pydantic import BaseModel
from langgraph.graph import StateGraph, START, END


class Sop1State(BaseModel):
	user_input: Optional[str] = None,
	user_email: Optional[str] = None,
	user_phone: Optional[str] = None,
	contoh_result: Optional[str] = None


def node_transaction_data_gathering(state: Sop1State) -> Sop1State:
	state.contoh_result = "oghey"
	return state


def construct_graph():
	graph = StateGraph(Sop1State)

	graph.add_node(node_transaction_data_gathering)

	graph.add_edge(START, 'node_transaction_data_gathering')
	graph.add_edge('node_transaction_data_gathering', END)

	return graph.compile()