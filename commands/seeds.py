from discord.ext import commands
from discord import app_commands
import discord

from config.config import MAX_GARDEN_SIZE
import data.storage as db
from data.models import (get_remaining_actions, record_actions,
                         get_seed_gathering_bonus, get_extra_garden_space)
from utils.logging import log_debug
from utils.time_utils import get_time_until_reset

class SeedCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='add_seed', description='Add seeds to your nest')
    @app_commands.describe(amount='Number of seeds to add (default: 1)')
    async def add_seed_own(self, interaction: discord.Interaction, amount: int = 1):
        await interaction.response.defer()
        log_debug(f"add_seed_own called by {interaction.user.id} for {amount}")
        user_id = str(interaction.user.id)

        if amount < 1:
            await interaction.followup.send("Please specify a positive number of seeds to add! 🌱")
            return

        remaining_actions = await get_remaining_actions(user_id)
        if remaining_actions <= 0:
            await interaction.followup.send(f"You've used all your actions for today! Come back in {get_time_until_reset()}! 🌙")
            return

        player = await db.load_player(user_id)
        birds = await db.get_player_birds(user_id)

        # Initialize garden_size if it doesn't exist
        garden_size = player.get("garden_size", 0) or 0

        # Apply garden size bonus if it's first action
        garden_bonus = await get_seed_gathering_bonus(user_id, birds)
        if garden_bonus > 0:
            # Get extra garden space from research progress
            extra_garden_space = await get_extra_garden_space()
            max_size = MAX_GARDEN_SIZE + extra_garden_space

            # Check if garden size would exceed the maximum (including extra space)
            if garden_size >= max_size:
                bonus_msg = f"\nYour garden is already at maximum size ({max_size})! 🌱"
            elif garden_size + garden_bonus > max_size:
                # Only increase up to the maximum
                actual_bonus = max_size - garden_size
                await db.increment_player_field(user_id, "garden_size", actual_bonus)
                garden_size = max_size
                bonus_msg = f"\nYour cockatoos helped expand your garden by {actual_bonus} (reached maximum size of {max_size})! 🦜"
            else:
                await db.increment_player_field(user_id, "garden_size", garden_bonus)
                garden_size += garden_bonus
                bonus_msg = f"\nYour cockatoos helped expand your garden by {garden_bonus}! 🦜"
        else:
            bonus_msg = ""

        space_available = player["twigs"] - player["seeds"]
        amount = min(amount, space_available, remaining_actions)

        if amount <= 0:
            await interaction.followup.send("Your nest is full! Add more twigs to store more seeds. 🪹")
            return

        await db.increment_player_field(user_id, "seeds", amount)
        await record_actions(user_id, amount, "seed")

        remaining = await get_remaining_actions(user_id)
        new_seeds = player["seeds"] + amount
        await interaction.followup.send(f"Added {amount} {'seed' if amount == 1 else 'seeds'} to your nest! 🏡\n"
                      f"Your nest now has {player['twigs']} twigs and {new_seeds} seeds.{bonus_msg}\n"
                      f"You have {remaining} {'action' if remaining == 1 else 'actions'} remaining today.")

    @app_commands.command(name='add_seed_common', description='Add seeds to the common nest')
    @app_commands.describe(amount='Number of seeds to add (default: 1)')
    async def add_seed_common(self, interaction: discord.Interaction, amount: int = 1):
        await interaction.response.defer()
        log_debug(f"add_seed_common called by {interaction.user.id} for {amount}")
        user_id = str(interaction.user.id)

        if amount < 1:
            await interaction.followup.send("Please specify a positive number of seeds to add! 🌱")
            return

        remaining_actions = await get_remaining_actions(user_id)
        if remaining_actions <= 0:
            await interaction.followup.send(f"You've used all your actions for today! Come back in {get_time_until_reset()}! 🌙")
            return

        # Get personal nest for checking cockatoo bonus
        player = await db.load_player(user_id)
        birds = await db.get_player_birds(user_id)
        common_nest = await db.load_common_nest()

        # Apply garden size bonus if it's first action
        garden_bonus = await get_seed_gathering_bonus(user_id, birds)
        if garden_bonus > 0:
            garden_size = player.get("garden_size", 0) or 0

            # Get extra garden space from research progress
            extra_garden_space = await get_extra_garden_space()
            max_size = MAX_GARDEN_SIZE + extra_garden_space

            # Check if garden size would exceed the maximum (including extra space)
            if garden_size >= max_size:
                bonus_msg = f"\nYour garden is already at maximum size ({max_size})! 🌱"
            elif garden_size + garden_bonus > max_size:
                # Only increase up to the maximum
                actual_bonus = max_size - garden_size
                await db.increment_player_field(user_id, "garden_size", actual_bonus)
                bonus_msg = f"\nYour cockatoos helped expand your garden by {actual_bonus} (reached maximum size of {max_size})! 🦜"
            else:
                await db.increment_player_field(user_id, "garden_size", garden_bonus)
                bonus_msg = f"\nYour cockatoos helped expand your garden by {garden_bonus}! 🦜"
        else:
            bonus_msg = ""

        space_available = common_nest["twigs"] - common_nest["seeds"]
        amount = min(amount, space_available, remaining_actions)

        if amount <= 0:
            await interaction.followup.send("The common nest is full! Add more twigs to store more seeds. 🪺")
            return

        await db.increment_common_nest("seeds", amount)
        await record_actions(user_id, amount, "seed")

        remaining = await get_remaining_actions(user_id)
        new_common_seeds = common_nest["seeds"] + amount
        await interaction.followup.send(f"Added {amount} {'seed' if amount == 1 else 'seeds'} to the common nest! 🌇\n"
                      f"The common nest now has {common_nest['twigs']} twigs and {new_common_seeds} seeds.{bonus_msg}\n"
                      f"You have {remaining} {'action' if remaining == 1 else 'actions'} remaining today.")

    @app_commands.command(name='donate_seeds', description='Move seeds from your nest to the common nest')
    @app_commands.describe(amount='Number of seeds to donate')
    async def move_seeds_own(self, interaction: discord.Interaction, amount: int):
        await interaction.response.defer()
        log_debug(f"move_seeds_own called by {interaction.user.id} for {amount} seeds")
        user_id = str(interaction.user.id)

        if amount <= 0:
            await interaction.followup.send("Please specify a positive number of seeds to move!")
            return

        player = await db.load_player(user_id)
        common_nest = await db.load_common_nest()

        if amount > player["seeds"]:
            await interaction.followup.send("You don't have enough seeds in your nest! 🏡")
            return

        if common_nest["seeds"] + amount > common_nest["twigs"]:
            await interaction.followup.send("The common nest doesn't have enough space! 🌇")
            return

        await db.increment_player_field(user_id, "seeds", -amount)
        await db.increment_common_nest("seeds", amount)

        new_player_seeds = player["seeds"] - amount
        new_common_seeds = common_nest["seeds"] + amount
        await interaction.followup.send(f"Moved {amount} seeds from your nest to the common nest!\n"
                      f"Your nest: {player['twigs']} twigs, {new_player_seeds} seeds\n"
                      f"Common nest: {common_nest['twigs']} twigs, {new_common_seeds} seeds")

    @app_commands.command(name='borrow_seeds', description='Move seeds from the common nest to your nest')
    @app_commands.describe(amount='Number of seeds to borrow')
    async def move_seeds_common(self, interaction: discord.Interaction, amount: int):
        await interaction.response.defer()
        log_debug(f"move_seeds_common called by {interaction.user.id} for {amount} seeds")
        user_id = str(interaction.user.id)

        if amount <= 0:
            await interaction.followup.send("Please specify a positive number of seeds to move!")
            return

        player = await db.load_player(user_id)
        common_nest = await db.load_common_nest()

        if amount > common_nest["seeds"]:
            await interaction.followup.send("There aren't enough seeds in the common nest! 🌇")
            return

        if player["seeds"] + amount > player["twigs"]:
            await interaction.followup.send("Your nest doesn't have enough space! 🏡")
            return

        await db.increment_common_nest("seeds", -amount)
        await db.increment_player_field(user_id, "seeds", amount)

        new_player_seeds = player["seeds"] + amount
        new_common_seeds = common_nest["seeds"] - amount
        await interaction.followup.send(f"Moved {amount} seeds from the common nest to your nest!\n"
                      f"Your nest: {player['twigs']} twigs, {new_player_seeds} seeds\n"
                      f"Common nest: {common_nest['twigs']} twigs, {new_common_seeds} seeds")

async def setup(bot):
    await bot.add_cog(SeedCommands(bot))
