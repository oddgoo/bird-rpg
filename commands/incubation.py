from discord.ext import commands
import discord
from datetime import datetime

from data.storage import load_data, save_data
from data.models import (
    get_personal_nest, get_remaining_actions, record_actions,
    has_brooded_egg, record_brooding, get_egg_cost,
    get_total_chicks, select_random_bird_species
)
from utils.logging import log_debug
from utils.time_utils import get_time_until_reset, get_current_date

class IncubationCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='lay_egg')
    async def lay_egg(self, ctx):
        """Convert seeds into an egg in your nest"""
        log_debug(f"lay_egg called by {ctx.author.id}")
        data = load_data()
        nest = get_personal_nest(data, ctx.author.id)

        # Check if nest already has an egg
        if "egg" in nest and nest["egg"] is not None:
            await ctx.send("Your nest already has an egg! 🥚")
            return

        # Calculate egg cost based on number of chicks
        egg_cost = get_egg_cost(nest)
        
        # Check if enough seeds
        if nest["seeds"] < egg_cost:
            await ctx.send(f"You need {egg_cost} seeds to lay an egg! You only have {nest['seeds']} seeds. 🌰")
            return

        # Create the egg
        nest["seeds"] -= egg_cost
        nest["egg"] = {
            "brooding_progress": 0,
            "brooded_by": []
        }
        
        save_data(data)
        await ctx.send(f"You laid an egg! It cost {egg_cost} seeds. 🥚\n"
                      f"The egg needs to be brooded 10 times to hatch.\n"
                      f"Your nest now has {nest['seeds']} seeds remaining.")

    @commands.command(name='brood')
    async def brood(self, ctx, target_user: discord.Member = None):
        """Brood an egg to help it hatch"""
        if target_user is None:
            target_user = ctx.author

        log_debug(f"brood called by {ctx.author.id} for {target_user.id}")
        data = load_data()

        # Check if brooder has actions
        remaining_actions = get_remaining_actions(data, ctx.author.id)
        if remaining_actions <= 0:
            await ctx.send(f"You've used all your actions for today! Come back in {get_time_until_reset()}! 🌙")
            return

        # Get target's nest
        target_nest = get_personal_nest(data, target_user.id)

        # Check if target has an egg
        if "egg" not in target_nest or target_nest["egg"] is None:
            await ctx.send(f"{'You don’t' if target_user == ctx.author else f'{target_user.display_name} doesn’t'} have an egg to brood! 🥚")
            return

        # Check if already brooded today
        today = today = get_current_date()
        if has_brooded_egg(data, ctx.author.id, target_user.id):
            await ctx.send(f"You've already brooded this egg today! Come back in {get_time_until_reset()}! 🥚")
            return

        # Record brooding
        record_brooding(data, ctx.author.id, target_user.id)
        target_nest["egg"]["brooding_progress"] += 1
        record_actions(data, ctx.author.id, 1)

        # Check if egg is ready to hatch
        if target_nest["egg"]["brooding_progress"] >= 10:
            bird_species = select_random_bird_species()
            chick = {
                "commonName": bird_species["commonName"],
                "scientificName": bird_species["scientificName"]
            }
            target_nest["chicks"].append(chick)
            target_nest["egg"] = None
            save_data(data)
            await ctx.send(f"🐣 The egg has hatched into a gorgeous **{chick['commonName']}** ({chick['scientificName']})! {target_user.display_name} now has {get_total_chicks(target_nest)} {'chick' if get_total_chicks(target_nest) == 1 else 'chicks'}! 🐦")
        else:
            save_data(data)
            remaining = 10 - target_nest["egg"]["brooding_progress"]
            await ctx.send(f"You brooded the egg! {remaining} more {'brood' if remaining == 1 else 'broods'} needed until it hatches. 🥚")

async def setup(bot):
    await bot.add_cog(IncubationCommands(bot))
