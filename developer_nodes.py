from langchain_community.tools import DuckDuckGoSearchRun
from states import DeveloperState
from utils import extract_python_code, node_logger, extract_json, clean_code
import os
from langchain_openai import ChatOpenAI
import subprocess
import sys
import json
import dotenv

dotenv.load_dotenv()

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))

llm = ChatOpenAI(
    base_url=os.getenv("LLM_BASE_URL"),
    api_key=os.getenv("LLM_API_KEY"),
    model=os.getenv("LLM_MODEL_DEVELOPER"),
    temperature=0.1, 
    max_tokens=8000
)

search_tool = DuckDuckGoSearchRun()

@node_logger
def coder_func(state: DeveloperState):
    print(f"-> [Coder] Пишу/Исправляю код... (Попытка {state.get('iterations', 0) + 1})")

    workspace_dir = os.path.join(PROJECT_ROOT, "workspace")
    os.makedirs(workspace_dir, exist_ok=True)
    files = os.listdir(workspace_dir)
    workspace_content = ", ".join(files) if files else "Папка пуста"

    registry_path = os.path.join(PROJECT_ROOT, "tools", "registry.json")
    tools_info = "Инструментов пока нет."
    if os.path.exists(registry_path):
        try:
            with open(registry_path, "r", encoding="utf-8") as f:
                tools_info = f.read()
        except: pass

    workspace_context = f"""
    [ТЕКУЩЕЕ СОСТОЯНИЕ ПРОЕКТА]:
    ВНИМАНИЕ: Твой код будет запущен прямо ВНУТРИ папки `workspace`. 
    Используй относительные пути без префикса (например, `file_name.txt`, а НЕ `workspace/file_name.txt`).
    Файлы в папке: {workspace_content}
    
    [ДОСТУПНЫЕ ИНСТРУМЕНТЫ (в папке tools/)]:
    Ты можешь импортировать готовые инструменты из реестра ниже.
    ПРАВИЛО ИМПОРТА: `from tools.<name> import <name>` (имя файла и главной функции всегда совпадают).
    Реестр:
    {tools_info}
    """
    
    if state.get("error_streak", 0) >= 3:
        prompt = f"""
        ВНИМАНИЕ: Твои предыдущие {state['error_streak']} попыток провалились с ОДНОЙ И ТОЙ ЖЕ ошибкой.
        
        {workspace_context}
        
        Твой текущий нерабочий код:
        ```python
        {state['code']}
        ```
        Ошибка интерпретатора: {state.get('error')}
        Найденная информация: {state.get('research_data', 'Нет данных')}

        ТВОЯ ЗАДАЧА:
        Прежде чем писать код, ты ОБЯЗАН провести анализ ситуации (напиши его обычным текстом):
        1. Почему твой предыдущий код вызывает эту ошибку?
        2. Оцени информацию из интернета: она полезна? Примени её.
        3. Сформулируй АБСОЛЮТНО НОВЫЙ подход к решению.

        Только ПОСЛЕ этого анализа напиши новый код.
        ПРАВИЛО: Код должен быть обернут в ```python ... ```
        """
    else:
        prompt = f"""
        Ты - Senior Python Developer. Твоя задача: {state['task']}
        
        {workspace_context}
        
        ПРАВИЛО: Выведи ТОЛЬКО код. Код должен быть обернут в ```python ... ```
        """
        if state.get("code"):
            prompt += f"\nТвой текущий код:\n```python\n{state['code']}\n```\n"

        has_issues = False
        if state.get("error"):
            prompt += f"\n[ТЕХНИЧЕСКАЯ ОШИБКА]:\n{state['error']}\n"
            has_issues = True
        if state.get("research_data"):
            prompt += f"\n[ПОДСКАЗКА ИЗ СЕТИ]:\n{state['research_data']}\n"
        if state.get("task_compliance") == False:
            prompt += f"\n[ОТЗЫВ ОТ QA]:\n{state['feedback']}\n"
            has_issues = True

        if has_issues:
            prompt += "\nИсправь ВСЕ вышеуказанные проблемы в новом коде."
            
    response = llm.invoke(prompt)
    clean_code = extract_python_code(response.content)
    return {"code": clean_code, "iterations": 1}

@node_logger
def reviewer_func(state: DeveloperState):
    workspace_dir = os.path.join(PROJECT_ROOT, "workspace")
    files_list = os.listdir(workspace_dir) if os.path.exists(workspace_dir) else []
    files_str = ", ".join(files_list) if files_list else "Папка пуста"

    prompt = f"""
    Ты - Senior QA-инженер. Твоя задача проверить, выполнил ли код ТЕКУЩУЮ ЗАДАЧУ.
    
    ВНИМАНИЕ: Тебе дано большое ТЗ, которое состоит из Глобальной цели и Текущей задачи на один шаг.
    Ты должен оценивать код ТОЛЬКО по блоку [ТВОЯ ЗАДАЧА НА ЭТОТ ШАГ]. Не требуй от программиста выполнения того, что не описано в текущем шаге!
    
    ПОЛНОЕ ТЗ:
    {state['task']}

    КОД, который был выполнен:
    ```python
    {state['code']}
    ```

    ВЫВОД НА ЭКРАН (stdout):
    ```text
    {state.get('output', 'Ничего не выведено')}
    ```
    
    ФАЙЛЫ В ПАПКЕ (workspace/): {files_str}

    ПРАВИЛА ТВОЕЙ РАБОТЫ:
    1. Ты не можешь верить коду на слово. Если код должен был создать или изменить файл, ты ОБЯЗАН его прочитать.
    2. Чтобы прочитать файл, напиши ровно одну строку: [READ: имя_файла.расширение]. Я дам тебе его содержимое.
    3. Если текущий шаг (и только он!) выполнен идеально, напиши ТОЛЬКО одно слово: [APPROVED]
    4. Если есть ошибка (в логике, или файл пустой), объясни почему и напиши в конце: [REJECTED]
    """

    messages = [{"role": "user", "content": prompt}]

    for step in range(4):
        response = llm.invoke(messages)
        text = response.content.strip()

        if "[READ:" in text:
            try:
                filename = text.split("[READ:")[1].split("]")[0].strip()
                filepath = os.path.join(workspace_dir, filename)
                
                print(f"   [Reviewer Tool]: Запросил чтение файла '{filename}'...")
                
                if os.path.exists(filepath):
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()
                        if len(content) > 3000: content = content[:3000] + "\n...[ОБРЕЗАНО]"
                else:
                    content = f"ОШИБКА: Файл {filename} не существует."

                messages.append({"role": "assistant", "content": text})
                messages.append({"role": "user", "content": f"Содержимое {filename}:\n```\n{content}\n```\nТеперь вынеси вердикт или прочитай другой файл."})
                continue
                
            except Exception as e:
                messages.append({"role": "assistant", "content": text})
                messages.append({"role": "user", "content": f"Синтаксическая ошибка. Используй точный формат [READ: filename.txt]"})
                continue

        if "[APPROVED]" in text:
            print("   [Reviewer]: Код идеален.")
            return {"task_compliance": True, "feedback": ""}
        else:
            return {"task_compliance": False, "feedback": text}

    return {"task_compliance": False, "feedback": "QA-инженер не смог принять решение за 3 шага. Перепроверь логику кода. [REJECTED]"}

@node_logger
def researcher_func(state: DeveloperState):
    error_lines = [line.strip() for line in state['error'].split('\n') if line.strip()]
    actual_error = error_lines[-1] 
    query = f"Python how to fix error: {actual_error}"
    try:
        search_result = search_tool.invoke(query)
        return {"research_data": search_result}
    except Exception as e:
        return {"research_data": "Подсказок нет."}

@node_logger
def tester_func(state: DeveloperState):
    code = state["code"]
    
    workspace_dir = os.path.join(PROJECT_ROOT, "workspace")
    os.makedirs(workspace_dir, exist_ok=True)
    
    script_path = os.path.join(workspace_dir, "agent_temp_script.py")
    
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(code)

    custom_env = os.environ.copy()
    custom_env["PYTHONPATH"] = f"{PROJECT_ROOT}{os.pathsep}{custom_env.get('PYTHONPATH', '')}"
    custom_env["MPLBACKEND"] = "Agg"

    custom_env["PYTHONIOENCODING"] = "utf-8"
    custom_env["PYTHONUTF8"] = "1"
        
    try:
        result = subprocess.run(
            [sys.executable, "agent_temp_script.py"],
            cwd=workspace_dir, 
            env=custom_env,
            capture_output=True,   
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15             
        )
        
        if os.path.exists(script_path):
            os.remove(script_path)

        if result.returncode == 0:
            return {
                "error": None, 
                "last_error": None, 
                "error_streak": 0, 
                "output": result.stdout.strip()
            }
        else:
            error_msg = result.stderr.strip() or result.stdout.strip()
            current_streak = state.get("error_streak", 0)
            new_streak = current_streak + 1 if error_msg == state.get("last_error") else 1
            
            return {
                "error": error_msg,
                "last_error": error_msg,
                "error_streak": new_streak,
                "output": result.stdout.strip()
            }
            
    except subprocess.TimeoutExpired:
        if os.path.exists(script_path): os.remove(script_path)
        error_msg = "TimeoutError: Программа выполнялась слишком долго (>15 сек)."
        current_streak = state.get("error_streak", 0)
        new_streak = current_streak + 1 if error_msg == state.get("last_error") else 1
        return {"error": error_msg, "last_error": error_msg, "error_streak": new_streak, "output": ""}
    except Exception as e:
        if os.path.exists(script_path): os.remove(script_path)
        error_msg = str(e)
        return {"error": error_msg, "last_error": error_msg, "error_streak": state.get("error_streak", 0) + 1, "output": ""}
        
@node_logger
def tool_saver_func(state: DeveloperState):
    print("-> [Tool Saver] Анализирую и сохраняю инструмент...")

    prompt = f"""
    Проанализируй следующий Python-код и верни JSON-объект с описанием его главной функции.
    КОД:
    ```python
    {state['code']}
    ```
    
    Твой ответ должен быть ТОЛЬКО в формате JSON и содержать 3 поля:
    1. "name" - точное название ГЛАВНОЙ ФУНКЦИИ из кода (например "organize_files"). Это критически важно для правильного импорта!
    2. "description" - краткое описание, что делает функция.
    3. "parameters" - словарь аргументов функции.
    """
    
    response = llm.invoke(prompt)
    tool_info = extract_json(response.content)
    
    tool_name = tool_info.get("name", "unnamed_tool")

    os.makedirs("tools", exist_ok=True)

    file_path = f"tools/{tool_name}.py"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(clean_code(state["code"]))

    registry_path = "tools/registry.json"
    registry = []
    if os.path.exists(registry_path):
        with open(registry_path, "r", encoding="utf-8") as f:
            try:
                registry = json.load(f)
            except:
                pass

    registry = [t for t in registry if t.get("name") != tool_name]
    registry.append(tool_info)
    
    with open(registry_path, "w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False, indent=4)
        
    print(f"   [Tool Saver]: Инструмент '{tool_name}' успешно сохранен в реестр!")
    return state

def check_compliance(state: DeveloperState) -> str:
    """Маршрутизатор после Ревьюера"""
    if state['task_compliance'] == False:
        return "to_fix"
    elif state.get('is_tool') == True:
        return "save_tool"
    else:
        return "success"

@node_logger
def fail_func(state: DeveloperState):
    print(f"[FAILED TO WRITE CODE]\n| Last error:\n{state['error']}")

@node_logger
def success_func(state: DeveloperState):
    print(f"[SUCCESS]\n| Code:\n{state['code']}")

def check_error(state: DeveloperState) -> str:
    if state["iterations"] >= 20:
        return "stop"
    if state["error"] != None:
        return "to_fix"
    return "success"