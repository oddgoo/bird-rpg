import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from data.storage import load_data, save_data
from datetime import datetime, timedelta
from config.config import MAX_GARDEN_SIZE
from data.models import add_bonus_actions, get_personal_nest, get_extra_garden_space

class FlockCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_flock = None  # Store the single active flock session

    @app_commands.command(name='start_flock', description='Start a pomodoro flock session')
    async def start_flock(self, interaction: discord.Interaction):
        """Start a pomodoro flock session"""
        if self.active_flock is not None:
            time_remaining = (self.active_flock['end_time'] - datetime.now()).total_seconds() / 60
            if time_remaining > 0:
                await interaction.response.send_message(f"❌ There's already an active flock session! Use `/join_flock` to join it ({time_remaining:.0f} minutes remaining)")
                return

        # Create new flock session
        self.active_flock = {
            'leader': interaction.user,
            'members': [interaction.user],
            'start_time': datetime.now(),
            'end_time': datetime.now() + timedelta(minutes=60),
            'channel': interaction.channel  # Store the channel
        }

        await interaction.response.send_message(f"🍅 {interaction.user.mention} has started a pomodoro flock! The tomato goddess is pleased! Join anytime during the next hour with `/join_flock` to be part of the group (then head to the #pomobirdo channel if you wish).")

        # Wait for session to complete
        await asyncio.sleep(3600)  # 3600 seconds = 60 minutes
        
        if self.active_flock:
            # Update garden sizes and add bonus actions for all participants
            data = load_data()
            for member in self.active_flock['members']:
                # Get the member's nest using the helper function
                nest = get_personal_nest(data, member.id)
                
                # Update garden size
                if "garden_size" not in nest:
                    nest["garden_size"] = 0
                
                # Get extra garden space from research progress
                extra_garden_space = get_extra_garden_space()
                
                # Check if garden size would exceed the maximum (considering extra space)
                if nest["garden_size"] < MAX_GARDEN_SIZE + extra_garden_space:
                    nest["garden_size"] += 1
                
                # Add bonus actions
                add_bonus_actions(data, member.id, 3)  # Add 3 bonus actions like in singing
            save_data(data)

            # End session and notify
            channel = self.active_flock['channel'] # Get the stored channel
            members_mentions = ' '.join([member.mention for member in self.active_flock['members']])
            await channel.send(f"🍅 The pomodoro flock has ended! {members_mentions} have received 3 bonus actions for today and may have grown their garden capacity (if not already at the maximum)")
            self.active_flock = None

    @app_commands.command(name='join_flock', description='Join the active flock session')
    async def join_flock(self, interaction: discord.Interaction):
        """Join the active flock session"""
        if not self.active_flock:
            await interaction.response.send_message("❌ There is no active flock session! Start one with `/start_flock`")
            return
        
        if datetime.now() > self.active_flock['end_time']:
            await interaction.response.send_message("❌ This flock session has already ended!")
            return

        if interaction.user in self.active_flock['members']:
            await interaction.response.send_message("❌ You're already in this flock!")
            return

        # Add member to flock
        self.active_flock['members'].append(interaction.user)
        time_remaining = (self.active_flock['end_time'] - datetime.now()).total_seconds() / 60
        await interaction.response.send_message(f"🍅 {interaction.user.mention} has joined the flock! {time_remaining:.0f} minutes remaining in the session. Get ready to focus together!")

async def setup(bot):
    await bot.add_cog(FlockCommands(bot))
