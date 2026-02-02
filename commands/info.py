from datetime import datetime
from discord.ext import commands
from discord import app_commands
import discord

import data.storage as db
from data.models import (
    get_remaining_actions, get_discovered_species_count,
    get_total_bird_species
)
from utils.logging import log_debug
from utils.time_utils import get_time_until_reset, get_current_date
from config.config import DEBUG
from constants import BASE_DAILY_ACTIONS


class InfoCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='nests', description='Show information about your nest')
    async def show_nests(self, interaction: discord.Interaction):
        log_debug(f"nests command called by {interaction.user.id}")
        user_id = str(interaction.user.id)

        # Get nest info from DB
        player = await db.load_player(user_id)
        birds = await db.get_player_birds(user_id)
        egg = await db.get_egg(user_id)
        common_nest = await db.load_common_nest()
        remaining_actions = await get_remaining_actions(user_id)

        # Get total actions available
        chick_bonus = len(birds)
        persistent_bonus = player.get("bonus_actions", 0) or 0
        total_actions = BASE_DAILY_ACTIONS + persistent_bonus + chick_bonus

        # Get community discovered species
        total_bird_species = await get_total_bird_species()
        discovered_species_count = await get_discovered_species_count()

        # Create status message
        status = "**🏠 Your Nest:**\n"
        status += f"```\nTwigs: {player['twigs']} 🪹 | Seeds: {player['seeds']} 🌰 \n"
        status += f"Inspiration: {player.get('inspiration', 0)} ✨ | Garden Size: {player.get('garden_size', 0)} 🌱\n"
        status += f"Chicks: {len(birds)} 🐦\n"
        if egg:
            status += f"Egg Progress: {egg['brooding_progress']}/10 🥚\n"
        else:
            status += f"No Egg 🥚\n"
        status += f"Remaining actions: {remaining_actions}/{total_actions}\n```\n"

        status += f"**🪹 View Your Nest:** https://bird-rpg.onrender.com/user/{interaction.user.id}\n"
        status += "**🌇 Community status:** https://bird-rpg.onrender.com/\n\n"

        # Add song information
        today = get_current_date()
        singers = await db.get_singers_today(user_id, today)
        if singers:
            singer_count = len(singers)
            status += f"Inspired by {singer_count} {'song' if singer_count == 1 else 'songs'} today! 🎵\n"

        status += f"\nTime until reset: {get_time_until_reset()} 🕒"

        await interaction.response.send_message(status)

    @app_commands.command(name='help', description='Show help information')
    async def help_command(self, interaction: discord.Interaction):
        help_text = "**🪹 Bird RPG Help**\n"
        help_text += "Visit the help page for a complete guide to all commands and game mechanics:\n"
        help_text += "https://bird-rpg.onrender.com/help\n\n"

        await interaction.response.send_message(help_text)

async def setup(bot):
    await bot.add_cog(InfoCommands(bot))
