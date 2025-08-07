import json
import random
from datetime import datetime, date
from pathlib import Path
import os

from discord.ext import commands
from discord import app_commands, File

from data.models import (
    get_personal_nest, get_common_nest, get_remaining_actions, 
    record_actions, get_swooping_bonus
)
from utils.checks import has_birds
from config.config import DATA_PATH
from data.storage import load_data, save_data
from utils.human_spawner import HumanSpawner
from utils.blessings import apply_blessing

class Swooping(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.defeat_gifs = {
            "small child": "static/gifs/small_child.gif",
            "average human on a bike": "static/gifs/average_human.gif",
            "bully kid": "static/gifs/bully_kid.gif",
            "a band of grifters": "static/gifs/a-band-of-grifters.gif"
        }

    def _record_defeated_human(self, human, blessing_name, blessing_amount):
        """Record a defeated human in the game data"""
        data = load_data()
        if "defeated_humans" not in data:
            data["defeated_humans"] = []
        
        data["defeated_humans"].append({
            "name": human["name"],
            "max_resilience": human["max_resilience"],
            "date": str(date.today()),
            "blessing": {
                "name": blessing_name,
                "amount": blessing_amount
            }
        })
        save_data(data)

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

        data = load_data()
        if blessing["type"] == "common_seeds":
            common_nest = get_common_nest(data)
            common_nest["seeds"] += amount
        elif blessing["type"] == "common_nest_growth":
            common_nest = get_common_nest(data)
            common_nest["twigs"] += amount
        else:
            nests = {user_id: get_personal_nest(data, user_id) for user_id in data["personal_nests"]}
            updated_nests = apply_blessing(nests, blessing["type"], amount)
            # Update the data with the blessed nests
            for user_id, nest in updated_nests.items():
                data["personal_nests"][user_id].update(nest)

        save_data(data)
        # Record the defeated human
        self._record_defeated_human(current_human, blessing["name"], amount)
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
            data = load_data()
            user_id = str(interaction.user.id)  # Convert to string to match data format
            remaining_actions = get_remaining_actions(data, user_id)
            
            if remaining_actions < amount:
                await interaction.followup.send(
                    f"You don't have enough actions! You have {remaining_actions} actions."
                )
                return

            # Get user's nest and check for swooping bonuses
            user_nest = get_personal_nest(data, user_id)
            bonus_damage = get_swooping_bonus(data, user_nest)

            spawner = HumanSpawner()
            human = spawner.spawn_human()
            
            # Check if human is already defeated
            if human["resilience"] <= 0:
                await interaction.followup.send("There are no humans to swoop at right now! The current human has already been defeated.")
                return
                
            damage = amount + bonus_damage
            was_defeated = spawner.damage_human(damage)
            record_actions(data, user_id, amount, "swoop")
            save_data(data)

            if not was_defeated:
                # Get updated human state after damage
                updated_state = spawner._get_current_state()
                updated_human = updated_state['current_human']
                message = [f"🦅 You swoop at the {human['name']}! 🦅"]
                if bonus_damage > 0:
                    message.append(f"✨ Your birds' special abilities add **+{bonus_damage}** damage! ✨")
                message.append(f"They still have **{updated_human['resilience']}/{updated_human['max_resilience']}** resilience left.")
                
                actions_left = get_remaining_actions(data, user_id)
                message.append(f"\n⚡ You have **{actions_left}** {'action' if actions_left == 1 else 'actions'} remaining")
                await interaction.followup.send("\n".join(message))
            else:
                blessing_name, blessing_amount = await self._apply_blessing()
                victory_gif_path = self.defeat_gifs.get(human['name'])
                message = [
                    f"🎉 **VICTORY!** 🎉",
                    f"The {human['name']} has been driven away! 🏃‍♂️💨"
                ]
                if bonus_damage > 0:
                    message.append(f"✨ Your birds' special abilities added **+{bonus_damage}** damage to the final blow! ✨")
                message.append(f"🙏 The bird gods are pleased and grant everyone: **{blessing_name}** (**{blessing_amount}**)")

                actions_left = get_remaining_actions(data, user_id)
                message.append(f"\n⚡ You have **{actions_left}** {'action' if actions_left == 1 else 'actions'} remaining")

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
