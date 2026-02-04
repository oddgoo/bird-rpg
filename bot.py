import os
import discord
from discord.ext import commands
from discord import app_commands
from config.config import DEBUG
from web.server import start_server
from utils.logging import log_debug
from commands.admin_utils import update_discord_usernames
import asyncio

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# Global check: block commands for users in an active flock (pomobirdo)
@bot.tree.interaction_check
async def flock_focus_check(interaction: discord.Interaction) -> bool:
    # Allow flock commands through
    if interaction.command and interaction.command.name in ('start_flock', 'join_flock'):
        return True
    # Check if user is in an active flock
    flock_cog = bot.cogs.get('FlockCommands')
    if flock_cog and flock_cog.active_flock:
        if interaction.user in flock_cog.active_flock['members']:
            if interaction.response.is_done():
                await interaction.followup.send("You cant do any actions while in a pomobirdo! You are focusing!")
            else:
                await interaction.response.send_message("You cant do any actions while in a pomobirdo! You are focusing!")
            return False
    return True

# Error handling
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandNotFound):
        msg = "❌ Command not recognized! Use `/help` to see available commands."
    elif isinstance(error, app_commands.MissingPermissions):
        msg = "❌ You don't have permission to use this command!"
    elif isinstance(error, app_commands.TransformerError):
        msg = "❌ Invalid argument! Please check the command options."
    else:
        log_debug(f"Unexpected error: {str(error)}")
        msg = "❌ An unexpected error occurred. Please try again later."

    if interaction.response.is_done():
        await interaction.followup.send(msg)
    else:
        await interaction.response.send_message(msg)

@bot.event
async def on_ready():
    print(f'Bot is ready. Logged in as {bot.user.name}')
    print(f'Debug mode: {"ON" if DEBUG else "OFF"}')

    # Sync slash commands
    try:
        print("Syncing slash commands...")
        await bot.tree.sync()
        print("Slash commands synced successfully!")
    except Exception as e:
        print(f"Failed to sync slash commands: {e}")

    # Print loaded commands after bot is ready
    print("\nLoaded commands:")
    for command in bot.tree.get_commands():
        print(f"/{command.name}")

    # Verify Supabase connectivity
    try:
        from data.db import get_async_client
        sb = await get_async_client()
        res = await sb.table("common_nest").select("id").limit(1).execute()
        print(f"Supabase connection verified. Common nest exists: {bool(res.data)}")
        if not res.data:
            # Initialize common nest singleton
            await sb.table("common_nest").insert({"id": 1, "twigs": 0, "seeds": 0}).execute()
            print("Initialized common nest in Supabase.")
    except Exception as e:
        print(f"Supabase connection error: {e}")

    # Update Discord usernames (skip in debug/local mode)
    if DEBUG:
        print("Skipping Discord username update (DEBUG mode)")
    else:
        try:
            print("Updating Discord usernames...")
            updated, errors, not_found = await update_discord_usernames(bot)
            print(f"Username update complete: {updated} updated, {errors} errors")
            if not_found:
                print(f"IDs not found: {', '.join(not_found)}")
        except Exception as e:
            print(f"Error during username update: {e}")

# Move cog loading into a function
async def load_cogs(bot):
    COGS = [
        'commands.build',
        'commands.seeds',
        'commands.singing',
        'commands.info',
        'commands.testing' if DEBUG else None,
        'commands.customisation',
        'commands.incubation',
        'commands.foraging',
        'commands.flock',
        'commands.lore',
        'commands.social',
        'commands.exploration',
        'commands.swooping',
        'commands.gardening',
        'commands.weather',
        'commands.research',
        'commands.manifest',
        'commands.admin_utils',
        'commands.birdwatch'
    ]


    for cog in COGS:
        try:
            await bot.load_extension(cog)
            print(f"Loaded {cog}")
        except Exception as e:
            print(f"Error loading {cog}: {str(e)}")

async def main():
    # Load cogs
    await load_cogs(bot)

    # Start web server
    server_thread = start_server()

    # Start the bot
    try:
        await bot.start(os.getenv('DISCORD_TOKEN'))
    finally:
        # Cleanup if needed
        print("Bot shutting down...")

if __name__ == "__main__":
    asyncio.run(main())
