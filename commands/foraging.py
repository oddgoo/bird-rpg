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

    @app_commands.command(name='forage', description='Forage for treasures in different locations')
    @app_commands.describe(location='The location to forage in', actions='Number of actions to invest (more=faster)')
    async def forage(self, interaction: discord.Interaction, location: str, actions: int):
        """Forage for treasures in different locations"""
        log_debug(f"forage called by {interaction.user.id} in {location} with {actions} actions")

        # Validate actions
        if actions <= 0:
            await interaction.response.send_message("You must invest at least 1 action to find a treasure! 🗺️", ephemeral=True)
            return

        # Load data and check remaining actions
        data = load_data()
        remaining_actions = get_remaining_actions(data, interaction.user.id)

        if remaining_actions < actions:
            await interaction.response.send_message(
                f"You don't have enough actions! You need {actions} but only have {remaining_actions} remaining. 🌙",
                ephemeral=True
            )
            return

        # Load treasures and validate location
        treasures_data = load_treasures()
        if location.lower() not in treasures_data:
            await interaction.response.send_message(f"Invalid location! Please choose from: {', '.join(treasures_data.keys())}", ephemeral=True)
            return

        # Record actions used
        record_actions(data, interaction.user.id, 1, "forage")
        save_data(data)

        # Calculate foraging time (logarithmic scale)
        # 30 actions = 1 hour (3600s), 500 actions = 1 second
        # Using a formula: time = a * exp(-b * actions)
        # We can solve for a and b with the two points
        # 3600 = a * exp(-b * 30)
        # 1 = a * exp(-b * 500)
        # From the second eq: a = exp(b * 500)
        # Substitute into first: 3600 = exp(b * 500) * exp(-b * 30) = exp(470b)
        # ln(3600) = 470b => b = ln(3600) / 470
        b = math.log(3600) / 470
        # a = exp(500 * b)
        a = math.exp(500 * b)
        
        foraging_time = a * math.exp(-b * actions)
        foraging_time = max(1, foraging_time) # Ensure at least 1 second

        await interaction.response.send_message(f"You started foraging in the {location} with {actions} actions. It will take approximately {int(foraging_time)} seconds... 🕰️")

        # Wait for the foraging to complete
        await asyncio.sleep(foraging_time)

        # Select a treasure
        location_treasures = treasures_data[location.lower()]
        treasures = [item for item in location_treasures]
        weights = [item["rarityWeight"] for item in location_treasures]
        
        found_treasure = random.choices(treasures, weights=weights, k=1)[0]

        # Add treasure to the nest
        nest = get_personal_nest(data, interaction.user.id)
        nest["treasures"].append(found_treasure["id"])
        save_data(data)

        # Announce the result
        embed = discord.Embed(
            title="🎉 Treasure Found! 🎉",
            description=f"You found a **{found_treasure['name']}**!",
            color=discord.Color.gold()
        )
        embed.add_field(name="Location", value=location.capitalize(), inline=True)
        embed.add_field(name="Rarity", value=found_treasure['rarity'].capitalize(), inline=True)
        embed.add_field(name="Type", value=found_treasure['type'].capitalize(), inline=True)
        
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(ForagingCommands(bot))
