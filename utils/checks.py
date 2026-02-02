from functools import wraps
import data.storage as db


def has_player():
    """Check if the user has a nest and is a valid player"""
    def decorator(func):
        @wraps(func)
        async def wrapper(self, interaction, *args, **kwargs):
            user_id = str(interaction.user.id)

            player = await db.load_player(user_id)
            if player.get("twigs", 0) == 0 and player.get("seeds", 0) == 0:
                await interaction.response.send_message(
                    "You need to have a nest first! Use `/build` to start building your nest."
                )
                return

            return await func(self, interaction, *args, **kwargs)
        return wrapper
    return decorator

def has_birds():
    """Check if the user has at least one bird in their nest"""
    def decorator(func):
        @wraps(func)
        async def wrapper(self, interaction, *args, **kwargs):
            user_id = str(interaction.user.id)

            player = await db.load_player(user_id)
            if player.get("twigs", 0) == 0 and player.get("seeds", 0) == 0:
                await interaction.response.send_message(
                    "You need to have a nest first! Use `/build` to start building your nest."
                )
                return

            birds = await db.get_player_birds(user_id)
            if not birds:
                await interaction.response.send_message(
                    "You need to have at least one bird in your nest! Try hatching an egg first."
                )
                return

            return await func(self, interaction, *args, **kwargs)
        return wrapper
    return decorator
