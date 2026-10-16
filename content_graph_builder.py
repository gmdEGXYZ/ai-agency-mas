from langgraph.graph import StateGraph, START, END
from states import ContentState
from content_nodes import researcher_node, writer_node, typesetter_node, editor_node, check_content_approval

content_builder = StateGraph(ContentState)

content_builder.add_node("researcher", researcher_node)
content_builder.add_node("writer", writer_node)
content_builder.add_node("typesetter", typesetter_node)
content_builder.add_node("editor", editor_node)

content_builder.add_edge(START, "researcher")
content_builder.add_edge("researcher", "writer")
content_builder.add_edge("writer", "typesetter")
content_builder.add_edge("typesetter", "editor")

content_builder.add_conditional_edges(
    "editor", check_content_approval,
    {"success": END, "to_fix": "writer"}
)

content_graph = content_builder.compile()