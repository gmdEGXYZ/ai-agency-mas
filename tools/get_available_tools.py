import json
import os

def get_available_tools() -> str:
    """
    Reads the tools registry from a JSON file and formats it into a 
    human-readable string suitable for an AI system prompt.
    """
    file_path = 'tools/registry.json'
    
    if not os.path.exists(file_path):
        return "Инструменты не найдены"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tools_data = json.load(f)
            
        if not tools_data:
            return "Инструменты не найдены"
            
        formatted_tools = []
        for tool in tools_data:
            name = tool.get('name', 'Неизвестно')
            description = tool.get('description', 'Описание отсутствует')
            params = tool.get('parameters', 'Нет параметров')
            
            tool_str = (
                f"Название: {name}\n"
                f"Описание: {description}\n"
                f"Параметры: {params}"
            )
            formatted_tools.append(tool_str)
            
        return "\n\n".join(formatted_tools)
        
    except (json.JSONDecodeError, IOError):
        return "Инструменты не найдены"