from datetime import datetime
import discord
from discord.ext import commands
from discord import app_commands

import data.storage as db
from data.models import (
    get_remaining_actions, record_actions, add_bonus_actions,
    get_singing_bonus, get_singing_inspiration_chance
)
from utils.logging import log_debug
from utils.time_utils import get_time_until_reset, get_current_date
from config.config import DEBUG

class SingingCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _process_singing(self, interaction: discord.Interaction, target_users: list[discord.User]):
        """Helper method to process the core singing logic for a list of target users."""
        singer_id = interaction.user.id
        successful_targets = []
        skipped_targets = []

        # Check initial actions before loop
        singer_remaining_actions = await get_remaining_actions(singer_id)
        if singer_remaining_actions <= 0:
            # If no actions at the start, skip everyone
            for target_user in target_users:
                 skipped_targets.append((target_user, "no actions left"))
            return successful_targets, skipped_targets

        today = get_current_date()

        # Process each target user
        for target_user in target_users:
            # Re-check actions at the start of each loop iteration
            singer_remaining_actions = await get_remaining_actions(singer_id)
            if singer_remaining_actions <= 0:
                skipped_targets.append((target_user, "no actions left"))
                continue # Skip this user and check the next

            target_id = target_user.id

            # Skip bots
            if target_user.bot:
                skipped_targets.append((target_user, "is a bot"))
                continue

            # Skip self unless in debug mode
            if singer_id == target_id and not DEBUG:
                skipped_targets.append((target_user, "is yourself"))
                continue

            # Skip if already sung to today
            if await db.has_been_sung_to_by(singer_id, target_id, today):
                skipped_targets.append((target_user, "already sung to today"))
                continue

            # Get bonuses
            birds = await db.get_player_birds(singer_id)
            bonus_actions = await get_singing_bonus(birds)
            inspiration_bonus = await get_singing_inspiration_chance(singer_id, birds)

            await db.record_song(singer_id, target_id, today)
            await add_bonus_actions(target_id, 3 + bonus_actions)
            await record_actions(singer_id, 1, "sing")

            # Add inspiration from finches
            if inspiration_bonus > 0:
                await db.increment_player_field(singer_id, "inspiration", inspiration_bonus)

            successful_targets.append((target_user, bonus_actions, inspiration_bonus))

        return successful_targets, skipped_targets


    @app_commands.command(name='sing', description='Give other users extra actions for the day')
    @app_commands.describe(target_users_str='The users to sing to (mention them)') # Corrected parameter name
    async def sing(self, interaction: discord.Interaction, target_users_str: str):
        """Give other users extra actions for the day. Each bird can only sing once to the same target per day."""
        await interaction.response.defer() # Defer response immediately

        # Parse mentioned users
        target_users = []
        for user_id in target_users_str.split():
            try:
                user_id = user_id.strip('<@!>') # Keep original name
                user = await self.bot.fetch_user(int(user_id))
                target_users.append(user)
            except Exception as e:
                log_debug(f"Could not parse user ID {user_id} in sing command: {e}")
                continue # Skip invalid mentions

        if not target_users:
            await interaction.response.send_message("Please mention valid users to sing to! Usage: /sing @user1 @user2 ...")
            return

        log_debug(f"sing command called by {interaction.user.id} for users {[user.id for user in target_users]}")

        # Store the list of all attempted target IDs for the /sing_repeat command
        await db.set_last_song_targets(interaction.user.id, [str(user.id) for user in target_users])

        # Call the helper method to process singing
        successful_targets, skipped_targets = await self._process_singing(interaction, target_users)

        # Construct response message
        if not successful_targets and not skipped_targets:
             # This case should ideally not happen if target_users was not empty, but good to handle
             await interaction.response.send_message("Something went wrong while trying to sing.")
             return
        elif not successful_targets:
            message = ["❌ Couldn't sing to any of the specified users:"]
            for user, reason in skipped_targets:
                message.append(f"• {user.mention} ({reason})")
        else:
            message = ["🎵 Your beautiful song has inspired:"]
            for user, action_bonus, inspiration_gained in successful_targets:
                base_msg = f"{user.mention} (+3"
                if action_bonus > 0:
                    base_msg += f" +{action_bonus}✨"
                base_msg += " actions)"
                message.append(base_msg)

            if any(insp > 0 for _, _, insp in successful_targets):
                message.append(f"\n✨ Your finches' songs brought you +{sum(insp for _, _, insp in successful_targets)} inspiration!")

            if skipped_targets:
                message.append("\n Couldn't sing to:")
                for user, reason in skipped_targets:
                    message.append(f"• {user.mention} ({reason})")

            singer_actions_left = await get_remaining_actions(interaction.user.id)
            message.append(f"\n(You have {singer_actions_left} {'action' if singer_actions_left == 1 else 'actions'} remaining)")

        await interaction.followup.send("\n".join(message)) # Use followup.send

    @app_commands.command(name='sing_repeat', description='Repeat your last singing action, targeting the same users.')
    async def sing_repeat(self, interaction: discord.Interaction):
        """Repeats the last singing action, targeting the same users as the previous /sing command."""
        await interaction.response.defer() # Defer response immediately
        log_debug(f"sing_repeat command called by {interaction.user.id}")

        last_target_ids = await db.get_last_song_targets(interaction.user.id)

        if not last_target_ids:
            await interaction.followup.send("You haven't used the `/sing` command recently, or your last attempt had no valid users, so there's no song to repeat! 🤷") # Use followup
            return

        # Fetch user objects from IDs
        target_users = []
        invalid_ids = []
        for user_id_str in last_target_ids:
            try:
                user = await self.bot.fetch_user(int(user_id_str))
                target_users.append(user)
            except discord.NotFound:
                log_debug(f"User ID {user_id_str} not found for sing_repeat.")
                invalid_ids.append(user_id_str)
            except ValueError:
                 log_debug(f"Invalid user ID format {user_id_str} for sing_repeat.")
                 invalid_ids.append(user_id_str) # Keep track of invalid IDs

        # Check if we have any valid users left after fetching
        if not target_users:
            msg = "Could not find any valid users from your last song."
            if invalid_ids:
                msg += f" Failed to find users with IDs: {', '.join(invalid_ids)}"
            await interaction.followup.send(msg + " 🤔") # Use followup
            return

        # Call the helper method to process singing
        successful_targets, skipped_targets = await self._process_singing(interaction, target_users)

        # Construct response message
        if not successful_targets and not skipped_targets:
             # This case should ideally not happen if target_users was not empty, but good to handle
             await interaction.followup.send("Something went wrong while trying to repeat the song.") # Use followup
             return
        elif not successful_targets:
            message = ["❌ Couldn't repeat the song for any of the previous targets:"]
            # Add skipped reasons from the helper method
            for user, reason in skipped_targets:
                message.append(f"• {user.mention} ({reason})")
            # Add invalid IDs found during fetching
            if invalid_ids:
                 message.append(f"\nAlso couldn't find users with IDs: {', '.join(invalid_ids)}")
        else:
            message = ["🎵 Repeating your song, you inspired:"] # Start repeat message
            for user, action_bonus, inspiration_gained in successful_targets:
                base_msg = f"{user.mention} (+3"
                if action_bonus > 0:
                    base_msg += f" +{action_bonus}✨"
                base_msg += " actions)"
                message.append(base_msg)

            if any(insp > 0 for _, _, insp in successful_targets):
                total_inspiration = sum(insp for _, _, insp in successful_targets)
                message.append(f"\n✨ Your finches' repeated songs brought you +{total_inspiration} inspiration!")

            # Add skipped reasons from the helper method
            if skipped_targets:
                message.append("\n Couldn't sing to:")
                for user, reason in skipped_targets:
                    message.append(f"• {user.mention} ({reason})")
            # Add invalid IDs found during fetching
            if invalid_ids:
                 message.append(f"\nAlso couldn't find users with IDs: {', '.join(invalid_ids)}")

            # Use the latest data to get remaining actions
            singer_actions_left = await get_remaining_actions(interaction.user.id)
            message.append(f"\n(You have {singer_actions_left} {'action' if singer_actions_left == 1 else 'actions'} remaining)")

        await interaction.followup.send("\n".join(message)) # Use followup.send

async def setup(bot):
    await bot.add_cog(SingingCommands(bot))
