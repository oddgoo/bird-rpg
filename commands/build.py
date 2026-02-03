from discord.ext import commands
from discord import app_commands
import discord

import data.storage as db
from data.models import get_remaining_actions, record_actions, get_nest_building_bonus
from utils.logging import log_debug
from utils.time_utils import get_time_until_reset

class BuildCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='build', description='Add twigs to your nest')
    @app_commands.describe(amount='Number of twigs to add (default: 1)')
    async def build_nest_own(self, interaction: discord.Interaction, amount: int = 1):
        await interaction.response.defer()
        user_id = str(interaction.user.id)
        log_debug(f"build_nest_own called by {user_id} for {amount}")

        if amount < 1:
            await interaction.followup.send("Please specify a positive number of twigs to add! 🪹")
            return

        remaining_actions = await get_remaining_actions(user_id)
        if remaining_actions <= 0:
            await interaction.followup.send(f"You've used all your actions for today! Come back in {get_time_until_reset()}! 🌙")
            return

        amount = min(amount, remaining_actions)

        birds = await db.get_player_birds(user_id)
        bonus_twigs = await get_nest_building_bonus(user_id, birds)
        total_twigs = amount + bonus_twigs

        await db.increment_player_field(user_id, "twigs", total_twigs)
        await record_actions(user_id, amount, "build")

        player = await db.load_player(user_id)
        remaining = await get_remaining_actions(user_id)

        message = f"Added {amount} {'twig' if amount == 1 else 'twigs'} to your nest!"
        if bonus_twigs:
            message += f"\n✨ Plains-wanderer's effect activated: +{bonus_twigs} bonus twigs!"

        message += f"\n🪹 Your nest now has {player['twigs']} twigs and {player['seeds']} seeds.\n"
        message += f"You have {remaining} {'action' if remaining == 1 else 'actions'} remaining today."

        await interaction.followup.send(message)

    @app_commands.command(name='build_common', description='Add twigs to the common nest')
    @app_commands.describe(amount='Number of twigs to add (default: 1)')
    async def build_nest_common(self, interaction: discord.Interaction, amount: int = 1):
        await interaction.response.defer()
        user_id = str(interaction.user.id)
        log_debug(f"build_nest_common called by {user_id} for {amount}")

        if amount < 1:
            await interaction.followup.send("Please specify a positive number of twigs to add! 🪺")
            return

        remaining_actions = await get_remaining_actions(user_id)
        if remaining_actions <= 0:
            await interaction.followup.send(f"You've used all your actions for today! Come back in {get_time_until_reset()}! 🌙")
            return

        amount = min(amount, remaining_actions)

        birds = await db.get_player_birds(user_id)
        bonus_twigs = await get_nest_building_bonus(user_id, birds)
        total_twigs = amount + bonus_twigs

        await db.increment_common_nest("twigs", total_twigs)
        await record_actions(user_id, amount, "build")

        common_nest = await db.load_common_nest()
        remaining = await get_remaining_actions(user_id)

        message = f"Added {amount} {'twig' if amount == 1 else 'twigs'} to the common nest!"
        if bonus_twigs:
            message += f"\n✨ Plains-wanderer's effect activated: +{bonus_twigs} bonus twigs!"

        message += f"\n🪺 The common nest now has {common_nest['twigs']} twigs and {common_nest['seeds']} seeds.\n"
        message += f"You have {remaining} {'action' if remaining == 1 else 'actions'} remaining today."

        await interaction.followup.send(message)

async def setup(bot):
    await bot.add_cog(BuildCommands(bot))
    log_debug("BuildCommands cog has been added.")
