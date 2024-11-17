import os
import json
import discord
from flask import Flask
from threading import Thread
from discord.ext import commands
from datetime import datetime
from dotenv import load_dotenv

app = Flask('')
port = int(os.getenv('PORT', 10000))

@app.route('/')
def home():
    return "Discord bot is running!"

def run_server():
    app.run(host='0.0.0.0', port=port)

STORAGE_PATH = '/var/data' if os.path.exists('/var/data') else '.'  # Use /var/data on Render, local directory otherwise
DATA_PATH = os.path.join(STORAGE_PATH, 'bird-rpg')
NESTS_FILE = os.path.join(DATA_PATH, 'nests.json')

os.makedirs(DATA_PATH, exist_ok=True)

# Load environment variables
load_dotenv()

# Bot configuration
DEBUG = False  # Set to True for testing, False for production
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# Debug logging
def log_debug(message):
    print(f"[DEBUG] {datetime.now().strftime('%H:%M:%S')}: {message}")

# File operations
def load_data():
    try:
        if os.path.exists(NESTS_FILE):
            with open(NESTS_FILE, 'r') as f:
                data = json.load(f)
                log_debug("Data loaded successfully")
                return data
        log_debug("No existing data, creating new")
        default_data = {
            "personal_nests": {},
            "common_nest": {"twigs": 0, "seeds": 0},
            "daily_actions": {}
        }
        save_data(default_data)
        return default_data
    except Exception as e:
        log_debug(f"Error loading data: {e}")
        raise

def save_data(data):
    try:
        # Create backup before saving?
        if os.path.exists(NESTS_FILE):
            # backup_file = f"{NESTS_FILE}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            # with open(NESTS_FILE, 'r') as src, open(backup_file, 'w') as dst:
            #     dst.write(src.read())
            # log_debug(f"Backup created: {backup_file}")
            pass
        
        with open(NESTS_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        log_debug("Data saved successfully")
    except Exception as e:
        log_debug(f"Error saving data: {e}")
        raise

# Helper functions
def get_personal_nest(data, user_id):
    user_id = str(user_id)
    if user_id not in data["personal_nests"]:
        data["personal_nests"][user_id] = {"twigs": 0, "seeds": 0}
    return data["personal_nests"][user_id]

def get_common_nest(data):
    return data["common_nest"]

def get_remaining_actions(data, user_id):
    user_id = str(user_id)
    today = datetime.now().strftime('%Y-%m-%d')
    
    if user_id not in data["daily_actions"]:
        data["daily_actions"][user_id] = {}
    
    if f"actions_{today}" not in data["daily_actions"][user_id]:
        data["daily_actions"][user_id][f"actions_{today}"] = 0
        
    actions_used = data["daily_actions"][user_id][f"actions_{today}"]
    return 3 - actions_used

def record_actions(data, user_id, count):
    user_id = str(user_id)
    today = datetime.now().strftime('%Y-%m-%d')
    
    if user_id not in data["daily_actions"]:
        data["daily_actions"][user_id] = {}
    
    if f"actions_{today}" not in data["daily_actions"][user_id]:
        data["daily_actions"][user_id][f"actions_{today}"] = 0
        
    data["daily_actions"][user_id][f"actions_{today}"] += count

# Core commands
@bot.command(name='build_nest_own', aliases=['build_nests_own'])
async def build_nest_own(ctx, amount: int = 1):
    log_debug(f"build_nest_own called by {ctx.author.id} for {amount}")
    data = load_data()
    
    if amount < 1:
        await ctx.send("Please specify a positive number of twigs to add! 🪹")
        return
    
    remaining_actions = get_remaining_actions(data, ctx.author.id)
    if remaining_actions <= 0:
        await ctx.send("You've used all your actions for today! Come back tomorrow! 🌙")
        return
    
    # Adjust amount if it would exceed remaining actions
    amount = min(amount, remaining_actions)
    
    nest = get_personal_nest(data, ctx.author.id)
    nest["twigs"] += amount
    record_actions(data, ctx.author.id, amount)
    
    save_data(data)
    remaining = get_remaining_actions(data, ctx.author.id)
    await ctx.send(f"Added {amount} {'twig' if amount == 1 else 'twigs'} to your nest! 🪹\n"
                  f"Your nest now has {nest['twigs']} twigs and {nest['seeds']} seeds.\n"
                  f"You have {remaining} {'action' if remaining == 1 else 'actions'} remaining today.")

@bot.command(name='build_nest_common', aliases=['build_nests_common'])
async def build_nest_common(ctx, amount: int = 1):
    log_debug(f"build_nest_common called by {ctx.author.id} for {amount}")
    data = load_data()
    
    if amount < 1:
        await ctx.send("Please specify a positive number of twigs to add! 🪺")
        return
    
    remaining_actions = get_remaining_actions(data, ctx.author.id)
    if remaining_actions <= 0:
        await ctx.send("You've used all your actions for today! Come back tomorrow! 🌙")
        return
    
    amount = min(amount, remaining_actions)
    
    data["common_nest"]["twigs"] += amount
    record_actions(data, ctx.author.id, amount)
    
    save_data(data)
    nest = data["common_nest"]
    remaining = get_remaining_actions(data, ctx.author.id)
    await ctx.send(f"Added {amount} {'twig' if amount == 1 else 'twigs'} to the common nest! 🪺\n"
                  f"The common nest now has {nest['twigs']} twigs and {nest['seeds']} seeds.\n"
                  f"You have {remaining} {'action' if remaining == 1 else 'actions'} remaining today.")

@bot.command(name='add_seed_own', aliases=['add_seeds_own'])
async def add_seed_own(ctx, amount: int = 1):
    log_debug(f"add_seed_own called by {ctx.author.id} for {amount}")
    data = load_data()
    
    if amount < 1:
        await ctx.send("Please specify a positive number of seeds to add! 🌱")
        return
    
    remaining_actions = get_remaining_actions(data, ctx.author.id)
    if remaining_actions <= 0:
        await ctx.send("You've used all your actions for today! Come back tomorrow! 🌙")
        return
    
    nest = get_personal_nest(data, ctx.author.id)
    space_available = nest["twigs"] - nest["seeds"]
    amount = min(amount, space_available, remaining_actions)
    
    if amount <= 0:
        await ctx.send("Your nest is full! Add more twigs to store more seeds. 🪹")
        return
    
    nest["seeds"] += amount
    record_actions(data, ctx.author.id, amount)
    
    save_data(data)
    remaining = get_remaining_actions(data, ctx.author.id)
    await ctx.send(f"Added {amount} {'seed' if amount == 1 else 'seeds'} to your nest! 🏡\n"
                  f"Your nest now has {nest['twigs']} twigs and {nest['seeds']} seeds.\n"
                  f"You have {remaining} {'action' if remaining == 1 else 'actions'} remaining today.")
                  
@bot.command(name='add_seed_common', aliases=['add_seeds_common'])
async def add_seed_common(ctx, amount: int = 1):
    log_debug(f"add_seed_common called by {ctx.author.id} for {amount}")
    data = load_data()
    
    if amount < 1:
        await ctx.send("Please specify a positive number of seeds to add! 🌱")
        return
    
    remaining_actions = get_remaining_actions(data, ctx.author.id)
    if remaining_actions <= 0:
        await ctx.send("You've used all your actions for today! Come back tomorrow! 🌙")
        return
    
    common_nest = data["common_nest"]
    space_available = common_nest["twigs"] - common_nest["seeds"]
    amount = min(amount, space_available, remaining_actions)
    
    if amount <= 0:
        await ctx.send("The common nest is full! Add more twigs to store more seeds. 🪺")
        return
    
    common_nest["seeds"] += amount
    record_actions(data, ctx.author.id, amount)
    
    save_data(data)
    remaining = get_remaining_actions(data, ctx.author.id)
    await ctx.send(f"Added {amount} {'seed' if amount == 1 else 'seeds'} to the common nest! 🌇\n"
                  f"The common nest now has {common_nest['twigs']} twigs and {common_nest['seeds']} seeds.\n"
                  f"You have {remaining} {'action' if remaining == 1 else 'actions'} remaining today.")

@bot.command(name='move_seeds_own')
async def move_seeds_own(ctx, amount: int):
    log_debug(f"move_seeds_own called by {ctx.author.id} for {amount} seeds")
    data = load_data()
    
    nest = get_personal_nest(data, ctx.author.id)
    common_nest = data["common_nest"]
    
    if amount > nest["seeds"]:
        await ctx.send("You don't have enough seeds in your nest! 🏡")
        return
    
    if common_nest["seeds"] + amount > common_nest["twigs"]:
        await ctx.send("The common nest doesn't have enough space! 🌇")
        return
    
    nest["seeds"] -= amount
    common_nest["seeds"] += amount
    
    save_data(data)
    await ctx.send(f"Moved {amount} seeds from your nest to the common nest!\n"
                  f"Your nest: {nest['twigs']} twigs, {nest['seeds']} seeds\n"
                  f"Common nest: {common_nest['twigs']} twigs, {common_nest['seeds']} seeds")

@bot.command(name='move_seeds_common')
async def move_seeds_common(ctx, amount: int):
    log_debug(f"move_seeds_common called by {ctx.author.id} for {amount} seeds")
    data = load_data()
    
    nest = get_personal_nest(data, ctx.author.id)
    common_nest = data["common_nest"]
    
    if amount > common_nest["seeds"]:
        await ctx.send("There aren't enough seeds in the common nest! 🌇")
        return
    
    if nest["seeds"] + amount > nest["twigs"]:
        await ctx.send("Your nest doesn't have enough space! 🏡")
        return
    
    common_nest["seeds"] -= amount
    nest["seeds"] += amount
    
    save_data(data)
    await ctx.send(f"Moved {amount} seeds from the common nest to your nest!\n"
                  f"Your nest: {nest['twigs']} twigs, {nest['seeds']} seeds\n"
                  f"Common nest: {common_nest['twigs']} twigs, {common_nest['seeds']} seeds")
    
@bot.command(name='nests')
async def show_nests(ctx):
    log_debug(f"nests command called by {ctx.author.id}")
    data = load_data()
    
    # Get nest info
    personal_nest = get_personal_nest(data, ctx.author.id)
    common_nest = get_common_nest(data)
    remaining_actions = get_remaining_actions(data, ctx.author.id)
    
    # Create status message
    status = "**🏠 Your Nest Status:**\n"
    status += f"```\nTwigs: {personal_nest['twigs']} 🪹\n"
    status += f"Seeds: {personal_nest['seeds']} 🌰\n"
    status += f"Space available: {personal_nest['twigs'] - personal_nest['seeds']} spots\n```\n"
    
    status += "**🌇 Common Nest Status:**\n"
    status += f"```\nTwigs: {common_nest['twigs']} 🪺\n"
    status += f"Seeds: {common_nest['seeds']} 🌰\n"
    status += f"Space available: {common_nest['twigs'] - common_nest['seeds']} spots\n```\n"
    
    status += "**📋 Today's Actions:**\n"
    status += f"Remaining actions: {remaining_actions}/3"
    
    await ctx.send(status)

# Testing commands
@bot.command(name='test_reset_daily')
async def test_reset_daily(ctx):
    if not DEBUG:
        await ctx.send("Debug mode is not enabled.")
        return
    log_debug("test_reset_daily called")
    data = load_data()
    data["daily_actions"] = {}
    save_data(data)
    await ctx.send("🔄 Reset all daily actions for testing")

@bot.command(name='test_status')
async def test_status(ctx):
    if not DEBUG:
        await ctx.send("Debug mode is not enabled.")
        return
    log_debug(f"test_status called by {ctx.author.id}")
    data = load_data()
    user_id = str(ctx.author.id)
    
    personal_nest = get_personal_nest(data, user_id)
    daily_actions = data["daily_actions"].get(user_id, {})
    
    status = f"**Your Status:**\n"
    status += f"🪹 Twigs: {personal_nest['twigs']}\n"
    status += f"🌰 Seeds: {personal_nest['seeds']}\n"
    status += "\n**Today's Actions:**\n"
    status += f"Built nest today: {'✅' if any('build_twig' in action for action in daily_actions) else '❌'}\n"
    status += f"Collected seed today: {'✅' if any('add_seed' in action for action in daily_actions) else '❌'}"
    
    await ctx.send(status)

@bot.command(name='nest_help', aliases=['help'])
async def help_command(ctx):
    help_text = """
**🪹 Nest Building Commands:**
`!build_nest_own [amount]` - Add twigs to your personal nest
`!build_nest_common [amount]` - Add twigs to the common nest
`!add_seed_own [amount]` - Add seeds to your personal nest
`!add_seed_common [amount]` - Add seeds to the common nest
`!move_seeds_own <amount>` - Move seeds from your nest to common nest
`!move_seeds_common <amount>` - Move seeds from common nest to your nest
`!nests` - Show status of your nest and common nest

**📋 Rules:**
• You have 3 actions per day total
• Each twig or seed added counts as one action
• A nest can only hold as many seeds as it has twigs
• Moving seeds doesn't count as an action

Note: If [amount] is not specified, it defaults to 1
"""
    
    if DEBUG:
        help_text += """
**🔧 Testing Commands:**
`!test_status` - Check your current status
`!test_reset_daily` - Reset daily actions
"""
    
    await ctx.send(help_text)

@bot.event
async def on_ready():
    print(f'Bot is ready. Logged in as {bot.user.name}')
    print(f'Debug mode: {"ON" if DEBUG else "OFF"}')
    
    if DEBUG:
        print("\nTest Commands Available:")
        print("!test_reset_daily - Reset all daily actions")
        print("!test_next_day - Simulate next day")
        print("!test_status - Check your current status")

# Error handling
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.errors.CommandNotFound):
        # Handle unknown commands
        command_used = ctx.message.content.split()[0][1:]  # Remove the ! prefix
        await ctx.send(f"❌ Command `!{command_used}` not recognized! Use `!nest_help` to see available commands.")
    elif isinstance(error, commands.errors.MissingRequiredArgument):
        await ctx.send("❌ Missing required argument! Check `!nest_help` for proper usage.")
    elif isinstance(error, commands.errors.BadArgument):
        await ctx.send("❌ Invalid argument! Please provide a valid number.")
    else:
        # Log the error details for debugging
        log_debug(f"Unexpected error: {str(error)}")
        # Send a generic error message to the user
        await ctx.send("❌ An unexpected error occurred. Please try again later.")


def main():
    # Start web server in a separate thread
    server_thread = Thread(target=run_server)
    server_thread.start()
    
    # Start the bot
    load_dotenv()
    bot.run(os.getenv('DISCORD_TOKEN'))

if __name__ == "__main__":
    main()