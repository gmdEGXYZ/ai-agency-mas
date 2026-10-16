from langgraph.graph import StateGraph, START, END
from states import DeveloperState
from developer_nodes import (
    coder_func, tester_func, reviewer_func, tool_saver_func, 
    fail_func, success_func, check_error, check_compliance
)

dev_builder = StateGraph(DeveloperState)

dev_builder.add_node("coder_node", coder_func)
dev_builder.add_node("tester_node", tester_func)
dev_builder.add_node("fail_node", fail_func)
dev_builder.add_node("success_node", success_func)
dev_builder.add_node("reviewer_node", reviewer_func)
dev_builder.add_node("tool_saver_node", tool_saver_func)

dev_builder.add_edge(START, "coder_node")
dev_builder.add_edge("coder_node", "tester_node")
dev_builder.add_edge("fail_node", END)
dev_builder.add_edge("success_node", END)

dev_builder.add_conditional_edges(
    "tester_node", check_error,
    {"stop": "fail_node", "to_fix": "coder_node", "success": "reviewer_node"}
)
dev_builder.add_conditional_edges(
    "reviewer_node", check_compliance,
    {"to_fix": "coder_node", "save_tool": "tool_saver_node", "success": "success_node"}
)

dev_builder.add_edge("tool_saver_node", "success_node")

developer_graph = dev_builder.compile()