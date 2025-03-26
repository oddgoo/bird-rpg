import discord
from discord.ext import commands
from data.storage import load_data, save_data
from utils.logging import log_debug

# Standalone function for updating usernames
async def update_discord_usernames(bot):
    """Updates the discord_username field for all users in nests.json."""
    try:
        data = load_data()
        if "personal_nests" not in data:
            log_debug("No personal nests found in data")
            return 0, 0, []

        updated_count = 0
        error_count = 0
        not_found_ids = []

        for user_id_str in list(data["personal_nests"].keys()):
            try:
                user_id = int(user_id_str)
                user = await bot.fetch_user(user_id)
                if user:
                    username = user.name  # Using user.name
                    data["personal_nests"][user_id_str]["discord_username"] = username
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
                log_debug(f"Invalid user ID format found in nests.json: {user_id_str}")
                error_count += 1
            except Exception as e:
                log_debug(f"Error fetching user {user_id_str}: {e}")
                error_count += 1

        save_data(data)
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
