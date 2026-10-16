import os
import json
from langchain_openai import ChatOpenAI
from states import AnalystState
from utils import node_logger, extract_json
from tools._db import get_memory_index, _load_db, _save_db
import dotenv

dotenv.load_dotenv()

llm = ChatOpenAI(
    base_url=os.getenv("LLM_BASE_URL"),
    api_key=os.getenv("LLM_API_KEY"),
    model=os.getenv("LLM_MODEL_ANALYST"),
    temperature=0.1, # низкая температура для строгости анализа
    max_tokens=8000
)

@node_logger
def analyst_worker_node(state: AnalystState):
    """Универсальный аналитик. Читает память, думает, структурирует данные."""
    
    memory_index = get_memory_index()
    
    prompt = f"""
    Ты - Senior Data Analyst & Universal Logic Engine в автономной AI-системе.
    Твоя задача глубоко проанализировать данные и выполнить ТЗ Менеджера.
    Ты умеешь: извлекать факты, структурировать грязный текст в JSON, находить аномалии, делать саммари, сравнивать документы.
    
    ТЗ ОТ МЕНЕДЖЕРА: 
    {state['task']}
    
    [ИНДЕКС СИСТЕМНОЙ ПАМЯТИ]:
    {memory_index}
    
    ПРАВИЛА ТВОЕЙ РАБОТЫ:
    1. Если тебе нужны данные для анализа, напиши: [LOAD_MEMORY: имя_ключа]. Я дам тебе их содержимое. Ты можешь делать это несколько раз.
    2. Когда соберешь все нужные данные, проведи глубокий анализ и напиши ФИНАЛЬНЫЙ ОТВЕТ (выжимку, JSON, или список фактов - как просил Менеджер).
    3. АБСОЛЮТНОЕ ПРАВИЛО: Не выдумывай факты. Если в загруженных данных нет ответа на задачу, прямо напиши об этом.
    4. Тебе НЕ НУЖНО самостоятельно сохранять данные в память или писать команды вроде [MEMORY_SAVE]. Твой финальный ответ будет сохранен в базу автоматически. Просто напиши итоговый вывод или JSON.
    """
    
    if state.get("feedback"):
        prompt += f"\n\n[ОТЗЫВ ОТ QA (ПРЕДЫДУЩАЯ ПОПЫТКА ПРОВАЛЕНА)]:\n{state['feedback']}\nИсправь логику анализа."

    messages = [{"role": "user", "content": prompt}]
    raw_context_accumulated = state.get("raw_data_context", "")
    
    for step in range(5):
        response = llm.invoke(messages)
        text = response.content.strip()
        
        if "[LOAD_MEMORY:" in text:
            try:
                key = text.split("[LOAD_MEMORY:")[1].split("]")[0].strip()
                print(f"   [Analyst Tool]: Загружаю '{key}' для анализа...")
                db = _load_db()
                if key in db:
                    content_str = json.dumps(db[key]["value"], ensure_ascii=False)
                    if len(content_str) > 15000: content_str = content_str[:15000] + "\n...[ОБРЕЗАНО]"
                else:
                    content_str = f"Ключ '{key}' не найден."

                raw_context_accumulated += f"\n--- Данные из {key} ---\n{content_str}\n"
                
                messages.append({"role": "assistant", "content": text})
                messages.append({"role": "user", "content": f"ДАННЫЕ:\n```\n{content_str}\n```\nПродолжай анализ или запрашивай другие ключи."})
                continue
            except Exception as e:
                messages.append({"role": "assistant", "content": text})
                messages.append({"role": "user", "content": "Ошибка синтаксиса. Пиши [LOAD_MEMORY: key]"})
                continue

        print("   [Analyst]: Анализ завершен.")
        return {"analysis_result": text, "raw_data_context": raw_context_accumulated, "iterations": 1}
        
    return {"analysis_result": text, "raw_data_context": raw_context_accumulated, "iterations": 1}

@node_logger
def analyst_qa_node(state: AnalystState):
    """Сверяет результат аналитика с исходными данными (Anti-Hallucination)"""
    prompt = f"""
    Ты - Senior QA Data Auditor. Твоя задача проверить работу Аналитика на логику и отсутствие галлюцинаций.
    
    ТЗ МЕНЕДЖЕРА (Что нужно было сделать):
    {state['task']}
    
    СЫРЫЕ ДАННЫЕ (Которые читал Аналитик):
    {state['raw_data_context'] if state['raw_data_context'] else "Аналитик не загружал данные из памяти."}
    
    РЕЗУЛЬТАТ АНАЛИТИКА:
    {state['analysis_result']}
    
    ПРАВИЛА ПРОВЕРКИ:
    1. Ответил ли Аналитик на ТЗ Менеджера?
    2. ФАКТЧЕКИНГ: Присутствуют ли факты/цифры из "Результата" в "Сырых данных"? Если Аналитик выдумал статистику, имена или факты - это КРИТИЧЕСКАЯ ОШИБКА.
    3. Если Аналитик написал "Данных нет" (и их реально нет в Сырых данных) - это УСПЕХ, он поступил правильно.
    
    Если всё идеально, напиши ТОЛЬКО: [APPROVED]
    Если есть галлюцинации или нарушение логики, объясни ошибку и в конце напиши: [REJECTED]
    """
    
    response = llm.invoke(prompt)
    verdict = response.content.strip()
    
    if "[APPROVED]" in verdict:
        print("   [Analyst QA]: Логика и факты подтверждены.")
        return {"is_approved": True, "feedback": ""}
    else:
        print("   [Analyst QA]: Найдены ошибки/галлюцинации.")
        return {"is_approved": False, "feedback": verdict}

@node_logger
def analyst_saver_node(state: AnalystState):
    """Генерирует ключ и сохраняет финальный анализ в память для других отделов"""
    if not state.get("is_approved"): return state
    
    prompt = f"""
    Придумай короткий snake_case ключ и описание для сохранения этого анализа в память.
    Ответь ТОЛЬКО в JSON: {{"key": "some_key", "desc": "описание"}}
    
    АНАЛИЗ: {state['analysis_result'][:500]}
    """
    res = llm.invoke(prompt)
    info = extract_json(res.content)
    
    key = info.get("key", "analyst_output")
    desc = info.get("desc", "Результаты работы отдела аналитики")
    
    db = _load_db()
    db[key] = {"value": state["analysis_result"], "description": desc}
    _save_db(db)
    
    print(f"   [Analyst Saver]: Результат сохранен в память под ключом '{key}'")

    final_output = f"Анализ успешно завершен и сохранен в память.\nКлюч: {key}\nОзнакомительное превью:\n{state['analysis_result'][:200]}..."
    return {"analysis_result": final_output}

def check_analyst_approval(state: AnalystState) -> str:
    if state["iterations"] >= 4: return "success"
    return "success" if state["is_approved"] else "to_fix"