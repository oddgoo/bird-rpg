from datetime import datetime, timedelta
import pytz

def get_time_until_reset():
    eastern_australia = pytz.timezone('Australia/Sydney')
    now = datetime.now(eastern_australia)
    tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    time_remaining = tomorrow - now
    hours = time_remaining.seconds // 3600
    minutes = (time_remaining.seconds % 3600) // 60
    
    if hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"