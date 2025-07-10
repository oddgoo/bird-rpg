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
    @app_commands.describe(x='The x-position of the sticker (0-100). optional.', y='The y-position of the sticker (0-100). optional')
    async def decorate_nest(self, interaction: discord.Interaction, x: app_commands.Range[int, 0, 100]=None, y: app_commands.Range[int, 0, 100]=None):
        await self.decoration_handler(interaction, 'nest', x, y)

    @app_commands.command(name='decorate_bird', description='Decorate a bird with a treasure')
    @app_commands.describe(x='The x-position of the sticker (0-100). optional', y='The y-position of the sticker (0-100). optional')
    async def decorate_bird(self, interaction: discord.Interaction, x: app_commands.Range[int, 0, 100]=None, y: app_commands.Range[int, 0, 100]=None):
        await self.decoration_handler(interaction, 'bird', x, y)

    @app_commands.command(name='decorate_plant', description='Decorate a plant with a treasure')
    @app_commands.describe(x='The x-position of the sticker (0-100). optional', y='The y-position of the sticker (0-100). optional')
    async def decorate_plant(self, interaction: discord.Interaction, x: app_commands.Range[int, 0, 100]=None, y: app_commands.Range[int, 0, 100]=None):
        await self.decoration_handler(interaction, 'plant', x, y)

    async def decoration_handler(self, interaction: discord.Interaction, entity_type: str, x: int=None, y: int=None):
        user_id = interaction.user.id
        data = load_data()
        nest = get_personal_nest(data, user_id)

        if not nest.get("treasures"):
            await interaction.response.send_message("You don't have any treasures to use for decoration!", ephemeral=True)
            return

        treasures_data = load_treasures()
        all_treasures = {t["id"]: t for loc in treasures_data.values() for t in loc}

        treasure_options = [discord.SelectOption(label=all_treasures.get(t_id, {}).get("name", t_id), value=str(i)) for i, t_id in enumerate(nest["treasures"][:25])]
        treasure_select = discord.ui.Select(placeholder="Choose a treasure to use...", options=treasure_options)

        # Add empty callback to prevent default interaction
        async def treasure_callback(interaction: discord.Interaction):
            await interaction.response.defer()
        treasure_select.callback = treasure_callback

        entity_options = []
        if entity_type == 'bird':
            entity_options = [discord.SelectOption(label=chick["commonName"], value=str(i)) for i, chick in enumerate(nest.get("chicks", [])[:25])]
            if not entity_options:
                await interaction.response.send_message("You don't have any birds to decorate!", ephemeral=True)
                return
        elif entity_type == 'plant':
            entity_options = [discord.SelectOption(label=plant["commonName"], value=str(i)) for i, plant in enumerate(nest.get("plants", [])[:25])]
            if not entity_options:
                await interaction.response.send_message("You don't have any plants to decorate!", ephemeral=True)
                return
        
        entity_select = None
        if entity_options:
            entity_select = discord.ui.Select(placeholder=f"Choose a {entity_type} to decorate...", options=entity_options)
            # Add empty callback to prevent default interaction
            async def entity_callback(interaction: discord.Interaction):
                await interaction.response.defer()
            entity_select.callback = entity_callback

        button = discord.ui.Button(label="Decorate", style=discord.ButtonStyle.green)

        async def button_callback(button_interaction: discord.Interaction):
            if button_interaction.user.id != user_id:
                await button_interaction.response.send_message("This is not your decoration session!", ephemeral=True)
                return

            if not treasure_select.values:
                await button_interaction.response.send_message("Please select a treasure.", ephemeral=True)
                return
            
            if entity_select and not entity_select.values:
                await button_interaction.response.send_message(f"Please select a {entity_type}.", ephemeral=True)
                return

            data = load_data()
            nest = get_personal_nest(data, user_id)
            
            treasure_index = int(treasure_select.values[0])
            treasure_id = nest["treasures"].pop(treasure_index)

            # Get the base treasure info
            base_treasure = all_treasures.get(treasure_id, {})
            
            decoration = {
                "id": treasure_id,
                "x": base_treasure.get('x', 0),
                "y": base_treasure.get('y', 0)
            }

            # Override with user-provided values if they exist
            if x is not None:
                decoration["x"] = x
            if y is not None:
                decoration["y"] = y

            target_name = "your nest"
            if entity_type == 'nest':
                if "treasures_applied_on_nest" not in nest:
                    nest["treasures_applied_on_nest"] = []
                nest["treasures_applied_on_nest"].append(decoration)
            else:
                entity_index = int(entity_select.values[0])
                target_list = nest.get("chicks" if entity_type == 'bird' else "plants", [])
                if entity_index < len(target_list):
                    target_entity = target_list[entity_index]
                    if "treasures" not in target_entity:
                        target_entity["treasures"] = []
                    target_entity["treasures"].append(decoration)
                    target_name = target_entity["commonName"]
                else:
                    await button_interaction.response.edit_message(content="The selected item is no longer available.", view=None)
                    return

            save_data(data)
            treasure_info = all_treasures.get(treasure_id)
            await button_interaction.response.edit_message(content=f"You have decorated {target_name} with a {treasure_info['name']}!", view=None)

        button.callback = button_callback

        view = discord.ui.View()
        view.add_item(treasure_select)
        if entity_select:
            view.add_item(entity_select)
        view.add_item(button)
        
        await interaction.response.send_message(f"Decorating a {entity_type}...", view=view, ephemeral=True)

    @app_commands.command(name='clean_nest', description='Remove all decorations from your nest')
    async def clean_nest(self, interaction: discord.Interaction):
        await self.cleaning_handler(interaction, 'nest')

    @app_commands.command(name='clean_bird', description='Remove all decorations from a bird')
    async def clean_bird(self, interaction: discord.Interaction):
        await self.cleaning_handler(interaction, 'bird')

    @app_commands.command(name='clean_plant', description='Remove all decorations from a plant')
    async def clean_plant(self, interaction: discord.Interaction):
        await self.cleaning_handler(interaction, 'plant')

    async def cleaning_handler(self, interaction: discord.Interaction, entity_type: str):
        user_id = interaction.user.id
        data = load_data()
        nest = get_personal_nest(data, user_id)

        if entity_type == 'nest':
            if not nest.get("treasures_applied_on_nest"):
                await interaction.response.send_message("Your nest has no decorations to remove!", ephemeral=True)
                return
            
            removed_decorations = nest.get("treasures_applied_on_nest", [])
            nest["treasures"].extend([t['id'] for t in removed_decorations])
            removed_count = len(removed_decorations)
            nest["treasures_applied_on_nest"] = []
            save_data(data)
            await interaction.response.send_message(f"Removed {removed_count} decorations from your nest. They have been returned to your inventory.", ephemeral=True)
            return

        entity_options = []
        decorated_entities_map = {}
        if entity_type == 'bird':
            decorated_chicks = [chick for chick in nest.get("chicks", []) if chick.get("treasures")]
            if not decorated_chicks:
                await interaction.response.send_message("You don't have any decorated birds!", ephemeral=True)
                return
            for i, chick in enumerate(decorated_chicks):
                entity_options.append(discord.SelectOption(label=chick["commonName"], value=str(i)))
                decorated_entities_map[i] = chick
        elif entity_type == 'plant':
            decorated_plants = [plant for plant in nest.get("plants", []) if plant.get("treasures")]
            if not decorated_plants:
                await interaction.response.send_message("You don't have any decorated plants!", ephemeral=True)
                return
            for i, plant in enumerate(decorated_plants):
                entity_options.append(discord.SelectOption(label=f'{plant["commonName"]} (planted on {plant["planted_date"]})', value=str(i)))
                decorated_entities_map[i] = plant
        
        entity_select = discord.ui.Select(placeholder=f"Choose a {entity_type} to clean...", options=entity_options[:25])

        async def select_callback(select_interaction: discord.Interaction):
            if select_interaction.user.id != user_id:
                await select_interaction.response.send_message("This is not your cleaning session!", ephemeral=True)
                return

            data = load_data()
            nest = get_personal_nest(data, user_id)
            
            entity_index = int(entity_select.values[0])
            
            selected_entity = decorated_entities_map.get(entity_index)

            if selected_entity:
                # Find the original entity in the nest data to modify it directly
                original_entity = None
                if entity_type == 'bird':
                    for chick in nest.get("chicks", []):
                        if chick == selected_entity:
                            original_entity = chick
                            break
                elif entity_type == 'plant':
                    for plant in nest.get("plants", []):
                        if plant == selected_entity:
                            original_entity = plant
                            break
                
                if original_entity and original_entity.get("treasures"):
                    removed_decorations = original_entity.get("treasures", [])
                    nest["treasures"].extend([t['id'] for t in removed_decorations])
                    removed_count = len(removed_decorations)
                    original_entity["treasures"] = []
                    save_data(data)
                    await select_interaction.response.edit_message(content=f"Removed {removed_count} decorations from {original_entity['commonName']}. They have been returned to your inventory.", view=None)
                else:
                    await select_interaction.response.edit_message(content="This item has no decorations to remove.", view=None)
            else:
                await select_interaction.response.edit_message(content="The selected item is no longer available.", view=None)

        entity_select.callback = select_callback
        view = discord.ui.View()
        view.add_item(entity_select)
        await interaction.response.send_message(f"Cleaning a {entity_type}...", view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(CustomisationCommands(bot))
