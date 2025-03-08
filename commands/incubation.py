from discord.ext import commands
from discord import app_commands
import discord
from datetime import datetime
import aiohttp
import random
import urllib.parse
import os

from config.config import MAX_BIRDS_PER_NEST, SPECIES_IMAGES_DIR
from data.storage import load_data, save_data, load_manifested_birds
from data.models import (
    get_personal_nest, get_remaining_actions, record_actions,
    has_brooded_egg, record_brooding, get_egg_cost,
    get_total_chicks, select_random_bird_species, load_bird_species,
    bless_egg, handle_blessed_egg_hatching, get_less_brood_chance,
    get_extra_bird_chance, get_extra_bird_space
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
        
        # Check for "less brood" effect from plants
        less_brood_chance = get_less_brood_chance(nest)
        initial_brooding_progress = 0
        less_brood_message = ""
        
        if less_brood_chance > 0:
            # Calculate how many guaranteed less broods (each 100% is one guaranteed brood)
            guaranteed_less_broods = int(less_brood_chance // 100)
            # Calculate chance for an additional less brood
            remaining_chance = less_brood_chance % 100
            
            # Apply guaranteed less broods
            if guaranteed_less_broods > 0:
                initial_brooding_progress += guaranteed_less_broods
                less_brood_message = f"\nYour plants provided {guaranteed_less_broods} less {'brood' if guaranteed_less_broods == 1 else 'broods'} needed! 🌱"
            
            # Check for chance of additional less brood
            if remaining_chance > 0 and random.random() < (remaining_chance / 100):
                initial_brooding_progress += 1
                less_brood_message += f"\nYour plants gave you an additional less brood needed (had a {remaining_chance:.1f}% chance)! 🍀"
        
        nest["egg"] = {
            "brooding_progress": initial_brooding_progress,
            "brooded_by": []
        }
        
        broods_needed = 10 - initial_brooding_progress
        
        save_data(data)
        
        # Create the response message
        message = f"You laid an egg! It cost {egg_cost} seeds. 🥚\n"
        
        # Add plants effect information if applicable
        if less_brood_chance > 0:
            message += f"Your plants reduced the brooding needed! "
            message += f"The egg needs to be brooded {broods_needed} times to hatch.{less_brood_message}\n"
        else:
            message += f"The egg needs to be brooded {broods_needed} times to hatch.\n"
            
        message += f"Your nest now has {nest['seeds']} seeds remaining."
        
        await interaction.response.send_message(message)

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
        hatched_targets = []
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
                if result_tuple[0] == "hatch":
                    hatched_targets.append(result_tuple)
                else:
                    successful_targets.append(result_tuple)
                record_actions(data, interaction.user.id, 1, "brood")
                remaining_actions -= 1
        
        save_data(data)

        # Send batched response for successful broods
        if successful_targets:
            brood_messages = []
            for _, remaining, target_nest, target_user in successful_targets:
                brood_messages.append(f"**{target_nest['name']}** (needs {remaining} more {'brood' if remaining == 1 else 'broods'})")
            
            await interaction.followup.send(f"You brooded at the following nests:\n• " + "\n• ".join(brood_messages) + f"\n\nYou have {remaining_actions} {'action' if remaining_actions == 1 else 'actions'} remaining today.")

        # Send individual responses for hatches
        for result in hatched_targets:
            await self.send_hatching_response(interaction, result)

        # Then send error messages if any
        if skipped_targets:
            skip_message = ["⚠️ Couldn't brood for:"]
            for user, reason in skipped_targets:
                skip_message.append(f"• {user.display_name} ({reason})")
            await interaction.followup.send("\n".join(skip_message))

        # No need to send remaining actions again as it's already included in the successful broods message

    @app_commands.command(name='brood_all', description='Use all remaining actions to brood eggs in all available nests')
    async def brood_all(self, interaction: discord.Interaction):
        """Use all remaining actions to brood eggs in all available nests"""
        # Defer the response since this might take a while
        await interaction.response.defer()
        
        log_debug(f"brood_all called by {interaction.user.id}")
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
                if nest.get("locked", False):
                    continue
                # Get extra bird space from research progress
                extra_bird_space = get_extra_bird_space()
                max_birds = MAX_BIRDS_PER_NEST + extra_bird_space
                
                # Skip users who are at their bird limit
                if get_total_chicks(nest) >= max_birds:
                    continue
                if not has_brooded_egg(data, interaction.user.id, user_id):
                    try:
                        member = await interaction.guild.fetch_member(int(user_id))
                        if member and not member.bot:
                            valid_targets.append(member)
                    except:
                        continue

        if not valid_targets:
            await interaction.followup.send("There are no nests available to brood! All nests either have no eggs, you've already brooded them today, or they are at capacity. 🥚")
            return

        # Process brooding for as many targets as possible
        successful_targets = []
        hatched_targets = []
        skipped_targets = []

        # Process each target until out of actions or targets
        for target_user in valid_targets:
            if remaining_actions <= 0:
                break

            result_tuple, error = await self.process_brooding(interaction, target_user, data, remaining_actions)
            if error:
                skipped_targets.append((target_user, error))
                continue

            if result_tuple[0] == "hatch":
                hatched_targets.append(result_tuple)
            else:
                successful_targets.append(result_tuple)

            record_actions(data, interaction.user.id, 1, "brood")
            remaining_actions -= 1

        save_data(data)

        # Send batched response for successful broods
        if successful_targets:
            brood_messages = []
            for _, remaining, target_nest, target_user in successful_targets:
                brood_messages.append(f"**{target_nest['name']}** (needs {remaining} more {'brood' if remaining == 1 else 'broods'})")
            
            await interaction.followup.send(f"You brooded at the following nests:\n• " + "\n• ".join(brood_messages) + f"\n\nYou have {remaining_actions} {'action' if remaining_actions == 1 else 'actions'} remaining today.")

        # Send individual responses for hatches
        for result in hatched_targets:
            await self.send_hatching_response(interaction, result)
            
        # Then send error messages if any
        if skipped_targets:
            skip_message = ["⚠️ Couldn't brood for:"]
            for user, reason in skipped_targets:
                skip_message.append(f"• {user.display_name} ({reason})")
            await interaction.followup.send("\n".join(skip_message))

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
                # Get extra bird space from research progress
                extra_bird_space = get_extra_bird_space()
                max_birds = MAX_BIRDS_PER_NEST + extra_bird_space
                
                # Skip users who are at their bird limit
                if get_total_chicks(nest) >= max_birds:
                    continue
                if not has_brooded_egg(data, interaction.user.id, user_id):
                    try:
                        member = await interaction.guild.fetch_member(int(user_id))
                        if member and not member.bot:
                            valid_targets.append(member)
                    except:
                        continue
        
        if not valid_targets:
            await interaction.followup.send("There are no nests available to brood! All nests either have no eggs,  you've already brooded them today, or they are at capacity! 🥚")
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
        if result_tuple[0] == "hatch":
            await self.send_hatching_response(interaction, result_tuple)
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

    @app_commands.command(name='bless_egg', description='Use 1 💡Inspiration and 30 🌰Seeds to bless your egg, preserving it and its prayers.')
    async def bless_egg(self, interaction: discord.Interaction):
        log_debug(f"bless_egg called by {interaction.user.id}")
        data = load_data()
        nest = get_personal_nest(data, interaction.user.id)

        success, message = bless_egg(nest)
        if success:
            save_data(data)
        await interaction.response.send_message(message)

    async def process_brooding(self, interaction_or_ctx, target_user, data, remaining_actions):
        """Helper function to process brooding for a single user"""
        # Get target's nest
        target_nest = get_personal_nest(data, target_user.id)

        # Check if target's nest is locked and brooder is not the owner
        user_id = getattr(interaction_or_ctx, 'user', getattr(interaction_or_ctx, 'author', None)).id
        if target_nest.get("locked", False) and str(user_id) != str(target_user.id):
            return None, "Nest is locked!"

        # Check if target has an egg
        if "egg" not in target_nest or target_nest["egg"] is None:
            return None, "doesn't have an egg to brood"

        # Initialize brooded_by list if it doesn't exist
        if "brooded_by" not in target_nest["egg"]:
            target_nest["egg"]["brooded_by"] = []

        # Check if already brooded today
        brooder_id = str(user_id)
        if has_brooded_egg(data, brooder_id, target_user.id):
            return None, "already brooded this egg today"

        # Record brooding
        record_brooding(data, user_id, target_user.id)
        target_nest["egg"]["brooding_progress"] += 1
        target_nest["egg"]["brooded_by"].append(brooder_id)

        # Check if egg is ready to hatch
        if target_nest["egg"]["brooding_progress"] >= 10:
            # Get extra bird space from research progress
            extra_bird_space = get_extra_bird_space()
            max_birds = MAX_BIRDS_PER_NEST + extra_bird_space
            
            # Check if the nest has reached the maximum bird limit
            current_birds = get_total_chicks(target_nest)
            if current_birds >= max_birds:
                return None, f"nest already has the maximum of {max_birds} birds"

            # Get multipliers if they exist
            multipliers = target_nest["egg"].get("multipliers", {})
            print(multipliers)

            # Get the main bird species
            bird_species = select_random_bird_species(multipliers)
            chick = {
                "commonName": bird_species["commonName"],
                "scientificName": bird_species["scientificName"]
            }
            
            # Add the main chick to the nest
            target_nest["chicks"].append(chick)
            
            # Check for "extra bird" effect from plants
            extra_bird_chance = get_extra_bird_chance(target_nest)
            extra_birds_message = ""
            extra_birds = []
            
            if extra_bird_chance > 0:
                # Calculate how many guaranteed extra birds (each 100% is one guaranteed bird)
                guaranteed_extra_birds = int(extra_bird_chance // 100)
                # Calculate chance for an additional extra bird
                remaining_chance = extra_bird_chance % 100
                
                # Add guaranteed extra birds
                for i in range(guaranteed_extra_birds):
                    extra_bird_species = select_random_bird_species(multipliers)
                    extra_chick = {
                        "commonName": extra_bird_species["commonName"],
                        "scientificName": extra_bird_species["scientificName"]
                    }
                    target_nest["chicks"].append(extra_chick)
                    extra_birds.append(extra_chick)
                
                # Check for chance of additional extra bird
                if remaining_chance > 0 and random.random() < (remaining_chance / 100):
                    extra_bird_species = select_random_bird_species(multipliers)
                    extra_chick = {
                        "commonName": extra_bird_species["commonName"],
                        "scientificName": extra_bird_species["scientificName"]
                    }
                    target_nest["chicks"].append(extra_chick)
                    extra_birds.append(extra_chick)
            
            # Handle blessed egg hatching
            saved_multipliers = handle_blessed_egg_hatching(target_nest, bird_species["scientificName"])

            # Clear the egg
            target_nest["egg"] = None

            # If we saved multipliers, create a new egg with them
            if saved_multipliers:
                target_nest["egg"] = {
                    "brooding_progress": 0,
                    "brooded_by": [],
                    "multipliers": saved_multipliers
                }
                
            # Add extra birds to the result tuple
            result_tuple = ("hatch", chick, target_nest, target_user)
            if extra_birds:
                result_tuple = ("hatch", chick, target_nest, target_user, extra_birds)

            return result_tuple, None
        else:
            remaining = 10 - target_nest["egg"]["brooding_progress"]
            return ("progress", remaining, target_nest, target_user), None

    async def send_hatching_response(self, interaction_or_ctx, result):
        """Helper function to send a hatching response"""
        # Check if we have extra birds in the result
        if len(result) > 4:
            _, chick, target_nest, target_user, extra_birds = result
        else:
            _, chick, target_nest, target_user = result
            extra_birds = []
            
        # Fetch image path and create embed for the main bird
        image_path, taxon_url = await self.fetch_bird_image(chick['scientificName'])
        
        # Create the base description for the main bird
        description = f"{target_user.mention}'s egg has hatched into a **{chick['commonName']}** (*{chick['scientificName']}*)!"
        
        embed = discord.Embed(
            title="🐣 Egg Hatched!",
            description=description,
            color=discord.Color.green()
        )
            
        embed.add_field(
            name="Total Chicks",
            value=f"{target_user.mention} now has {get_total_chicks(target_nest)} {'chick' if get_total_chicks(target_nest) == 1 else 'chicks'}! 🐦",
            inline=False
        )
        
        # Add plant effect explanation if extra birds hatched
        if extra_birds:
            plant_effect = f"Your garden's plants gave you {len(extra_birds)} extra {'bird' if len(extra_birds) == 1 else 'birds'}! 🌱"
            embed.add_field(
                name="Plant Effect",
                value=plant_effect,
                inline=False
            )
            
        embed.add_field(
            name="View Chicks",
            value=f"[Click Here](https://bird-rpg.onrender.com/user/{target_user.id})",
            inline=False
        )
        
        # Handle different context types with image attachment if it exists
        if os.path.exists(image_path):
            # Create a safe filename for the attachment
            filename = f"{urllib.parse.quote(chick['scientificName'])}.jpg"
            if chick['scientificName'] == "Casspie":
                filename = "Casspie.png"
                
            # Create the file attachment
            file = discord.File(image_path, filename=filename)
            embed.set_image(url=f"attachment://{filename}")
            
            if hasattr(interaction_or_ctx, 'followup'):
                await interaction_or_ctx.followup.send(file=file, embed=embed)
            else:
                await interaction_or_ctx.send(file=file, embed=embed)
        else:
            # If image doesn't exist, send embed without image
            if hasattr(interaction_or_ctx, 'followup'):
                await interaction_or_ctx.followup.send(embed=embed)
            else:
                await interaction_or_ctx.send(embed=embed)
        
        # Send individual messages for each extra bird
        for extra_chick in extra_birds:
            await self.send_extra_bird_message(interaction_or_ctx, extra_chick, target_user)

    async def send_extra_bird_message(self, interaction_or_ctx, extra_chick, target_user):
        """Helper function to send a message for each extra bird"""
        # Fetch image path for the extra bird
        image_path, _ = await self.fetch_bird_image(extra_chick['scientificName'])
        
        # Create embed for the extra bird
        extra_embed = discord.Embed(
            title="🐣 Extra Bird Hatched!",
            description=f"{target_user.mention} received an extra bird: **{extra_chick['commonName']}** (*{extra_chick['scientificName']}*)!",
            color=discord.Color.gold()
        )
        
        extra_embed.add_field(
            name="Plant Effect",
            value="This extra bird hatched thanks to your garden's plants! 🌱",
            inline=False
        )
        
        # Handle different context types with image attachment if it exists
        if os.path.exists(image_path):
            # Create a safe filename for the attachment
            filename = f"{urllib.parse.quote(extra_chick['scientificName'])}.jpg"
            if extra_chick['scientificName'] == "Casspie":
                filename = "Casspie.png"
                
            # Create the file attachment
            file = discord.File(image_path, filename=filename)
            extra_embed.set_image(url=f"attachment://{filename}")
            
            if hasattr(interaction_or_ctx, 'followup'):
                await interaction_or_ctx.followup.send(file=file, embed=extra_embed)
            else:
                await interaction_or_ctx.send(file=file, embed=extra_embed)
        else:
            # If image doesn't exist, send embed without image
            if hasattr(interaction_or_ctx, 'followup'):
                await interaction_or_ctx.followup.send(embed=extra_embed)
            else:
                await interaction_or_ctx.send(embed=extra_embed)
    
    async def fetch_bird_image(self, scientific_name):
        """Fetches the bird image path and taxon URL."""
        # Check if this is a special bird
        if scientific_name == "Casspie":
            # For special birds, return the local image path
            image_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                                     "static", "images", "special-birds", f"{scientific_name}.png")
            return image_path, None
        
        # For regular birds and manifested birds, check the species_images directory
        image_path = os.path.join(SPECIES_IMAGES_DIR, f"{urllib.parse.quote(scientific_name)}.jpg")
        return image_path, None

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

        # Validate bird species exists in either main codex or manifested birds
        all_birds = load_bird_species()  # This now includes both standard and manifested birds
        
        valid_species = False
        for species in all_birds:
            if species["scientificName"].lower() == scientific_name.lower():
                scientific_name = species["scientificName"]  # Use correct casing
                valid_species = True
                break

        if not valid_species:
            await interaction.response.send_message(f"Invalid bird species: {scientific_name}. Make sure it exists in the codex or has been fully manifested.")
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
        for species in all_birds:
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

        base_percentage = (target_base_weight / sum(s["rarityWeight"] for s in all_birds)) * 100
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
