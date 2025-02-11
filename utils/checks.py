from functools import wraps
from data.models import get_personal_nest
from data.storage import load_data

def has_player():
    """Check if the user has a nest and is a valid player"""
    def decorator(func):
        @wraps(func)
        async def wrapper(self, interaction, *args, **kwargs):
            data = load_data()
            user_id = str(interaction.user.id)
            
            # Check if user has a nest
            if user_id not in data.get("personal_nests", {}):
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
            data = load_data()
            user_id = str(interaction.user.id)
            
            # Check if user has a nest
            if user_id not in data.get("personal_nests", {}):
                await interaction.response.send_message(
                    "You need to have a nest first! Use `/build` to start building your nest."
                )
                return

            # Check if user has any birds
            nest = data["personal_nests"][user_id]
            if not nest.get("chicks", []):
                await interaction.response.send_message(
                    "You need to have at least one bird in your nest! Try hatching an egg first."
                )
                return
            
            return await func(self, interaction, *args, **kwargs)
        return wrapper
    return decorator 