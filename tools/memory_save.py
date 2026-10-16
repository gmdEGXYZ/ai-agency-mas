from tools._db import _load_db, _save_db

def memory_save(key: str, value: any, description: str) -> bool:
    """Сохраняет любые данные (словари, списки, строки) в глобальную память."""
    db = _load_db()
    db[key] = {
        "value": value,
        "description": description
    }
    _save_db(db)
    return True