import json
import random
from datetime import datetime, date
from pathlib import Path
import os

from discord.ext import commands
from discord import app_commands, File

from data.models import (
    get_remaining_actions, record_actions, get_swooping_bonus
)
import data.storage as db
from utils.checks import has_birds
from utils.human_spawner import HumanSpawner

class Swooping(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.defeat_gifs = {
            "small child": "static/gifs/small_child.gif",
            "average human on a bike": "static/gifs/average_human.gif",
            "bully kid": "static/gifs/bully_kid.gif",
            "a band of grifters": "static/gifs/a-band-of-grifters.gif"
        }

    async def _apply_blessing(self):
        """Apply a random blessing to all players when human is defeated"""
        # Load human data directly
        file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'human_entities.json')
        with open(file_path, 'r') as f:
            human_data = json.load(f)

        blessing = random.choice(human_data["blessings"])
        # Get tier based on defeated human's tier_level
        spawner = HumanSpawner()
        state = spawner._get_current_state()
        current_human = state['current_human']
        tier_level = current_human.get("tier_level", 1)
        tier_index = tier_level - 1

        amount = blessing["tiers"][tier_index]

        # Apply blessing via DB operations instead of in-memory dict manipulation
        if blessing["type"] == "common_seeds":
            await db.increment_common_nest("seeds", amount)
        elif blessing["type"] == "common_nest_growth":
            await db.increment_common_nest("twigs", amount)
        elif blessing["type"] == "individual_seeds":
            players = await db.load_all_players()
            for player in players:
                user_id = player["user_id"]
                space_left = player.get("twigs", 0) - player.get("seeds", 0)
                add_amount = min(amount, max(0, space_left))
                if add_amount > 0:
                    await db.increment_player_field(user_id, "seeds", add_amount)
        elif blessing["type"] == "inspiration":
            players = await db.load_all_players()
            for player in players:
                await db.increment_player_field(player["user_id"], "inspiration", amount)
        elif blessing["type"] == "garden_growth":
            players = await db.load_all_players()
            from config.config import MAX_GARDEN_SIZE
            for player in players:
                current_size = player.get("garden_size", 0)
                new_size = min(current_size + amount, MAX_GARDEN_SIZE)
                increment = new_size - current_size
                if increment > 0:
                    await db.increment_player_field(player["user_id"], "garden_size", increment)
        elif blessing["type"] == "bonus_actions":
            players = await db.load_all_players()
            for player in players:
                await db.increment_player_field(player["user_id"], "bonus_actions", amount)
        elif blessing["type"] == "individual_nest_growth":
            players = await db.load_all_players()
            for player in players:
                await db.increment_player_field(player["user_id"], "twigs", amount)

        # Record the defeated human
        await db.add_defeated_human(
            current_human["name"],
            current_human["max_resilience"],
            str(date.today()),
            blessing["name"],
            amount
        )
        return blessing["name"], amount

    @app_commands.command(
        name="swoop",
        description="Swoop at the current human intruder with your birds"
    )
    @app_commands.describe(
        amount="Amount of actions to use for swooping"
    )
    @has_birds()
    async def swoop(self, interaction, amount: int):
        await interaction.response.defer()
        if amount <= 0:
            await interaction.followup.send("You need to use at least 1 action to swoop!")
            return

        try:
            user_id = str(interaction.user.id)
            remaining_actions = await get_remaining_actions(user_id)

            if remaining_actions < amount:
                await interaction.followup.send(
                    f"You don't have enough actions! You have {remaining_actions} actions."
                )
                return

            # Get user's birds and check for swooping bonuses
            birds = await db.get_player_birds(user_id)
            bonus_damage = await get_swooping_bonus(user_id, birds)

            spawner = HumanSpawner()
            human = spawner.spawn_human()

            # Check if human is already defeated
            if human["resilience"] <= 0:
                await interaction.followup.send("There are no humans to swoop at right now! The current human has already been defeated.")
                return

            damage = amount + bonus_damage
            was_defeated = spawner.damage_human(damage)
            await record_actions(user_id, amount, "swoop")

            if not was_defeated:
                # Get updated human state after damage
                updated_state = spawner._get_current_state()
                updated_human = updated_state['current_human']
                message = [f"\U0001F985 You swoop at the {human['name']}! \U0001F985"]
                if bonus_damage > 0:
                    message.append(f"\u2728 Your birds' special abilities add **+{bonus_damage}** damage! \u2728")
                message.append(f"They still have **{updated_human['resilience']}/{updated_human['max_resilience']}** resilience left.")

                actions_left = await get_remaining_actions(user_id)
                message.append(f"\n\u26A1 You have **{actions_left}** {'action' if actions_left == 1 else 'actions'} remaining")
                await interaction.followup.send("\n".join(message))
            else:
                blessing_name, blessing_amount = await self._apply_blessing()
                victory_gif_path = self.defeat_gifs.get(human['name'])
                message = [
                    f"\U0001F389 **VICTORY!** \U0001F389",
                    f"The {human['name']} has been driven away! \U0001F3C3\u200D\u2642\uFE0F\U0001F4A8"
                ]
                if bonus_damage > 0:
                    message.append(f"\u2728 Your birds' special abilities added **+{bonus_damage}** damage to the final blow! \u2728")
                message.append(f"\U0001F64F The bird gods are pleased and grant everyone: **{blessing_name}** (**{blessing_amount}**)")

                actions_left = await get_remaining_actions(user_id)
                message.append(f"\n\u26A1 You have **{actions_left}** {'action' if actions_left == 1 else 'actions'} remaining")

                if victory_gif_path and os.path.exists(victory_gif_path):
                    await interaction.followup.send("\n".join(message), file=File(victory_gif_path))
                else:
                    await interaction.followup.send("\n".join(message))

        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            print(f"Error in swoop command: {str(e)}\n{error_traceback}")
            await interaction.followup.send(f"Sorry, something went wrong while processing your swoop: `{str(e)}`. Check console for full traceback.")

    @app_commands.command(
        name="current_human",
        description="Check the current human intruder's status"
    )
    async def check_human(self, interaction):
        spawner = HumanSpawner()
        human = spawner.spawn_human()
        await interaction.response.send_message(
            f"Current intruder: {human['name']}\n"
            f"Resilience: {human['resilience']}/{human['max_resilience']}\n"
            f"{human['description']}"
        )

async def setup(bot):
    await bot.add_cog(Swooping(bot))
