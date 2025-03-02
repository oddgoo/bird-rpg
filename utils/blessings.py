from copy import deepcopy
from config.config import MAX_GARDEN_SIZE

def get_blessing_amount(max_resilience):
    """Calculate blessing amount based on human difficulty"""
    tiers = [10, 20, 30]
    if max_resilience <= 25:
        return tiers[0]
    elif max_resilience <= 50:
        return tiers[1]
    return tiers[2]

def apply_blessing(nests, blessing_type, amount):
    """Apply a blessing to all nests"""
    nests = deepcopy(nests)  # Don't modify the original
    
    if blessing_type == "individual_seeds":
        for user_id, nest in nests.items():
            # Check nest capacity
            space_left = nest["twigs"] - nest.get("seeds", 0)
            nest["seeds"] = nest.get("seeds", 0) + min(amount, space_left)
    elif blessing_type == "inspiration":
        for user_id, nest in nests.items():
            nest["inspiration"] = nest.get("inspiration", 0) + amount
    elif blessing_type == "garden_growth":
        for user_id, nest in nests.items():
            current_size = nest.get("garden_size", 0)
            # Ensure we don't exceed MAX_GARDEN_SIZE
            nest["garden_size"] = min(current_size + amount, MAX_GARDEN_SIZE)
    elif blessing_type == "bonus_actions":
        for user_id, nest in nests.items():
            nest["bonus_actions"] = nest.get("bonus_actions", 0) + amount
    elif blessing_type == "individual_nest_growth":
        for user_id, nest in nests.items():
            nest["twigs"] = nest.get("twigs", 0) + amount
    
    return nests
