from langgraph.graph import StateGraph, MessagesState, START, END

def mock_llm(state: MessagesState):
	state["messages"].append({"role": "ai", "content": "hello world"})
	return state

def print_out (state: MessagesState):
	print(f"[AI]: {state["messages"][-1].content}" )
	return state


while True:
	user_input = input('[User]: ')

	graph = StateGraph(MessagesState)
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