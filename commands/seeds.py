from discord.ext import commands

from data.storage import load_data, save_data
from data.models import get_personal_nest, get_common_nest, get_remaining_actions, record_actions
from utils.logging import log_debug
from utils.time_utils import get_time_until_reset

class SeedCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='add_seed', aliases=['add_seeds','add_seeds_own','add_seed_own'])
    async def add_seed_own(self, ctx, amount: int = 1):
        log_debug(f"add_seed_own called by {ctx.author.id} for {amount}")
        data = load_data()
        
        if amount < 1:
            await ctx.send("Please specify a positive number of seeds to add! 🌱")
            return
        
        remaining_actions = get_remaining_actions(data, ctx.author.id)
        if remaining_actions <= 0:
            await ctx.send(f"You've used all your actions for today! Come back in {get_time_until_reset()}! 🌙")
            return
        
        nest = get_personal_nest(data, ctx.author.id)
        space_available = nest["twigs"] - nest["seeds"]
        amount = min(amount, space_available, remaining_actions)
        
        if amount <= 0:
            await ctx.send("Your nest is full! Add more twigs to store more seeds. 🪹")
            return
        
        nest["seeds"] += amount
        record_actions(data, ctx.author.id, amount)
        
        save_data(data)
        remaining = get_remaining_actions(data, ctx.author.id)
        await ctx.send(f"Added {amount} {'seed' if amount == 1 else 'seeds'} to your nest! 🏡\n"
                      f"Your nest now has {nest['twigs']} twigs and {nest['seeds']} seeds.\n"
                      f"You have {remaining} {'action' if remaining == 1 else 'actions'} remaining today.")

    @commands.command(name='add_seed_common', aliases=['add_seeds_common'])
    async def add_seed_common(self, ctx, amount: int = 1):
        log_debug(f"add_seed_common called by {ctx.author.id} for {amount}")
        data = load_data()
        
        if amount < 1:
            await ctx.send("Please specify a positive number of seeds to add! 🌱")
            return
        
        remaining_actions = get_remaining_actions(data, ctx.author.id)
        if remaining_actions <= 0:
            await ctx.send(f"You've used all your actions for today! Come back in {get_time_until_reset()}! 🌙")
            return
        
        common_nest = data["common_nest"]
        space_available = common_nest["twigs"] - common_nest["seeds"]
        amount = min(amount, space_available, remaining_actions)
        
        if amount <= 0:
            await ctx.send("The common nest is full! Add more twigs to store more seeds. 🪺")
            return
        
        common_nest["seeds"] += amount
        record_actions(data, ctx.author.id, amount)
        
        save_data(data)
        remaining = get_remaining_actions(data, ctx.author.id)
        await ctx.send(f"Added {amount} {'seed' if amount == 1 else 'seeds'} to the common nest! 🌇\n"
                      f"The common nest now has {common_nest['twigs']} twigs and {common_nest['seeds']} seeds.\n"
                      f"You have {remaining} {'action' if remaining == 1 else 'actions'} remaining today.")

    @commands.command(name='donate_seeds', aliases=['donate_seed','move_seeds_own'])
    async def move_seeds_own(self, ctx, amount: int):
        log_debug(f"move_seeds_own called by {ctx.author.id} for {amount} seeds")
        data = load_data()
        
        if amount <= 0:
            await ctx.send("Please specify a positive number of seeds to move!")
            return

        nest = get_personal_nest(data, ctx.author.id)
        common_nest = data["common_nest"]
        
        if amount > nest["seeds"]:
            await ctx.send("You don't have enough seeds in your nest! 🏡")
            return
        
        if common_nest["seeds"] + amount > common_nest["twigs"]:
            await ctx.send("The common nest doesn't have enough space! 🌇")
            return
        
        nest["seeds"] -= amount
        common_nest["seeds"] += amount
        
        save_data(data)
        await ctx.send(f"Moved {amount} seeds from your nest to the common nest!\n"
                      f"Your nest: {nest['twigs']} twigs, {nest['seeds']} seeds\n"
                      f"Common nest: {common_nest['twigs']} twigs, {common_nest['seeds']} seeds")


    @commands.command(name='borrow_seeds', aliases=['borrow_seed','move_seeds_common','move_seed_common'])
    async def move_seeds_common(self, ctx, amount: int):
        log_debug(f"move_seeds_common called by {ctx.author.id} for {amount} seeds")
        data = load_data()
        
        if amount <= 0:
            await ctx.send("Please specify a positive number of seeds to move!")
            return
        
        nest = get_personal_nest(data, ctx.author.id)
        common_nest = data["common_nest"]
        
        if amount > common_nest["seeds"]:
            await ctx.send("There aren't enough seeds in the common nest! 🌇")
            return
        
        if nest["seeds"] + amount > nest["twigs"]:
            await ctx.send("Your nest doesn't have enough space! 🏡")
            return
        
        common_nest["seeds"] -= amount
        nest["seeds"] += amount
        
        save_data(data)
        await ctx.send(f"Moved {amount} seeds from the common nest to your nest!\n"
                      f"Your nest: {nest['twigs']} twigs, {nest['seeds']} seeds\n"
                      f"Common nest: {common_nest['twigs']} twigs, {common_nest['seeds']} seeds")

async def setup(bot):
    await bot.add_cog(SeedCommands(bot))