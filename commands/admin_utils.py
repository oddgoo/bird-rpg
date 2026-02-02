import discord
from discord.ext import commands
import data.storage as db
from utils.logging import log_debug

# Standalone function for updating usernames
async def update_discord_usernames(bot):
    """Updates the discord_username field for all users in the database."""
    try:
        players = await db.load_all_players()
        if not players:
            log_debug("No players found in database")
            return 0, 0, []

        updated_count = 0
        error_count = 0
        not_found_ids = []

        for player in players:
            user_id_str = str(player.get("user_id", ""))
            try:
                user_id = int(user_id_str)
                user = await bot.fetch_user(user_id)
                if user:
                    username = user.name  # Using user.name
                    await db.update_player(user_id_str, discord_username=username)
                    updated_count += 1
                    log_debug(f"Updated username for {user_id_str}: {username}")
                else:
                    log_debug(f"Could not find user for ID: {user_id_str}")
                    not_found_ids.append(user_id_str)
                    error_count += 1
            except discord.NotFound:
                log_debug(f"Discord user not found for ID: {user_id_str}")
                not_found_ids.append(user_id_str)
                error_count += 1
            except ValueError:
                log_debug(f"Invalid user ID format found: {user_id_str}")
                error_count += 1
            except Exception as e:
                log_debug(f"Error fetching user {user_id_str}: {e}")
                error_count += 1

        log_debug(f"Username update complete. Updated: {updated_count}, Errors: {error_count}")
        return updated_count, error_count, not_found_ids

    except Exception as e:
        log_debug(f"Error in update_discord_usernames: {e}")
        return 0, 0, []

class AdminUtils(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

# The setup function should be defined only once at the end of the file
async def setup(bot):
    await bot.add_cog(AdminUtils(bot))
