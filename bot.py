import os
import discord
from discord.ext import commands
from discord import app_commands
from config.config import DEBUG
from web.server import start_server
from utils.logging import log_debug
from data.storage import load_data, save_data
import asyncio

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# Error handling
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandNotFound):
        await interaction.response.send_message("❌ Command not recognized! Use `/help` to see available commands.")
    elif isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("❌ You don't have permission to use this command!")
    elif isinstance(error, app_commands.TransformerError):
        await interaction.response.send_message("❌ Invalid argument! Please check the command options.")
    else:
        log_debug(f"Unexpected error: {str(error)}")
        await interaction.response.send_message("❌ An unexpected error occurred. Please try again later.")

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
    
    # Run data migration on startup
    try:
        data = load_data()
        
        # Migrate old song data format to new format
        if "daily_songs" in data:
            for date, songs in data["daily_songs"].items():
                if isinstance(songs, list):
                    print(f"Migrating songs data for {date}...")
                    new_format = {}
                    for user_id in songs:
                        new_format[user_id] = ["migration"]
                    data["daily_songs"][date] = new_format
                    
            save_data(data)
            print("Song data migration completed!")
    except Exception as e:
        print(f"Error during data migration: {e}")

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
        'commands.flock',
        'commands.lore',
        'commands.social',
        'commands.exploration',
        'commands.swooping'
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