from datetime import datetime
import discord
from discord.ext import commands
from discord import app_commands

from data.storage import load_data, save_data
from data.models import (
    get_remaining_actions, record_actions, has_been_sung_to_by,
    record_song, add_bonus_actions, get_personal_nest, get_singing_bonus,
    get_singing_inspiration_chance
)
from utils.logging import log_debug
from utils.time_utils import get_time_until_reset, get_current_date
from config.config import DEBUG

class SingingCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='sing', description='Give other users extra actions for the day')
    @app_commands.describe(target_users='The users to sing to (mention them)')
    async def sing(self, interaction: discord.Interaction, target_users: str):
        """Give other users extra actions for the day. Each bird can only sing once to the same target per day."""
        # Parse mentioned users
        mentioned_users = []
        for user_id in target_users.split():
            try:
                user_id = user_id.strip('<@!>')
                user = await self.bot.fetch_user(int(user_id))
                mentioned_users.append(user)
            except:
                continue

        if not mentioned_users:
            await interaction.response.send_message("Please specify users to sing to! Usage: /sing @user1 @user2 ...")
            return
        
        log_debug(f"sing command called by {interaction.user.id} for users {[user.id for user in mentioned_users]}")
        data = load_data()
        
        # Get singer's remaining actions
        singer_remaining_actions = get_remaining_actions(data, interaction.user.id)
        if singer_remaining_actions <= 0:
            await interaction.response.send_message(f"You don't have any actions left to sing! Come back in {get_time_until_reset()}! 🌙")
            return

        successful_targets = []
        skipped_targets = []

        # Process each target user
        for target_user in mentioned_users:
            # Skip if out of actions
            if singer_remaining_actions <= 0:
                skipped_targets.append((target_user, "no actions left"))
                continue
            
            # Skip bots
            if target_user.bot:
                skipped_targets.append((target_user, "is a bot"))
                continue
            
            # Skip self unless in debug mode
            if interaction.user.id == target_user.id and not DEBUG:
                skipped_targets.append((target_user, "is yourself"))
                continue
            
            # Skip if already sung to
            if has_been_sung_to_by(data, interaction.user.id, target_user.id):
                skipped_targets.append((target_user, "already sung to today"))
                continue
            
            singer_nest = get_personal_nest(data, interaction.user.id)
            bonus_actions = get_singing_bonus(singer_nest)
            inspiration_bonus = get_singing_inspiration_chance(data, singer_nest)
            
            # Record the song and add bonus actions
            record_song(data, interaction.user.id, target_user.id)
            add_bonus_actions(data, target_user.id, 3 + bonus_actions)
            record_actions(data, interaction.user.id, 1, "sing")
            
            # Add inspiration from finches
            if inspiration_bonus > 0:
                singer_nest["inspiration"] += inspiration_bonus
            
            singer_remaining_actions -= 1
            successful_targets.append((target_user, bonus_actions, inspiration_bonus))

        save_data(data)
        
        # Construct response message
        if not successful_targets:
            message = ["❌ Couldn't sing to any of the specified users:"]
            for user, reason in skipped_targets:
                message.append(f"• {user.display_name} ({reason})")
        else:
            message = ["🎵 Your beautiful song has inspired:"]
            for user, action_bonus, inspiration_gained in successful_targets:
                base_msg = f"**{user.display_name}** (+3"
                if action_bonus > 0:
                    base_msg += f" +{action_bonus}✨"
                base_msg += " actions)"
                message.append(base_msg)
            
            if any(insp > 0 for _, _, insp in successful_targets):
                message.append(f"\n✨ Your finches' songs brought you +{sum(insp for _, _, insp in successful_targets)} inspiration!")
            
            if skipped_targets:
                message.append("\n Couldn't sing to:")
                for user, reason in skipped_targets:
                    message.append(f"• {user.display_name} ({reason})")
            
            singer_actions_left = get_remaining_actions(data, interaction.user.id)
            message.append(f"\n(You have {singer_actions_left} {'action' if singer_actions_left == 1 else 'actions'} remaining)")
        
        await interaction.response.send_message("\n".join(message))

async def setup(bot):
    await bot.add_cog(SingingCommands(bot))