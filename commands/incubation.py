from discord.ext import commands
import discord
from datetime import datetime
import aiohttp  # Import aiohttp for asynchronous HTTP requests
import random

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

    async def process_brooding(self, ctx, target_user, data, remaining_actions):
        """Helper function to process brooding for a single user"""
        # Get target's nest
        target_nest = get_personal_nest(data, target_user.id)

        # Check if target has an egg
        if "egg" not in target_nest or target_nest["egg"] is None:
            return None, f"{'You don`t' if target_user == ctx.author else target_user.display_name + ' doesn`t'} have an egg to brood"

        # Check if already brooded today
        if has_brooded_egg(data, ctx.author.id, target_user.id):
            return None, f"Already brooded at {target_user.display_name}'s nest today"

        # Record brooding
        record_brooding(data, ctx.author.id, target_user.id)
        target_nest["egg"]["brooding_progress"] += 1

        # Check if egg is ready to hatch
        if target_nest["egg"]["brooding_progress"] >= 10:
            bird_species = select_random_bird_species()
            chick = {
                "commonName": bird_species["commonName"],
                "scientificName": bird_species["scientificName"]
            }
            target_nest["chicks"].append(chick)
            target_nest["egg"] = None
            return ("hatch", chick, target_nest, target_user), None
        else:
            remaining = 10 - target_nest["egg"]["brooding_progress"]
            return ("progress", remaining, target_nest, target_user), None

    @commands.command(name='brood')
    async def brood(self, ctx, *target_users: discord.Member):
        """Brood eggs to help them hatch"""
        if not target_users:
            target_users = [ctx.author]

        log_debug(f"brood called by {ctx.author.id} for users {[user.id for user in target_users]}")
        data = load_data()

        # Check if brooder has actions
        remaining_actions = get_remaining_actions(data, ctx.author.id)
        if remaining_actions <= 0:
            await ctx.send(f"You've used all your actions for today! Come back in {get_time_until_reset()}! 🌙")
            return

        successful_targets = []
        skipped_targets = []

        # Process each target user
        for target_user in target_users:
            if remaining_actions <= 0:
                skipped_targets.append((target_user, "no actions left"))
                continue

            result, error = await self.process_brooding(ctx, target_user, data, remaining_actions)
            if error:
                skipped_targets.append((target_user, error))
            else:
                successful_targets.append(result)
                record_actions(data, ctx.author.id, 1, "brood")
                remaining_actions -= 1

        save_data(data)

        # Send responses
        for result in successful_targets:
            if result[0] == "hatch":
                _, chick, target_nest, target_user = result
                # Fetch image and create embed
                image_url, taxon_url = await self.fetch_bird_image(chick['scientificName'])
                embed = discord.Embed(
                    title="🐣 Egg Hatched!",
                    description=f"The egg has hatched into a **{chick['commonName']}** (*{chick['scientificName']}*)!",
                    color=discord.Color.green()
                )
                if image_url:
                    embed.set_image(url=image_url)
                embed.add_field(
                    name="Total Chicks",
                    value=f"{target_user.display_name} now has {get_total_chicks(target_nest)} {'chick' if get_total_chicks(target_nest) == 1 else 'chicks'}! 🐦",
                    inline=False
                )
                embed.add_field(
                    name="View Chicks",
                    value=f"[Click Here](https://bird-rpg.onrender.com/user/{target_user.id})",
                    inline=False
                )
                await ctx.send(embed=embed)
            else:
                _, remaining, target_nest, target_user = result
                await ctx.send(f"You brooded at **{target_nest['name']}**! The egg needs {remaining} more {'brood' if remaining == 1 else 'broods'} until it hatches. 🥚")

        if skipped_targets:
            skip_message = ["⚠️ Couldn't brood for:"]
            for user, reason in skipped_targets:
                skip_message.append(f"• {user.display_name} ({reason})")
            await ctx.send("\n".join(skip_message))

        remaining_actions = get_remaining_actions(data, ctx.author.id)
        await ctx.send(f"You have {remaining_actions} {'action' if remaining_actions == 1 else 'actions'} remaining today.")

    @commands.command(name='brood_random')
    async def brood_random(self, ctx):
        """Brood a random nest that hasn't been brooded today"""
        log_debug(f"brood_random called by {ctx.author.id}")
        data = load_data()

        # Check if brooder has actions
        remaining_actions = get_remaining_actions(data, ctx.author.id)
        if remaining_actions <= 0:
            await ctx.send(f"You've used all your actions for today! Come back in {get_time_until_reset()}! 🌙")
            return

        # Find all nests with eggs that haven't been brooded by the user today
        valid_targets = []
        for user_id, nest in data["personal_nests"].items():  # Changed to use personal_nests
            if "egg" in nest and nest["egg"] is not None:
                if not has_brooded_egg(data, ctx.author.id, user_id):
                    try:
                        member = await ctx.guild.fetch_member(int(user_id))
                        if member and not member.bot and member.id != ctx.author.id:  # Added check to exclude self
                            valid_targets.append(member)
                    except:
                        continue

        if not valid_targets:
            await ctx.send("There are no nests available to brood! All nests either have no eggs or you've already brooded them today. 🥚")
            return

        # Select a random target and brood their egg
        target_user = random.choice(valid_targets)
        result, error = await self.process_brooding(ctx, target_user, data, remaining_actions)
        
        if error:
            await ctx.send(f"Couldn't brood at {target_user.display_name}'s nest: {error}")
            return

        record_actions(data, ctx.author.id, 1, "brood")
        save_data(data)

        # Send appropriate response
        if result[0] == "hatch":
            _, chick, target_nest, target_user = result
            # Fetch image and create embed
            image_url, taxon_url = await self.fetch_bird_image(chick['scientificName'])
            embed = discord.Embed(
                title="🐣 Egg Hatched!",
                description=f"The egg has hatched into a **{chick['commonName']}** (*{chick['scientificName']}*)!",
                color=discord.Color.green()
            )
            if image_url:
                embed.set_image(url=image_url)
            embed.add_field(
                name="Total Chicks",
                value=f"{target_user.display_name} now has {get_total_chicks(target_nest)} {'chick' if get_total_chicks(target_nest) == 1 else 'chicks'}! 🐦",
                inline=False
            )
            embed.add_field(
                name="View Chicks",
                value=f"[Click Here](https://bird-rpg.onrender.com/user/{target_user.id})",
                inline=False
            )
            await ctx.send(embed=embed)
        else:
            _, remaining, target_nest, target_user = result
            remaining_actions = get_remaining_actions(data, ctx.author.id)
            await ctx.send(f"You brooded at **{target_nest['name']}**! The egg needs {remaining} more {'brood' if remaining == 1 else 'broods'} until it hatches. 🥚\nYou have {remaining_actions} {'action' if remaining_actions == 1 else 'actions'} remaining today.")

    async def fetch_bird_image(self, scientific_name):
        """Fetches the bird image URL and taxon URL from iNaturalist."""
        api_url = f"https://api.inaturalist.org/v1/taxa?q={scientific_name}&limit=1"
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(api_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data['results']:
                            taxon = data['results'][0]
                            image_url = taxon.get('default_photo', {}).get('medium_url')
                            taxon_url = taxon.get('url')
                            return image_url, taxon_url
            except Exception as e:
                log_debug(f"Error fetching image from iNaturalist: {e}")
        return None, None

async def setup(bot):
    await bot.add_cog(IncubationCommands(bot))
