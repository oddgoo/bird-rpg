from discord.ext import commands
from discord import app_commands
import discord

from data.storage import load_data, save_data
from data.models import get_personal_nest, get_common_nest, get_remaining_actions, record_actions, get_nest_building_bonus
from utils.logging import log_debug
from utils.time_utils import get_time_until_reset

class BuildCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='build', description='Add twigs to your nest')
    @app_commands.describe(amount='Number of twigs to add (default: 1)')
    async def build_nest_own(self, interaction: discord.Interaction, amount: int = 1):
        log_debug(f"build_nest_own called by {interaction.user.id} for {amount}")
        data = load_data()
        
        if amount < 1:
            await interaction.response.send_message("Please specify a positive number of twigs to add! 🪹")
            return
        
        remaining_actions = get_remaining_actions(data, interaction.user.id)
        if remaining_actions <= 0:
            await interaction.response.send_message(f"You've used all your actions for today! Come back in {get_time_until_reset()}! 🌙")
            return
        
        amount = min(amount, remaining_actions)
        
        nest = get_personal_nest(data, interaction.user.id)
        bonus_twigs = get_nest_building_bonus(data, nest)
        total_twigs = amount + bonus_twigs
        
        nest["twigs"] += total_twigs
        record_actions(data, interaction.user.id, amount, "build")
        
        save_data(data)
        remaining = get_remaining_actions(data, interaction.user.id)
        
        message = f"Added {amount} {'twig' if amount == 1 else 'twigs'} to your nest!"
        if bonus_twigs:
            message += f"\n✨ Plains-wanderer's effect activated: +{bonus_twigs} bonus twigs!"
        
        message += f"\n🪹 Your nest now has {nest['twigs']} twigs and {nest['seeds']} seeds.\n"
        message += f"You have {remaining} {'action' if remaining == 1 else 'actions'} remaining today."
        
        await interaction.response.send_message(message)

    @app_commands.command(name='build_common', description='Add twigs to the common nest')
    @app_commands.describe(amount='Number of twigs to add (default: 1)')
    async def build_nest_common(self, interaction: discord.Interaction, amount: int = 1):
        log_debug(f"build_nest_common called by {interaction.user.id} for {amount}")
        data = load_data()
        
        if amount < 1:
            await interaction.response.send_message("Please specify a positive number of twigs to add! 🪺")
            return
        
        remaining_actions = get_remaining_actions(data, interaction.user.id)
        if remaining_actions <= 0:
            await interaction.response.send_message(f"You've used all your actions for today! Come back in {get_time_until_reset()}! 🌙")
            return
        
        amount = min(amount, remaining_actions)
        
        nest = get_personal_nest(data, interaction.user.id)
        bonus_twigs = get_nest_building_bonus(data, nest)
        total_twigs = amount + bonus_twigs
        
        data["common_nest"]["twigs"] += total_twigs
        record_actions(data, interaction.user.id, amount, "build")
        
        save_data(data)
        nest = data["common_nest"]
        remaining = get_remaining_actions(data, interaction.user.id)
        
        message = f"Added {amount} {'twig' if amount == 1 else 'twigs'} to the common nest!"
        if bonus_twigs:
            message += f"\n✨ Plains-wanderer's effect activated: +{bonus_twigs} bonus twigs!"
        
        message += f"\n🪺 The common nest now has {nest['twigs']} twigs and {nest['seeds']} seeds.\n"
        message += f"You have {remaining} {'action' if remaining == 1 else 'actions'} remaining today."
        
        await interaction.response.send_message(message)

async def setup(bot):
    await bot.add_cog(BuildCommands(bot))
    log_debug("BuildCommands cog has been added.")