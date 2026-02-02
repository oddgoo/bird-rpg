from discord.ext import commands
from discord import app_commands
import discord
import json
import os

import data.storage as db
from data.models import get_extra_bird_space, add_bonus_actions
from utils.logging import log_debug
from config.config import MAX_BIRDS_PER_NEST
from commands.foraging import load_treasures

class SocialCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='entrust', description='Give one of your birds to another user')
    @app_commands.describe(
        bird_name='The common name of the bird to give',
        target_user='The user to give the bird to'
    )
    async def entrust(self, interaction: discord.Interaction, bird_name: str, target_user: discord.User):
        try:
            # Don't allow giving birds to yourself
            if target_user.id == interaction.user.id:
                await interaction.response.send_message("\u274C You can't give a bird to yourself!")
                return

            # Don't allow giving birds to bots
            if target_user.bot:
                await interaction.response.send_message("\u274C You can't give birds to bots!")
                return

            log_debug(f"entrust called by {interaction.user.id} giving '{bird_name}' to {target_user.id}")

            user_id = str(interaction.user.id)
            target_id = str(target_user.id)

            # Check if receiver's nest is at the limit before removing bird
            extra_bird_space = await get_extra_bird_space()
            max_birds = MAX_BIRDS_PER_NEST + extra_bird_space
            receiver_birds = await db.get_player_birds(target_id)

            if len(receiver_birds) >= max_birds:
                await interaction.response.send_message(f"\u274C {target_user.display_name}'s nest is already full! They have reached the limit of {max_birds} birds.")
                return

            # Remove bird from giver's nest
            removed_bird = await db.remove_bird_by_name(user_id, bird_name)
            if not removed_bird:
                await interaction.response.send_message(f"\u274C You don't have a {bird_name} in your nest!")
                return

            # Add bird to receiver's nest
            await db.add_bird(target_id, removed_bird["common_name"], removed_bird["scientific_name"])

            # Get updated bird counts for the embed
            giver_birds = await db.get_player_birds(user_id)
            receiver_birds = await db.get_player_birds(target_id)

            # Create embed for success message
            embed = discord.Embed(
                title="\U0001F91D Bird Entrusted",
                description=f"**{removed_bird['common_name']}** (*{removed_bird['scientific_name']}*) has been given to {target_user.mention}!",
                color=discord.Color.green()
            )
            embed.add_field(
                name="From",
                value=f"{interaction.user.display_name}'s Nest ({len(giver_birds)} birds remaining)",
                inline=True
            )
            embed.add_field(
                name="To",
                value=f"{target_user.display_name}'s Nest (now has {len(receiver_birds)} birds)",
                inline=True
            )

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            log_debug(f"Error in entrust command: {e}")
            await interaction.response.send_message("\u274C Usage: /entrust <bird_name> <@user>")

    @app_commands.command(name='regurgitate', description='Give some of your bonus actions to another user')
    @app_commands.describe(
        target_user='The user to give bonus actions to',
        amount='The number of bonus actions to give'
    )
    async def regurgitate(self, interaction: discord.Interaction, target_user: discord.User, amount: int):
        try:
            # Don't allow giving actions to yourself
            if target_user.id == interaction.user.id:
                await interaction.response.send_message("\u274C You can't regurgitate actions to yourself!")
                return

            if amount <= 0:
                await interaction.response.send_message("\u274C You must regurgitate a positive amount of actions!")
                return

            log_debug(f"regurgitate called by {interaction.user.id} giving {amount} bonus_actions to {target_user.id}")

            user_id = str(interaction.user.id)
            target_id = str(target_user.id)

            # Load giver's player data to check bonus actions
            giver_player = await db.load_player(user_id)

            # Check if giver has enough bonus actions
            if giver_player.get("bonus_actions", 0) < amount:
                await interaction.response.send_message(f"\u274C You don't have enough bonus actions! You only have {giver_player.get('bonus_actions', 0)}.")
                return

            # Transfer bonus actions: decrement giver, increment receiver
            await db.increment_player_field(user_id, "bonus_actions", -amount)
            await add_bonus_actions(target_id, amount)

            # Reload both players for the embed display
            giver_player = await db.load_player(user_id)
            receiver_player = await db.load_player(target_id)

            # Create embed for success message
            embed = discord.Embed(
                title="\u2764\uFE0F Actions Regurgitated",
                description=f"You have successfully given **{amount} bonus action(s)** to {target_user.mention}!",
                color=discord.Color.magenta()
            )
            embed.add_field(
                name="From",
                value=f"{interaction.user.display_name} (now has {giver_player.get('bonus_actions', 0)} bonus actions)",
                inline=True
            )
            embed.add_field(
                name="To",
                value=f"{target_user.display_name} (now has {receiver_player.get('bonus_actions', 0)} bonus actions)",
                inline=True
            )

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            log_debug(f"Error in regurgitate command: {e}")
            await interaction.response.send_message(f"\u274C An error occurred. Usage: /regurgitate <@user> <amount>")

    @app_commands.command(name='gift_treasure', description='Give a treasure to another user')
    @app_commands.describe(treasure_name='The name of the treasure to gift', target_user='The user to give the treasure to')
    async def gift_treasure(self, interaction: discord.Interaction, treasure_name: str, target_user: discord.User):
        if target_user.id == interaction.user.id:
            await interaction.response.send_message("You can't gift a treasure to yourself!", ephemeral=True)
            return

        user_id = str(interaction.user.id)
        target_id = str(target_user.id)

        # Get giver's treasures from DB
        giver_treasures = await db.get_player_treasures(user_id)

        if not giver_treasures:
            await interaction.response.send_message("You don't have any treasures to gift!", ephemeral=True)
            return

        treasures_data = load_treasures()
        all_treasures = {t["id"]: t for loc in treasures_data.values() for t in loc}

        # Find the treasure by name in the giver's inventory
        found_treasure_id = None
        for treasure_row in giver_treasures:
            t_id = treasure_row["treasure_id"]
            if all_treasures.get(t_id, {}).get("name", "").lower() == treasure_name.lower():
                found_treasure_id = t_id
                break

        if not found_treasure_id:
            await interaction.response.send_message(f"Treasure '{treasure_name}' not found in your inventory.", ephemeral=True)
            return

        # Remove treasure from giver's inventory
        removed = await db.remove_player_treasure(user_id, found_treasure_id)
        if not removed:
            await interaction.response.send_message(f"Failed to remove treasure from your inventory.", ephemeral=True)
            return

        # Add treasure to receiver's inventory
        await db.add_player_treasure(target_id, found_treasure_id)

        treasure_info = all_treasures.get(found_treasure_id)
        embed = discord.Embed(
            title="\U0001F381 Treasure Gifted!",
            description=f"{interaction.user.mention} has gifted a **{treasure_info['name']}** to {target_user.mention}!",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(SocialCommands(bot))
