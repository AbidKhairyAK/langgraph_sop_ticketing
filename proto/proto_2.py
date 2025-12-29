from typing import Dict, List, Literal
from langgraph.graph import StateGraph, MessagesState, START, END
from typing_extensions import TypedDict, Annotated
from pydantic import BaseModel

class MyMessage(BaseModel):
	role: Literal["ai", "user"]
	content: str

class MyState(BaseModel):
	messages: List[MyMessage]
	

def mock_llm(state: MyState):
	state.messages.append(MyMessage(role="ai", content="hello world"))
	return state

def print_out (state: MyState):
	print(f"[AI]: {state.messages[-1].content}" )
	return state


while True:
	user_input = input('[User]: ')

	graph = StateGraph(MyState)
	graph.add_node(mock_llm)
	graph.add_node(print_out)
	graph.add_edge(START, "mock_llm")
	graph.add_edge("mock_llm", "print_out")
	graph.add_edge("print_out", END)
	graph = graph.compile()

	graph.invoke({
		"messages": [
			{ "role": "user", "content": str(user_input) }
		]
	})