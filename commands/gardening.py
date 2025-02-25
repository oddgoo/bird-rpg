from discord.ext import commands
from discord import app_commands
import discord
from datetime import datetime
import aiohttp
import random

from data.storage import load_data, save_data
from data.models import (
    get_personal_nest, get_remaining_actions, record_actions
)
from utils.logging import log_debug
from utils.time_utils import get_time_until_reset, get_current_date
import os
import json

class GardeningCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @app_commands.command(name='plant_new', description='Adopt a new plant in your garden')
    @app_commands.describe(plant_name='Common or scientific name of the plant to plant')
    async def plant_new(self, interaction: discord.Interaction, plant_name: str):
        """Adopt a new plant in your garden"""
        log_debug(f"plant_new called by {interaction.user.id} for plant: {plant_name}")
        
        # Defer the response since this might take a while
        await interaction.response.defer()
        
        data = load_data()
        nest = get_personal_nest(data, interaction.user.id)
        
        # Initialize plants array if it doesn't exist
        if "plants" not in nest:
            nest["plants"] = []
            
        # Process the planting
        result, error = await self.process_planting(interaction, plant_name, nest)
        
        if error:
            # Send error message only visible to the user
            await interaction.followup.send(error, ephemeral=True)
            return
            
        # Save data and send success response
        save_data(data)
        await self.send_planting_response(interaction, result)
    
    async def process_planting(self, interaction, plant_name, nest):
        """Process planting a new plant with Discord interaction"""
        # Use the non-async version for the actual logic
        result, error = self.process_planting_logic(plant_name, nest)
        return result, error
        
    def process_planting_logic(self, plant_name, nest):
        """Process planting a new plant - core logic without Discord dependencies"""
        # Load plant species data
        plant_species = self.load_plant_species()
        
        # Find the plant by name (common or scientific)
        plant = None
        for p in plant_species:
            if p["commonName"].lower() == plant_name.lower() or p["scientificName"].lower() == plant_name.lower():
                plant = p
                break
                
        if not plant:
            return None, f"Plant '{plant_name}' not found. Please check the name and try again."
            
        # Check if user has enough resources
        if nest["seeds"] < plant["seedCost"]:
            return None, f"You need {plant['seedCost']} seeds to plant this {plant['commonName']}. You only have {nest['seeds']} seeds. 🌰"
            
        if nest.get("inspiration", 0) < plant["inspirationCost"]:
            return None, f"You need {plant['inspirationCost']} inspiration to plant this {plant['commonName']}. You only have {nest.get('inspiration', 0)} inspiration. 💡"
            
        # Calculate total garden space used by existing plants
        total_space_used = 0
        for existing_plant in nest.get("plants", []):
            # Find the plant species data for each planted plant
            for species in plant_species:
                if species["commonName"] == existing_plant["commonName"]:
                    total_space_used += species["sizeCost"]
                    break
        
        space_remaining = nest.get("garden_size", 0) - total_space_used
        
        # Check if there's enough space for the new plant
        if space_remaining < plant["sizeCost"]:
            return None, f"You need {plant['sizeCost']} garden space for this {plant['commonName']}. You only have {space_remaining} space remaining out of {nest.get('garden_size', 0)} total garden size. 🌱"
            
        # Consume resources
        nest["seeds"] -= plant["seedCost"]
        nest["inspiration"] -= plant["inspirationCost"]
        # Note: garden_size is not reduced as it's a limit, not a consumable resource
        
        # Add plant to nest - only store the common name and planted date
        new_plant = {
            "commonName": plant["commonName"],
            "scientificName": plant["scientificName"],
            "planted_date": get_current_date()
        }
        
        nest["plants"].append(new_plant)
        
        return (plant, nest), None  # Return the full plant data for the response
        
    async def send_planting_response(self, interaction, result):
        """Send a response for successful planting"""
        plant, nest = result
        
        # Fetch image and create embed
        image_url = await self.fetch_plant_image(plant['scientificName'])
        embed = discord.Embed(
            title="🌱 New Plant Adopted!",
            description=f"You've planted a **{plant['commonName']}** (*{plant['scientificName']}*) in your garden!",
            color=discord.Color.green()
        )
        
        if image_url:
            embed.set_image(url=image_url)
            
        embed.add_field(
            name="Effect",
            value=plant['effect'],
            inline=False
        )
        
        embed.add_field(
            name="Resources Remaining",
            value=f"Seeds: {nest['seeds']}\nInspiration: {nest['inspiration']}\nGarden Size: {nest['garden_size']}",
            inline=False
        )
        
        embed.add_field(
            name="View Garden",
            value=f"[Click Here](https://bird-rpg.onrender.com/user/{interaction.user.id})",
            inline=False
        )
        
        await interaction.followup.send(embed=embed)
        
    async def fetch_plant_image(self, scientific_name):
        """Fetches the plant image URL from iNaturalist."""
        api_url = f"https://api.inaturalist.org/v1/taxa?q={scientific_name}&limit=1"
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(api_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data['results']:
                            taxon = data['results'][0]
                            image_url = taxon.get('default_photo', {}).get('medium_url')
                            return image_url
            except Exception as e:
                log_debug(f"Error fetching image from iNaturalist: {e}")
        return None
        
    def load_plant_species(self):
        """Load plant species from the JSON file"""
        file_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'plant_species.json')
        with open(file_path, 'r') as file:
            data = json.load(file)
        return data
        
    @app_commands.command(name='plant_compost', description='Give back a plant for 80% of its cost')
    @app_commands.describe(plant_name='Common or scientific name of the plant you want to compost')
    async def plant_compost(self, interaction: discord.Interaction, plant_name: str):
        """Give back a plant for 80% of its cost"""
        log_debug(f"plant_compost called by {interaction.user.id} for plant: {plant_name}")
        
        # Defer the response since this might take a while
        await interaction.response.defer()
        
        data = load_data()
        nest = get_personal_nest(data, interaction.user.id)
        
        # Check if plants array exists
        if "plants" not in nest or not nest["plants"]:
            await interaction.followup.send("You don't have any plants in your garden to compost.", ephemeral=True)
            return
            
        # Process the composting
        result, error = await self.process_composting(interaction, plant_name, nest)
        
        if error:
            # Send error message only visible to the user
            await interaction.followup.send(error, ephemeral=True)
            return
            
        # Save data and send success response
        save_data(data)
        await self.send_composting_response(interaction, result)
    
    async def process_composting(self, interaction, plant_name, nest):
        """Process composting a plant with Discord interaction"""
        # Use the non-async version for the actual logic
        result, error = self.process_composting_logic(plant_name, nest)
        return result, error
        
    def process_composting_logic(self, plant_name, nest):
        """Process composting a plant - core logic without Discord dependencies"""
        # Load plant species data
        plant_species = self.load_plant_species()
        
        # Find the plant in user's garden
        plant_to_compost = None
        plant_index = -1
        
        for i, p in enumerate(nest["plants"]):
            if p["commonName"].lower() == plant_name.lower() or p["scientificName"].lower() == plant_name.lower():
                plant_to_compost = p
                plant_index = i
                break
                
        if plant_to_compost is None:
            return None, f"You don't have a plant named '{plant_name}' in your garden. Please check the name and try again."
            
        # Find the plant species data
        plant_data = None
        for p in plant_species:
            if p["commonName"].lower() == plant_to_compost["commonName"].lower():
                plant_data = p
                break
                
        if not plant_data:
            return None, f"Error: Could not find data for plant '{plant_name}'."
            
        # Calculate refund (80% of original cost)
        seed_refund = int(plant_data["seedCost"] * 0.8)
        inspiration_refund = int(plant_data["inspirationCost"] * 0.8)
        
        # Add refund to user's resources
        nest["seeds"] += seed_refund
        nest["inspiration"] = nest.get("inspiration", 0) + inspiration_refund
        
        # Remove plant from garden
        removed_plant = nest["plants"].pop(plant_index)
        
        return (removed_plant, plant_data, seed_refund, inspiration_refund, nest), None
        
    async def send_composting_response(self, interaction, result):
        """Send a response for successful composting"""
        removed_plant, plant_data, seed_refund, inspiration_refund, nest = result
        
        embed = discord.Embed(
            title="🧺 Plant Composted",
            description=f"You've composted your **{removed_plant['commonName']}** (*{removed_plant['scientificName']}*) and received a partial refund.",
            color=discord.Color.gold()
        )
        
        embed.add_field(
            name="Refund Received",
            value=f"Seeds: +{seed_refund} (80% of {plant_data['seedCost']})\nInspiration: +{inspiration_refund} (80% of {plant_data['inspirationCost']})",
            inline=False
        )
        
        embed.add_field(
            name="Resources Remaining",
            value=f"Seeds: {nest['seeds']}\nInspiration: {nest['inspiration']}\nGarden Size: {nest['garden_size']}",
            inline=False
        )
        
        embed.add_field(
            name="View Garden",
            value=f"[Click Here](https://bird-rpg.onrender.com/user/{interaction.user.id})",
            inline=False
        )
        
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(GardeningCommands(bot))
