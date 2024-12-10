import discord
from discord.ext import commands
import asyncio
from data.storage import load_data, save_data
from datetime import datetime, timedelta
from data.models import add_bonus_actions, get_personal_nest

class FlockCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_flock = None  # Store the single active flock session

    @commands.command()
    async def start_flock(self, ctx):
        """Start a pomodoro flock session"""
        if self.active_flock is not None:
            time_remaining = (self.active_flock['end_time'] - datetime.now()).total_seconds() / 60
            if time_remaining > 0:
                await ctx.send(f"❌ There's already an active flock session! Use `!join_flock` to join it ({time_remaining:.0f} minutes remaining)")
                return

        # Create new flock session
        self.active_flock = {
            'leader': ctx.author,
            'members': [ctx.author],
            'start_time': datetime.now(),
            'end_time': datetime.now() + timedelta(minutes=60)
        }

        await ctx.send(f"🍅 {ctx.author.mention} has started a pomodoro flock! The tomato goddess is pleased! Join anytime during the next hour with `!join_flock` to be part of the group (then head to the #pomobirdo channel).")

        # Wait for session to complete
        await asyncio.sleep(5)  # 3600 seconds = 60 minutes
        
        if self.active_flock:
            # Update garden sizes and add bonus actions for all participants
            data = load_data()
            for member in self.active_flock['members']:
                # Get the member's nest using the helper function
                nest = get_personal_nest(data, member.id)
                
                # Update garden size
                if "garden_size" not in nest:
                    nest["garden_size"] = 0
                nest["garden_size"] += 1
                
                # Add bonus actions
                add_bonus_actions(data, member.id, 5)  # Add 5 bonus actions like in singing
            save_data(data)

            # End session and notify
            members_mentions = ' '.join([member.mention for member in self.active_flock['members']])
            await ctx.send(f"🍅 The pomodoro flock has ended! {members_mentions} have grown their garden capacity by +1 and received 5 bonus actions for today! 🍅")
            self.active_flock = None

    @commands.command()
    async def join_flock(self, ctx):
        """Join the active flock session"""
        if not self.active_flock:
            await ctx.send("❌ There is no active flock session! Start one with `!start_flock`")
            return
        
        if datetime.now() > self.active_flock['end_time']:
            await ctx.send("❌ This flock session has already ended!")
            return

        if ctx.author in self.active_flock['members']:
            await ctx.send("❌ You're already in this flock!")
            return

        # Add member to flock
        self.active_flock['members'].append(ctx.author)
        time_remaining = (self.active_flock['end_time'] - datetime.now()).total_seconds() / 60
        await ctx.send(f"🍅 {ctx.author.mention} has joined the flock! {time_remaining:.0f} minutes remaining in the session. Get ready to focus together!")

async def setup(bot):
    await bot.add_cog(FlockCommands(bot))
