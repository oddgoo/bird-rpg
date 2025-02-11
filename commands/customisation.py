from discord.ext import commands
from discord import app_commands
import discord

from data.storage import load_data, save_data
from data.models import get_personal_nest, load_bird_species, get_discovered_species
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

    @app_commands.command(name='feature_bird', description='Set a bird to be featured in your nest display')
    @app_commands.describe(bird_name='The scientific or common name of the bird to feature')
    async def feature_bird(self, interaction: discord.Interaction, bird_name: str):
        """Set a bird to be featured in your nest display"""
        log_debug(f"feature_bird called by {interaction.user.id} with bird: {bird_name}")
        
        # Load data and get user's nest
        data = load_data()
        nest = get_personal_nest(data, interaction.user.id)
        chicks = nest.get("chicks", [])
        
        # Find the bird in user's hatched birds
        target_bird = None
        for chick in chicks:
            if bird_name.lower() in [chick['scientificName'].lower(), chick['commonName'].lower()]:
                target_bird = chick
                break
                
        if not target_bird:
            await interaction.response.send_message("❌ Bird not found in your hatched birds! You can only feature birds you have hatched.")
            return
            
        # Update featured bird
        nest["featured_bird"] = target_bird
        save_data(data)
        
        await interaction.response.send_message(f"✨ Your nest now features the {target_bird['commonName']} ({target_bird['scientificName']})!")

async def setup(bot):
    await bot.add_cog(CustomisationCommands(bot))
