from datetime import datetime

def log_debug(message):
    print(f"[DEBUG] {datetime.now().strftime('%H:%M:%S')}: {message}")