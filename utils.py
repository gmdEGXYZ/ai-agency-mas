import functools
from states import DeveloperState
import json
import re

def extract_python_code(text: str) -> str:
    """Вырезает чистый код из ответа модели (между ```python и ```)"""
    if "```python" in text:
        return text.split("```python")[1].split("```")[0].strip()
    elif "```" in text:
        return text.split("```")[1].split("```")[0].strip()
    return text.strip()

def node_logger(func):
    """Декоратор для логирования узлов LangGraph"""
    @functools.wraps(func)
    def wrapper(state: DeveloperState, *args, **kwargs):
        print(f"\n" + "="*50)
        print(f"[ЗАПУСК УЗЛА]: {func.__name__.upper()}")
        
        result = func(state, *args, **kwargs)
        
        print(f"[ИЗМЕНЕНИЯ В STATE]:")
        if result:
            for key, value in result.items():
                str_val = str(value)
                print(f"   -> {key}: {str_val}")
        else:
            print("   -> (Нет изменений)")
            
        return result
    return wrapper

def extract_json(text: str) -> dict:
    """Вырезает и парсит JSON из ответа модели"""
    try:
        if "```json" in text:
            json_str = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            json_str = text.split("```")[1].split("```")[0].strip()
        else:
            json_str = text.strip()
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"⚠️ Ошибка парсинга JSON: {e}")
        return {"name": "unknown_tool", "description": "Ошибка парсинга", "parameters": {}}

def clean_code(code: str) -> str:
    """Удаляет блок if __name__ == '__main__': и всё, что ниже него"""
    return re.split(r"if\s+__name__\s*==\s*['\"]__main__['\"]\s*:", code)[0].strip()