from datetime import datetime
import json
import os
import random
from utils.time_utils import get_current_date
from constants import BASE_DAILY_ACTIONS  # Updated import path

def get_personal_nest(data, user_id):
    """Get or create a personal nest for a user"""
    user_id = str(user_id)  # Convert to string for consistency
    if "personal_nests" not in data:
        data["personal_nests"] = {}
    if user_id not in data["personal_nests"]:
        data["personal_nests"][user_id] = {
            "twigs": 0,
            "seeds": 0
        }
        
    nest = data["personal_nests"][user_id]
    if "egg" not in nest:
        nest["egg"] = None
    if "chicks" not in nest:
        nest["chicks"] = []
    if "name" not in nest:
        nest["name"] = "Some Bird's Nest"
    if "garden_size" not in nest:
        nest["garden_size"] = 0
    if "inspiration" not in nest:
        nest["inspiration"] = 0
    if "bonus_actions" not in nest:  # New field for persistent bonus actions
        nest["bonus_actions"] = 0
    return nest

def get_common_nest(data):
    if "common_nest" not in data or data["common_nest"] is None:
        data["common_nest"] = {"twigs": 0, "seeds": 0}
    return data["common_nest"]

def get_remaining_actions(data, user_id):
    user_id = str(user_id)
    today = get_current_date()
    
    if user_id not in data["daily_actions"]:
        data["daily_actions"][user_id] = {}
    
    if f"actions_{today}" not in data["daily_actions"][user_id]:
        data["daily_actions"][user_id][f"actions_{today}"] = {
            "used": 0,
            "action_history": []  # Only track used actions and history per day
        }
    
    # Convert old format if necessary
    if isinstance(data["daily_actions"][user_id][f"actions_{today}"], (int, float)):
        used_actions = data["daily_actions"][user_id][f"actions_{today}"]
        data["daily_actions"][user_id][f"actions_{today}"] = {
            "used": used_actions,
            "action_history": []
        }
    
    actions_data = data["daily_actions"][user_id][f"actions_{today}"]
    
    # Get persistent bonus actions from nest
    nest = get_personal_nest(data, user_id)
    chick_bonus = get_total_chicks(nest)
    persistent_bonus = nest["bonus_actions"]
    
    total_available = BASE_DAILY_ACTIONS + persistent_bonus + chick_bonus
    return total_available - actions_data["used"]

def record_actions(data, user_id, count, action_type=None):
    """
    Record actions used by a user
    action_type can be: 'build', 'sing', 'seed', 'brood'
    """
    user_id = str(user_id)
    today = get_current_date()
    
    if user_id not in data["daily_actions"]:
        data["daily_actions"][user_id] = {}
    
    if f"actions_{today}" not in data["daily_actions"][user_id]:
        data["daily_actions"][user_id][f"actions_{today}"] = {
            "used": 0,
            "bonus": 0,
            "action_history": []  # List to track action types in order
        }
    
    daily_data = data["daily_actions"][user_id][f"actions_{today}"]
    
    # Convert old format if necessary
    if isinstance(daily_data, (int, float)):
        daily_data = {
            "used": daily_data,
            "bonus": 0,
            "action_history": []
        }
        data["daily_actions"][user_id][f"actions_{today}"] = daily_data
    elif "action_history" not in daily_data:
        daily_data["action_history"] = []
    
    daily_data["used"] += count
    if action_type:
        daily_data["action_history"].extend([action_type] * count)

def is_first_action_of_type(data, user_id, action_type):
    """Check if this is the first action of a specific type today"""
    user_id = str(user_id)
    today = get_current_date()
    
    if user_id not in data["daily_actions"]:
        return True
        
    daily_data = data["daily_actions"][user_id].get(f"actions_{today}")
    if not daily_data or not isinstance(daily_data, dict):
        return True
        
    action_history = daily_data.get("action_history", [])
    return action_type not in action_history

def has_been_sung_to(data, user_id):
    user_id = str(user_id)
    today = today = get_current_date()
    
    if "daily_songs" not in data:
        data["daily_songs"] = {}
    
    return (today in data["daily_songs"] and 
            user_id in data["daily_songs"][today] and 
            len(data["daily_songs"][today][user_id]) > 0)

def has_been_sung_to_by(data, singer_id, target_id):
    singer_id = str(singer_id)
    target_id = str(target_id)
    today = today = get_current_date()
    
    if "daily_songs" not in data:
        data["daily_songs"] = {}
    
    if today not in data["daily_songs"]:
        return False
    
    return (target_id in data["daily_songs"][today] and 
            singer_id in data["daily_songs"][today][target_id])

def record_song(data, singer_id, target_id):
    singer_id = str(singer_id)
    target_id = str(target_id)
    today = today = get_current_date()
    
    if "daily_songs" not in data:
        data["daily_songs"] = {}
    
    if today not in data["daily_songs"]:
        data["daily_songs"][today] = {}
        
    if target_id not in data["daily_songs"][today]:
        data["daily_songs"][today][target_id] = []
        
    data["daily_songs"][today][target_id].append(singer_id)

def get_singers_today(data, target_id):
    target_id = str(target_id)
    today = today = get_current_date()
    
    if "daily_songs" not in data:
        return []
        
    if today not in data["daily_songs"]:
        return []
        
    return data["daily_songs"][today].get(target_id, [])

def add_bonus_actions(data, user_id, amount):
    user_id = str(user_id)
    nest = get_personal_nest(data, user_id)
    nest["bonus_actions"] += amount

def get_egg_cost(nest):
    """Calculate the cost of laying an egg based on number of chicks"""
    base_cost = 20
    #chick_count = get_total_chicks(nest) no scaling for now
    return base_cost

def has_brooded_egg(data, brooder_id, target_id):
    """Check if brooder has brooded target's egg today"""
    brooder_id = str(brooder_id)
    target_id = str(target_id)
    today = today = get_current_date()
    
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
    today = today = get_current_date()
    
    # Record in daily_brooding structure
    if "daily_brooding" not in data:
        data["daily_brooding"] = {}
    
    if today not in data["daily_brooding"]:
        data["daily_brooding"][today] = {}
        
    if target_id not in data["daily_brooding"][today]:
        data["daily_brooding"][today][target_id] = []
        
    data["daily_brooding"][today][target_id].append(brooder_id)
    
    # Also record in the egg's brooded_by list
    nest = get_personal_nest(data, target_id)
    if nest["egg"] and brooder_id not in nest["egg"]["brooded_by"]:
        nest["egg"]["brooded_by"].append(brooder_id)

def get_total_chicks(nest):
    """Return the number of chicks in the nest"""
    return len(nest.get("chicks", []))

def load_bird_species():
    """Load bird species from the JSON file"""
    file_path = os.path.join(os.path.dirname(__file__), 'bird_species.json')
    with open(file_path, 'r') as file:
        data = json.load(file)
    return data["bird_species"]

def get_bird_effect(scientific_name):
    """Get the effect for a bird species by scientific name"""
    bird_species = load_bird_species()
    for species in bird_species:
        if species["scientificName"] == scientific_name:
            return species.get("effect", "")
    return ""

def select_random_bird_species(multipliers=None):
    """
    Select a random bird species based on rarity weights and optional multipliers
    
    Args:
        multipliers (dict): Optional dictionary mapping scientific names to multipliers
    """
    bird_species = load_bird_species()
    weights = []
    
    for species in bird_species:
        base_weight = species["rarityWeight"]
        if multipliers and species["scientificName"] in multipliers:
            weights.append(base_weight * multipliers[species["scientificName"]])
        else:
            weights.append(base_weight)
            
    return random.choices(bird_species, weights=weights, k=1)[0]

def get_discovered_species(data):
    """Retrieve all unique bird species discovered by all users."""
    discovered = set()
    for nest in data.get("personal_nests", {}).values():
        for chick in nest.get("chicks", []):
            discovered.add( (chick["commonName"], chick["scientificName"]) )
    return discovered

def get_discovered_species_count(data):
    """Return the count of all unique bird species discovered."""
    return len(get_discovered_species(data))

def get_total_bird_species(data):
    """Return the total number of bird species available."""
    bird_species = load_bird_species()
    return len(bird_species)

def get_nest_building_bonus(data, nest):
    """Calculate building bonus from birds that give first-build-of-day bonuses"""
    # Get user_id from nest
    user_id = next(
        uid for uid, user_nest in data["personal_nests"].items() 
        if user_nest == nest
    )
    
    if not is_first_action_of_type(data, user_id, "build"):
        return 0
    
    # Calculate bonus from all chicks with building effects
    total_bonus = 0
    for chick in nest.get("chicks", []):
        effect = get_bird_effect(chick["scientificName"])
        if "Your first nest-building action of the day gives" in effect:
            bonus_amount = int(''.join(filter(str.isdigit, effect)))
            total_bonus += bonus_amount
            
    return total_bonus

def get_singing_bonus(nest):
    """Calculate total singing bonus from birds with song-enhancing effects"""
    total_bonus = 0
    for chick in nest.get("chicks", []):
        effect = get_bird_effect(chick["scientificName"])
        if "All your songs give" in effect:
            # Extract the number from strings like "+3 bonus actions"
            bonus_amount = int(''.join(filter(str.isdigit, effect)))
            total_bonus += bonus_amount
            
    return total_bonus
def get_singing_inspiration_chance(data, nest):
    """Calculate chance-based inspiration bonus from finches on first singing action"""
    # Get user_id from nest
    user_id = next(
        uid for uid, user_nest in data["personal_nests"].items() 
        if user_nest == nest
    )
    
    if not is_first_action_of_type(data, user_id, "sing"):
        return 0
    
    # Count finches with inspiration chance effects
    inspiration_chances = 0
    for chick in nest.get("chicks", []):
        effect = get_bird_effect(chick["scientificName"])
        if "has a 50% chance to give you +1 inspiration" in effect:
            if random.random() < 0.5:  # 50% chance for each finch
                inspiration_chances += 1
                
    return inspiration_chances

def get_seed_gathering_bonus(data, nest):
    """Calculate garden size bonus from birds that give first-gather-of-day bonuses"""
    # Get user_id from nest
    user_id = next(
        uid for uid, user_nest in data["personal_nests"].items() 
        if user_nest == nest
    )
    
    if not is_first_action_of_type(data, user_id, "seed"):
        return 0
    
    # Calculate bonus from all chicks with seed gathering effects
    total_bonus = 0
    for chick in nest.get("chicks", []):
        effect = get_bird_effect(chick["scientificName"])
        if "Your first seed gathering action of the day also gives" in effect:
            bonus_amount = int(''.join(filter(str.isdigit, effect)))
            total_bonus += bonus_amount
            
    return total_bonus
