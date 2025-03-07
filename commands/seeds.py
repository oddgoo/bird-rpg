from discord.ext import commands
from discord import app_commands
import discord

from config.config import MAX_GARDEN_SIZE
from data.storage import load_data, save_data
from data.models import (get_personal_nest, get_common_nest, get_remaining_actions, 
                        record_actions, get_seed_gathering_bonus, get_extra_garden_space)
from utils.logging import log_debug
from utils.time_utils import get_time_until_reset

class SeedCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='add_seed', description='Add seeds to your nest')
    @app_commands.describe(amount='Number of seeds to add (default: 1)')
    async def add_seed_own(self, interaction: discord.Interaction, amount: int = 1):
        log_debug(f"add_seed_own called by {interaction.user.id} for {amount}")
        data = load_data()
        
        if amount < 1:
            await interaction.response.send_message("Please specify a positive number of seeds to add! 🌱")
            return
        
        remaining_actions = get_remaining_actions(data, interaction.user.id)
        if remaining_actions <= 0:
            await interaction.response.send_message(f"You've used all your actions for today! Come back in {get_time_until_reset()}! 🌙")
            return
        
        nest = get_personal_nest(data, interaction.user.id)
        
        # Initialize garden_size if it doesn't exist
        if "garden_size" not in nest:
            nest["garden_size"] = 0
        
        # Apply garden size bonus if it's first action
        garden_bonus = get_seed_gathering_bonus(data, nest)
        if garden_bonus > 0:
            # Get extra garden space from research progress
            extra_garden_space = get_extra_garden_space()
            max_size = MAX_GARDEN_SIZE + extra_garden_space
            
            # Check if garden size would exceed the maximum (including extra space)
            if nest["garden_size"] >= max_size:
                bonus_msg = f"\nYour garden is already at maximum size ({max_size})! 🌱"
            elif nest["garden_size"] + garden_bonus > max_size:
                # Only increase up to the maximum
                actual_bonus = max_size - nest["garden_size"]
                nest["garden_size"] = max_size
                bonus_msg = f"\nYour cockatoos helped expand your garden by {actual_bonus} (reached maximum size of {max_size})! 🦜"
            else:
                nest["garden_size"] += garden_bonus
                bonus_msg = f"\nYour cockatoos helped expand your garden by {garden_bonus}! 🦜"
        else:
            bonus_msg = ""
        
        space_available = nest["twigs"] - nest["seeds"]
        amount = min(amount, space_available, remaining_actions)
        
        if amount <= 0:
            await interaction.response.send_message("Your nest is full! Add more twigs to store more seeds. 🪹")
            return
        
        nest["seeds"] += amount
        record_actions(data, interaction.user.id, amount, "seed")
        
        save_data(data)
        remaining = get_remaining_actions(data, interaction.user.id)
        await interaction.response.send_message(f"Added {amount} {'seed' if amount == 1 else 'seeds'} to your nest! 🏡\n"
                      f"Your nest now has {nest['twigs']} twigs and {nest['seeds']} seeds.{bonus_msg}\n"
                      f"You have {remaining} {'action' if remaining == 1 else 'actions'} remaining today.")

    @app_commands.command(name='add_seed_common', description='Add seeds to the common nest')
    @app_commands.describe(amount='Number of seeds to add (default: 1)')
    async def add_seed_common(self, interaction: discord.Interaction, amount: int = 1):
        log_debug(f"add_seed_common called by {interaction.user.id} for {amount}")
        data = load_data()
        
        if amount < 1:
            await interaction.response.send_message("Please specify a positive number of seeds to add! 🌱")
            return
        
        remaining_actions = get_remaining_actions(data, interaction.user.id)
        if remaining_actions <= 0:
            await interaction.response.send_message(f"You've used all your actions for today! Come back in {get_time_until_reset()}! 🌙")
            return
        
        # Get personal nest for checking cockatoo bonus
        nest = get_personal_nest(data, interaction.user.id)
        common_nest = data["common_nest"]
        
        # Apply garden size bonus if it's first action
        garden_bonus = get_seed_gathering_bonus(data, nest)
        if garden_bonus > 0:
            if "garden_size" not in nest:
                nest["garden_size"] = 0
            
            # Get extra garden space from research progress
            extra_garden_space = get_extra_garden_space()
            max_size = MAX_GARDEN_SIZE + extra_garden_space
                
            # Check if garden size would exceed the maximum (including extra space)
            if nest["garden_size"] >= max_size:
                bonus_msg = f"\nYour garden is already at maximum size ({max_size})! 🌱"
            elif nest["garden_size"] + garden_bonus > max_size:
                # Only increase up to the maximum
                actual_bonus = max_size - nest["garden_size"]
                nest["garden_size"] = max_size
                bonus_msg = f"\nYour cockatoos helped expand your garden by {actual_bonus} (reached maximum size of {max_size})! 🦜"
            else:
                nest["garden_size"] += garden_bonus
                bonus_msg = f"\nYour cockatoos helped expand your garden by {garden_bonus}! 🦜"
        else:
            bonus_msg = ""
        
        space_available = common_nest["twigs"] - common_nest["seeds"]
        amount = min(amount, space_available, remaining_actions)
        
        if amount <= 0:
            await interaction.response.send_message("The common nest is full! Add more twigs to store more seeds. 🪺")
            return
        
        common_nest["seeds"] += amount
        record_actions(data, interaction.user.id, amount, "seed")
        
        save_data(data)
        remaining = get_remaining_actions(data, interaction.user.id)
        await interaction.response.send_message(f"Added {amount} {'seed' if amount == 1 else 'seeds'} to the common nest! 🌇\n"
                      f"The common nest now has {common_nest['twigs']} twigs and {common_nest['seeds']} seeds.{bonus_msg}\n"
                      f"You have {remaining} {'action' if remaining == 1 else 'actions'} remaining today.")

    @app_commands.command(name='donate_seeds', description='Move seeds from your nest to the common nest')
    @app_commands.describe(amount='Number of seeds to donate')
    async def move_seeds_own(self, interaction: discord.Interaction, amount: int):
        log_debug(f"move_seeds_own called by {interaction.user.id} for {amount} seeds")
        data = load_data()
        
        if amount <= 0:
            await interaction.response.send_message("Please specify a positive number of seeds to move!")
            return

        nest = get_personal_nest(data, interaction.user.id)
        common_nest = data["common_nest"]
        
        if amount > nest["seeds"]:
            await interaction.response.send_message("You don't have enough seeds in your nest! 🏡")
            return
        
        if common_nest["seeds"] + amount > common_nest["twigs"]:
            await interaction.response.send_message("The common nest doesn't have enough space! 🌇")
            return
        
        nest["seeds"] -= amount
        common_nest["seeds"] += amount
        
        save_data(data)
        await interaction.response.send_message(f"Moved {amount} seeds from your nest to the common nest!\n"
                      f"Your nest: {nest['twigs']} twigs, {nest['seeds']} seeds\n"
                      f"Common nest: {common_nest['twigs']} twigs, {common_nest['seeds']} seeds")

    @app_commands.command(name='borrow_seeds', description='Move seeds from the common nest to your nest')
    @app_commands.describe(amount='Number of seeds to borrow')
    async def move_seeds_common(self, interaction: discord.Interaction, amount: int):
        log_debug(f"move_seeds_common called by {interaction.user.id} for {amount} seeds")
        data = load_data()
        
        if amount <= 0:
            await interaction.response.send_message("Please specify a positive number of seeds to move!")
            return
        
        nest = get_personal_nest(data, interaction.user.id)
        common_nest = data["common_nest"]
        
        if amount > common_nest["seeds"]:
            await interaction.response.send_message("There aren't enough seeds in the common nest! 🌇")
            return
        
        if nest["seeds"] + amount > nest["twigs"]:
            await interaction.response.send_message("Your nest doesn't have enough space! 🏡")
            return
        
        common_nest["seeds"] -= amount
        nest["seeds"] += amount
        
        save_data(data)
        await interaction.response.send_message(f"Moved {amount} seeds from the common nest to your nest!\n"
                      f"Your nest: {nest['twigs']} twigs, {nest['seeds']} seeds\n"
                      f"Common nest: {common_nest['twigs']} twigs, {common_nest['seeds']} seeds")

async def setup(bot):
    await bot.add_cog(SeedCommands(bot))
