from datetime import datetime
from data.storage import load_bird_species
import json
import os
import random

def get_personal_nest(data, user_id):
    user_id = str(user_id)
    if user_id not in data["personal_nests"]:
        data["personal_nests"][user_id] = {
            "twigs": 0,
            "seeds": 0,
            "name": "Some Bird's Nest",
            "egg": None,
            "chicks": []
        }
    # Ensure existing nests have all required fields
    nest = data["personal_nests"][user_id]
    if "egg" not in nest:
        nest["egg"] = None
    if "chicks" not in nest:
        nest["chicks"] = []
    if "name" not in nest:
        nest["name"] = "Some Bird's Nest"
    return nest

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
    
    # Convert old format if necessary
    if isinstance(data["daily_actions"][user_id][f"actions_{today}"], (int, float)):
        used_actions = data["daily_actions"][user_id][f"actions_{today}"]
        data["daily_actions"][user_id][f"actions_{today}"] = {
            "used": used_actions,
            "bonus": 0
        }
    
    actions_data = data["daily_actions"][user_id][f"actions_{today}"]
    
    # Add bonus actions from chicks
    nest = get_personal_nest(data, user_id)
    chick_bonus = get_total_chicks(nest)
    
    base_actions = 3
    total_available = base_actions + actions_data["bonus"] + chick_bonus
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

def get_egg_cost(nest):
    """Calculate the cost of laying an egg based on number of chicks"""
    base_cost = 15
    chick_count = get_total_chicks(nest)
    return base_cost + (chick_count * 5)

def has_brooded_egg(data, brooder_id, target_id):
    """Check if brooder has brooded target's egg today"""
    brooder_id = str(brooder_id)
    target_id = str(target_id)
    today = datetime.now().strftime('%Y-%m-%d')
    
    if "daily_brooding" not in data:
        data["daily_brooding"] = {}
    
    if today not in data["daily_brooding"]:
        return False
    
    return (target_id in data["daily_brooding"][today] and 
            brooder_id in data["daily_brooding"][today][target_id])

def record_brooding(data, brooder_id, target_id):
    """Record that brooder has brooded target's egg today"""
    brooder_id = str(brooder_id)
    target_id = str(target_id)
    today = datetime.now().strftime('%Y-%m-%d')
    
    if "daily_brooding" not in data:
        data["daily_brooding"] = {}
    
    if today not in data["daily_brooding"]:
        data["daily_brooding"][today] = {}
        
    if target_id not in data["daily_brooding"][today]:
        data["daily_brooding"][today][target_id] = []
        
    data["daily_brooding"][today][target_id].append(brooder_id)

def get_total_chicks(nest):
    """Return the number of chicks in the nest"""
    return len(nest.get("chicks", []))

def load_bird_species():
    """Load bird species from the JSON file"""
    file_path = os.path.join(os.path.dirname(__file__), 'bird_species.json')
    with open(file_path, 'r') as file:
        data = json.load(file)
    return data["bird_species"]

def select_random_bird_species():
    """Select a random bird species based on rarity weights"""
    bird_species = load_bird_species()
    total_weight = sum(species["rarityWeight"] for species in bird_species)
    rand = random.uniform(0, total_weight)
    upto = 0
    for species in bird_species:
        if upto + species["rarityWeight"] >= rand:
            return species
        upto += species["rarityWeight"]
    return bird_species[-1]  # Fallback