from discord.ext import commands
from discord import app_commands
import discord
import asyncio
import json
import random
import math
import os

from data.storage import load_data, save_data
from data.models import get_personal_nest, get_remaining_actions, record_actions
from utils.logging import log_debug

def load_treasures():
    """Load treasures from the JSON file"""
    file_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'treasures.json')
    with open(file_path, 'r') as file:
        return json.load(file)

class ForagingCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_foraging_tasks = {}

    @app_commands.command(name='forage', description='Forage for treasures in different locations')
    @app_commands.describe(actions='Number of actions to invest (more=faster)')
    async def forage(self, interaction: discord.Interaction, actions: int):
        """Forage for treasures in different locations"""
        user_id = interaction.user.id
        log_debug(f"forage called by {user_id} with {actions} actions")

        if user_id in self.active_foraging_tasks:
            await interaction.response.send_message("You are already foraging! Use `/cancel_forage` if you want to stop.", ephemeral=True)
            return

        # Validate actions
        if actions <= 0:
            await interaction.response.send_message("You must invest at least 1 action to find a treasure! 🗺️", ephemeral=True)
            return

        # Load data and check remaining actions
        data = load_data()
        remaining_actions = get_remaining_actions(data, user_id)

        if remaining_actions < actions:
            await interaction.response.send_message(
                f"You don't have enough actions! You need {actions} but only have {remaining_actions} remaining. 🌙",
                ephemeral=True
            )
            return

        treasures_data = load_treasures()
        options = [discord.SelectOption(label=loc) for loc in treasures_data.keys()]

        select = discord.ui.Select(placeholder="Choose a location to forage in...", options=options)

        async def select_callback(select_interaction: discord.Interaction):
            if select_interaction.user.id != interaction.user.id:
                await select_interaction.response.send_message("This is not your foraging session!", ephemeral=True)
                return

            location = select.values[0]
            
            # Record actions used
            record_actions(data, user_id, 1, "forage")
            save_data(data)

            # Calculate foraging time
            b = math.log(3600) / 470
            a = math.exp(500 * b)
            foraging_time = a * math.exp(-b * actions)
            foraging_time = max(1, foraging_time)

            await select_interaction.response.edit_message(content=f"You started foraging in the {location.capitalize()} with {actions} actions. It will take approximately {int(foraging_time)} seconds... 🕰️", view=None)

            task = asyncio.create_task(self.forage_task(interaction, location, actions, foraging_time))
            self.active_foraging_tasks[user_id] = {"task": task, "actions": actions}

        select.callback = select_callback
        view = discord.ui.View()
        view.add_item(select)
        await interaction.response.send_message("Where would you like to forage?", view=view, ephemeral=True)


    async def forage_task(self, interaction, location, actions, foraging_time):
        user = interaction.user
        channel = interaction.channel
        try:
            await asyncio.sleep(foraging_time)

            data = load_data()
            treasures_data = load_treasures()
            location_treasures = treasures_data[location]
            treasures = [item for item in location_treasures]
            weights = [item["rarityWeight"] for item in location_treasures]
            
            found_treasure = random.choices(treasures, weights=weights, k=1)[0]

            nest = get_personal_nest(data, interaction.user.id)
            nest["treasures"].append(found_treasure["id"])
            save_data(data)

            embed = discord.Embed(
                title="🎉 Treasure Found! 🎉",
                description=f"You found a **{found_treasure['name']}**!",
                color=discord.Color.gold()
            )
            embed.add_field(name="Location", value=location.capitalize(), inline=True)
            embed.add_field(name="Rarity", value=found_treasure['rarity'].capitalize(), inline=True)
            embed.add_field(name="Type", value=found_treasure['type'].capitalize(), inline=True)

            treasure_id = found_treasure["id"]
            image_path = f"static/images/decorations/{treasure_id}.png"
            if os.path.exists(image_path):
                file = discord.File(image_path, filename=f"{treasure_id}.png")
                embed.set_image(url=f"attachment://{treasure_id}.png")
                await channel.send(content=user.mention, embed=embed, file=file)
            else:
                log_debug(f"Image not found for treasure: {treasure_id}")
                await channel.send(content=user.mention, embed=embed)
        except asyncio.CancelledError:
            await channel.send(f"Foraging cancelled for {user.mention}.")
        finally:
            if interaction.user.id in self.active_foraging_tasks:
                del self.active_foraging_tasks[interaction.user.id]

    @app_commands.command(name='cancel_forage', description='Cancel your ongoing foraging action')
    async def cancel_forage(self, interaction: discord.Interaction):
        """Cancel your ongoing foraging action"""
        user_id = interaction.user.id
        if user_id not in self.active_foraging_tasks:
            await interaction.response.send_message("You are not currently foraging.", ephemeral=True)
            return

        task_info = self.active_foraging_tasks[user_id]
        task_info["task"].cancel()
        
        # Refund actions
        data = load_data()
        nest = get_personal_nest(data, user_id)
        nest["bonus_actions"] += task_info["actions"]
        save_data(data)

        del self.active_foraging_tasks[user_id]
        await interaction.response.send_message(f"Foraging cancelled. {task_info['actions']} actions have been refunded.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(ForagingCommands(bot))
