from discord.ext import commands
from discord import app_commands
import discord
import aiohttp
import json
import os
import urllib.parse
import random

import data.storage as db
from data.models import get_remaining_actions, record_actions
from data.manifest_constants import get_points_needed
from utils.logging import log_debug
from config.config import SPECIES_IMAGES_DIR

class ManifestCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def find_bird_by_name(self, name, manifested_birds):
        """Find a bird in the manifested birds list by scientific or common name"""
        for bird in manifested_birds:
            if (bird["scientificName"].lower() == name.lower() or
                bird["commonName"].lower() == name.lower()):
                return bird
        return None

    def find_plant_by_name(self, name, manifested_plants):
        """Find a plant in the manifested plants list by scientific or common name"""
        for plant in manifested_plants:
            if (plant["scientificName"].lower() == name.lower() or
                plant["commonName"].lower() == name.lower()):
                return plant
        return None

    @app_commands.command(name='manifest_bird', description='Manifest a bird species by its scientific name or common name')
    @app_commands.describe(
        name='Scientific name or common name of the bird to manifest',
        actions='Number of actions to spend on manifestation'
    )
    async def manifest_bird(
        self,
        interaction: discord.Interaction,
        name: str,
        actions: int
    ):
        """Manifest a bird species by its scientific name or common name"""
        log_debug(f"manifest_bird called by {interaction.user.id} for {name} with {actions} actions")

        # Defer the response since this might take a while
        await interaction.response.defer()

        user_id = str(interaction.user.id)

        # Validate actions
        if actions <= 0:
            await interaction.followup.send("You must spend at least 1 action to manifest a bird! 🐦")
            return

        # Check if user has enough actions
        remaining_actions = await get_remaining_actions(user_id)
        if remaining_actions < actions:
            await interaction.followup.send(
                f"You don't have enough actions! You need {actions} but only have {remaining_actions} remaining. 🌙"
            )
            return

        # Load manifested birds
        manifested_birds = await db.load_manifested_birds()

        # First, fetch from iNaturalist API to get the canonical scientific name
        species_data = await self.fetch_species_data(name)
        if not species_data:
            await interaction.followup.send(f"Species '{name}' might not exist. Please check the name and try again.")
            return

        # Check if it's a bird
        if species_data.get("iconic_taxon_name") != "Aves":
            await interaction.followup.send(f"'{name}' is not a bird! It's classified as {species_data.get('iconic_taxon_name', 'unknown')}.")
            return

        # Get the scientific name from the species data
        scientific_name = species_data.get("name")
        common_name = species_data.get("preferred_common_name", "")

        # Now check if the bird already exists in the manifested birds list using the scientific name
        existing_bird = self.find_bird_by_name(scientific_name, manifested_birds)

        if existing_bird:
            # Bird already exists in our database
            scientific_name = existing_bird["scientificName"]
            common_name = existing_bird["commonName"]

            # Check if it's already fully manifested
            if existing_bird.get("fully_manifested", False):
                await interaction.followup.send(f"'{common_name}' ({scientific_name}) has already been fully manifested!")
                return

            # Use the existing bird data
            bird = existing_bird
        else:
            # Bird doesn't exist in our database, create a new entry

            # Determine rarity based on observations count
            observations_count = species_data.get("observations_count", 0)
            if observations_count > 4000:
                rarity = "common"
            elif observations_count > 1000:
                rarity = "uncommon"
            elif observations_count > 50:
                rarity = "rare"
            else:
                rarity = "mythical"

            # Get effect and rarityWeight from a similar bird
            similar_bird = self.find_similar_bird(rarity)

            # Create new bird entry
            bird = {
                "commonName": common_name,
                "scientificName": scientific_name,
                "rarityWeight": similar_bird.get("rarityWeight", 0),
                "effect": similar_bird.get("effect", ""),
                "rarity": rarity,
                "manifested_points": 0,
                "fully_manifested": False
            }

        # Calculate how many more points are needed to fully manifest
        points_needed = get_points_needed(bird["rarity"])
        points_remaining = max(0, points_needed - bird["manifested_points"])

        # Only use as many actions as needed to fully manifest
        actions_used = min(actions, points_remaining)

        # Add manifestation points
        bird["manifested_points"] += actions_used

        # Check if fully manifested
        is_newly_manifested = False

        if bird["manifested_points"] >= points_needed and not bird.get("fully_manifested", False):
            bird["fully_manifested"] = True
            is_newly_manifested = True

            # Download the image if it's newly manifested
            await self.download_species_image(bird["scientificName"])

        # Save the updated data via upsert
        await db.upsert_manifested_bird(bird)

        # Record only the actions actually used
        await record_actions(user_id, actions_used, "manifest")

        # Create and send response
        if is_newly_manifested:
            await self.send_fully_manifested_response(interaction, bird)
        else:
            # If we used fewer actions than requested, inform the user
            if actions_used < actions:
                await interaction.followup.send(
                    f"You only needed {actions_used} actions to continue manifesting this bird, so the remaining {actions - actions_used} actions were not used."
                )
            await self.send_manifestation_progress_response(interaction, bird, points_needed, actions_used, remaining_actions - actions_used)

    @app_commands.command(name='manifest_plant', description='Manifest a plant species by its scientific name or common name')
    @app_commands.describe(
        name='Scientific name or common name of the plant to manifest',
        actions='Number of actions to spend on manifestation'
    )
    async def manifest_plant(
        self,
        interaction: discord.Interaction,
        name: str,
        actions: int
    ):
        """Manifest a plant species by its scientific name or common name"""
        log_debug(f"manifest_plant called by {interaction.user.id} for {name} with {actions} actions")

        # Defer the response since this might take a while
        await interaction.response.defer()

        user_id = str(interaction.user.id)

        # Validate actions
        if actions <= 0:
            await interaction.followup.send("You must spend at least 1 action to manifest a plant! 🌱")
            return

        # Check if user has enough actions
        remaining_actions = await get_remaining_actions(user_id)
        if remaining_actions < actions:
            await interaction.followup.send(
                f"You don't have enough actions! You need {actions} but only have {remaining_actions} remaining. 🌙"
            )
            return

        # Load manifested plants
        manifested_plants = await db.load_manifested_plants()

        # First, fetch from iNaturalist API to get the canonical scientific name
        species_data = await self.fetch_species_data(name)
        if not species_data:
            await interaction.followup.send(f"Species '{name}' might not exist. Please check the name and try again.")
            return

        # Check if it's a plant
        if species_data.get("iconic_taxon_name") != "Plantae":
            await interaction.followup.send(f"'{name}' is not a plant! It's classified as {species_data.get('iconic_taxon_name', 'unknown')}.")
            return

        # Get the scientific name from the species data
        scientific_name = species_data.get("name")
        common_name = species_data.get("preferred_common_name", "")

        # Now check if the plant already exists in the manifested plants list using the scientific name
        existing_plant = self.find_plant_by_name(scientific_name, manifested_plants)

        if existing_plant:
            # Plant already exists in our database
            scientific_name = existing_plant["scientificName"]
            common_name = existing_plant["commonName"]

            # Check if it's already fully manifested
            if existing_plant.get("fully_manifested", False):
                await interaction.followup.send(f"'{common_name}' ({scientific_name}) has already been fully manifested!")
                return

            # Use the existing plant data
            plant = existing_plant
        else:
            # Plant doesn't exist in our database, create a new entry

            # Determine rarity based on observations count
            observations_count = species_data.get("observations_count", 0)
            if observations_count > 4000:
                rarity = "common"
            elif observations_count > 1000:
                rarity = "uncommon"
            elif observations_count > 50:
                rarity = "rare"
            else:
                rarity = "mythical"

            # Get effect, rarityWeight, and costs from a similar plant
            similar_plant = self.find_similar_plant(rarity)

            # Create new plant entry
            plant = {
                "commonName": common_name,
                "scientificName": scientific_name,
                "rarityWeight": similar_plant.get("rarityWeight", 0),
                "effect": similar_plant.get("effect", ""),
                "rarity": rarity,
                "seedCost": similar_plant.get("seedCost", 30),
                "sizeCost": similar_plant.get("sizeCost", 1),
                "inspirationCost": similar_plant.get("inspirationCost", 0.2),
                "manifested_points": 0,
                "fully_manifested": False
            }

        # Calculate how many more points are needed to fully manifest
        points_needed = get_points_needed(plant["rarity"])
        points_remaining = max(0, points_needed - plant["manifested_points"])

        # Only use as many actions as needed to fully manifest
        actions_used = min(actions, points_remaining)

        # Add manifestation points
        plant["manifested_points"] += actions_used

        # Check if fully manifested
        is_newly_manifested = False

        if plant["manifested_points"] >= points_needed and not plant.get("fully_manifested", False):
            plant["fully_manifested"] = True
            is_newly_manifested = True

            # Download the image if it's newly manifested
            await self.download_species_image(plant["scientificName"])

        # Save the updated data via upsert
        await db.upsert_manifested_plant(plant)

        # Record only the actions actually used
        await record_actions(user_id, actions_used, "manifest")

        # Create and send response
        if is_newly_manifested:
            await self.send_fully_manifested_plant_response(interaction, plant)
        else:
            # If we used fewer actions than requested, inform the user
            if actions_used < actions:
                await interaction.followup.send(
                    f"You only needed {actions_used} actions to continue manifesting this plant, so the remaining {actions - actions_used} actions were not used."
                )
            await self.send_manifestation_progress_response(interaction, plant, points_needed, actions_used, remaining_actions - actions_used, is_plant=True)

    async def fetch_species_data(self, name):
        """Fetch species data from iNaturalist API"""
        # Special case for testing with Southern Cassowary
        if name == "Casuarius casuarius" or name.lower() == "southern cassowary":
            return {
                "name": "Casuarius casuarius",
                "preferred_common_name": "Southern Cassowary",
                "iconic_taxon_name": "Aves",
                "observations_count": 2188
            }

        api_url = f"https://api.inaturalist.org/v1/taxa?q={name}&limit=1"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('results') and len(data['results']) > 0:
                            return data['results'][0]
        except Exception as e:
            log_debug(f"Error fetching data from iNaturalist: {e}")
        return None

    def find_similar_bird(self, rarity):
        """Find a similar bird based on rarity"""
        try:
            # Load bird species
            with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'bird_species.json'), 'r') as f:
                bird_data = json.load(f)
                birds = bird_data.get('bird_species', [])

            # Filter birds by rarity
            similar_birds = [bird for bird in birds if bird.get('rarity', '').lower() == rarity.lower()]

            if similar_birds:
                return random.choice(similar_birds)
            else:
                # Fallback to any bird if no matching rarity
                return random.choice(birds)
        except Exception as e:
            log_debug(f"Error finding similar bird: {e}")
            # Return default values if error
            return {
                "rarityWeight": 1,
                "effect": ""
            }

    def find_similar_plant(self, rarity):
        """Find a similar plant based on rarity"""
        try:
            # Load plant species
            with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'plant_species.json'), 'r') as f:
                plants = json.load(f)

            # Filter plants by rarity
            similar_plants = [plant for plant in plants if plant.get('rarity', '').lower() == rarity.lower()]

            if similar_plants:
                return random.choice(similar_plants)
            else:
                # Fallback to any plant if no matching rarity
                return random.choice(plants)
        except Exception as e:
            log_debug(f"Error finding similar plant: {e}")
            # Return default values if error
            return {
                "rarityWeight": 1,
                "effect": "",
                "seedCost": 30,
                "sizeCost": 1,
                "inspirationCost": 1
            }


    async def download_species_image(self, scientific_name):
        """Download species image from iNaturalist"""
        try:
            # Check if image already exists
            filename = f"{urllib.parse.quote(scientific_name)}.jpg"
            filepath = os.path.join(SPECIES_IMAGES_DIR, filename)

            if os.path.exists(filepath):
                log_debug(f"Image for {scientific_name} already exists, skipping download")
                return True

            # Image doesn't exist, fetch from iNaturalist API
            api_url = f"https://api.inaturalist.org/v1/taxa?q={scientific_name}&limit=1"
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data['results']:
                            taxon = data['results'][0]
                            image_url = taxon.get('default_photo', {}).get('medium_url')

                            if image_url:
                                # Download the image
                                async with session.get(image_url) as img_response:
                                    if img_response.status == 200:
                                        image_data = await img_response.read()
                                        with open(filepath, 'wb') as f:
                                            f.write(image_data)
                                        log_debug(f"Downloaded image for {scientific_name}")
                                        return True

            log_debug(f"Failed to download image for {scientific_name}")
            return False
        except Exception as e:
            log_debug(f"Error downloading species image: {e}")
            return False

    async def send_fully_manifested_response(self, interaction, bird):
        """Send a response for a fully manifested bird"""
        # Create the image path
        image_filename = f"{urllib.parse.quote(bird['scientificName'])}.jpg"
        image_path = os.path.join(SPECIES_IMAGES_DIR, image_filename)

        embed = discord.Embed(
            title="🐦 Bird Fully Manifested! ✨",
            description=f"You have fully manifested **{bird['commonName']}** (*{bird['scientificName']}*)!",
            color=discord.Color.green()
        )

        embed.add_field(
            name="Rarity",
            value=bird['rarity'].capitalize(),
            inline=True
        )

        embed.add_field(
            name="Effect",
            value=bird['effect'] if bird['effect'] else "No special effect",
            inline=True
        )

        embed.add_field(
            name="Next Steps",
            value="This bird can now be hatched from eggs just like other birds in the codex!",
            inline=False
        )

        # Check if the image file exists
        if os.path.exists(image_path):
            # Send the file as an attachment with the embed
            file = discord.File(image_path, filename=f"{bird['scientificName']}.jpg")
            embed.set_image(url=f"attachment://{bird['scientificName']}.jpg")
            await interaction.followup.send(file=file, embed=embed)
        else:
            # If image doesn't exist, send embed without image
            await interaction.followup.send(embed=embed)

    async def send_fully_manifested_plant_response(self, interaction, plant):
        """Send a response for a fully manifested plant"""
        # Create the image path
        image_filename = f"{urllib.parse.quote(plant['scientificName'])}.jpg"
        image_path = os.path.join(SPECIES_IMAGES_DIR, image_filename)

        embed = discord.Embed(
            title="🌱 Plant Fully Manifested! ✨",
            description=f"You have fully manifested **{plant['commonName']}** (*{plant['scientificName']}*)!",
            color=discord.Color.green()
        )

        embed.add_field(
            name="Rarity",
            value=plant['rarity'].capitalize(),
            inline=True
        )

        embed.add_field(
            name="Effect",
            value=plant['effect'] if plant['effect'] else "No special effect",
            inline=True
        )

        embed.add_field(
            name="Costs",
            value=f"Seeds: {plant['seedCost']}\nGarden Size: {plant['sizeCost']}\nInspiration: {plant['inspirationCost']}",
            inline=True
        )

        embed.add_field(
            name="Next Steps",
            value="This plant can now be adopted in your garden just like other plants in the codex!",
            inline=False
        )

        # Check if the image file exists
        if os.path.exists(image_path):
            # Send the file as an attachment with the embed
            file = discord.File(image_path, filename=f"{plant['scientificName']}.jpg")
            embed.set_image(url=f"attachment://{plant['scientificName']}.jpg")
            await interaction.followup.send(file=file, embed=embed)
        else:
            # If image doesn't exist, send embed without image
            await interaction.followup.send(embed=embed)

    async def send_manifestation_progress_response(self, interaction, species, points_needed, actions_spent, actions_remaining, is_plant=False):
        """Send a response for manifestation progress"""
        species_type = "Plant" if is_plant else "Bird"
        emoji = "🌱" if is_plant else "🐦"

        embed = discord.Embed(
            title=f"{emoji} {species_type} Manifestation Progress",
            description=f"You spent {actions_spent} actions manifesting **{species['commonName']}** (*{species['scientificName']}*).",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="Rarity",
            value=species['rarity'].capitalize(),
            inline=True
        )

        # Calculate progress percentage
        progress_percent = min(100, int((species['manifested_points'] / points_needed) * 100))
        progress_bar = self.generate_progress_bar(progress_percent)

        embed.add_field(
            name="Manifestation Progress",
            value=f"{progress_bar} {progress_percent}%\n{species['manifested_points']}/{points_needed} points",
            inline=False
        )

        embed.add_field(
            name="Actions Remaining",
            value=f"You have {actions_remaining} actions remaining today.",
            inline=False
        )

        await interaction.followup.send(embed=embed)

    def generate_progress_bar(self, percent, length=10):
        """Generate a text-based progress bar"""
        filled = int(length * (percent / 100))
        bar = "█" * filled + "░" * (length - filled)
        return bar

async def setup(bot):
    await bot.add_cog(ManifestCommands(bot))
