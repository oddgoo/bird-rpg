from discord.ext import commands
from discord import app_commands
import discord
from datetime import datetime
import aiohttp
import random

from data.storage import load_data, save_data
from data.models import (
    get_personal_nest, get_remaining_actions, record_actions,
    has_brooded_egg, record_brooding, get_egg_cost,
    get_total_chicks, select_random_bird_species, load_bird_species
)
from utils.logging import log_debug
from utils.time_utils import get_time_until_reset, get_current_date

class IncubationCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='lay_egg', description='Convert seeds into an egg in your nest')
    async def lay_egg(self, interaction: discord.Interaction):
        """Convert seeds into an egg in your nest"""
        log_debug(f"lay_egg called by {interaction.user.id}")
        data = load_data()
        nest = get_personal_nest(data, interaction.user.id)

        # Check if nest already has an egg
        if "egg" in nest and nest["egg"] is not None:
            await interaction.response.send_message("Your nest already has an egg! 🥚")
            return

        # Calculate egg cost based on number of chicks
        egg_cost = get_egg_cost(nest)
        
        # Check if enough seeds
        if nest["seeds"] < egg_cost:
            await interaction.response.send_message(f"You need {egg_cost} seeds to lay an egg! You only have {nest['seeds']} seeds. 🌰")
            return

        # Create the egg
        nest["seeds"] -= egg_cost
        nest["egg"] = {
            "brooding_progress": 0,
            "brooded_by": []
        }
        
        save_data(data)
        await interaction.response.send_message(f"You laid an egg! It cost {egg_cost} seeds. 🥚\n"
                      f"The egg needs to be brooded 10 times to hatch.\n"
                      f"Your nest now has {nest['seeds']} seeds remaining.")

    @app_commands.command(name='brood', description='Brood eggs to help them hatch')
    @app_commands.describe(target_users='The users whose eggs you want to brood (mention them)')
    async def brood(self, interaction: discord.Interaction, target_users: str = None):
        """Brood eggs to help them hatch"""
        # Defer the response since this might take a while
        await interaction.response.defer()
        
        # Parse mentioned users or default to self
        mentioned_users = []
        if target_users:
            for user_id in target_users.split():
                try:
                    user_id = user_id.strip('<@!>')
                    user = await self.bot.fetch_user(int(user_id))
                    mentioned_users.append(user)
                except:
                    continue
        
        if not mentioned_users:
            mentioned_users = [interaction.user]

        log_debug(f"brood called by {interaction.user.id} for users {[user.id for user in mentioned_users]}")
        data = load_data()

        # Check if brooder has actions
        remaining_actions = get_remaining_actions(data, interaction.user.id)
        if remaining_actions <= 0:
            await interaction.followup.send(f"You've used all your actions for today! Come back in {get_time_until_reset()}! 🌙")
            return

        successful_targets = []
        skipped_targets = []

        # Process each target user
        for target_user in mentioned_users:
            if remaining_actions <= 0:
                skipped_targets.append((target_user, "no actions left"))
                continue

            result_tuple, error = await self.process_brooding(interaction, target_user, data, remaining_actions)
            if error:
                skipped_targets.append((target_user, error))
            else:
                successful_targets.append(result_tuple)
                record_actions(data, interaction.user.id, 1, "brood")
                remaining_actions -= 1
        
        save_data(data)

        # Send responses - first send all success messages
        for result_tuple in successful_targets:
            action_type = result_tuple[0]
            if action_type == "hatch":
                _, chick, target_nest, target_user = result_tuple
                # Fetch image and create embed
                image_url, taxon_url = await self.fetch_bird_image(chick['scientificName'])
                embed = discord.Embed(
                    title="🐣 Egg Hatched!",
                    description=f"{target_user.mention}'s egg has hatched into a **{chick['commonName']}** (*{chick['scientificName']}*)!",
                    color=discord.Color.green()
                )
                if image_url:
                    embed.set_image(url=image_url)
                embed.add_field(
                    name="Total Chicks",
                    value=f"{target_user.mention} now has {get_total_chicks(target_nest)} {'chick' if get_total_chicks(target_nest) == 1 else 'chicks'}! 🐦",
                    inline=False
                )
                embed.add_field(
                    name="View Chicks",
                    value=f"[Click Here](https://bird-rpg.onrender.com/user/{target_user.id})",
                    inline=False
                )
                await interaction.followup.send(embed=embed)
            else:
                _, remaining, target_nest, target_user = result_tuple
                await interaction.followup.send(f"You brooded at {target_user.mention}'s **{target_nest['name']}**! The egg needs {remaining} more {'brood' if remaining == 1 else 'broods'} until it hatches. 🥚\nYou have {remaining_actions} {'action' if remaining_actions == 1 else 'actions'} remaining today.")

        # Then send error messages if any
        if skipped_targets:
            skip_message = ["⚠️ Couldn't brood for:"]
            for user, reason in skipped_targets:
                skip_message.append(f"• {user.display_name} ({reason})")
            await interaction.followup.send("\n".join(skip_message))

        # Finally send remaining actions
        remaining_actions = get_remaining_actions(data, interaction.user.id)
        await interaction.followup.send(f"You have {remaining_actions} {'action' if remaining_actions == 1 else 'actions'} remaining today.")

    @app_commands.command(name='brood_random', description='Brood a random nest that hasn\'t been brooded today')
    async def brood_random(self, interaction: discord.Interaction):
        """Brood a random nest that hasn't been brooded today"""
        # Defer the response since this might take a while
        await interaction.response.defer()
        
        log_debug(f"brood_random called by {interaction.user.id}")
        data = load_data()
        
        # Check if brooder has actions
        remaining_actions = get_remaining_actions(data, interaction.user.id)
        if remaining_actions <= 0:
            await interaction.followup.send(f"You've used all your actions for today! Come back in {get_time_until_reset()}! 🌙")
            return

        # Find all nests with eggs that haven't been brooded by the user today
        valid_targets = []
        for user_id, nest in data["personal_nests"].items():
            if "egg" in nest and nest["egg"] is not None:
                # Skip locked nests
                if nest.get("locked", False) and str(interaction.user.id) != user_id:
                    continue
                if not has_brooded_egg(data, interaction.user.id, user_id):
                    try:
                        member = await interaction.guild.fetch_member(int(user_id))
                        if member and not member.bot and member.id != interaction.user.id:
                            valid_targets.append(member)
                    except:
                        continue
        
        if not valid_targets:
            await interaction.followup.send("There are no nests available to brood! All nests either have no eggs or you've already brooded them today. 🥚")
            return
            
        # Select a random target and brood their egg
        target_user = random.choice(valid_targets)
        result_tuple, error = await self.process_brooding(interaction, target_user, data, remaining_actions)
        
        if error:
            await interaction.followup.send(f"Couldn't brood at {target_user.display_name}'s nest: {error}")
            return

        record_actions(data, interaction.user.id, 1, "brood")
        save_data(data)

        # Send appropriate response
        action_type = result_tuple[0]
        if action_type == "hatch":
            _, chick, target_nest, target_user = result_tuple
            # Fetch image and create embed
            image_url, taxon_url = await self.fetch_bird_image(chick['scientificName'])
            embed = discord.Embed(
                title="🐣 Egg Hatched!",
                description=f"{target_user.mention}'s egg has hatched into a **{chick['commonName']}** (*{chick['scientificName']}*)!",
                color=discord.Color.green()
            )
            if image_url:
                embed.set_image(url=image_url)
            embed.add_field(
                name="Total Chicks",
                value=f"{target_user.mention} now has {get_total_chicks(target_nest)} {'chick' if get_total_chicks(target_nest) == 1 else 'chicks'}! 🐦",
                inline=False
            )
            embed.add_field(
                name="View Chicks",
                value=f"[Click Here](https://bird-rpg.onrender.com/user/{target_user.id})",
                inline=False
            )
            await interaction.followup.send(embed=embed)
        else:
            _, remaining, target_nest, target_user = result_tuple
            remaining_actions = get_remaining_actions(data, interaction.user.id)
            await interaction.followup.send(f"You brooded at {target_user.mention}'s **{target_nest['name']}**! The egg needs {remaining} more {'brood' if remaining == 1 else 'broods'} until it hatches. 🥚\nYou have {remaining_actions} {'action' if remaining_actions == 1 else 'actions'} remaining today.")

    @app_commands.command(name='lock_nest', description='Lock your nest to prevent others from brooding')
    async def lock_nest(self, interaction: discord.Interaction):
        """Lock your nest to prevent others from brooding"""
        log_debug(f"lock_nest called by {interaction.user.id}")
        data = load_data()
        nest = get_personal_nest(data, interaction.user.id)

        # Check if nest is already locked
        if nest.get("locked", False):
            await interaction.response.send_message("Your nest is already locked! 🔒")
            return

        # Lock the nest
        nest["locked"] = True
        save_data(data)
        await interaction.response.send_message("Your nest is now locked! Other players cannot brood your eggs. 🔒")

    @app_commands.command(name='unlock_nest', description='Unlock your nest to allow others to brood')
    async def unlock_nest(self, interaction: discord.Interaction):
        """Unlock your nest to allow others to brood"""
        log_debug(f"unlock_nest called by {interaction.user.id}")
        data = load_data()
        nest = get_personal_nest(data, interaction.user.id)

        # Check if nest is already unlocked
        if not nest.get("locked", False):
            await interaction.response.send_message("Your nest is already unlocked! 🔓")
            return

        # Unlock the nest
        nest["locked"] = False
        save_data(data)
        await interaction.response.send_message("Your nest is now unlocked! Other players can brood your eggs. 🔓")

    async def process_brooding(self, interaction: discord.Interaction, target_user, data, remaining_actions):
        """Helper function to process brooding for a single user"""
        # Get target's nest
        target_nest = get_personal_nest(data, target_user.id)

        # Check if target's nest is locked and brooder is not the owner
        if target_nest.get("locked", False) and str(interaction.user.id) != str(target_user.id):
            return None, "Nest is locked!"

        # Check if target has an egg
        if "egg" not in target_nest or target_nest["egg"] is None:
            return None, "doesn't have an egg to brood"

        # Initialize brooded_by list if it doesn't exist
        if "brooded_by" not in target_nest["egg"]:
            target_nest["egg"]["brooded_by"] = []

        # Check if already brooded today
        brooder_id = str(interaction.user.id)
        if has_brooded_egg(data, brooder_id, target_user.id):
            return None, "already brooded this egg today"

        # Record brooding
        record_brooding(data, interaction.user.id, target_user.id)
        target_nest["egg"]["brooding_progress"] += 1
        target_nest["egg"]["brooded_by"].append(brooder_id)

        # Check if egg is ready to hatch
        if target_nest["egg"]["brooding_progress"] >= 10:
            # Get multipliers if they exist
            multipliers = target_nest["egg"].get("multipliers", {})
            bird_species = select_random_bird_species(multipliers)
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

    async def fetch_bird_image(self, scientific_name):
        """Fetches the bird image URL and taxon URL from iNaturalist."""
        # First check if this is a special bird by looking it up in bird_species.json
        data = load_data()
        for bird in data.get("bird_species", []):
            if bird["scientificName"] == scientific_name and bird.get("rarity") == "Special":
                # For special birds, return the local image path
                local_image_url = f"/static/images/special-birds/{scientific_name}.png"
                return local_image_url, None

        # For regular birds, continue with iNaturalist API
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

    @app_commands.command(name='pray_for_bird', description='Pray for a specific bird to increase its hatching chance')
    @app_commands.describe(
        scientific_name='The scientific name of the bird to pray for',
        amount_of_prayers='How many prayers to offer (consumes this many actions)'
    )
    async def pray_for_bird(
        self,
        interaction: discord.Interaction,
        scientific_name: str,
        amount_of_prayers: int
    ):
        """Pray for a specific bird to increase its hatching chance"""
        log_debug(f"pray_for_bird called by {interaction.user.id}")
        data = load_data()
        nest = get_personal_nest(data, interaction.user.id)

        # Check if nest has an egg
        if "egg" not in nest or nest["egg"] is None:
            await interaction.response.send_message("You don't have an egg to pray for! 🥚")
            return

        # Validate amount of prayers
        if amount_of_prayers <= 0:
            await interaction.response.send_message("You must pray at least once! 🙏")
            return

        # Check if user has enough actions
        remaining_actions = get_remaining_actions(data, interaction.user.id)
        if remaining_actions < amount_of_prayers:
            await interaction.response.send_message(
                f"You don't have enough actions! You need {amount_of_prayers} but only have {remaining_actions} remaining. 🌙"
            )
            return

        # Validate bird species exists
        bird_species = load_bird_species()
        valid_species = False
        for species in bird_species:
            if species["scientificName"].lower() == scientific_name.lower():
                scientific_name = species["scientificName"]  # Use correct casing
                valid_species = True
                break

        if not valid_species:
            await interaction.response.send_message(f"Invalid bird species: {scientific_name}")
            return

        # Initialize multipliers if they don't exist
        if "multipliers" not in nest["egg"]:
            nest["egg"]["multipliers"] = {}

        # Add or update multiplier
        current_multiplier = nest["egg"]["multipliers"].get(scientific_name, 0)
        nest["egg"]["multipliers"][scientific_name] = current_multiplier + amount_of_prayers

        # Calculate actual percentage chance
        total_weight = 0
        target_weight = 0
        target_base_weight = 0
        
        # Calculate total weights with multipliers
        for species in bird_species:
            base_weight = species["rarityWeight"]
            if species["scientificName"] == scientific_name:
                target_base_weight = base_weight
                multiplied_weight = base_weight * nest["egg"]["multipliers"][scientific_name]
                target_weight = multiplied_weight
                total_weight += multiplied_weight
            else:
                # Apply any existing multipliers for other species
                if "multipliers" in nest["egg"] and species["scientificName"] in nest["egg"]["multipliers"]:
                    total_weight += base_weight * nest["egg"]["multipliers"][species["scientificName"]]
                else:
                    total_weight += base_weight

        base_percentage = (target_base_weight / sum(s["rarityWeight"] for s in bird_species)) * 100
        actual_percentage = (target_weight / total_weight) * 100

        # Consume actions
        record_actions(data, interaction.user.id, amount_of_prayers, "pray")
        save_data(data)

        await interaction.response.send_message(
            f"🙏 You offered {amount_of_prayers} {'prayer' if amount_of_prayers == 1 else 'prayers'} for {scientific_name}! 🙏\n"
            f"Their hatching chance multiplier is now {nest['egg']['multipliers'][scientific_name]}x\n"
            f"Base chance: {base_percentage:.1f}% → Current chance: {actual_percentage:.1f}%"
        )

async def setup(bot):
    await bot.add_cog(IncubationCommands(bot))
