from discord.ext import commands

from data.storage import load_data, save_data
from data.models import get_personal_nest, get_common_nest, get_remaining_actions, record_actions
from utils.logging import log_debug
from utils.time_utils import get_time_until_reset

class BuildCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='build_nest_own', aliases=['build_nests_own'])
    async def build_nest_own(self, ctx, amount: int = 1):
        log_debug(f"build_nest_own called by {ctx.author.id} for {amount}")
        data = load_data()
        
        if amount < 1:
            await ctx.send("Please specify a positive number of twigs to add! 🪹")
            return
        
        remaining_actions = get_remaining_actions(data, ctx.author.id)
        if remaining_actions <= 0:
            await ctx.send(f"You've used all your actions for today! Come back in {get_time_until_reset()}! 🌙")
            return
        
        amount = min(amount, remaining_actions)
        
        nest = get_personal_nest(data, ctx.author.id)
        nest["twigs"] += amount
        record_actions(data, ctx.author.id, amount)
        
        save_data(data)
        remaining = get_remaining_actions(data, ctx.author.id)
        await ctx.send(f"Added {amount} {'twig' if amount == 1 else 'twigs'} to your nest! 🪹\n"
                      f"Your nest now has {nest['twigs']} twigs and {nest['seeds']} seeds.\n"
                      f"You have {remaining} {'action' if remaining == 1 else 'actions'} remaining today.")

    @commands.command(name='build_nest_common', aliases=['build_nests_common'])
    async def build_nest_common(self, ctx, amount: int = 1):
        log_debug(f"build_nest_common called by {ctx.author.id} for {amount}")
        data = load_data()
        
        if amount < 1:
            await ctx.send("Please specify a positive number of twigs to add! 🪺")
            return
        
        remaining_actions = get_remaining_actions(data, ctx.author.id)
        if remaining_actions <= 0:
            await ctx.send(f"You've used all your actions for today! Come back in {get_time_until_reset()}! 🌙")
            return
        
        amount = min(amount, remaining_actions)
        
        data["common_nest"]["twigs"] += amount
        record_actions(data, ctx.author.id, amount)
        
        save_data(data)
        nest = data["common_nest"]
        remaining = get_remaining_actions(data, ctx.author.id)
        await ctx.send(f"Added {amount} {'twig' if amount == 1 else 'twigs'} to the common nest! 🪺\n"
                      f"The common nest now has {nest['twigs']} twigs and {nest['seeds']} seeds.\n"
                      f"You have {remaining} {'action' if remaining == 1 else 'actions'} remaining today.")

async def setup(bot):
    await bot.add_cog(BuildCommands(bot))
    log_debug("BuildCommands cog has been added.")