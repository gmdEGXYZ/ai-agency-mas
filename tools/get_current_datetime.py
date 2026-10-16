from datetime import datetime

def get_current_datetime() -> str:
    """
    Returns the current system date and time in 'YYYY-MM-DD HH:MM:SS' format.
    """
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

if __name__ == '__main__':
    print(get_current_datetime())