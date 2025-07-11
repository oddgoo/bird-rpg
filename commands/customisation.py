from discord.ext import commands
from discord import app_commands
import discord

from data.storage import load_data, save_data
from data.models import get_personal_nest
from utils.logging import log_debug
from commands.foraging import load_treasures

class CustomisationCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='rename_nest', description='Rename your personal nest')
    @app_commands.describe(new_name='The new name for your nest (max 256 characters)')
    async def rename_nest(self, interaction: discord.Interaction, new_name: str):
        """Rename your personal nest"""
        log_debug(f"rename_nest called by {interaction.user.id} with name: {new_name}")
        
        if len(new_name) > 256:
            await interaction.response.send_message("❌ Nest name must be 256 characters or less!")
            return
            
        if len(new_name) < 1:
            await interaction.response.send_message("❌ Please provide a name for your nest!")
            return

        data = load_data()
        nest = get_personal_nest(data, interaction.user.id)
        
        old_name = nest.get("name", "Some Bird's Nest")
        
        nest["name"] = new_name
        save_data(data)
        
        await interaction.response.send_message(f"🪹 Renamed your nest from \"{old_name}\" to \"{new_name}\"!")

    @app_commands.command(name='feature_bird', description='Set a bird to be featured in your nest display')
    @app_commands.describe(bird_name='The scientific or common name of the bird to feature')
    async def feature_bird(self, interaction: discord.Interaction, bird_name: str):
        """Set a bird to be featured in your nest display"""
        log_debug(f"feature_bird called by {interaction.user.id} with bird: {bird_name}")
        
        data = load_data()
        nest = get_personal_nest(data, interaction.user.id)
        chicks = nest.get("chicks", [])
        
        target_bird = None
        for chick in chicks:
            if bird_name.lower() in [chick['scientificName'].lower(), chick['commonName'].lower()]:
                target_bird = chick
                break
                
        if not target_bird:
            await interaction.response.send_message("❌ Bird not found in your hatched birds! You can only feature birds you have hatched.")
            return
            
        nest["featured_bird"] = target_bird
        save_data(data)
        
        await interaction.response.send_message(f"✨ Your nest now features the {target_bird['commonName']} ({target_bird['scientificName']})!")

    @app_commands.command(name='decorate_nest', description='Decorate your nest with a treasure')
    @app_commands.describe(treasure_name='The name of the treasure to use', x='The x-position of the sticker (0-100). optional.', y='The y-position of the sticker (0-100). optional')
    async def decorate_nest(self, interaction: discord.Interaction, treasure_name: str, x: app_commands.Range[int, 0, 100]=None, y: app_commands.Range[int, 0, 100]=None):
        await self.decoration_handler(interaction, 'nest', treasure_name, x=x, y=y)

    @app_commands.command(name='decorate_bird', description='Decorate a bird with a treasure')
    @app_commands.describe(bird_name='The common or scientific name of the bird', treasure_name='The name of the treasure to use', x='The x-position of the sticker (0-100). optional', y='The y-position of the sticker (0-100). optional')
    async def decorate_bird(self, interaction: discord.Interaction, bird_name: str, treasure_name: str, x: app_commands.Range[int, 0, 100]=None, y: app_commands.Range[int, 0, 100]=None):
        await self.decoration_handler(interaction, 'bird', treasure_name, entity_name=bird_name, x=x, y=y)

    @app_commands.command(name='decorate_plant', description='Decorate a plant with a treasure')
    @app_commands.describe(plant_name='The common name of the plant', treasure_name='The name of the treasure to use', x='The x-position of the sticker (0-100). optional', y='The y-position of the sticker (0-100). optional')
    async def decorate_plant(self, interaction: discord.Interaction, plant_name: str, treasure_name: str, x: app_commands.Range[int, 0, 100]=None, y: app_commands.Range[int, 0, 100]=None):
        await self.decoration_handler(interaction, 'plant', treasure_name, entity_name=plant_name, x=x, y=y)

    async def decoration_handler(self, interaction: discord.Interaction, entity_type: str, treasure_name: str, entity_name: str = None, x: int = None, y: int = None):
        user_id = interaction.user.id
        data = load_data()
        nest = get_personal_nest(data, user_id)

        if not nest.get("treasures"):
            await interaction.response.send_message("You don't have any treasures to use for decoration!", ephemeral=True)
            return

        treasures_data = load_treasures()
        all_treasures = {t["id"]: t for loc in treasures_data.values() for t in loc}
        
        # Find the treasure by name
        found_treasure_id = None
        treasure_index = -1
        for i, t_id in enumerate(nest["treasures"]):
            if all_treasures.get(t_id, {}).get("name", "").lower() == treasure_name.lower():
                found_treasure_id = t_id
                treasure_index = i
                break
        
        if not found_treasure_id:
            await interaction.response.send_message(f"Treasure '{treasure_name}' not found in your inventory.", ephemeral=True)
            return

        # Remove the treasure from inventory
        nest["treasures"].pop(treasure_index)

        base_treasure = all_treasures.get(found_treasure_id, {})
        decoration = {
            "id": found_treasure_id,
            "x": base_treasure.get('x', 0),
            "y": base_treasure.get('y', 0)
        }

        if x is not None: decoration["x"] = x
        if y is not None: decoration["y"] = y

        target_name = "your nest"
        if entity_type == 'nest':
            if "treasures_applied_on_nest" not in nest:
                nest["treasures_applied_on_nest"] = []
            nest["treasures_applied_on_nest"].append(decoration)
        else:
            target_list = nest.get("chicks" if entity_type == 'bird' else "plants", [])
            target_entity = None
            if entity_type == 'bird':
                for chick in target_list:
                    if entity_name.lower() in [chick['scientificName'].lower(), chick['commonName'].lower()]:
                        target_entity = chick
                        break
            elif entity_type == 'plant':
                for plant in target_list:
                    if entity_name.lower() == plant['commonName'].lower():
                        target_entity = plant
                        break
            
            if not target_entity:
                await interaction.response.send_message(f"{entity_type.capitalize()} '{entity_name}' not found.", ephemeral=True)
                # Return treasure to inventory
                nest["treasures"].insert(treasure_index, found_treasure_id)
                return

            if "treasures" not in target_entity:
                target_entity["treasures"] = []
            target_entity["treasures"].append(decoration)
            target_name = target_entity["commonName"]

        save_data(data)
        treasure_info = all_treasures.get(found_treasure_id)
        await interaction.response.send_message(f"You have decorated {target_name} with a {treasure_info['name']}!", ephemeral=True)

    @app_commands.command(name='clean_nest', description='Remove all decorations from your nest')
    async def clean_nest(self, interaction: discord.Interaction):
        await self.cleaning_handler(interaction, 'nest')

    @app_commands.command(name='clean_bird', description='Remove all decorations from a bird')
    @app_commands.describe(bird_name='The common or scientific name of the bird to clean')
    async def clean_bird(self, interaction: discord.Interaction, bird_name: str):
        await self.cleaning_handler(interaction, 'bird', entity_name=bird_name)

    @app_commands.command(name='clean_plant', description='Remove all decorations from a plant')
    @app_commands.describe(plant_name='The common name of the plant to clean')
    async def clean_plant(self, interaction: discord.Interaction, plant_name: str):
        await self.cleaning_handler(interaction, 'plant', entity_name=plant_name)

    async def cleaning_handler(self, interaction: discord.Interaction, entity_type: str, entity_name: str = None):
        user_id = interaction.user.id
        data = load_data()
        nest = get_personal_nest(data, user_id)

        if entity_type == 'nest':
            if not nest.get("treasures_applied_on_nest"):
                await interaction.response.send_message("Your nest has no decorations to remove!", ephemeral=True)
                return
            
            removed_decorations = nest.pop("treasures_applied_on_nest", [])
            if removed_decorations:
                nest.setdefault("treasures", []).extend([t['id'] for t in removed_decorations])
                save_data(data)
                await interaction.response.send_message(f"Removed {len(removed_decorations)} decorations from your nest. They have been returned to your inventory.", ephemeral=True)
            else:
                await interaction.response.send_message("Your nest has no decorations to remove!", ephemeral=True)
            return

        target_list = nest.get("chicks" if entity_type == 'bird' else "plants", [])
        target_entity = None
        
        if not entity_name:
            await interaction.response.send_message(f"Please specify the name of the {entity_type} you want to clean.", ephemeral=True)
            return

        if entity_type == 'bird':
            for chick in target_list:
                if entity_name.lower() in [chick['scientificName'].lower(), chick['commonName'].lower()]:
                    target_entity = chick
                    break
        elif entity_type == 'plant':
            for plant in target_list:
                if entity_name.lower() == plant['commonName'].lower():
                    target_entity = plant
                    break
        
        if not target_entity:
            await interaction.response.send_message(f"{entity_type.capitalize()} '{entity_name}' not found.", ephemeral=True)
            return

        if not target_entity.get("treasures"):
            await interaction.response.send_message(f"{target_entity['commonName']} has no decorations to remove.", ephemeral=True)
            return

        removed_decorations = target_entity.pop("treasures", [])
        if removed_decorations:
            nest.setdefault("treasures", []).extend([t['id'] for t in removed_decorations])
            save_data(data)
            await interaction.response.send_message(f"Removed {len(removed_decorations)} decorations from {target_entity['commonName']}. They have been returned to your inventory.", ephemeral=True)
        else:
            await interaction.response.send_message(f"{target_entity['commonName']} has no decorations to remove.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(CustomisationCommands(bot))
