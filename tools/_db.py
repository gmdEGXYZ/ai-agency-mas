import os
import json

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEMORY_FILE = os.path.join(PROJECT_ROOT, "memory.json")

def _load_db() -> dict:
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def _save_db(db: dict):
    with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=4)

def get_memory_index() -> str:
    db = _load_db()
    if not db:
        return "Системная память пока пуста."
    
    lines = ["[АКТИВНАЯ ПАМЯТЬ СИСТЕМЫ]:"]
    for k, v in db.items():
        desc = v.get("description", "Без описания")
        lines.append(f"- Ключ: '{k}' | Описание: '{desc}'")
    return "\n".join(lines)