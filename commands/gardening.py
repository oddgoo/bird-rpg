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
import data.storage as db
from data.models import load_plant_species, get_extra_garden_space, can_afford_plant, has_garden_space, calc_compost_refund
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

        user_id = interaction.user.id
        player = await db.load_player(user_id)

        # Load plant species data (including manifested plants)
        plant_species = await load_plant_species()

        # Find the plant by name (common or scientific)
        plant = None
        for p in plant_species:
            if p["commonName"].lower() == plant_name.lower() or p["scientificName"].lower() == plant_name.lower():
                plant = p
                break

        if not plant:
            await interaction.followup.send(
                f"Plant '{plant_name}' not found. Please check the name and try again.",
                ephemeral=True
            )
            return

        # Check if user has enough resources
        if player["seeds"] < plant["seedCost"]:
            await interaction.followup.send(
                f"You need {plant['seedCost']} seeds to plant this {plant['commonName']}. You only have {player['seeds']} seeds. 🌰",
                ephemeral=True
            )
            return

        if player.get("inspiration", 0) < plant["inspirationCost"]:
            await interaction.followup.send(
                f"You need {plant['inspirationCost']} inspiration to plant this {plant['commonName']}. You only have {player.get('inspiration', 0)} inspiration. 💡",
                ephemeral=True
            )
            return

        # Calculate total garden space used by existing plants
        existing_plants = await db.get_player_plants(user_id)
        total_space_used = 0
        for existing_plant in existing_plants:
            # Find the plant species data for each planted plant
            plant_found = False
            for species in plant_species:
                if species["commonName"] == existing_plant["common_name"]:
                    total_space_used += species["sizeCost"]
                    plant_found = True
                    break

            if not plant_found:
                # Default to 1 if plant data not found
                total_space_used += 1

        garden_size = player.get("garden_size", 0)
        space_remaining = garden_size - total_space_used

        # Check if there's enough space for the new plant
        if space_remaining < plant["sizeCost"]:
            await interaction.followup.send(
                f"You need {plant['sizeCost']} garden space for this {plant['commonName']}. You only have {space_remaining} space remaining out of {garden_size} total garden size. 🌱",
                ephemeral=True
            )
            return

        # Consume resources
        await db.increment_player_field(user_id, "seeds", -plant["seedCost"])
        await db.increment_player_field(user_id, "inspiration", -plant["inspirationCost"])

        # Add plant to garden
        await db.add_plant(user_id, plant["commonName"], plant["scientificName"], get_current_date())

        # Calculate new space remaining after planting
        space_remaining = space_remaining - plant["sizeCost"]

        # Re-read player for updated resource values
        player = await db.load_player(user_id)

        # Send success response
        await self.send_planting_response(interaction, plant, player, space_remaining)

    async def send_planting_response(self, interaction, plant, player, space_remaining):
        """Send a response for successful planting"""
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
            value=f"Seeds: {player['seeds']}\nInspiration: {player['inspiration']}\nGarden Space: {space_remaining}/{player['garden_size']} remaining",
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

    @app_commands.command(name='plant_compost', description='Give back a plant for 80% of its cost')
    @app_commands.describe(plant_name='Common or scientific name of the plant you want to compost')
    async def plant_compost(self, interaction: discord.Interaction, plant_name: str):
        """Give back a plant for 80% of its cost"""
        log_debug(f"plant_compost called by {interaction.user.id} for plant: {plant_name}")

        # Defer the response since this might take a while
        await interaction.response.defer()

        user_id = interaction.user.id
        existing_plants = await db.get_player_plants(user_id)

        # Check if plants exist
        if not existing_plants:
            await interaction.followup.send("You don't have any plants in your garden to compost.", ephemeral=True)
            return

        # Find the plant in user's garden
        plant_to_compost = None
        for p in existing_plants:
            if p["common_name"].lower() == plant_name.lower() or p["scientific_name"].lower() == plant_name.lower():
                plant_to_compost = p
                break

        if plant_to_compost is None:
            await interaction.followup.send(
                f"You don't have a plant named '{plant_name}' in your garden. Please check the name and try again.",
                ephemeral=True
            )
            return

        # Load plant species data (including manifested plants)
        plant_species = await load_plant_species()

        # Find the plant species data
        plant_data = None
        for p in plant_species:
            if p["commonName"].lower() == plant_to_compost["common_name"].lower() or p["scientificName"].lower() == plant_to_compost["scientific_name"].lower():
                plant_data = p
                break

        if not plant_data:
            await interaction.followup.send(
                f"Error: Could not find data for plant '{plant_name}'.",
                ephemeral=True
            )
            return

        # Calculate refund (80% of original cost)
        seed_refund = int(plant_data["seedCost"] * 0.8)
        inspiration_refund = int(plant_data["inspirationCost"] * 0.8)

        # Remove plant from garden
        await db.remove_plant_by_name(user_id, plant_to_compost["common_name"])

        # Add refund to user's resources
        await db.increment_player_field(user_id, "seeds", seed_refund)
        await db.increment_player_field(user_id, "inspiration", inspiration_refund)

        # Re-read player for updated resource values
        player = await db.load_player(user_id)

        # Calculate garden space remaining after composting
        remaining_plants = await db.get_player_plants(user_id)
        total_space_used = 0
        for existing_plant in remaining_plants:
            plant_found = False
            for species in plant_species:
                if species["commonName"] == existing_plant["common_name"]:
                    total_space_used += species["sizeCost"]
                    plant_found = True
                    break

            if not plant_found:
                total_space_used += 1

        garden_size = player.get("garden_size", 0)
        space_remaining = garden_size - total_space_used

        # Send success response
        await self.send_composting_response(interaction, plant_to_compost, plant_data, seed_refund, inspiration_refund, player, space_remaining)

    async def send_composting_response(self, interaction, removed_plant, plant_data, seed_refund, inspiration_refund, player, space_remaining):
        """Send a response for successful composting"""
        embed = discord.Embed(
            title="🧺 Plant Composted",
            description=f"You've composted your **{removed_plant['common_name']}** (*{removed_plant['scientific_name']}*) and received a partial refund.",
            color=discord.Color.gold()
        )

        embed.add_field(
            name="Refund Received",
            value=f"Seeds: +{seed_refund} (80% of {plant_data['seedCost']})\nInspiration: +{inspiration_refund} (80% of {plant_data['inspirationCost']})",
            inline=False
        )

        embed.add_field(
            name="Resources Remaining",
            value=f"Seeds: {player['seeds']}\nInspiration: {player['inspiration']}\nGarden Space: {space_remaining}/{player['garden_size']} remaining",
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
