from discord.ext import commands
from discord import app_commands
import discord
from datetime import datetime
import aiohttp
import random
import urllib.parse
import os
import json

from config.config import SPECIES_IMAGES_DIR
from data.storage import load_data, save_data, load_manifested_plants
from data.models import (
    get_personal_nest, get_remaining_actions, record_actions
)
from utils.logging import log_debug
from utils.time_utils import get_time_until_reset, get_current_date

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
        # Load plant species data (including manifested plants)
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
            plant_found = False
            # Check in main plant species
            for species in plant_species:
                if species["commonName"] == existing_plant["commonName"]:
                    total_space_used += species["sizeCost"]
                    plant_found = True
                    break
            
            if not plant_found:
                # Default to 1 if plant data not found
                total_space_used += 1
        
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
        
        # Fetch image path and create embed
        image_path = self.get_plant_image_path(plant['scientificName'])
        embed = discord.Embed(
            title="🌱 New Plant Adopted!",
            description=f"You've planted a **{plant['commonName']}** (*{plant['scientificName']}*) in your garden!",
            color=discord.Color.green()
        )
        
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
        
        # Handle image attachment if it exists
        if os.path.exists(image_path):
            # Create a safe filename for the attachment
            filename = f"{urllib.parse.quote(plant['scientificName'])}.jpg"
                
            # Create the file attachment
            file = discord.File(image_path, filename=filename)
            embed.set_image(url=f"attachment://{filename}")
            
            await interaction.followup.send(file=file, embed=embed)
        else:
            # If image doesn't exist, send embed without image
            await interaction.followup.send(embed=embed)
        
    def get_plant_image_path(self, scientific_name):
        """Get the plant image file path from the species_images directory"""
        # All images are stored in the species_images directory
        return os.path.join(SPECIES_IMAGES_DIR, f"{urllib.parse.quote(scientific_name)}.jpg")
        
    def load_plant_species(self):
        """Load plant species from the JSON file and include manifested plants"""
        # Use the updated function from data/models.py
        from data.models import load_plant_species as models_load_plant_species
        return models_load_plant_species()
        
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
        # Load plant species data (including manifested plants)
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
            if p["commonName"].lower() == plant_to_compost["commonName"].lower() or p["scientificName"].lower() == plant_to_compost["scientificName"].lower():
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
