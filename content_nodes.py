import os
import subprocess
from langchain_openai import ChatOpenAI
from states import ContentState
from utils import node_logger
from tools._db import get_memory_index
import dotenv

dotenv.load_dotenv()

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))

llm = ChatOpenAI(
    base_url=os.getenv("LLM_BASE_URL"),
    api_key=os.getenv("LLM_API_KEY"),
    model=os.getenv("LLM_MODEL_CONTENT"),
    temperature=0.4, # больше креативности для текстов
    max_tokens=8000
)

@node_logger
def researcher_node(state: ContentState):
    """Анализирует задачу и составляет подробный план конспекта/статьи"""
    if state.get("research_data") and state.get("error_streak", 0) > 0:
        return state
        
    prompt = f"""
    Твоя задача - подготовить детальный план и собрать ключевые тезисы для написания документа.
    ТЕМА / ТЗ: {state['task']}
    Формат документа: {state.get('format_type', 'txt')}
    
    Выведи структурированный план и главные факты/формулы, которые обязательно должны войти в текст.
    """
    response = llm.invoke(prompt)
    return {"research_data": response.content, "iterations": 1}

@node_logger
def writer_node(state: ContentState):
    memory_index = get_memory_index()
    
    prompt = f"""
    Ты - профессиональный технический писатель и аналитик.
    ТЗ: {state['task']}
    ЦЕЛЕВОЙ ФОРМАТ: {state.get('format_type', 'txt')}
    
    ПЛАН И ФАКТЫ ОТ ИССЛЕДОВАТЕЛЯ:
    {state['research_data']}
    
    {memory_index}
    
    ПРАВИЛА ИНТЕГРАЦИИ ДАННЫХ:
    1. Чтобы прочитать данные, напиши: [LOAD_MEMORY: имя_ключа]. Я дам тебе содержимое.
    2. Когда получишь данные, напиши готовый текст.
    
    [КРИТИЧЕСКОЕ ПРАВИЛО ОТВЕТСТВЕННОСТИ]:
    Если ты загрузил память и видишь, что данных АБСОЛЮТНО не хватает (там мусор, ошибки парсинга, или нет нужных фактов) — НЕ ВЫДУМЫВАЙ ФАКТЫ! 
    Откажись от работы. Для этого напиши ровно одну строку: [REJECT_DATA: причина, почему данные плохие и что именно нужно найти].
    
    ПРАВИЛА ОФОРМЛЕНИЯ LATEX:
    - Выведи ТОЛЬКО текст документа, начиная с \\documentclass.
    - Для широких таблиц используй \\usepackage{{pdflscape}} и \\begin{{landscape}}.
    """

    messages = [{"role": "user", "content": prompt}]
    
    for step in range(4):
        response = llm.invoke(messages)
        text = response.content.strip()
        
        if "[LOAD_MEMORY:" in text:
            try:
                import json
                from tools._db import _load_db
                key = text.split("[LOAD_MEMORY:")[1].split("]")[0].strip()
                db = _load_db()
                if key in db:
                    content = json.dumps(db[key]["value"], ensure_ascii=False, indent=2)
                    if len(content) > 4000: content = content[:4000] + "\n...[ОБРЕЗАНО]"
                else:
                    content = f"ОШИБКА: Ключ '{key}' не найден."
                    
                messages.append({"role": "assistant", "content": text})
                messages.append({"role": "user", "content": f"ДАННЫЕ [{key}]:\n```\n{content}\n```\nПиши текст или используй [REJECT_DATA:...]"})
                continue
            except: pass
                
        if "[REJECT_DATA:" in text:
            reason = text.split("[REJECT_DATA:")[1].split("]")[0].strip()
            print(f"   [Writer]: ОТКАЗАЛСЯ ОТ РАБОТЫ! Причина: {reason}")
            return {"draft": "", "error": f"Писатель забраковал данные: {reason}"}
            
        draft = text
        if draft.startswith("```"):
            draft = "\n".join(draft.split("\n")[1:-1])
            
        print("   [Writer]: Текст написан.")
        return {"draft": draft, "error": None}

    return {"draft": text, "error": None}

@node_logger
def typesetter_node(state: ContentState):
    """Сохраняет файл в workspace и компилирует PDF, если нужно"""
    if state.get("error"):
        print("   [Typesetter]: Пропуск работы из-за ошибки на этапе написания.")
        return state
        
    workspace_dir = os.path.join(PROJECT_ROOT, "workspace")
    os.makedirs(workspace_dir, exist_ok=True)
    
    fmt = state.get("format_type", "txt").lower()
    base_name = "document"
    
    if fmt == "pdf" or fmt == "tex":
        tex_path = os.path.join(workspace_dir, f"{base_name}.tex")
        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(state["draft"])
            
        if fmt == "pdf":
            print(f"-> [Typesetter] Компилирую PDF через pdflatex (может занять время при скачивании пакетов)...")
            try:
                result = subprocess.run(
                    ["pdflatex", "-interaction=nonstopmode", f"{base_name}.tex"],
                    cwd=workspace_dir,
                    capture_output=True, 
                    text=True, 
                    encoding="utf-8", 
                    errors="replace", 
                    timeout=180
                )
                
                pdf_path = os.path.join(workspace_dir, f"{base_name}.pdf")
                if os.path.exists(pdf_path):
                    return {"file_path": pdf_path, "error": None}
                else:
                    error_text = result.stdout[-1000:] if result.stdout else "Неизвестная ошибка компиляции (stdout пуст)."
                    return {"error": error_text, "file_path": tex_path}
                    
            except subprocess.TimeoutExpired:
                return {"error": "Таймаут: Компиляция PDF заняла > 3 минут.", "file_path": tex_path}
            except FileNotFoundError:
                return {"error": "СИСТЕМНАЯ ОШИБКА: pdflatex не установлен.", "file_path": tex_path}
        
        return {"file_path": tex_path, "error": None}
        
    else:
        file_path = os.path.join(workspace_dir, f"{base_name}.{fmt}")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(state["draft"])
        return {"file_path": file_path, "error": None}

@node_logger
def editor_node(state: ContentState):
    """Проверяет, создался ли файл и нет ли ошибок"""
    if state.get("error"):
        return {"is_approved": False, "feedback": state["error"], "iterations": 1}
        
    if not os.path.exists(state.get("file_path", "")):
        return {"is_approved": False, "feedback": "Файл не был создан физически.", "iterations": 1}
        
    return {"is_approved": True, "feedback": "Файл успешно создан и скомпилирован.", "iterations": 1}

def check_content_approval(state: ContentState) -> str:
    if state["iterations"] >= 5: return "success"
    return "success" if state["is_approved"] else "to_fix"