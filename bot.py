import os
import json
import discord
from flask import Flask
from threading import Thread
from discord.ext import commands
from datetime import datetime, timedelta  # Need to add timedelta
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
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'  # Correct - comparing with lowercase
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# Debug logging
def log_debug(message):
    print(f"[DEBUG] {datetime.now().strftime('%H:%M:%S')}: {message}")


def get_time_until_reset():
    now = datetime.now()
    tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    time_remaining = tomorrow - now
    hours = time_remaining.seconds // 3600
    minutes = (time_remaining.seconds % 3600) // 60
    
    if hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"

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
            "daily_actions": {},
            "daily_songs": {}  # New field to track who has been sung to
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
        data["daily_actions"][user_id][f"actions_{today}"] = {
            "used": 0,
            "bonus": 0
        }
    
    # If it's old format (just a number), convert to new format
    if isinstance(data["daily_actions"][user_id][f"actions_{today}"], (int, float)):
        used_actions = data["daily_actions"][user_id][f"actions_{today}"]
        data["daily_actions"][user_id][f"actions_{today}"] = {
            "used": used_actions,
            "bonus": 0
        }
    
    actions_data = data["daily_actions"][user_id][f"actions_{today}"]
    base_actions = 3
    total_available = base_actions + actions_data["bonus"]
    return total_available - actions_data["used"]

def record_actions(data, user_id, count):
    user_id = str(user_id)
    today = datetime.now().strftime('%Y-%m-%d')
    
    if user_id not in data["daily_actions"]:
        data["daily_actions"][user_id] = {}
    
    if f"actions_{today}" not in data["daily_actions"][user_id]:
        data["daily_actions"][user_id][f"actions_{today}"] = {
            "used": 0,
            "bonus": 0
        }
    
    # Convert old format if needed
    if isinstance(data["daily_actions"][user_id][f"actions_{today}"], (int, float)):
        used_actions = data["daily_actions"][user_id][f"actions_{today}"]
        data["daily_actions"][user_id][f"actions_{today}"] = {
            "used": used_actions,
            "bonus": 0
        }
    
    data["daily_actions"][user_id][f"actions_{today}"]["used"] += count


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
        await ctx.send(f"You've used all your actions for today! Come back in {get_time_until_reset()}! 🌙")
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

    if amount <= 0:
        await ctx.send("Please specify a positive number of seeds to move!")
        return
    
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
    

# Update the nests command to show if user has been sung to
@bot.command(name='nests')
async def show_nests(ctx):
    log_debug(f"nests command called by {ctx.author.id}")
    data = load_data()
    
    # Get nest info
    personal_nest = get_personal_nest(data, ctx.author.id)
    common_nest = get_common_nest(data)
    remaining_actions = get_remaining_actions(data, ctx.author.id)
    has_song = has_been_sung_to(data, ctx.author.id)
    
    # Get total actions available
    today = datetime.now().strftime('%Y-%m-%d')
    actions_data = data["daily_actions"].get(str(ctx.author.id), {}).get(f"actions_{today}", {"used": 0, "bonus": 0})
    if isinstance(actions_data, (int, float)):
        actions_data = {"used": actions_data, "bonus": 0}
    total_actions = 3 + actions_data["bonus"]
    
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
    status += f"Remaining actions: {remaining_actions}/{total_actions}"
    
    # Add song information
    singers = get_singers_today(data, ctx.author.id)
    if singers:
        singer_count = len(singers)
        status += f"\nInspired by {singer_count} {'song' if singer_count == 1 else 'songs'} today! 🎵"
    
    status += f"\nTime until reset: {get_time_until_reset()} 🕒"
    
    await ctx.send(status)


def has_been_sung_to(data, user_id):
    """Check if user has been sung to by anyone today (used in status displays)"""
    user_id = str(user_id)
    today = datetime.now().strftime('%Y-%m-%d')
    
    if "daily_songs" not in data:
        data["daily_songs"] = {}
    
    return (today in data["daily_songs"] and 
            user_id in data["daily_songs"][today] and 
            len(data["daily_songs"][today][user_id]) > 0)

def has_been_sung_to_by(data, singer_id, target_id):
    """Check if target has been sung to by this specific singer today"""
    singer_id = str(singer_id)
    target_id = str(target_id)
    today = datetime.now().strftime('%Y-%m-%d')
    
    if "daily_songs" not in data:
        data["daily_songs"] = {}
    
    if today not in data["daily_songs"]:
        return False
        
    # New format: daily_songs[date][target_id] = [singer1_id, singer2_id, ...]
    return target_id in data["daily_songs"][today] and singer_id in data["daily_songs"][today][target_id]


def record_song(data, singer_id, target_id):
    """Record that singer has sung to target today"""
    singer_id = str(singer_id)
    target_id = str(target_id)
    today = datetime.now().strftime('%Y-%m-%d')
    
    if "daily_songs" not in data:
        data["daily_songs"] = {}
    
    if today not in data["daily_songs"]:
        data["daily_songs"][today] = {}
        
    if target_id not in data["daily_songs"][today]:
        data["daily_songs"][today][target_id] = []
        
    data["daily_songs"][today][target_id].append(singer_id)


def get_singers_today(data, target_id):
    """Get list of who has sung to target today"""
    target_id = str(target_id)
    today = datetime.now().strftime('%Y-%m-%d')
    
    if "daily_songs" not in data:
        return []
        
    if today not in data["daily_songs"]:
        return []
        
    return data["daily_songs"][today].get(target_id, [])

def add_bonus_actions(data, user_id, amount):
    user_id = str(user_id)
    today = datetime.now().strftime('%Y-%m-%d')
    
    if user_id not in data["daily_actions"]:
        data["daily_actions"][user_id] = {}
    
    if f"actions_{today}" not in data["daily_actions"][user_id]:
        data["daily_actions"][user_id][f"actions_{today}"] = {
            "used": 0,
            "bonus": 0
        }
    
    # Convert old format if needed
    if isinstance(data["daily_actions"][user_id][f"actions_{today}"], (int, float)):
        used_actions = data["daily_actions"][user_id][f"actions_{today}"]
        data["daily_actions"][user_id][f"actions_{today}"] = {
            "used": used_actions,
            "bonus": 0
        }
    
    data["daily_actions"][user_id][f"actions_{today}"]["bonus"] += amount

@bot.command(name='sing', aliases=['inspire'])
async def sing(ctx, target_user: discord.Member = None):
    """Give another user 3 extra actions for the day. Each bird can only sing once to the same target per day."""
    # Basic input validation
    if target_user is None:
        await ctx.send("Please specify a user to sing to! Usage: !sing @user")
        return
    
    if target_user.bot:
        await ctx.send("You can't sing to a bot! 🤖")
        return
        
    log_debug(f"sing command called by {ctx.author.id} for user {target_user.id}")
    data = load_data()
    
    # Check if trying to sing to self
    if ctx.author.id == target_user.id:
        await ctx.send("You can't sing to yourself! 🎵")
        return
    
    # Check if singer has enough actions
    singer_remaining_actions = get_remaining_actions(data, ctx.author.id)
    if singer_remaining_actions <= 0:
        await ctx.send(f"You don't have any actions left to sing! Come back in {get_time_until_reset()}! 🌙")
        return
    
    # Check if singer has already sung to this target today
    if has_been_sung_to_by(data, ctx.author.id, target_user.id):
        await ctx.send(f"You've already sung to {target_user.display_name} today! 🎵")
        return
    
    # Record the song and add bonus actions
    record_song(data, ctx.author.id, target_user.id)
    add_bonus_actions(data, target_user.id, 3)
    record_actions(data, ctx.author.id, 1)  # Singing costs 1 action
    
    save_data(data)
    
    # Get list of other singers for flavor text
    #singers = get_singers_today(data, target_user.id)
    #singer_count = len(singers)
    
    # Get total available actions for target
    today = datetime.now().strftime('%Y-%m-%d')
    actions_data = data["daily_actions"].get(str(target_user.id), {}).get(f"actions_{today}", {"used": 0, "bonus": 0})
    if isinstance(actions_data, (int, float)):
        actions_data = {"used": actions_data, "bonus": 0}
    total_actions = 3 + actions_data["bonus"]
    remaining_actions = total_actions - actions_data["used"]
    
    # Get singer's remaining actions
    singer_actions_left = get_remaining_actions(data, ctx.author.id)
    
    # Construct success message
    message = [
        f"🎵 {ctx.author.display_name}'s beautiful song has inspired {target_user.display_name}!",
        f"They now have {remaining_actions}/{total_actions} actions available for the next {get_time_until_reset()}! 🎶",
        f"(You have {singer_actions_left} {'action' if singer_actions_left == 1 else 'actions'} remaining)"
    ]
    
    await ctx.send("\n".join(message))

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

    today = datetime.now().strftime('%Y-%m-%d')
    actions_data = data["daily_actions"].get(str(user_id), {}).get(f"actions_{today}", {"used": 0, "bonus": 0})
    if isinstance(actions_data, (int, float)):
        actions_data = {"used": actions_data, "bonus": 0}
    total_actions = 3 + actions_data["bonus"]
    status += f"Actions used today: {actions_data['used']}/{total_actions}\n"

    status += f"Has been sung to: {'✅' if has_been_sung_to(data, user_id) else '❌'}"
    
    await ctx.send(status)

# Add these new test commands

@bot.command(name='test_sing')
async def test_sing(ctx, target_user: discord.Member):
    """Test version of sing command that only works in DEBUG mode"""
    if not DEBUG:
        await ctx.send("Debug mode is not enabled.")
        return
        
    log_debug(f"test_sing command called by {ctx.author.id} for user {target_user.id}")
    data = load_data()
    
    # Show current state before singing
    remaining_before = get_remaining_actions(data, target_user.id)
    was_sung_to = has_been_sung_to_by(data, ctx.author.id, target_user.id)  # Check specific singer
    singer_remaining = get_remaining_actions(data, ctx.author.id)
    
    await ctx.send(f"TEST - Before singing:\n"
                  f"Target user remaining actions: {remaining_before}\n"
                  f"Singer remaining actions: {singer_remaining}\n"
                  f"Has been sung to by singer: {was_sung_to}")
    
    # Check singer's actions
    if singer_remaining <= 0:
        await ctx.send(f"TEST - Singer has no actions remaining!")
        return
    
    # Check if already sung to by this singer
    if was_sung_to:
        await ctx.send(f"TEST - {target_user.display_name} has already been sung to by {ctx.author.display_name} today! 🎵")
        return
    
    # Perform sing operation
    record_song(data, ctx.author.id, target_user.id)
    add_bonus_actions(data, target_user.id, 3)
    record_actions(data, ctx.author.id, 1)
    save_data(data)
    
    # Show state after singing
    remaining_after = get_remaining_actions(data, target_user.id)
    is_sung_to = has_been_sung_to_by(data, ctx.author.id, target_user.id)
    singer_remaining_after = get_remaining_actions(data, ctx.author.id)
    
    await ctx.send(f"TEST - After singing:\n"
                  f"Target user remaining actions: {remaining_after}\n"
                  f"Singer remaining actions: {singer_remaining_after}\n"
                  f"Has been sung to by singer: {is_sung_to}")

@bot.command(name='test_reset_songs')
async def test_reset_songs(ctx):
    """Reset the daily songs tracking"""
    if not DEBUG:
        await ctx.send("Debug mode is not enabled.")
        return
        
    log_debug("test_reset_songs called")
    data = load_data()
    data["daily_songs"] = {}
    save_data(data)
    await ctx.send("🔄 Reset all daily songs for testing")

@bot.command(name='test_show_all')
async def test_show_all(ctx):
    """Show all relevant data for testing"""
    if not DEBUG:
        await ctx.send("Debug mode is not enabled.")
        return
        
    log_debug("test_show_all called")
    data = load_data()
    today = datetime.now().strftime('%Y-%m-%d')
    
    debug_info = "**🔍 Debug Information:**\n```\n"
    
    # Show daily actions
    debug_info += "Daily Actions:\n"
    for user_id, actions in data["daily_actions"].items():
        debug_info += f"User {user_id}: {actions}\n"
    
    # Show daily songs
    debug_info += "\nDaily Songs:\n"
    if today in data.get("daily_songs", {}):
        for target_id, singers in data["daily_songs"][today].items():
            debug_info += f"User {target_id} was sung to by: {singers}\n"
    else:
        debug_info += "No songs today\n"
        
    debug_info += "```"
    await ctx.send(debug_info)


# Update the help command to include test commands
@bot.command(name='test_help')
async def test_help(ctx):
    """Show help for test commands"""
    if not DEBUG:
        await ctx.send("Debug mode is not enabled.")
        return
        
    help_text = """
**🔧 Testing Commands:**
`!test_sing <@user>` - Test the sing command with debug output
`!test_reset_daily` - Reset all daily actions
`!test_reset_songs` - Reset all daily songs
`!test_show_all` - Show all debug information
`!test_status` - Check your current status
"""
    await ctx.send(help_text)

# Update help command to include sing
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
`!sing <@user>` - Give another bird 3 extra actions for the day

**📋 Rules:**
• You have 3 actions per day total
• Each twig or seed added counts as one action
• A nest can only hold as many seeds as it has twigs
• Moving seeds doesn't count as an action
• Each bird can only receive one song (3 extra actions) per day

Note: If [amount] is not specified, it defaults to 1
"""
    
    if DEBUG:
        help_text += """
**🔧 Testing Commands:**
`!test_help`
"""
    
    await ctx.send(help_text)


@bot.event
async def on_ready():
    print(f'Bot is ready. Logged in as {bot.user.name}')
    print(f'Debug mode: {"ON" if DEBUG else "OFF"}')
    
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
    
    if DEBUG:
        print("\nTest Commands Available:")
        print("!test_reset_daily - Reset all daily actions")
        print("!test_reset_songs - Reset all daily songs")
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