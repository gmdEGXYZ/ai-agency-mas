from tools._db import _load_db

def memory_load(key: str) -> any:
    """Загружает данные из памяти по ключу."""
    db = _load_db()
    if key in db:
        return db[key]["value"]
    raise KeyError(f"Ключ '{key}' не найден в памяти.")