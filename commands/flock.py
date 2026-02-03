import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from datetime import datetime, timedelta

import data.storage as db
from data.models import add_bonus_actions, get_extra_garden_space
from config.config import MAX_GARDEN_SIZE

class FlockCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_flock = None  # Store the single active flock session

    @app_commands.command(name='start_flock', description='Start a pomodoro flock session')
    async def start_flock(self, interaction: discord.Interaction):
        """Start a pomodoro flock session"""
        await interaction.response.defer()
        if self.active_flock is not None:
            time_remaining = (self.active_flock['end_time'] - datetime.now()).total_seconds() / 60
            if time_remaining > 0:
                await interaction.followup.send(f"\u274C There's already an active flock session! Use `/join_flock` to join it ({time_remaining:.0f} minutes remaining)")
                return

        # Create new flock session
        self.active_flock = {
            'leader': interaction.user,
            'members': [interaction.user],
            'start_time': datetime.now(),
            'end_time': datetime.now() + timedelta(minutes=60),
            'channel': interaction.channel  # Store the channel
        }

        await interaction.followup.send(f"\U0001F345 {interaction.user.mention} has started a pomodoro flock! The tomato goddess is pleased! Join anytime during the next hour with `/join_flock` to be part of the group (then head to the #pomobirdo channel if you wish).")

        # Wait for session to complete
        await asyncio.sleep(3600)  # 3600 seconds = 60 minutes

        if self.active_flock:
            # Get extra garden space from research progress
            extra_garden_space = await get_extra_garden_space()

            # Update garden sizes and add bonus actions for all participants via DB
            for member in self.active_flock['members']:
                member_id = str(member.id)
                player = await db.load_player(member_id)

                # Update garden size
                current_garden = player.get("garden_size", 0)
                if current_garden < MAX_GARDEN_SIZE + extra_garden_space:
                    await db.increment_player_field(member_id, "garden_size", 1)

                # Add bonus actions
                await add_bonus_actions(member_id, 3)

            # End session and notify
            channel = self.active_flock['channel']  # Get the stored channel
            members_mentions = ' '.join([member.mention for member in self.active_flock['members']])
            await channel.send(f"\U0001F345 The pomodoro flock has ended! {members_mentions} have received 3 bonus actions for today and may have grown their garden capacity (if not already at the maximum)")
            self.active_flock = None

    @app_commands.command(name='join_flock', description='Join the active flock session')
    async def join_flock(self, interaction: discord.Interaction):
        """Join the active flock session"""
        await interaction.response.defer()
        if not self.active_flock:
            await interaction.followup.send("\u274C There is no active flock session! Start one with `/start_flock`")
            return

        if datetime.now() > self.active_flock['end_time']:
            await interaction.followup.send("\u274C This flock session has already ended!")
            return

        if interaction.user in self.active_flock['members']:
            await interaction.followup.send("\u274C You're already in this flock!")
            return

        # Add member to flock
        self.active_flock['members'].append(interaction.user)
        time_remaining = (self.active_flock['end_time'] - datetime.now()).total_seconds() / 60
        await interaction.followup.send(f"\U0001F345 {interaction.user.mention} has joined the flock! {time_remaining:.0f} minutes remaining in the session. Get ready to focus together!")

async def setup(bot):
    await bot.add_cog(FlockCommands(bot))
