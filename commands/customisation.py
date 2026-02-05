from discord.ext import commands
from discord import app_commands
import discord

import data.storage as db
from utils.logging import log_debug

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
            await interaction.followup.send("Nest name must be 256 characters or less!")
            return

        if len(new_name) < 1:
            await interaction.followup.send("Please provide a name for your nest!")
            return

        user_id = interaction.user.id
        player = await db.load_player(user_id)

        old_name = player.get("nest_name", "Some Bird's Nest")

        await db.update_player(user_id, nest_name=new_name)

        await interaction.followup.send(f"Renamed your nest from \"{old_name}\" to \"{new_name}\"!")

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
            await interaction.followup.send("Bird not found in your hatched birds! You can only feature birds you have hatched.")
            return

        await db.update_player(user_id,
            featured_bird_common_name=target_bird['common_name'],
            featured_bird_scientific_name=target_bird['scientific_name']
        )

        await interaction.followup.send(f"Your nest now features the {target_bird['common_name']} ({target_bird['scientific_name']})!")

    @app_commands.command(name='group', description='Assign birds and plants to a named group')
    @app_commands.describe(
        group_name='Name for the group (max 64 characters)',
        names='Comma-separated common or scientific names of birds/plants to group',
    )
    async def group(self, interaction: discord.Interaction, group_name: str, names: str):
        await interaction.response.defer()
        user_id = interaction.user.id

        if len(group_name) > 64:
            await interaction.followup.send("Group name must be 64 characters or less!")
            return
        if len(group_name) < 1:
            await interaction.followup.send("Please provide a group name!")
            return

        birds = await db.get_player_birds(user_id)
        plants = await db.get_player_plants(user_id)

        name_list = [n.strip() for n in names.split(',') if n.strip()]
        if not name_list:
            await interaction.followup.send("Please provide at least one name to group!")
            return

        assigned = []
        not_found = []

        for name in name_list:
            name_lower = name.lower()
            matched = False

            # Try birds first
            for bird in birds:
                if name_lower in [bird['common_name'].lower(), bird['scientific_name'].lower()]:
                    if bird.get('group_name'):
                        continue  # skip already-grouped
                    await db.update_bird_group(bird['id'], group_name)
                    bird['group_name'] = group_name  # mutate in-memory to prevent double-assign
                    assigned.append(bird['common_name'])
                    matched = True
                    break

            if matched:
                continue

            # Try plants
            for plant in plants:
                if name_lower in [plant['common_name'].lower(), plant['scientific_name'].lower()]:
                    if plant.get('group_name'):
                        continue  # skip already-grouped
                    await db.update_plant_group(plant['id'], group_name)
                    plant['group_name'] = group_name
                    assigned.append(plant['common_name'])
                    matched = True
                    break

            if not matched:
                not_found.append(name)

        parts = []
        if assigned:
            parts.append(f"Assigned to **{group_name}**: {', '.join(assigned)}")
        if not_found:
            parts.append(f"Not found or already grouped: {', '.join(not_found)}")
        if not parts:
            parts.append("Nothing was assigned.")

        await interaction.followup.send('\n'.join(parts))

    @app_commands.command(name='ungroup', description='Remove all birds and plants from a named group')
    @app_commands.describe(group_name='The group name to dissolve')
    async def ungroup(self, interaction: discord.Interaction, group_name: str):
        await interaction.response.defer()
        user_id = interaction.user.id

        bird_count = await db.clear_group_birds(user_id, group_name)
        plant_count = await db.clear_group_plants(user_id, group_name)

        total = bird_count + plant_count
        if total == 0:
            await interaction.followup.send(f"No birds or plants found in group **{group_name}**.")
        else:
            await interaction.followup.send(f"Removed {total} bird(s)/plant(s) from group **{group_name}**.")

async def setup(bot):
    await bot.add_cog(CustomisationCommands(bot))
