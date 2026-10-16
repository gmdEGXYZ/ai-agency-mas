from typing import TypedDict, Annotated, List
import operator

class DeveloperState(TypedDict):
    task: str
    code: str
    error: str
    iterations: Annotated[int, operator.add]
    task_compliance: bool
    feedback: str 
    research_data: str 
    last_error: str       
    error_streak: int     
    output: str
    is_tool: bool

class ManagerState(TypedDict):
    global_task: str           # Исходный запрос
    step_history: List[str]    # Журнал действий (что делали и какой результат)
    next_step: dict            # Сгенерированный следующий шаг (отдел, ТЗ)
    final_report: str          # Итоговый ответ (если задача завершена)
    is_finished: bool          # Флаг завершения работы
    iterations: Annotated[int, operator.add] # Защита от бесконечного цикла Менеджера

class ContentState(TypedDict):
    task: str              # ТЗ от Менеджера (например, "Напиши конспект по физике в LaTeX")
    format_type: str       # Целевой формат (md, tex, pdf, txt)
    research_data: str     # Собранные факты / План статьи
    draft: str             # Написанный текст
    file_path: str         # Путь к итоговому сохраненному файлу
    error: str             # Ошибки компиляции (если есть)
    iterations: Annotated[int, operator.add]
    is_approved: bool      # Вердикт Редактора
    feedback: str          # Замечания Редактора

class AnalystState(TypedDict):
    task: str                 # ТЗ от Менеджера
    raw_data_context: str     # Склеенные данные, которые Аналитик выгрузил из памяти (для QA)
    analysis_result: str      # Итоговый вывод/анализ/JSON
    iterations: Annotated[int, operator.add]
    is_approved: bool         # Вердикт QA-Аналитика
    feedback: str             # Замечания от QA