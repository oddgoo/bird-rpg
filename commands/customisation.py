from discord.ext import commands
from discord import app_commands
import discord

from data.storage import load_data, save_data
from data.models import get_personal_nest
from utils.logging import log_debug

class CustomisationCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='rename_nest', description='Rename your personal nest')
    @app_commands.describe(new_name='The new name for your nest (max 256 characters)')
    async def rename_nest(self, interaction: discord.Interaction, new_name: str):
        """Rename your personal nest"""
        log_debug(f"rename_nest called by {interaction.user.id} with name: {new_name}")
        
        # Input validation
        if len(new_name) > 256:
            await interaction.response.send_message("❌ Nest name must be 256 characters or less!")
            return
            
        if len(new_name) < 1:
            await interaction.response.send_message("❌ Please provide a name for your nest!")
            return

        data = load_data()
        nest = get_personal_nest(data, interaction.user.id)
        
        # Store the old name for the confirmation message
        old_name = nest.get("name", "Some Bird's Nest")
        
        # Update the nest name
        nest["name"] = new_name
        save_data(data)
        
        await interaction.response.send_message(f"🪹 Renamed your nest from \"{old_name}\" to \"{new_name}\"!")

async def setup(bot):
    await bot.add_cog(CustomisationCommands(bot))
