from langgraph.graph import StateGraph, START, END
from states import ManagerState
from manager_nodes import manager_thinker_node, manager_delegator_node

manager_builder = StateGraph(ManagerState)

manager_builder.add_node("thinker", manager_thinker_node)
manager_builder.add_node("delegator", manager_delegator_node)

manager_builder.add_edge(START, "thinker")

def check_if_finished(state: ManagerState):
    if state.get("is_finished") or state.get("iterations", 0) >= 15:
        return "finish"
    return "continue"

manager_builder.add_conditional_edges(
    "thinker", check_if_finished,
    {"continue": "delegator", "finish": END}
)

manager_builder.add_edge("delegator", "thinker")

master_graph = manager_builder.compile()

if __name__ == "__main__":
    initial_manager_state = {
        "global_task":  # сюда перед запуском записывается запрос
        """

        """,
        "step_history": [],
        "next_step": {},
        "final_report": "",
        "is_finished": False,
        "iterations": 0
    }
    
    print("\n[ЗАПУСК ГЛОБАЛЬНОГО МЕНЕДЖЕРА]")
    final_state = master_graph.invoke(initial_manager_state)
    
    print("\n" + "="*50)
    print("[ИТОГОВЫЙ ОТЧЕТ СИСТЕМЫ]")
    print(final_state.get("final_report", "Отчет не сформирован."))