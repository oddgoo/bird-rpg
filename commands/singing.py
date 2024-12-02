from datetime import datetime
import discord

from discord.ext import commands
from data.storage import load_data, save_data
from data.models import (
    get_remaining_actions, record_actions, has_been_sung_to_by,
    record_song, add_bonus_actions, get_personal_nest, get_singing_bonus
)
from utils.logging import log_debug
from utils.time_utils import get_time_until_reset, get_current_date

class SingingCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='sing', aliases=['inspire'])
    async def sing(self, ctx, *target_users: discord.Member):
        """Give other users extra actions for the day. Each bird can only sing once to the same target per day."""
        # Basic input validation
        if not target_users:
            await ctx.send("Please specify users to sing to! Usage: !sing @user1 @user2 ...")
            return
        
        log_debug(f"sing command called by {ctx.author.id} for users {[user.id for user in target_users]}")
        data = load_data()
        
        # Get singer's remaining actions
        singer_remaining_actions = get_remaining_actions(data, ctx.author.id)
        if singer_remaining_actions <= 0:
            await ctx.send(f"You don't have any actions left to sing! Come back in {get_time_until_reset()}! 🌙")
            return

        successful_targets = []
        skipped_targets = []

        # Process each target user
        for target_user in target_users:
            # Skip if out of actions
            if singer_remaining_actions <= 0:
                skipped_targets.append((target_user, "no actions left"))
                continue
            
            # Skip bots
            if target_user.bot:
                skipped_targets.append((target_user, "is a bot"))
                continue
            
            # Skip self
            if ctx.author.id == target_user.id:
                skipped_targets.append((target_user, "is yourself"))
                continue
            
            # Skip if already sung to
            if has_been_sung_to_by(data, ctx.author.id, target_user.id):
                skipped_targets.append((target_user, "already sung to today"))
                continue
            
            singer_nest = get_personal_nest(data, ctx.author.id)
            bonus_inspiration = get_singing_bonus(singer_nest)

            # Record the song and add bonus actions
            record_song(data, ctx.author.id, target_user.id)
            add_bonus_actions(data, target_user.id, 3 + bonus_inspiration)
            record_actions(data, ctx.author.id, 1)
            singer_remaining_actions -= 1
            successful_targets.append((target_user, bonus_inspiration))

        save_data(data)
        
        # Construct response message
        if not successful_targets:
            message = ["❌ Couldn't sing to any of the specified users:"]
            for user, reason in skipped_targets:
                message.append(f"• {user.display_name} ({reason})")
        else:
            message = ["🎵 Your beautiful song has inspired:"]
            for user, bonus in successful_targets:
                base_msg = f"**{user.display_name}** (+3"
                if bonus > 0:
                    base_msg += f" +{bonus}✨"
                base_msg += " actions)"
                message.append(base_msg)
            
            if skipped_targets:
                message.append("\n⚠️ Couldn't sing to:")
                for user, reason in skipped_targets:
                    message.append(f"• {user.display_name} ({reason})")
            
            singer_actions_left = get_remaining_actions(data, ctx.author.id)
            message.append(f"\n(You have {singer_actions_left} {'action' if singer_actions_left == 1 else 'actions'} remaining)")
        
        await ctx.send("\n".join(message))

async def setup(bot):
    await bot.add_cog(SingingCommands(bot))