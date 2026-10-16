from langgraph.graph import StateGraph, START, END
from states import AnalystState
from analyst_nodes import analyst_worker_node, analyst_qa_node, analyst_saver_node, check_analyst_approval

analyst_builder = StateGraph(AnalystState)

analyst_builder.add_node("worker", analyst_worker_node)
analyst_builder.add_node("qa", analyst_qa_node)
analyst_builder.add_node("saver", analyst_saver_node)

analyst_builder.add_edge(START, "worker")
analyst_builder.add_edge("worker", "qa")

analyst_builder.add_conditional_edges(
    "qa", check_analyst_approval,
    {"success": "saver", "to_fix": "worker"}
)

analyst_builder.add_edge("saver", END)

analyst_graph = analyst_builder.compile()