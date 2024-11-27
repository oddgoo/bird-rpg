import os
import discord
from discord.ext import commands
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
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.errors.CommandNotFound):
        command_used = ctx.message.content.split()[0][1:]
        await ctx.send(f"❌ Command `!{command_used}` not recognized! Use `!nest_help` to see available commands.")
    elif isinstance(error, commands.errors.MissingRequiredArgument):
        await ctx.send("❌ Missing required argument! Check `!nest_help` for proper usage.")
    elif isinstance(error, commands.errors.BadArgument):
        await ctx.send("❌ Invalid argument! Please provide a valid number.")
    else:
        log_debug(f"Unexpected error: {str(error)}")
        await ctx.send("❌ An unexpected error occurred. Please try again later.")


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    print(f"Message received: {message.content}")
    await bot.process_commands(message)

@bot.event
async def on_ready():
    print(f'Bot is ready. Logged in as {bot.user.name}')
    print(f'Debug mode: {"ON" if DEBUG else "OFF"}')
    
    # Print loaded commands after bot is ready
    print("\nLoaded commands:")
    for cog_name, cog in bot.cogs.items():
        commands_list = [cmd.name for cmd in cog.get_commands()]
        print(f"{cog_name}: {commands_list}")
    
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
        'commands.testing',
        'commands.customisation',
        'commands.incubation'
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