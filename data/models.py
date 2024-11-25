from datetime import datetime

def get_personal_nest(data, user_id):
    user_id = str(user_id)
    if user_id not in data["personal_nests"]:
        data["personal_nests"][user_id] = {"twigs": 0, "seeds": 0}
    return data["personal_nests"][user_id]

def get_common_nest(data):
    if "common_nest" not in data or data["common_nest"] is None:
        data["common_nest"] = {"twigs": 0, "seeds": 0}
    return data["common_nest"]

def get_remaining_actions(data, user_id):
    user_id = str(user_id)
    today = datetime.now().strftime('%Y-%m-%d')
    
    if user_id not in data["daily_actions"]:
        data["daily_actions"][user_id] = {}
    
    if f"actions_{today}" not in data["daily_actions"][user_id]:
        data["daily_actions"][user_id][f"actions_{today}"] = {
            "used": 0,
            "bonus": 0
        }
    
    # If it's old format (just a number), convert to new format
    if isinstance(data["daily_actions"][user_id][f"actions_{today}"], (int, float)):
        used_actions = data["daily_actions"][user_id][f"actions_{today}"]
        data["daily_actions"][user_id][f"actions_{today}"] = {
            "used": used_actions,
            "bonus": 0
        }
    
    actions_data = data["daily_actions"][user_id][f"actions_{today}"]
    base_actions = 3
    total_available = base_actions + actions_data["bonus"]
    return total_available - actions_data["used"]

def record_actions(data, user_id, count):
    user_id = str(user_id)
    today = datetime.now().strftime('%Y-%m-%d')
    
    if user_id not in data["daily_actions"]:
        data["daily_actions"][user_id] = {}
    
    if f"actions_{today}" not in data["daily_actions"][user_id]:
        data["daily_actions"][user_id][f"actions_{today}"] = {
            "used": 0,
            "bonus": 0
        }
    
    if isinstance(data["daily_actions"][user_id][f"actions_{today}"], (int, float)):
        used_actions = data["daily_actions"][user_id][f"actions_{today}"]
        data["daily_actions"][user_id][f"actions_{today}"] = {
            "used": used_actions,
            "bonus": 0
        }
    
    data["daily_actions"][user_id][f"actions_{today}"]["used"] += count

def has_been_sung_to(data, user_id):
    user_id = str(user_id)
    today = datetime.now().strftime('%Y-%m-%d')
    
    if "daily_songs" not in data:
        data["daily_songs"] = {}
    
    return (today in data["daily_songs"] and 
            user_id in data["daily_songs"][today] and 
            len(data["daily_songs"][today][user_id]) > 0)

def has_been_sung_to_by(data, singer_id, target_id):
    singer_id = str(singer_id)
    target_id = str(target_id)
    today = datetime.now().strftime('%Y-%m-%d')
    
    if "daily_songs" not in data:
        data["daily_songs"] = {}
    
    if today not in data["daily_songs"]:
        return False
    
    return (target_id in data["daily_songs"][today] and 
            singer_id in data["daily_songs"][today][target_id])

def record_song(data, singer_id, target_id):
    singer_id = str(singer_id)
    target_id = str(target_id)
    today = datetime.now().strftime('%Y-%m-%d')
    
    if "daily_songs" not in data:
        data["daily_songs"] = {}
    
    if today not in data["daily_songs"]:
        data["daily_songs"][today] = {}
        
    if target_id not in data["daily_songs"][today]:
        data["daily_songs"][today][target_id] = []
        
    data["daily_songs"][today][target_id].append(singer_id)

def get_singers_today(data, target_id):
    target_id = str(target_id)
    today = datetime.now().strftime('%Y-%m-%d')
    
    if "daily_songs" not in data:
        return []
        
    if today not in data["daily_songs"]:
        return []
        
    return data["daily_songs"][today].get(target_id, [])

def add_bonus_actions(data, user_id, amount):
    user_id = str(user_id)
    today = datetime.now().strftime('%Y-%m-%d')
    
    if user_id not in data["daily_actions"]:
        data["daily_actions"][user_id] = {}
    
    if f"actions_{today}" not in data["daily_actions"][user_id]:
        data["daily_actions"][user_id][f"actions_{today}"] = {
            "used": 0,
            "bonus": 0
        }
    
    if isinstance(data["daily_actions"][user_id][f"actions_{today}"], (int, float)):
        used_actions = data["daily_actions"][user_id][f"actions_{today}"]
        data["daily_actions"][user_id][f"actions_{today}"] = {
            "used": used_actions,
            "bonus": 0
        }
    
    data["daily_actions"][user_id][f"actions_{today}"]["bonus"] += amount