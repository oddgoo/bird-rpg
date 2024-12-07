import discord
from discord.ext import commands
import asyncio
from data.storage import load_data, save_data
from datetime import datetime, timedelta
from data.models import add_bonus_actions

class FlockCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_flocks = {}  # Store active flock sessions

    @commands.command()
    async def start_flock(self, ctx):
        """Start a pomodoro flock session"""
        if ctx.author.id in self.active_flocks.values():
            await ctx.send("❌ You're already in an active flock session!")
            return

        # Create new flock session
        self.active_flocks[ctx.author.id] = {
            'leader': ctx.author,
            'members': [ctx.author],
            'start_time': datetime.now(),
            'joining_deadline': datetime.now() + timedelta(minutes=10)
        }

        await ctx.send(f"🍅 {ctx.author.mention} has started a pomodoro flock! The tomato goddess is pleased! Join in the next 10 minutes with `!join_flock {ctx.author.mention}` to be part of the group")

        # Wait for joining period to end, then start the session
        await asyncio.sleep(600)  # 10 minutes
        if ctx.author.id in self.active_flocks:
            flock = self.active_flocks[ctx.author.id]
            members_mentions = ' '.join([member.mention for member in flock['members']])
            await ctx.send(f"🍅 The flock session is starting! {members_mentions} Go to the #video-chat channel to join and focus. The session will end in 60 minutes.")

            # Wait for session to complete
            await asyncio.sleep(3600)  # 60 minutes
            
            # Update garden sizes and add bonus actions for all participants
            data = load_data()
            for member in flock['members']:
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
            members_mentions = ' '.join([member.mention for member in flock['members']])
            await ctx.send(f"🍅 The pomodoro flock has ended! {members_mentions} have grown their gardens by +1 and received 5 bonus actions! Tweet tweet!")
            del self.active_flocks[ctx.author.id]

    @commands.command()
    async def join_flock(self, ctx, leader: discord.Member):
        """Join an existing pomodoro flock session"""
        if leader.id not in self.active_flocks:
            await ctx.send("❌ There is no active flock session from this user!")
            return

        flock = self.active_flocks[leader.id]
        
        if datetime.now() > flock['joining_deadline']:
            await ctx.send("❌ The joining period for this flock has ended!")
            return

        if ctx.author in flock['members']:
            await ctx.send("❌ You're already in this flock!")
            return

        if ctx.author.id in self.active_flocks.values():
            await ctx.send("❌ You're already in an active flock session!")
            return

        # Add member to flock
        flock['members'].append(ctx.author)
        await ctx.send(f"🍅 {ctx.author.mention} has joined {leader.mention}'s pomodoro flock! Get ready to focus together!")

async def setup(bot):
    await bot.add_cog(FlockCommands(bot))
