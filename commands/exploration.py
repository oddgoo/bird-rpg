from discord.ext import commands
from data.storage import load_data, save_data
from data.models import get_remaining_actions, record_actions
from utils.logging import log_debug
from utils.time_utils import get_time_until_reset

VALID_REGIONS = ['oceania']

class ExplorationCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='explore', aliases=['eggplsore'])
    async def explore(self, ctx, region: str, amount: int = 1):
        log_debug(f"explore called by {ctx.author.id} for {amount} in {region}")
        region = region.lower()
        
        if region not in VALID_REGIONS:
            await ctx.send(f"That region isn't available for exploration yet! Currently available: {', '.join(VALID_REGIONS)}")
            return
            
        data = load_data()
        
        if amount < 1:
            await ctx.send("Please specify a positive number of exploration points to add! 🗺️")
            return
            
        remaining_actions = get_remaining_actions(data, ctx.author.id)
        if remaining_actions <= 0:
            await ctx.send(f"You've used all your actions for today! Come back in {get_time_until_reset()}! 🌙")
            return
            
        # Initialize exploration data if it doesn't exist
        if "exploration" not in data:
            data["exploration"] = {}
        if region not in data["exploration"]:
            data["exploration"][region] = 0
            
        # Limit amount to remaining actions
        amount = min(amount, remaining_actions)
        
        # Add exploration points
        data["exploration"][region] += amount
        record_actions(data, ctx.author.id, amount, "explore")
        
        save_data(data)
        remaining = get_remaining_actions(data, ctx.author.id)
        await ctx.send(f"Added {amount} exploration {'point' if amount == 1 else 'points'} to {region}! 🗺️\n"
                      f"Total exploration in {region}: {data['exploration'][region]} points\n"
                      f"You have {remaining} {'action' if remaining == 1 else 'actions'} remaining today.")

async def setup(bot):
    await bot.add_cog(ExplorationCommands(bot))
