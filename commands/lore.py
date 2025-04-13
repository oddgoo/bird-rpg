import json
import os
from datetime import datetime
from discord.ext import commands
from discord import app_commands
import discord

from data.storage import load_data, save_data, load_lore, save_lore
from data.models import get_personal_nest
from utils.time_utils import get_current_date
from utils.logging import log_debug

class LoreCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='memoir', description='Add a memoir to the Wings of Time')
    @app_commands.describe(text='Your memoir text (max 256 characters)')
    async def add_memoir(self, interaction: discord.Interaction, text: str):
        log_debug(f"add_memoir called by {interaction.user.id}")
        
        if len(text) > 2048:
            await interaction.response.send_message("Your memoir is too long! Please keep it under 2048 characters.")
            return

        data = load_data()
        nest = get_personal_nest(data, interaction.user.id)
        today = get_current_date()
        
        # Load lore data
        lore_data = load_lore()
        
        # Check if user already posted today
        for memoir in lore_data["memoirs"]:
            if memoir["user_id"] == str(interaction.user.id) and memoir["date"] == today:
                await interaction.response.send_message("You have already shared a memoir today. Return tomorrow to share more of your story!")
                return

        # Add memoir
        new_memoir = {
            "user_id": str(interaction.user.id),
            "nest_name": nest.get("name", "Unknown Nest"),
            "text": text,
            "date": today
        }
        
        lore_data["memoirs"].append(new_memoir)
        save_lore(lore_data)

        # Add garden life
        if "inspiration" not in nest:
            nest["inspiration"] = 0
        nest["inspiration"] += 1
        save_data(data)

        await interaction.response.send_message(f"Your memoir has been added to the Wings of Time:\n✨ {text} ✨\n\n(+1 Inspiration)\nView all memoirs at: https://bird-rpg.onrender.com/wings-of-time")

async def setup(bot):
    await bot.add_cog(LoreCommands(bot))
    log_debug("LoreCommands cog has been added.")
