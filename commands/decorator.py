"""Discord command to generate visual decorator URLs."""

from discord.ext import commands
from discord import app_commands
import discord
from web.decorator_tokens import create_token
from config.config import WEB_BASE_URL
import data.storage as db


class DecoratorCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='decorator', description='Open the visual sticker decorator for a bird, plant, or nest')
    @app_commands.describe(
        entity_type='What to decorate',
        entity_name='Name of the bird or plant (not needed for nest)'
    )
    @app_commands.choices(entity_type=[
        app_commands.Choice(name='Bird', value='bird'),
        app_commands.Choice(name='Plant', value='plant'),
        app_commands.Choice(name='Nest', value='nest'),
    ])
    async def decorator(self, interaction: discord.Interaction,
                        entity_type: app_commands.Choice[str],
                        entity_name: str = None):
        await interaction.response.defer(ephemeral=True)
        user_id = interaction.user.id
        etype = entity_type.value

        if etype == 'nest':
            entity_id = str(user_id)
            display_name = "your nest"
        elif etype == 'bird':
            if not entity_name:
                await interaction.followup.send("Please specify a bird name.", ephemeral=True)
                return
            birds = await db.get_player_birds(user_id)
            target = None
            name_lower = entity_name.lower()
            for bird in birds:
                if name_lower in (bird['scientific_name'].lower(), bird['common_name'].lower()):
                    target = bird
                    break
            if not target:
                # Try partial match
                for bird in birds:
                    if name_lower in bird['common_name'].lower() or name_lower in bird['scientific_name'].lower():
                        target = bird
                        break
            if not target:
                await interaction.followup.send(f"Bird '{entity_name}' not found in your nest.", ephemeral=True)
                return
            entity_id = target['id']
            display_name = target['common_name']
        elif etype == 'plant':
            if not entity_name:
                await interaction.followup.send("Please specify a plant name.", ephemeral=True)
                return
            plants = await db.get_player_plants(user_id)
            target = None
            name_lower = entity_name.lower()
            for plant in plants:
                if name_lower in (plant['scientific_name'].lower(), plant['common_name'].lower()):
                    target = plant
                    break
            if not target:
                for plant in plants:
                    if name_lower in plant['common_name'].lower() or name_lower in plant['scientific_name'].lower():
                        target = plant
                        break
            if not target:
                await interaction.followup.send(f"Plant '{entity_name}' not found in your garden.", ephemeral=True)
                return
            entity_id = target['id']
            display_name = target['common_name']
        else:
            await interaction.followup.send("Invalid entity type.", ephemeral=True)
            return

        token = create_token(user_id, etype, entity_id)
        base_url = WEB_BASE_URL
        url = f"{base_url}/decorate/{token}"

        await interaction.followup.send(
            f"Open the decorator for **{display_name}**:\n{url}\n\nThis link expires in 1 hour.",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(DecoratorCommands(bot))
