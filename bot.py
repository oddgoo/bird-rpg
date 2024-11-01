import os
import json
import discord
from discord.ext import commands
from datetime import datetime
from dotenv import load_dotenv

STORAGE_PATH = '/var/data' if os.path.exists('/var/data') else '.'  # Use /var/data on Render, local directory otherwise
DATA_PATH = os.path.join(STORAGE_PATH, 'bird-rpg')
NESTS_FILE = os.path.join(DATA_PATH, 'nests.json')

# Load environment variables
load_dotenv()

# Bot configuration
DEBUG = True  # Set to True for testing, False for production
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Debug logging
def log_debug(message):
    if DEBUG:
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
        # Save default data if it doesn't exist
        save_data(default_data)
        return default_data
    except Exception as e:
        log_debug(f"Error loading data: {e}")
        raise

def save_data(data):
    try:
        # Create backup before saving
        if os.path.exists(NESTS_FILE):
            backup_file = f"{NESTS_FILE}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            with open(NESTS_FILE, 'r') as src, open(backup_file, 'w') as dst:
                dst.write(src.read())
            log_debug(f"Backup created: {backup_file}")
        
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

def check_daily_action(data, user_id, action_type):
    user_id = str(user_id)
    today = datetime.now().strftime('%Y-%m-%d')
    
    if user_id not in data["daily_actions"]:
        data["daily_actions"][user_id] = {}
    
    return f"{action_type}_{today}" in data["daily_actions"][user_id]

def record_daily_action(data, user_id, action_type):
    user_id = str(user_id)
    today = datetime.now().strftime('%Y-%m-%d')
    
    if user_id not in data["daily_actions"]:
        data["daily_actions"][user_id] = {}
    
    data["daily_actions"][user_id][f"{action_type}_{today}"] = True

# Core commands
@bot.command(name='build_nest_own')
async def build_nest_own(ctx):
    log_debug(f"build_nest_own called by {ctx.author.id}")
    data = load_data()
    
    if check_daily_action(data, ctx.author.id, 'build_twig'):
        await ctx.send("You've already built a nest today! 🪹")
        return
    
    nest = get_personal_nest(data, ctx.author.id)
    nest["twigs"] += 1
    record_daily_action(data, ctx.author.id, 'build_twig')
    
    save_data(data)
    await ctx.send(f"Added a twig to your nest! 🪹\nYour nest now has {nest['twigs']} twigs and {nest['seeds']} seeds.")

@bot.command(name='build_nest_common')
async def build_nest_common(ctx):
    log_debug(f"build_nest_common called by {ctx.author.id}")
    data = load_data()
    
    if check_daily_action(data, ctx.author.id, 'build_twig'):
        await ctx.send("You've already built a nest today! 🪺")
        return
    
    data["common_nest"]["twigs"] += 1
    record_daily_action(data, ctx.author.id, 'build_twig')
    
    save_data(data)
    nest = data["common_nest"]
    await ctx.send(f"Added a twig to the common nest! 🪺\nThe common nest now has {nest['twigs']} twigs and {nest['seeds']} seeds.")

@bot.command(name='add_seed_own')
async def add_seed_own(ctx):
    log_debug(f"add_seed_own called by {ctx.author.id}")
    data = load_data()
    
    if check_daily_action(data, ctx.author.id, 'add_seed'):
        await ctx.send("You've already collected a seed today! 🌱")
        return
    
    nest = get_personal_nest(data, ctx.author.id)
    if nest["seeds"] >= nest["twigs"]:
        await ctx.send("Your nest is full! Add more twigs to store more seeds. 🪹")
        return
    
    nest["seeds"] += 1
    record_daily_action(data, ctx.author.id, 'add_seed')
    
    save_data(data)
    await ctx.send(f"Added a seed to your nest! 🏡\nYour nest now has {nest['twigs']} twigs and {nest['seeds']} seeds.")

@bot.command(name='add_seed_common')
async def add_seed_common(ctx):
    log_debug(f"add_seed_common called by {ctx.author.id}")
    data = load_data()
    
    if check_daily_action(data, ctx.author.id, 'add_seed'):
        await ctx.send("You've already collected a seed today! 🌱")
        return
    
    common_nest = data["common_nest"]
    if common_nest["seeds"] >= common_nest["twigs"]:
        await ctx.send("The common nest is full! Add more twigs to store more seeds. 🪺")
        return
    
    common_nest["seeds"] += 1
    record_daily_action(data, ctx.author.id, 'add_seed')
    
    save_data(data)
    await ctx.send(f"Added a seed to the common nest! 🌇\nThe common nest now has {common_nest['twigs']} twigs and {common_nest['seeds']} seeds.")

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
    
    # Get personal nest info
    personal_nest = get_personal_nest(data, ctx.author.id)
    daily_actions = data["daily_actions"].get(str(ctx.author.id), {})
    common_nest = get_common_nest(data)
    
    # Calculate remaining actions
    today = datetime.now().strftime('%Y-%m-%d')
    can_build = not any(f"build_twig_{today}" in action for action in daily_actions)
    can_collect = not any(f"add_seed_{today}" in action for action in daily_actions)
    
    # Create status message with emojis and formatting
    status = "**🏠 Your Nest Status:**\n"
    status += f"```\nTwigs: {personal_nest['twigs']} 🪹\n"
    status += f"Seeds: {personal_nest['seeds']} 🌰\n"
    status += f"Space available: {personal_nest['twigs'] - personal_nest['seeds']} spots\n```\n"
    
    status += "**🌇 Common Nest Status:**\n"
    status += f"```\nTwigs: {common_nest['twigs']} 🪺\n"
    status += f"Seeds: {common_nest['seeds']} 🌰\n"
    status += f"Space available: {common_nest['twigs'] - common_nest['seeds']} spots\n```\n"
    
    status += "**📋 Today's Actions:**\n"
    status += f"Can build nest: {'✅' if can_build else '❌'}\n"
    status += f"Can collect seed: {'✅' if can_collect else '❌'}"
    
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

@bot.command(name='test_next_day')
async def test_next_day(ctx):
    if not DEBUG:
        await ctx.send("Debug mode is not enabled.")
        return
    log_debug("test_next_day called")
    data = load_data()
    data["daily_actions"] = {}
    save_data(data)
    await ctx.send("🌅 Simulated next day - all daily actions reset")

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

@bot.command(name='nest_help')
async def help_command(ctx):
    help_text = """
**🪹 Nest Building Commands:**
`!build_nest_own` - Add a twig to your personal nest
`!build_nest_common` - Add a twig to the common nest
`!add_seed_own` - Add a seed to your personal nest
`!add_seed_common` - Add a seed to the common nest
`!move_seeds_own <amount>` - Move seeds from your nest to common nest
`!move_seeds_common <amount>` - Move seeds from common nest to your nest
`!nests` - Show status of your nest and common nest

**📋 Rules:**
• You can only collect 1 seed per day
• You can only add 1 twig per day
• A nest can only hold as many seeds as it has twigs
"""
    
    if DEBUG:
        help_text += """
**🔧 Testing Commands:**
`!test_status` - Check your current status
`!test_reset_daily` - Reset daily actions
`!test_next_day` - Simulate next day
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
        command_used = ctx.message.content.split()[0][1:]  # Remove the ! prefix
        available_commands = "🔍 Here are the available commands:\n\n"
        
        # Core commands
        available_commands += "**Nest Building:**\n"
        available_commands += "`!build_nest_own` - Add a twig to your personal nest\n"
        available_commands += "`!build_nest_common` - Add a twig to the common nest\n"
        available_commands += "`!add_seed_own` - Add a seed to your personal nest\n"
        available_commands += "`!add_seed_common` - Add a seed to the common nest\n"
        available_commands += "`!move_seeds_own <amount>` - Move seeds from your nest to common nest\n"
        available_commands += "`!move_seeds_common <amount>` - Move seeds from common nest to your nest\n"
        available_commands += "`!nests` - Show status of your nest and common nest\n"
        available_commands += "`!nest_help` - Show detailed help\n"
        
        # Only show debug commands if DEBUG is True
        if DEBUG:
            available_commands += "\n**Debug Commands:**\n"
            available_commands += "`!test_status` - Check your current status\n"
            available_commands += "`!test_reset_daily` - Reset daily actions\n"
            available_commands += "`!test_next_day` - Simulate next day\n"
        
        await ctx.send(f"❌ Command `!{command_used}` not recognized!\n\n{available_commands}")
        
    elif isinstance(error, commands.errors.MissingRequiredArgument):
        await ctx.send("❌ Missing required argument! Check `!nest_help` for proper usage.")
        
    elif isinstance(error, commands.errors.BadArgument):
        await ctx.send("❌ Invalid argument! Please provide a valid number.")
        
    else:
        log_debug(f"Error: {str(error)}")
        await ctx.send("❌ An unexpected error occurred. Please try again.")


# Run the bot
if __name__ == "__main__":
    bot.run(os.getenv('DISCORD_TOKEN'))