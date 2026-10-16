import os
import copy
from langchain_openai import ChatOpenAI
from states import ManagerState
from utils import extract_json, node_logger
from tools._db import get_memory_index

from developer_graph_builder import developer_graph
from content_graph_builder import content_graph
from analyst_graph_builder import analyst_graph

DEPARTMENTS = {
    "developer": developer_graph,
    "content": content_graph,
    "analyst": analyst_graph
}

llm = ChatOpenAI(
    base_url=os.getenv("LLM_BASE_URL"),
    api_key=os.getenv("LLM_API_KEY"),
    model=os.getenv("LLM_MODEL_MANAGER"), 
    temperature=0.2, 
    max_tokens=8000
)

@node_logger
def manager_thinker_node(state: ManagerState):
    """Мозг системы. Оценивает прогресс и придумывает ровно ОДИН следующий шаг."""
    print(f"-> [Manager Thinker] Анализирую ситуацию (Итерация {state.get('iterations', 0) + 1})...")
    
    registry_path = os.path.join("tools", "registry.json")
    tools_info = "Инструментов пока нет."
    if os.path.exists(registry_path):
        with open(registry_path, "r", encoding="utf-8") as f:
            tools_info = f.read()
            
    history_str = "\n".join(state["step_history"]) if state["step_history"] else "Мы еще ничего не делали. Это самый первый шаг."
    memory_idx = get_memory_index()
    
    prompt = f"""
    Ты - Главный AI-Менеджер автономной системы. Твоя цель - выполнить ГЛОБАЛЬНУЮ ЗАДАЧУ.
    Ты работаешь в цикле. За один раз ты можешь поручить только ОДИН шаг одному отделу.
    
    [ГЛОБАЛЬНАЯ ЗАДАЧА]:
    {state['global_task']}
    
    [ИСТОРИЯ ВЫПОЛНЕННЫХ ШАГОВ]:
    {history_str}
    
    [СИСТЕМНАЯ ПАМЯТЬ (Какие данные у нас уже есть)]:
    {memory_idx}
    
    [ДОСТУПНЫЕ ИНСТРУМЕНТЫ РАЗРАБОТЧИКА]:
    {tools_info}
    
    У ТЕБЯ В ПОДЧИНЕНИИ 3 ОТДЕЛА:
    1. "developer" - пишет код, парсит сайты (без извлечения смысла), скачивает файлы, работает с API. Не должен анализировать текст!
    2. "analyst" - читает память, анализирует огромные тексты, извлекает факты, структурирует данные в JSON, находит ошибки. 
    3. "content" - читает память и пишет красивые тексты, статьи, компилирует PDF через LaTeX. Не может анализировать "грязные" данные.

    (Никогда не проси отдел Developer извлекать факты, параметры или конкретные данные из неструктурированного текста с помощью Python-кода (регулярок). Это всегда ведет к ошибкам. Извлекать факты из текста должен ТОЛЬКО отдел Analyst.)
    (Если нужны данные из интернета, недостаточно просто прочитать сниппеты поиска. Всегда требуй от Developer использовать fetch_webpage_text для загрузки полного текста.)
    
    ТВОЯ ЗАДАЧА ПРЯМО СЕЙЧАС:
    Проанализируй Историю и Память. 
    - Если цель полностью достигнута (например, нужный PDF создан, или задача решена) -> установи is_finished = true и напиши final_report.
    - Если в Истории есть ошибка (например, не хватает варианта лабы, или скрипт упал) -> придумай ОБХОДНОЙ ПУТЬ (например, поручи разработчику скачать таблицу вариантов из Telegram).
    - Если цель не достигнута -> сформулируй ОДИН следующий конкретный шаг.
    
    ОТВЕТЬ ТОЛЬКО В ФОРМАТЕ JSON:
    {{
        "reasoning": "Твои мысли: что уже сделано, что пошло не так, и что нужно сделать сейчас",
        "is_finished": false,
        "final_report": "Текст отчета для пользователя (заполнять только если is_finished = true)",
        "next_step": {{
            "department": "developer или content",
            "task": "Подробное ТЗ для отдела на ЭТОТ шаг",
            "format_type": "pdf, tex, md, txt (только для content)",
            "is_tool": false
        }}
    }}
    """
    
    response = llm.invoke(prompt)
    decision = extract_json(response.content)
    
    print(f"   [Мысли Менеджера]: {decision.get('reasoning', '')}")
    
    return {
        "next_step": decision.get("next_step", {}),
        "is_finished": decision.get("is_finished", False),
        "final_report": decision.get("final_report", ""),
        "iterations": 1
    }

@node_logger
def manager_delegator_node(state: ManagerState):
    """Исполнительные руки. Отдает шаг в отдел и записывает результат в историю."""
    step = state["next_step"]
    dept_name = step.get("department", "developer")
    
    if not step or not dept_name:
        return {"step_history": state["step_history"] + ["[Ошибка] Менеджер не передал корректный шаг."]}
    
    print(f"-> [Delegator] Направляю задачу в отдел [{dept_name.upper()}]...")
    
    memory_index = get_memory_index()
    combined_task = f"""
    [ГЛОБАЛЬНОЕ ТЗ (ДЛЯ ПОНИМАНИЯ ОБЩЕЙ ЦЕЛИ)]:
    {state['global_task']}
    
    {memory_index}
    
    [ТВОЯ ЗАДАЧА НА ЭТОТ ШАГ]:
    {step.get('task', '')}
    """
    
    try:
        if dept_name == "content":
            content_state = {
                "task": combined_task, 
                "format_type": step.get("format_type", "pdf"),
                "research_data": "", "draft": "", "file_path": "",
                "error": None, "iterations": 0, "is_approved": False, "feedback": ""
            }
            final_state = DEPARTMENTS["content"].invoke(content_state)
            
            if final_state.get("is_approved"):
                result = f"УСПЕХ. Документ создан: {final_state.get('file_path')}"
            else:
                result = f"ПРОВАЛ. Ошибка: {final_state.get('feedback')}"
        
        elif dept_name == "analyst":
            analyst_state = {
                "task": combined_task,
                "raw_data_context": "", "analysis_result": "",
                "iterations": 0, "is_approved": False, "feedback": ""
            }
            final_state = DEPARTMENTS["analyst"].invoke(analyst_state)
            
            if final_state.get("is_approved"):
                result = f"УСПЕХ. Аналитика завершена: {final_state.get('analysis_result')}"
            else:
                result = f"ПРОВАЛ. QA Аналитика забраковал работу: {final_state.get('feedback')}"
                
        else: # developer
            dev_state = {
                "task": combined_task,
                "code": "", "error": None, "iterations": 0,
                "task_compliance": None, "last_error": None, "error_streak": 0,
                "output": "", "is_tool": step.get("is_tool", False)
            }
            final_state = DEPARTMENTS["developer"].invoke(dev_state)
            
            if final_state.get("task_compliance"):
                result = f"УСПЕХ. Код отработал. Вывод: {final_state.get('output')}"
            else:
                result = f"ПРОВАЛ. QA завернул код. Последняя ошибка: {final_state.get('feedback')}. Ошибка интерпретатора: {final_state.get('error')}"
                
    except Exception as e:
         result = f"КРИТИЧЕСКИЙ ПРОВАЛ ОТДЕЛА: {str(e)}"
         
    log_entry = f"Шаг: {step.get('task')} -> Результат: {result}"
    print(f"   [Результат Шага]: {result}")
    
    new_history = copy.deepcopy(state["step_history"])
    new_history.append(log_entry)
    
    return {"step_history": new_history}