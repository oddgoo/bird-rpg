import json
import os
from datetime import datetime
from discord.ext import commands
from discord import app_commands
import discord

import data.storage as db
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

        user_id = interaction.user.id
        player = await db.load_player(user_id)
        today = get_current_date()

        # Check if user already posted today
        memoirs = await db.get_player_memoirs(user_id)
        for memoir in memoirs:
            if memoir["date"] == today:
                await interaction.response.send_message("You have already shared a memoir today. Return tomorrow to share more of your story!")
                return

        # Add memoir
        nest_name = player.get("nest_name", "Unknown Nest")
        await db.add_memoir(user_id, nest_name, text, today)

        # Add inspiration
        await db.increment_player_field(user_id, "inspiration", 1)

        await interaction.response.send_message(f"Your memoir has been added to the Wings of Time:\n✨ {text} ✨\n\n(+1 Inspiration)\nView all memoirs at: https://bird-rpg.onrender.com/wings-of-time")

async def setup(bot):
    await bot.add_cog(LoreCommands(bot))
    log_debug("LoreCommands cog has been added.")
