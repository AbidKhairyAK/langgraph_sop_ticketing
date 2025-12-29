from typing import Optional
from pydantic import BaseModel
from langgraph.graph import StateGraph, START, END


class Sop2State(BaseModel):
	user_input: Optional[str] = None,
	user_email: Optional[str] = None,
	user_phone: Optional[str] = None,
	contoh_result: Optional[str] = None


def node_transaction_data_gathering(state: Sop2State) -> Sop2State:
	state.contoh_result = "oghey"
	return state


def construct_graph():
	graph = StateGraph(Sop2State)

	graph.add_node(node_transaction_data_gathering)

	graph.add_edge(START, 'node_transaction_data_gathering')
	graph.add_edge('node_transaction_data_gathering', END)

	return graph.compile()