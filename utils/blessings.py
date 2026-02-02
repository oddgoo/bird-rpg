from config.config import MAX_GARDEN_SIZE
import data.storage as db


def get_blessing_amount(max_resilience):
    """Calculate blessing amount based on human difficulty"""
    tiers = [10, 20, 30]
    if max_resilience <= 25:
        return tiers[0]
    elif max_resilience <= 50:
        return tiers[1]
    return tiers[2]


async def apply_blessing(blessing_type, amount):
    """Apply a blessing to all players via DB operations"""
    players = await db.load_all_players()

    if blessing_type == "individual_seeds":
        for player in players:
            user_id = player["user_id"]
            space_left = player.get("twigs", 0) - player.get("seeds", 0)
            add_amount = min(amount, max(0, space_left))
            if add_amount > 0:
                await db.increment_player_field(user_id, "seeds", add_amount)
    elif blessing_type == "inspiration":
        for player in players:
            await db.increment_player_field(player["user_id"], "inspiration", amount)
    elif blessing_type == "garden_growth":
        for player in players:
            user_id = player["user_id"]
            current_size = player.get("garden_size", 0)
            increase = min(amount, MAX_GARDEN_SIZE - current_size)
            if increase > 0:
                await db.increment_player_field(user_id, "garden_size", increase)
    elif blessing_type == "bonus_actions":
        for player in players:
            await db.increment_player_field(player["user_id"], "bonus_actions", amount)
    elif blessing_type == "individual_nest_growth":
        for player in players:
            await db.increment_player_field(player["user_id"], "twigs", amount)
