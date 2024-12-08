from datetime import datetime
from discord.ext import commands

from data.storage import load_data
from data.models import (
    get_personal_nest, get_common_nest, get_remaining_actions,
    has_been_sung_to, get_singers_today,
    get_discovered_species_count, get_total_bird_species, get_total_chicks
)
from utils.logging import log_debug
from utils.time_utils import get_time_until_reset, get_current_date
from config.config import DEBUG


class InfoCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='nests')
    async def show_nests(self, ctx):
        log_debug(f"nests command called by {ctx.author.id}")
        data = load_data()
        
        # Get nest info
        personal_nest = get_personal_nest(data, ctx.author.id)
        common_nest = get_common_nest(data)
        remaining_actions = get_remaining_actions(data, ctx.author.id)
        
        # Get total actions available
        today = today = get_current_date()
        actions_data = data["daily_actions"].get(str(ctx.author.id), {}).get(f"actions_{today}", {"used": 0, "bonus": 0})
        if isinstance(actions_data, (int, float)):
            actions_data = {"used": actions_data, "bonus": 0}
        chick_bonus = get_total_chicks(personal_nest)
        total_actions = 3 + actions_data["bonus"] + chick_bonus
        
        # Get community discovered species
        total_bird_species = get_total_bird_species(data)
        discovered_species_count = get_discovered_species_count(data)
        
        # Create status message
        status = "**🏠 Your Nest:**\n"
        status += f"```\nTwigs: {personal_nest['twigs']} 🪹 | Seeds: {personal_nest['seeds']} 🌰 \n"
        status += f"Chicks: {get_total_chicks(personal_nest)} 🐦\n"
        if personal_nest['egg']:
            status += f"Egg Progress: {personal_nest['egg']['brooding_progress']}/10 🥚\n"
        else:
            status += f"No Egg 🥚\n"
        status += f"Remaining actions: {remaining_actions}/{total_actions}\n```\n"
        
        status += f"**🪹 View Your Nest:** https://bird-rpg.onrender.com/user/{ctx.author.id}\n"
        status += "**🌇 Common Nest Status:** https://bird-rpg.onrender.com/\n\n"
        
        # Add community discovered species tally
        status += f"**🦜 Community Discovered Species:** {discovered_species_count} / {total_bird_species}\n"
    
        # Add song information
        singers = get_singers_today(data, ctx.author.id)
        if singers:
            singer_count = len(singers)
            status += f"Inspired by {singer_count} {'song' if singer_count == 1 else 'songs'} today! 🎵\n"
        
        status += f"\nTime until reset: {get_time_until_reset()} 🕒"
        
        await ctx.send(status)

    @commands.command(name='nest_help', aliases=['help'])
    async def help_command(self, ctx):
        help_text = "**🪹 Bird RPG Help**\n"
        help_text += "Visit the help page for a complete guide to all commands and game mechanics:\n"
        help_text += "https://bird-rpg.onrender.com/help\n\n"
        
        await ctx.send(help_text)

async def setup(bot):
    await bot.add_cog(InfoCommands(bot))