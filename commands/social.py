from discord.ext import commands
from discord import app_commands
import discord
import json
import os

from data.storage import load_data, save_data
from data.models import get_personal_nest, get_total_chicks, get_extra_bird_space, record_actions, add_bonus_actions
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
                await interaction.response.send_message("❌ You can't give a bird to yourself!")
                return

            # Don't allow giving birds to bots
            if target_user.bot:
                await interaction.response.send_message("❌ You can't give birds to bots!")
                return

            log_debug(f"entrust called by {interaction.user.id} giving '{bird_name}' to {target_user.id}")
            data = load_data()

            # Get both nests
            giver_nest = get_personal_nest(data, interaction.user.id)
            receiver_nest = get_personal_nest(data, target_user.id)

            # Find the bird in giver's nest
            bird_to_give = None
            for i, bird in enumerate(giver_nest.get("chicks", [])):
                if bird["commonName"].lower() == bird_name.lower():
                    bird_to_give = giver_nest["chicks"].pop(i)
                    break

            if not bird_to_give:
                await interaction.response.send_message(f"❌ You don't have a {bird_name} in your nest!")
                return

            # Get extra bird space from research progress
            extra_bird_space = get_extra_bird_space()
            max_birds = MAX_BIRDS_PER_NEST + extra_bird_space
            
            # Check if receiver's nest is at the limit
            if get_total_chicks(receiver_nest) >= max_birds:
                # Put the bird back in the giver's nest
                giver_nest["chicks"].append(bird_to_give)
                await interaction.response.send_message(f"❌ {target_user.display_name}'s nest is already full! They have reached the limit of {max_birds} birds.")
                return

            # Add bird to receiver's nest
            if "chicks" not in receiver_nest:
                receiver_nest["chicks"] = []
            receiver_nest["chicks"].append(bird_to_give)

            save_data(data)

            # Create embed for success message
            embed = discord.Embed(
                title="🤝 Bird Entrusted",
                description=f"**{bird_to_give['commonName']}** (*{bird_to_give['scientificName']}*) has been given to {target_user.mention}!",
                color=discord.Color.green()
            )
            embed.add_field(
                name="From",
                value=f"{interaction.user.display_name}'s Nest ({len(giver_nest['chicks'])} birds remaining)",
                inline=True
            )
            embed.add_field(
                name="To",
                value=f"{target_user.display_name}'s Nest (now has {len(receiver_nest['chicks'])} birds)",
                inline=True
            )

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            log_debug(f"Error in entrust command: {e}")
            await interaction.response.send_message("❌ Usage: /entrust <bird_name> <@user>")

    @app_commands.command(name='regurgitate', description='Give some of your bonus actions to another user')
    @app_commands.describe(
        target_user='The user to give bonus actions to',
        amount='The number of bonus actions to give'
    )
    async def regurgitate(self, interaction: discord.Interaction, target_user: discord.User, amount: int):
        try:
            # Don't allow giving actions to yourself
            if target_user.id == interaction.user.id:
                await interaction.response.send_message("❌ You can't regurgitate actions to yourself!")
                return

            if amount <= 0:
                await interaction.response.send_message("❌ You must regurgitate a positive amount of actions!")
                return

            log_debug(f"regurgitate called by {interaction.user.id} giving {amount} bonus_actions to {target_user.id}")
            data = load_data()

            # Get both nests
            giver_nest = get_personal_nest(data, interaction.user.id)
            receiver_nest = get_personal_nest(data, target_user.id)

            # Check if giver has enough bonus actions
            if giver_nest.get("bonus_actions", 0) < amount:
                await interaction.response.send_message(f"❌ You don't have enough bonus actions! You only have {giver_nest.get('bonus_actions', 0)}.")
                return

            # Transfer bonus actions
            giver_nest["bonus_actions"] = giver_nest.get("bonus_actions", 0) - amount
            add_bonus_actions(data, target_user.id, amount) # Uses the existing function from models.py

            save_data(data)

            # Create embed for success message
            embed = discord.Embed(
                title="❤️ Actions Regurgitated",
                description=f"You have successfully given **{amount} bonus action(s)** to {target_user.mention}!",
                color=discord.Color.magenta()
            )
            embed.add_field(
                name="From",
                value=f"{interaction.user.display_name} (now has {giver_nest.get('bonus_actions', 0)} bonus actions)",
                inline=True
            )
            embed.add_field(
                name="To",
                value=f"{target_user.display_name} (now has {receiver_nest.get('bonus_actions', 0)} bonus actions)",
                inline=True
            )

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            log_debug(f"Error in regurgitate command: {e}")
            await interaction.response.send_message(f"❌ An error occurred. Usage: /regurgitate <@user> <amount>")

    @app_commands.command(name='gift_treasure', description='Give a treasure to another user')
    @app_commands.describe(treasure_name='The name of the treasure to gift', target_user='The user to give the treasure to')
    async def gift_treasure(self, interaction: discord.Interaction, treasure_name: str, target_user: discord.User):
        if target_user.id == interaction.user.id:
            await interaction.response.send_message("You can't gift a treasure to yourself!", ephemeral=True)
            return
        # if target_user.bot:
        #     await interaction.response.send_message("You can't gift treasures to bots!", ephemeral=True)
        #     return

        data = load_data()
        giver_nest = get_personal_nest(data, interaction.user.id)
        
        if not giver_nest.get("treasures"):
            await interaction.response.send_message("You don't have any treasures to gift!", ephemeral=True)
            return

        treasures_data = load_treasures()
        all_treasures = {t["id"]: t for loc in treasures_data.values() for t in loc}

        # Find the treasure by name
        found_treasure_id = None
        treasure_index = -1
        for i, t_id in enumerate(giver_nest["treasures"]):
            if all_treasures.get(t_id, {}).get("name", "").lower() == treasure_name.lower():
                found_treasure_id = t_id
                treasure_index = i
                break
        
        if not found_treasure_id:
            await interaction.response.send_message(f"Treasure '{treasure_name}' not found in your inventory.", ephemeral=True)
            return

        # Remove treasure from giver's inventory
        treasure_id = giver_nest["treasures"].pop(treasure_index)
        
        receiver_nest = get_personal_nest(data, target_user.id)
        if "treasures" not in receiver_nest:
            receiver_nest["treasures"] = []
        receiver_nest["treasures"].append(treasure_id)
        save_data(data)

        treasure_info = all_treasures.get(treasure_id)
        embed = discord.Embed(
            title="🎁 Treasure Gifted!",
            description=f"{interaction.user.mention} has gifted a **{treasure_info['name']}** to {target_user.mention}!",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(SocialCommands(bot))
