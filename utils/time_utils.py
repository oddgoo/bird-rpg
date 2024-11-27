from datetime import datetime, timedelta
import pytz

def get_australian_time():
    """Get current time in Australian Eastern timezone"""
    eastern_australia = pytz.timezone('Australia/Sydney')
    return datetime.now(eastern_australia)

def get_current_date():
    """Get current date in Australian Eastern timezone"""
    return get_australian_time().strftime('%Y-%m-%d')

def get_time_until_reset():
    eastern_australia = pytz.timezone('Australia/Sydney')
    now = datetime.now(eastern_australia)
    tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0)

    time_remaining = tomorrow - now
    hours = time_remaining.seconds // 3600
    minutes = (time_remaining.seconds % 3600) // 60
    
    if hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"