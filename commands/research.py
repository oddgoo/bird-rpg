from discord.ext import commands
from discord import app_commands
import discord
import aiohttp
import urllib.parse

from data.storage import load_data, save_data
from data.models import get_personal_nest, load_bird_species
from utils.logging import log_debug

class ResearchCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @app_commands.command(name='graduate_bird', description='Release a bird from your nest')
    @app_commands.describe(bird_name='Common or scientific name of the bird to release')
    async def graduate_bird(self, interaction: discord.Interaction, bird_name: str):
        """Release a bird from your nest and add it to the released birds collection"""
        log_debug(f"graduate_bird called by {interaction.user.id} for bird: {bird_name}")
        
        # Defer the response since this might take a while
        await interaction.response.defer()
        
        data = load_data()
        nest = get_personal_nest(data, interaction.user.id)
        
        # Check if chicks array exists
        if "chicks" not in nest or not nest["chicks"]:
            await interaction.followup.send("You don't have any birds in your nest to release.", ephemeral=True)
            return
            
        # Find the bird in the user's nest
        bird_to_release = None
        bird_index = -1
        
        for i, bird in enumerate(nest["chicks"]):
            if bird["commonName"].lower() == bird_name.lower() or bird["scientificName"].lower() == bird_name.lower():
                bird_to_release = bird
                bird_index = i
                break
                
        if bird_to_release is None:
            await interaction.followup.send(f"You don't have a bird named '{bird_name}' in your nest. Please check the name and try again.", ephemeral=True)
            return
            
        # Remove the bird from the user's nest
        removed_bird = nest["chicks"].pop(bird_index)
        
        # Initialize released_birds array if it doesn't exist
        if "released_birds" not in data:
            data["released_birds"] = []
            
        # Check if the bird already exists in released_birds
        found = False
        for released_bird in data["released_birds"]:
            if released_bird["scientificName"] == removed_bird["scientificName"]:
                released_bird["count"] += 1
                found = True
                break
                
        # If not found, add it to released_birds
        if not found:
            data["released_birds"].append({
                "scientificName": removed_bird["scientificName"],
                "commonName": removed_bird["commonName"],
                "count": 1
            })
            
        # Save data
        save_data(data)
        
        # Fetch image and create embed
        image_url = await self.fetch_bird_image(removed_bird['scientificName'])
        embed = discord.Embed(
            title="🕊️ Bird Graduated!",
            description=f" **{removed_bird['commonName']}** (*{removed_bird['scientificName']}*) has graduated from your nest!",
            color=discord.Color.blue()
        )
        
        if image_url:
            embed.set_image(url=image_url)
            
        embed.add_field(
            name="Research",
            value="It is doing something that it not yet fully understood.",
            inline=False
        )
        
        embed.add_field(
            name="Birds Remaining",
            value=f"You now have {len(nest['chicks'])} {'bird' if len(nest['chicks']) == 1 else 'birds'} in your nest.",
            inline=False
        )
        
        embed.add_field(
            name="View Nest",
            value=f"[Click Here](https://bird-rpg.onrender.com/user/{interaction.user.id})",
            inline=False
        )
        
        await interaction.followup.send(embed=embed)
        
    async def fetch_bird_image(self, scientific_name):
        """Fetches the bird image URL."""
        # Check if this is a special bird
        bird_species = load_bird_species()
        for bird in bird_species:
            if bird["scientificName"] == scientific_name and bird.get("rarity") == "Special":
                # For special birds, return the local image path
                return f"/static/images/special-birds/{scientific_name}.png"
                
        # For regular birds and manifested birds, check the species_images directory
        image_url = f"/species_images/{urllib.parse.quote(scientific_name)}.jpg"
        return image_url

async def setup(bot):
    await bot.add_cog(ResearchCommands(bot))
