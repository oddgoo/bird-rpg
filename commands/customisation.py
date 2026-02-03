from discord.ext import commands
from discord import app_commands
import discord

import data.storage as db
from utils.logging import log_debug
from commands.foraging import load_treasures

class CustomisationCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='rename_nest', description='Rename your personal nest')
    @app_commands.describe(new_name='The new name for your nest (max 256 characters)')
    async def rename_nest(self, interaction: discord.Interaction, new_name: str):
        """Rename your personal nest"""
        await interaction.response.defer()
        log_debug(f"rename_nest called by {interaction.user.id} with name: {new_name}")

        if len(new_name) > 256:
            await interaction.followup.send("❌ Nest name must be 256 characters or less!")
            return

        if len(new_name) < 1:
            await interaction.followup.send("❌ Please provide a name for your nest!")
            return

        user_id = interaction.user.id
        player = await db.load_player(user_id)

        old_name = player.get("nest_name", "Some Bird's Nest")

        await db.update_player(user_id, nest_name=new_name)

        await interaction.followup.send(f"🪹 Renamed your nest from \"{old_name}\" to \"{new_name}\"!")

    @app_commands.command(name='feature_bird', description='Set a bird to be featured in your nest display')
    @app_commands.describe(bird_name='The scientific or common name of the bird to feature')
    async def feature_bird(self, interaction: discord.Interaction, bird_name: str):
        """Set a bird to be featured in your nest display"""
        await interaction.response.defer()
        log_debug(f"feature_bird called by {interaction.user.id} with bird: {bird_name}")

        user_id = interaction.user.id
        birds = await db.get_player_birds(user_id)

        target_bird = None
        for bird in birds:
            if bird_name.lower() in [bird['scientific_name'].lower(), bird['common_name'].lower()]:
                target_bird = bird
                break

        if not target_bird:
            await interaction.followup.send("❌ Bird not found in your hatched birds! You can only feature birds you have hatched.")
            return

        await db.update_player(user_id,
            featured_bird_common_name=target_bird['common_name'],
            featured_bird_scientific_name=target_bird['scientific_name']
        )

        await interaction.followup.send(f"✨ Your nest now features the {target_bird['common_name']} ({target_bird['scientific_name']})!")

    @app_commands.command(name='decorate_nest', description='Decorate your nest with a treasure')
    @app_commands.describe(treasure_name='The name of the treasure to use', x='The x-position of the sticker (0-100). optional.', y='The y-position of the sticker (0-100). optional')
    async def decorate_nest(self, interaction: discord.Interaction, treasure_name: str, x: app_commands.Range[int, 0, 100]=None, y: app_commands.Range[int, 0, 100]=None):
        await interaction.response.defer(ephemeral=True)
        await self.decoration_handler(interaction, 'nest', treasure_name, x=x, y=y)

    @app_commands.command(name='decorate_bird', description='Decorate a bird with a treasure')
    @app_commands.describe(bird_name='The common or scientific name of the bird', treasure_name='The name of the treasure to use', x='The x-position of the sticker (0-100). optional', y='The y-position of the sticker (0-100). optional')
    async def decorate_bird(self, interaction: discord.Interaction, bird_name: str, treasure_name: str, x: app_commands.Range[int, 0, 100]=None, y: app_commands.Range[int, 0, 100]=None):
        await interaction.response.defer(ephemeral=True)
        await self.decoration_handler(interaction, 'bird', treasure_name, entity_name=bird_name, x=x, y=y)

    @app_commands.command(name='decorate_plant', description='Decorate a plant with a treasure')
    @app_commands.describe(plant_name='The common name of the plant', treasure_name='The name of the treasure to use', x='The x-position of the sticker (0-100). optional', y='The y-position of the sticker (0-100). optional')
    async def decorate_plant(self, interaction: discord.Interaction, plant_name: str, treasure_name: str, x: app_commands.Range[int, 0, 100]=None, y: app_commands.Range[int, 0, 100]=None):
        await interaction.response.defer(ephemeral=True)
        await self.decoration_handler(interaction, 'plant', treasure_name, entity_name=plant_name, x=x, y=y)

    async def decoration_handler(self, interaction: discord.Interaction, entity_type: str, treasure_name: str, entity_name: str = None, x: int = None, y: int = None):
        user_id = interaction.user.id

        player_treasures = await db.get_player_treasures(user_id)

        if not player_treasures:
            await interaction.followup.send("You don't have any treasures to use for decoration!", ephemeral=True)
            return

        treasures_data = load_treasures()
        all_treasures = {t["id"]: t for loc in treasures_data.values() for t in loc}

        # Find the treasure by name in the player's inventory
        found_treasure_id = None
        for t_id in player_treasures:
            if all_treasures.get(t_id, {}).get("name", "").lower() == treasure_name.lower():
                found_treasure_id = t_id
                break

        if not found_treasure_id:
            await interaction.followup.send(f"Treasure '{treasure_name}' not found in your inventory.", ephemeral=True)
            return

        base_treasure = all_treasures.get(found_treasure_id, {})
        dec_x = base_treasure.get('x', 0) if x is None else x
        dec_y = base_treasure.get('y', 0) if y is None else y

        target_name = "your nest"
        if entity_type == 'nest':
            # Remove from inventory and add to nest decorations
            await db.remove_player_treasure(user_id, found_treasure_id)
            await db.add_nest_treasure(user_id, found_treasure_id, dec_x, dec_y)
        else:
            # For bird/plant, find the entity first
            if entity_type == 'bird':
                birds = await db.get_player_birds(user_id)
                target_entity = None
                for bird in birds:
                    if entity_name.lower() in [bird['scientific_name'].lower(), bird['common_name'].lower()]:
                        target_entity = bird
                        break

                if not target_entity:
                    await interaction.followup.send(f"Bird '{entity_name}' not found.", ephemeral=True)
                    return

                # Remove from inventory and add to bird decorations
                await db.remove_player_treasure(user_id, found_treasure_id)
                await db.add_bird_treasure(target_entity['id'], found_treasure_id, dec_x, dec_y)
                target_name = target_entity["common_name"]

            elif entity_type == 'plant':
                plants = await db.get_player_plants(user_id)
                target_entity = None
                for plant in plants:
                    if entity_name.lower() == plant['common_name'].lower():
                        target_entity = plant
                        break

                if not target_entity:
                    await interaction.followup.send(f"Plant '{entity_name}' not found.", ephemeral=True)
                    return

                # Remove from inventory and add to plant decorations
                await db.remove_player_treasure(user_id, found_treasure_id)
                await db.add_plant_treasure(target_entity['id'], found_treasure_id, dec_x, dec_y)
                target_name = target_entity["common_name"]

        treasure_info = all_treasures.get(found_treasure_id)
        await interaction.followup.send(f"You have decorated {target_name} with a {treasure_info['name']}!", ephemeral=True)

    @app_commands.command(name='clean_nest', description='Remove all decorations from your nest')
    async def clean_nest(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.cleaning_handler(interaction, 'nest')

    @app_commands.command(name='clean_bird', description='Remove all decorations from a bird')
    @app_commands.describe(bird_name='The common or scientific name of the bird to clean')
    async def clean_bird(self, interaction: discord.Interaction, bird_name: str):
        await interaction.response.defer(ephemeral=True)
        await self.cleaning_handler(interaction, 'bird', entity_name=bird_name)

    @app_commands.command(name='clean_plant', description='Remove all decorations from a plant')
    @app_commands.describe(plant_name='The common name of the plant to clean')
    async def clean_plant(self, interaction: discord.Interaction, plant_name: str):
        await interaction.response.defer(ephemeral=True)
        await self.cleaning_handler(interaction, 'plant', entity_name=plant_name)

    async def cleaning_handler(self, interaction: discord.Interaction, entity_type: str, entity_name: str = None):
        user_id = interaction.user.id

        if entity_type == 'nest':
            nest_treasures = await db.get_nest_treasures(user_id)
            if not nest_treasures:
                await interaction.followup.send("Your nest has no decorations to remove!", ephemeral=True)
                return

            # Return all treasures to inventory
            for t in nest_treasures:
                await db.add_player_treasure(user_id, t['id'])
            # Remove all nest decorations
            await db.remove_nest_treasures(user_id)

            await interaction.followup.send(f"Removed {len(nest_treasures)} decorations from your nest. They have been returned to your inventory.", ephemeral=True)
            return

        if not entity_name:
            await interaction.followup.send(f"Please specify the name of the {entity_type} you want to clean.", ephemeral=True)
            return

        if entity_type == 'bird':
            birds = await db.get_player_birds(user_id)
            target_entity = None
            for bird in birds:
                if entity_name.lower() in [bird['scientific_name'].lower(), bird['common_name'].lower()]:
                    target_entity = bird
                    break

            if not target_entity:
                await interaction.followup.send(f"Bird '{entity_name}' not found.", ephemeral=True)
                return

            bird_treasures = await db.get_bird_treasures(target_entity['id'])
            if not bird_treasures:
                await interaction.followup.send(f"{target_entity['common_name']} has no decorations to remove.", ephemeral=True)
                return

            # Return all treasures to inventory
            for t in bird_treasures:
                await db.add_player_treasure(user_id, t['id'])
            # Remove all bird decorations
            await db.remove_bird_treasures(target_entity['id'])

            await interaction.followup.send(f"Removed {len(bird_treasures)} decorations from {target_entity['common_name']}. They have been returned to your inventory.", ephemeral=True)

        elif entity_type == 'plant':
            plants = await db.get_player_plants(user_id)
            target_entity = None
            for plant in plants:
                if entity_name.lower() == plant['common_name'].lower():
                    target_entity = plant
                    break

            if not target_entity:
                await interaction.followup.send(f"Plant '{entity_name}' not found.", ephemeral=True)
                return

            plant_treasures = await db.get_plant_treasures(target_entity['id'])
            if not plant_treasures:
                await interaction.followup.send(f"{target_entity['common_name']} has no decorations to remove.", ephemeral=True)
                return

            # Return all treasures to inventory
            for t in plant_treasures:
                await db.add_player_treasure(user_id, t['id'])
            # Remove all plant decorations
            await db.remove_plant_treasures(target_entity['id'])

            await interaction.followup.send(f"Removed {len(plant_treasures)} decorations from {target_entity['common_name']}. They have been returned to your inventory.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(CustomisationCommands(bot))
