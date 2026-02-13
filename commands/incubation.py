from discord.ext import commands
from discord import app_commands
import discord
import asyncio
from datetime import datetime
import aiohttp
import random
import urllib.parse
import os

from config.config import MAX_BIRDS_PER_NEST, SPECIES_IMAGES_DIR
import data.storage as db
from data.models import (
    get_remaining_actions, record_actions,
    get_egg_cost, select_random_bird_species, load_bird_species,
    bless_egg, handle_blessed_egg_hatching, get_less_brood_chance,
    get_extra_bird_chance, get_extra_bird_space, get_prayer_effectiveness_bonus
)
from utils.logging import log_debug
from utils.time_utils import get_time_until_reset, get_current_date

class IncubationCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _resolve_members_for_user_ids(self, guild, user_ids):
        """Resolve user IDs to guild members with cached lookup first."""
        if guild is None:
            return {}

        members_by_id = {}
        unresolved = []

        for user_id in user_ids:
            try:
                int_user_id = int(user_id)
            except ValueError:
                continue

            member = guild.get_member(int_user_id)
            if member is not None:
                members_by_id[user_id] = member
            else:
                unresolved.append((user_id, int_user_id))

        if not unresolved:
            return members_by_id

        semaphore = asyncio.Semaphore(5)

        async def fetch_member(user_id, int_user_id):
            async with semaphore:
                try:
                    member = await guild.fetch_member(int_user_id)
                    return user_id, member
                except (discord.NotFound, discord.HTTPException):
                    return user_id, None

        resolved = await asyncio.gather(*(fetch_member(user_id, int_user_id) for user_id, int_user_id in unresolved))
        for user_id, member in resolved:
            if member is not None:
                members_by_id[user_id] = member

        return members_by_id

    async def _get_broodable_targets(self, interaction, max_birds, today, allow_own_locked=False):
        """Find broodable targets with batch DB queries."""
        brooder_id = str(interaction.user.id)
        all_players = await db.load_all_players()

        candidate_players = []
        candidate_user_ids = []
        for player in all_players:
            target_user_id = str(player["user_id"])
            if player.get("locked", False) and not (allow_own_locked and target_user_id == brooder_id):
                continue
            candidate_players.append(player)
            candidate_user_ids.append(target_user_id)

        if not candidate_user_ids:
            return []

        eggs_by_user = await db.get_eggs_for_users(candidate_user_ids)
        if not eggs_by_user:
            return []

        users_with_eggs = list(eggs_by_user.keys())
        bird_counts_by_user = await db.get_bird_counts_for_users(users_with_eggs)
        already_brooded = await db.get_brooded_targets_today(brooder_id, today, users_with_eggs)

        ordered_target_ids = []
        players_by_id = {str(player["user_id"]): player for player in candidate_players}
        for player in candidate_players:
            target_user_id = str(player["user_id"])
            if target_user_id not in eggs_by_user:
                continue
            if bird_counts_by_user.get(target_user_id, 0) >= max_birds:
                continue
            if target_user_id in already_brooded:
                continue
            ordered_target_ids.append(target_user_id)

        if not ordered_target_ids:
            return []

        members_by_id = await self._resolve_members_for_user_ids(interaction.guild, ordered_target_ids)

        valid_targets = []
        for target_user_id in ordered_target_ids:
            member = members_by_id.get(target_user_id)
            if member and not member.bot:
                valid_targets.append((member, players_by_id[target_user_id], eggs_by_user[target_user_id]))
        return valid_targets

    @app_commands.command(name='lay_egg', description='Convert seeds into an egg in your nest')
    async def lay_egg(self, interaction: discord.Interaction):
        """Convert seeds into an egg in your nest"""
        await interaction.response.defer()
        log_debug(f"lay_egg called by {interaction.user.id}")
        user_id = str(interaction.user.id)
        player = await db.load_player(user_id)

        # Check if nest already has an egg
        egg = await db.get_egg(user_id)
        if egg is not None:
            await interaction.followup.send("Your nest already has an egg! \U0001f95a")
            return

        # Calculate egg cost based on number of chicks
        egg_cost = get_egg_cost(player)

        # Check if enough seeds
        if player["seeds"] < egg_cost:
            await interaction.followup.send(f"You need {egg_cost} seeds to lay an egg! You only have {player['seeds']} seeds. \U0001f330")
            return

        # Deduct seeds
        await db.increment_player_field(user_id, "seeds", -egg_cost)

        # Check for "less brood" effect from plants
        plants = await db.get_player_plants(user_id)
        less_brood_chance = await get_less_brood_chance(plants)
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
                less_brood_message = f"\nYour plants provided {guaranteed_less_broods} less {'brood' if guaranteed_less_broods == 1 else 'broods'} needed! \U0001f331"

            # Check for chance of additional less brood
            if remaining_chance > 0 and random.random() < (remaining_chance / 100):
                initial_brooding_progress += 1
                less_brood_message += f"\nYour plants gave you an additional less brood needed (had a {remaining_chance:.1f}% chance)! \U0001f340"

        # Create the egg in DB
        await db.create_egg(user_id, brooding_progress=initial_brooding_progress, protected_prayers=False)

        broods_needed = 10 - initial_brooding_progress

        # Re-read player to get updated seeds for the message
        player = await db.load_player(user_id)

        # Create the response message
        message = f"You laid an egg! It cost {egg_cost} seeds. \U0001f95a\n"

        # Add plants effect information if applicable
        if less_brood_chance > 0:
            message += f"Your plants reduced the brooding needed! "
            message += f"The egg needs to be brooded {broods_needed} times to hatch.{less_brood_message}\n"
        else:
            message += f"The egg needs to be brooded {broods_needed} times to hatch.\n"

        message += f"Your nest now has {player['seeds']} seeds remaining."

        await interaction.followup.send(message)

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
                except (ValueError, discord.NotFound, discord.HTTPException):
                    continue

        if not mentioned_users:
            mentioned_users = [interaction.user]

        log_debug(f"brood called by {interaction.user.id} for users {[user.id for user in mentioned_users]}")

        # Check if brooder has actions
        remaining_actions = await get_remaining_actions(interaction.user.id)
        if remaining_actions <= 0:
            await interaction.followup.send(f"You've used all your actions for today! Come back in {get_time_until_reset()}! \U0001f319")
            return

        successful_targets = []
        hatched_targets = []
        skipped_targets = []

        # Process each target user
        for target_user in mentioned_users:
            if remaining_actions <= 0:
                skipped_targets.append((target_user, "no actions left"))
                continue

            result_tuple, error = await self.process_brooding(interaction, target_user, remaining_actions)
            if error:
                skipped_targets.append((target_user, error))
            else:
                if result_tuple[0] == "hatch":
                    hatched_targets.append(result_tuple)
                else:
                    successful_targets.append(result_tuple)
                await record_actions(interaction.user.id, 1, "brood")
                remaining_actions -= 1

        # Send batched response for successful broods
        if successful_targets:
            brood_messages = []
            for _, remaining, target_nest_name, target_user in successful_targets:
                brood_messages.append(f"**{target_nest_name}** (needs {remaining} more {'brood' if remaining == 1 else 'broods'})")

            await interaction.followup.send(f"You brooded at the following nests:\n\u2022 " + "\n\u2022 ".join(brood_messages) + f"\n\nYou have {remaining_actions} {'action' if remaining_actions == 1 else 'actions'} remaining today.")

        # Send individual responses for hatches
        for result in hatched_targets:
            await self.send_hatching_response(interaction, result)

        # Then send error messages if any
        if skipped_targets:
            skip_message = ["\u26a0\ufe0f Couldn't brood for:"]
            for user, reason in skipped_targets:
                skip_message.append(f"\u2022 {user.display_name} ({reason})")
            await interaction.followup.send("\n".join(skip_message))

        # No need to send remaining actions again as it's already included in the successful broods message

    @app_commands.command(name='brood_all', description='Use all remaining actions to brood eggs in all available nests')
    async def brood_all(self, interaction: discord.Interaction):
        """Use all remaining actions to brood eggs in all available nests"""
        # Defer the response since this might take a while
        await interaction.response.defer()

        log_debug(f"brood_all called by {interaction.user.id}")

        # Check if brooder has actions
        remaining_actions = await get_remaining_actions(interaction.user.id)
        if remaining_actions <= 0:
            await interaction.followup.send(f"You've used all your actions for today! Come back in {get_time_until_reset()}! \U0001f319")
            return

        # Get extra bird space from research progress
        extra_bird_space = await get_extra_bird_space()
        max_birds = MAX_BIRDS_PER_NEST + extra_bird_space
        today = get_current_date()

        valid_targets = await self._get_broodable_targets(interaction, max_birds, today, allow_own_locked=False)

        if not valid_targets:
            await interaction.followup.send("There are no nests available to brood! All nests either have no eggs, you've already brooded them today, or they are at capacity. \U0001f95a")
            return

        # Process brooding for as many targets as possible
        successful_targets = []
        hatched_targets = []
        skipped_targets = []
        successful_count = 0

        # Process each target until out of actions or targets
        for target_user, target_player, target_egg in valid_targets:
            if remaining_actions <= 0:
                break

            result_tuple, error = await self.process_brooding(
                interaction,
                target_user,
                remaining_actions,
                prefetched_player=target_player,
                prefetched_egg=target_egg,
                max_birds=max_birds,
            )
            if error:
                skipped_targets.append((target_user, error))
                continue

            if result_tuple[0] == "hatch":
                hatched_targets.append(result_tuple)
            else:
                successful_targets.append(result_tuple)

            successful_count += 1
            remaining_actions -= 1

        if successful_count > 0:
            await record_actions(interaction.user.id, successful_count, "brood")

        # Send batched response for successful broods
        if successful_targets:
            brood_messages = []
            for _, remaining, target_nest_name, target_user in successful_targets:
                brood_messages.append(f"**{target_nest_name}** (needs {remaining} more {'brood' if remaining == 1 else 'broods'})")

            await interaction.followup.send(f"You brooded at the following nests:\n\u2022 " + "\n\u2022 ".join(brood_messages) + f"\n\nYou have {remaining_actions} {'action' if remaining_actions == 1 else 'actions'} remaining today.")

        # Send individual responses for hatches
        for result in hatched_targets:
            await self.send_hatching_response(interaction, result)

        # Then send error messages if any
        if skipped_targets:
            skip_message = ["\u26a0\ufe0f Couldn't brood for:"]
            for user, reason in skipped_targets:
                skip_message.append(f"\u2022 {user.display_name} ({reason})")
            await interaction.followup.send("\n".join(skip_message))

    @app_commands.command(name='brood_random', description='Brood a random nest that hasn\'t been brooded today')
    async def brood_random(self, interaction: discord.Interaction):
        """Brood a random nest that hasn't been brooded today"""
        # Defer the response since this might take a while
        await interaction.response.defer()

        log_debug(f"brood_random called by {interaction.user.id}")

        # Check if brooder has actions
        remaining_actions = await get_remaining_actions(interaction.user.id)
        if remaining_actions <= 0:
            await interaction.followup.send(f"You've used all your actions for today! Come back in {get_time_until_reset()}! \U0001f319")
            return

        # Get extra bird space from research progress
        extra_bird_space = await get_extra_bird_space()
        max_birds = MAX_BIRDS_PER_NEST + extra_bird_space
        today = get_current_date()

        valid_targets = await self._get_broodable_targets(interaction, max_birds, today, allow_own_locked=True)

        if not valid_targets:
            await interaction.followup.send("There are no nests available to brood! All nests either have no eggs,  you've already brooded them today, or they are at capacity! \U0001f95a")
            return

        # Select a random target and brood their egg
        target_user, target_player, target_egg = random.choice(valid_targets)
        result_tuple, error = await self.process_brooding(
            interaction,
            target_user,
            remaining_actions,
            prefetched_player=target_player,
            prefetched_egg=target_egg,
            max_birds=max_birds,
        )

        if error:
            await interaction.followup.send(f"Couldn't brood at {target_user.display_name}'s nest: {error}")
            return

        await record_actions(interaction.user.id, 1, "brood")

        # Send appropriate response
        if result_tuple[0] == "hatch":
            await self.send_hatching_response(interaction, result_tuple)
        else:
            _, remaining, target_nest_name, target_user = result_tuple
            remaining_actions = await get_remaining_actions(interaction.user.id)
            await interaction.followup.send(f"You brooded at {target_user.mention}'s **{target_nest_name}**! The egg needs {remaining} more {'brood' if remaining == 1 else 'broods'} until it hatches. \U0001f95a\nYou have {remaining_actions} {'action' if remaining_actions == 1 else 'actions'} remaining today.")

    @app_commands.command(name='lock_nest', description='Lock your nest to prevent others from brooding')
    async def lock_nest(self, interaction: discord.Interaction):
        """Lock your nest to prevent others from brooding"""
        await interaction.response.defer()
        log_debug(f"lock_nest called by {interaction.user.id}")
        user_id = str(interaction.user.id)
        player = await db.load_player(user_id)

        # Check if nest is already locked
        if player.get("locked", False):
            await interaction.followup.send("Your nest is already locked! \U0001f512")
            return

        # Lock the nest
        await db.update_player(user_id, locked=True)
        await interaction.followup.send("Your nest is now locked! Other players cannot brood your eggs. \U0001f512")

    @app_commands.command(name='unlock_nest', description='Unlock your nest to allow others to brood')
    async def unlock_nest(self, interaction: discord.Interaction):
        """Unlock your nest to allow others to brood"""
        await interaction.response.defer()
        log_debug(f"unlock_nest called by {interaction.user.id}")
        user_id = str(interaction.user.id)
        player = await db.load_player(user_id)

        # Check if nest is already unlocked
        if not player.get("locked", False):
            await interaction.followup.send("Your nest is already unlocked! \U0001f513")
            return

        # Unlock the nest
        await db.update_player(user_id, locked=False)
        await interaction.followup.send("Your nest is now unlocked! Other players can brood your eggs. \U0001f513")

    @app_commands.command(name='bless_egg', description='Use 1 \U0001f4a1Inspiration and 30 \U0001f330Seeds to bless your egg, preserving it and its prayers.')
    async def bless_egg_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer()
        log_debug(f"bless_egg called by {interaction.user.id}")
        user_id = str(interaction.user.id)

        success, message = await bless_egg(user_id)
        await interaction.followup.send(message)

    async def process_brooding(self, interaction_or_ctx, target_user, remaining_actions, prefetched_player=None, prefetched_egg=None, max_birds=None):
        """Helper function to process brooding for a single user"""
        target_user_id = str(target_user.id)
        target_player = prefetched_player if prefetched_player is not None else await db.load_player(target_user_id)

        # Check if target's nest is locked and brooder is not the owner
        user_id = getattr(interaction_or_ctx, 'user', getattr(interaction_or_ctx, 'author', None)).id
        if target_player.get("locked", False) and str(user_id) != target_user_id:
            return None, "Nest is locked!"

        # Check if target has an egg
        egg = prefetched_egg if prefetched_egg is not None else await db.get_egg(target_user_id)
        if egg is None:
            return None, "doesn't have an egg to brood"

        # Check if already brooded today
        brooder_id = str(user_id)
        today = get_current_date()
        if await db.has_brooded_today(brooder_id, target_user_id, today):
            return None, "already brooded this egg today"

        # Check nest capacity before hatching would occur
        would_hatch = egg["brooding_progress"] >= 10 or egg["brooding_progress"] + 1 >= 10
        if would_hatch:
            if max_birds is None:
                extra_bird_space = await get_extra_bird_space()
                max_birds = MAX_BIRDS_PER_NEST + extra_bird_space
            current_birds = await db.get_player_birds(target_user_id)
            if len(current_birds) >= max_birds:
                return None, f"nest already has the maximum of {max_birds} birds — free a spot before hatching"

        # If egg is already at hatching threshold (stuck state recovery), skip increment
        if egg["brooding_progress"] >= 10:
            new_progress = egg["brooding_progress"]
        else:
            # Record brooding and increment
            await db.record_brooding(brooder_id, target_user_id, today)
            new_progress = egg["brooding_progress"] + 1
            await db.update_egg(target_user_id, brooding_progress=new_progress)
            await db.add_egg_brooder(target_user_id, brooder_id)

        target_nest_name = target_player.get("nest_name", "Some Bird's Nest")

        if new_progress >= 10:
            if "multipliers" not in egg:
                full_egg = await db.get_egg(target_user_id)
                if full_egg is not None:
                    egg = full_egg

            # Get multipliers if they exist
            multipliers = egg.get("multipliers", {})

            # Get the main bird species
            bird_species = await select_random_bird_species(multipliers)
            chick = {
                "commonName": bird_species["commonName"],
                "scientificName": bird_species["scientificName"]
            }

            # Add the main chick to the nest via DB
            await db.add_bird(target_user_id, chick["commonName"], chick["scientificName"])

            # Check for "extra bird" effect from plants
            target_plants = await db.get_player_plants(target_user_id)
            extra_bird_chance = await get_extra_bird_chance(target_plants)
            extra_birds = []

            if extra_bird_chance > 0:
                # Calculate how many guaranteed extra birds (each 100% is one guaranteed bird)
                guaranteed_extra_birds = int(extra_bird_chance // 100)
                # Calculate chance for an additional extra bird
                remaining_chance = extra_bird_chance % 100

                # Add guaranteed extra birds
                for i in range(guaranteed_extra_birds):
                    extra_bird_species = await select_random_bird_species(multipliers)
                    extra_chick = {
                        "commonName": extra_bird_species["commonName"],
                        "scientificName": extra_bird_species["scientificName"]
                    }
                    await db.add_bird(target_user_id, extra_chick["commonName"], extra_chick["scientificName"])
                    extra_birds.append(extra_chick)

                # Check for chance of additional extra bird
                if remaining_chance > 0 and random.random() < (remaining_chance / 100):
                    extra_bird_species = await select_random_bird_species(multipliers)
                    extra_chick = {
                        "commonName": extra_bird_species["commonName"],
                        "scientificName": extra_bird_species["scientificName"]
                    }
                    await db.add_bird(target_user_id, extra_chick["commonName"], extra_chick["scientificName"])
                    extra_birds.append(extra_chick)

            # Handle blessed egg hatching
            saved_multipliers = handle_blessed_egg_hatching(egg, bird_species["scientificName"])

            # Delete the egg (cascades to multipliers/brooders)
            await db.delete_egg(target_user_id)

            # If we saved multipliers, create a new egg with them
            if saved_multipliers:
                # Apply plant brood reduction to the new egg (same as /lay_egg)
                less_brood_chance = await get_less_brood_chance(target_plants)
                initial_brooding_progress = 0
                if less_brood_chance > 0:
                    guaranteed_less_broods = int(less_brood_chance // 100)
                    remaining_chance = less_brood_chance % 100
                    if guaranteed_less_broods > 0:
                        initial_brooding_progress += guaranteed_less_broods
                    if remaining_chance > 0 and random.random() < (remaining_chance / 100):
                        initial_brooding_progress += 1
                await db.create_egg(target_user_id, brooding_progress=initial_brooding_progress, protected_prayers=False)
                for sci_name, mult_value in saved_multipliers.items():
                    await db.upsert_egg_multiplier(target_user_id, sci_name, mult_value)

            # Get updated bird count for the response
            updated_birds = await db.get_player_birds(target_user_id)
            total_chicks = len(updated_birds)

            # Add extra birds to the result tuple
            result_tuple = ("hatch", chick, target_nest_name, target_user, total_chicks)
            if extra_birds:
                result_tuple = ("hatch", chick, target_nest_name, target_user, total_chicks, extra_birds)

            return result_tuple, None
        else:
            remaining = 10 - new_progress
            return ("progress", remaining, target_nest_name, target_user), None

    async def send_hatching_response(self, interaction_or_ctx, result):
        """Helper function to send a hatching response"""
        # Check if we have extra birds in the result
        if len(result) > 5:
            _, chick, target_nest_name, target_user, total_chicks, extra_birds = result
        else:
            _, chick, target_nest_name, target_user, total_chicks = result
            extra_birds = []

        # Fetch image path and create embed for the main bird
        image_path, taxon_url = await self.fetch_bird_image(chick['scientificName'])

        # Create the base description for the main bird
        description = f"{target_user.mention}'s egg has hatched into a **{chick['commonName']}** (*{chick['scientificName']}*)!"

        embed = discord.Embed(
            title="\U0001f423 Egg Hatched!",
            description=description,
            color=discord.Color.green()
        )

        embed.add_field(
            name="Total Chicks",
            value=f"{target_user.mention} now has {total_chicks} {'chick' if total_chicks == 1 else 'chicks'}! \U0001f426",
            inline=False
        )

        # Add plant effect explanation if extra birds hatched
        if extra_birds:
            plant_effect = f"Your garden's plants gave you {len(extra_birds)} extra {'bird' if len(extra_birds) == 1 else 'birds'}! \U0001f331"
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
            title="\U0001f423 Extra Bird Hatched!",
            description=f"{target_user.mention} received an extra bird: **{extra_chick['commonName']}** (*{extra_chick['scientificName']}*)!",
            color=discord.Color.gold()
        )

        extra_embed.add_field(
            name="Plant Effect",
            value="This extra bird hatched thanks to your garden's plants! \U0001f331",
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
        await interaction.response.defer()
        log_debug(f"pray_for_bird called by {interaction.user.id}")
        user_id = str(interaction.user.id)

        # Check if nest has an egg
        egg = await db.get_egg(user_id)
        if egg is None:
            await interaction.followup.send("You don't have an egg to pray for! \U0001f95a")
            return

        # Validate amount of prayers
        if amount_of_prayers <= 0:
            await interaction.followup.send("You must pray at least once! \U0001f64f")
            return

        # Check if user has enough actions
        remaining_actions = await get_remaining_actions(user_id)
        if remaining_actions < amount_of_prayers:
            await interaction.followup.send(
                f"You don't have enough actions! You need {amount_of_prayers} but only have {remaining_actions} remaining. \U0001f319"
            )
            return

        # Validate bird species exists in either main codex or manifested birds
        all_birds = await load_bird_species()  # This now includes both standard and manifested birds

        valid_species = False
        for species in all_birds:
            if species["scientificName"].lower() == scientific_name.lower():
                scientific_name = species["scientificName"]  # Use correct casing
                valid_species = True
                break

        if not valid_species:
            await interaction.followup.send(f"Invalid bird species: {scientific_name}. Make sure it exists in the codex or has been fully manifested.")
            return

        # Get current multiplier from the egg
        multipliers = egg.get("multipliers", {})
        current_multiplier = multipliers.get(scientific_name, 0)

        # Get prayer effectiveness exponent from research
        prayer_exponent = await get_prayer_effectiveness_bonus()

        # Calculate effective prayers to add using exponentiation
        if amount_of_prayers > 0:
            effective_prayers_to_add = amount_of_prayers ** prayer_exponent
        else:
            effective_prayers_to_add = 0

        new_multiplier = current_multiplier + effective_prayers_to_add
        await db.upsert_egg_multiplier(user_id, scientific_name, new_multiplier)

        # Calculate actual percentage chance
        total_weight = 0
        target_weight = 0
        target_base_weight = 0

        # Calculate total weights with multipliers
        # Re-read egg to get all current multipliers including the one we just updated
        updated_multipliers = egg.get("multipliers", {})
        updated_multipliers[scientific_name] = new_multiplier

        for species in all_birds:
            base_weight = species["rarityWeight"]
            if species["scientificName"] == scientific_name:
                target_base_weight = base_weight
                multiplied_weight = base_weight * new_multiplier
                target_weight = multiplied_weight
                total_weight += multiplied_weight
            else:
                # Apply any existing multipliers for other species
                if species["scientificName"] in updated_multipliers:
                    total_weight += base_weight * updated_multipliers[species["scientificName"]]
                else:
                    total_weight += base_weight

        base_percentage = (target_base_weight / sum(s["rarityWeight"] for s in all_birds)) * 100
        actual_percentage = (target_weight / total_weight) * 100

        # Consume actions
        await record_actions(user_id, amount_of_prayers, "pray")

        response_message = (
            f"\U0001f64f You offered {amount_of_prayers} {'prayer' if amount_of_prayers == 1 else 'prayers'} for {scientific_name}! \U0001f64f\n"
        )
        if prayer_exponent > 1.0: # Check if there's any bonus
            response_message += f"Your research empowered your prayers (exponent: {prayer_exponent:.2f}), resulting in {effective_prayers_to_add:.2f} effective prayers added!\n"

        response_message += (
            f"Their hatching chance multiplier is now {new_multiplier:.2f}x\n"
            f"Base chance: {base_percentage:.1f}% \u2192 Current chance: {actual_percentage:.1f}%"
        )

        await interaction.followup.send(response_message)

async def setup(bot):
    await bot.add_cog(IncubationCommands(bot))
