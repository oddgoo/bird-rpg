import discord
from discord.ext import commands
import json
import os
from dotenv import load_dotenv

# Create a .env file if it doesn't exist
if not os.path.exists('.env'):
    with open('.env', 'w') as f:
        f.write('DISCORD_TOKEN=your_token_here')
    print("Created .env file - please add your bot token!")

# Create initial JSON file if it doesn't exist
if not os.path.exists('nests.json'):
    initial_data = {
        "personal_nests": {
            "test_user": {
                "twigs": 5,
                "seeds": 3
            }
        },
        "common_nest": {
            "twigs": 10,
            "seeds": 8
        },
        "daily_actions": {}
    }
    with open('nests.json', 'w') as f:
        json.dump(initial_data, f, indent=2)
    print("Created initial nests.json with test data!")

# Test the environment
try:
    load_dotenv()
    token = os.getenv('DISCORD_TOKEN')
    if token == 'your_token_here' or not token:
        print("\n⚠️ Please add your bot token to .env file!")
    else:
        print("\n✅ Found bot token in .env")
        
    print("\n✅ JSON file ready for testing")
    print("\nEnvironment is set up! You can now run your bot script.")
    print("\nReminder: Make sure to:")
    print("1. Add your bot to a test server using the OAuth2 URL generator")
    print("2. Enable the Message Content Intent in your bot's settings")
    print("3. Run the main bot script with 'python bot.py'")
    
except Exception as e:
    print(f"\n❌ Error during setup: {e}")