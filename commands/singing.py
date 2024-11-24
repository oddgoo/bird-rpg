from datetime import datetime
import discord

from discord.ext import commands
from data.storage import load_data, save_data
from data.models import (
    get_remaining_actions, record_actions, has_been_sung_to_by,
    record_song, add_bonus_actions
)
from utils.logging import log_debug
from utils.time_utils import get_time_until_reset


class SingingCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='sing', aliases=['inspire'])
    async def sing(self, ctx, target_user: discord.Member = None):
        """Give another user 3 extra actions for the day. Each bird can only sing once to the same target per day."""
        # Basic input validation
        if target_user is None:
            await ctx.send("Please specify a user to sing to! Usage: !sing @user")
            return
        
        if target_user.bot:
            await ctx.send("You can't sing to a bot! 🤖")
            return
            
        log_debug(f"sing command called by {ctx.author.id} for user {target_user.id}")
        data = load_data()
        
        # Check if trying to sing to self
        if ctx.author.id == target_user.id:
            await ctx.send("You can't sing to yourself! 🎵")
            return
        
        # Check if singer has enough actions
        singer_remaining_actions = get_remaining_actions(data, ctx.author.id)
        if singer_remaining_actions <= 0:
            await ctx.send(f"You don't have any actions left to sing! Come back in {get_time_until_reset()}! 🌙")
            return
        
        # Check if singer has already sung to this target today
        if has_been_sung_to_by(data, ctx.author.id, target_user.id):
            await ctx.send(f"You've already sung to {target_user.display_name} today! 🎵")
            return
        
        # Record the song and add bonus actions
        record_song(data, ctx.author.id, target_user.id)
        add_bonus_actions(data, target_user.id, 3)
        record_actions(data, ctx.author.id, 1)  # Singing costs 1 action
        
        save_data(data)
        
        # Get total available actions for target
        today = datetime.now().strftime('%Y-%m-%d')
        actions_data = data["daily_actions"].get(str(target_user.id), {}).get(f"actions_{today}", {"used": 0, "bonus": 0})
        if isinstance(actions_data, (int, float)):
            actions_data = {"used": actions_data, "bonus": 0}
        total_actions = 3 + actions_data["bonus"]
        remaining_actions = total_actions - actions_data["used"]
        
        # Get singer's remaining actions
        singer_actions_left = get_remaining_actions(data, ctx.author.id)
        
        # Construct success message
        message = [
            f"🎵 {ctx.author.display_name}'s beautiful song has inspired {target_user.display_name}!",
            f"They now have {remaining_actions}/{total_actions} actions available for the next {get_time_until_reset()}! 🎶",
            f"(You have {singer_actions_left} {'action' if singer_actions_left == 1 else 'actions'} remaining)"
        ]
        
        await ctx.send("\n".join(message))

async def setup(bot):
    await bot.add_cog(SingingCommands(bot))