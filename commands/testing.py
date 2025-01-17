from discord.ext import commands
from discord import app_commands
import discord
from datetime import datetime, timedelta

from config.config import DEBUG
from data.storage import load_data, save_data
from data.models import (
    get_personal_nest, get_remaining_actions, add_bonus_actions,
    has_been_sung_to, has_been_sung_to_by, record_song,
    record_actions, get_common_nest, select_random_bird_species
)
from utils.logging import log_debug
from utils.time_utils import get_current_date

class TestCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    async def cog_check(self, ctx):
        """Only allow these commands if DEBUG is True"""
        return DEBUG

    @app_commands.command(name='test_reset_daily', description='Reset all daily actions')
    async def test_reset_daily(self, interaction: discord.Interaction):
        """Reset all daily actions"""
        log_debug("test_reset_daily called")
        data = load_data()
        data["daily_actions"] = {}
        save_data(data)
        await interaction.response.send_message("🔄 Reset all daily actions for testing")

    @app_commands.command(name='test_status', description='Show detailed status for current user')
    async def test_status(self, interaction: discord.Interaction):
        """Show detailed status for current user"""
        log_debug(f"test_status called by {interaction.user.id}")
        data = load_data()
        user_id = str(interaction.user.id)
        
        personal_nest = get_personal_nest(data, user_id)
        
        status = f"**Your Status:**\n"
        status += f"🪹 Twigs: {personal_nest['twigs']}\n"
        status += f"🌰 Seeds: {personal_nest['seeds']}\n"
        status += "\n**Today's Actions:**\n"

        today = get_current_date()
        actions_data = data["daily_actions"].get(str(user_id), {}).get(f"actions_{today}", {"used": 0, "bonus": 0})
        if isinstance(actions_data, (int, float)):
            actions_data = {"used": actions_data, "bonus": 0}
        total_actions = 3 + actions_data["bonus"]
        status += f"Actions used today: {actions_data['used']}/{total_actions}\n"
        status += f"Bonus actions: {actions_data['bonus']}\n"
        status += f"Has been sung to: {'✅' if has_been_sung_to(data, user_id) else '❌'}"
        
        await interaction.response.send_message(status)

    @app_commands.command(name='test_sing', description='Test version of sing command with debug output')
    @app_commands.describe(target_user='The user to test sing to')
    async def test_sing(self, interaction: discord.Interaction, target_user: discord.User):
        """Test version of sing command with debug output"""
        log_debug(f"test_sing command called by {interaction.user.id} for user {target_user.id}")
        data = load_data()
        
        # Show current state before singing
        remaining_before = get_remaining_actions(data, target_user.id)
        was_sung_to = has_been_sung_to_by(data, interaction.user.id, target_user.id)  # Check specific singer
        singer_remaining = get_remaining_actions(data, interaction.user.id)
        
        await interaction.response.send_message(f"TEST - Before singing:\n"
                      f"Target user remaining actions: {remaining_before}\n"
                      f"Singer remaining actions: {singer_remaining}\n"
                      f"Has been sung to by singer: {was_sung_to}")
        
        # Check singer's actions
        if singer_remaining <= 0:
            await interaction.followup.send(f"TEST - Singer has no actions remaining!")
            return
        
        # Check if already sung to by this singer
        if was_sung_to:
            await interaction.followup.send(f"TEST - {target_user.display_name} has already been sung to by {interaction.user.display_name} today! 🎵")
            return
        
        # Perform sing operation
        record_song(data, interaction.user.id, target_user.id)
        add_bonus_actions(data, target_user.id, 3)
        record_actions(data, interaction.user.id, 1)
        save_data(data)
        
        # Show state after singing
        remaining_after = get_remaining_actions(data, target_user.id)
        is_sung_to = has_been_sung_to_by(data, interaction.user.id, target_user.id)
        singer_remaining_after = get_remaining_actions(data, interaction.user.id)
        
        await interaction.followup.send(f"TEST - After singing:\n"
                      f"Target user remaining actions: {remaining_after}\n"
                      f"Singer remaining actions: {singer_remaining_after}\n"
                      f"Has been sung to by singer: {is_sung_to}")

    @app_commands.command(name='test_reset_songs', description='Reset the daily songs tracking')
    async def test_reset_songs(self, interaction: discord.Interaction):
        """Reset the daily songs tracking"""
        log_debug("test_reset_songs called")
        data = load_data()
        data["daily_songs"] = {}
        save_data(data)
        await interaction.response.send_message("🔄 Reset all daily songs for testing")

    @app_commands.command(name='test_show_all', description='Show all relevant data for testing')
    async def test_show_all(self, interaction: discord.Interaction):
        """Show all relevant data for testing"""
        log_debug("test_show_all called")
        data = load_data()
        today = get_current_date()
        
        debug_info = "**🔍 Debug Information:**\n```\n"
        
        # Show daily actions
        debug_info += "Daily Actions:\n"
        for user_id, actions in data["daily_actions"].items():
            user = interaction.guild.get_member(int(user_id))
            user_name = user.display_name if user else user_id
            debug_info += f"User {user_name}: {actions}\n"
        
        # Show daily songs
        debug_info += "\nDaily Songs:\n"
        if today in data.get("daily_songs", {}):
            for target_id, singers in data["daily_songs"][today].items():
                target = interaction.guild.get_member(int(target_id))
                target_name = target.display_name if target else target_id
                
                singer_names = []
                for singer_id in singers:
                    singer = interaction.guild.get_member(int(singer_id))
                    singer_names.append(singer.display_name if singer else singer_id)
                    
                debug_info += f"User {target_name} was sung to by: {', '.join(singer_names)}\n"
        else:
            debug_info += "No songs today\n"
            
        debug_info += "\nCommon Nest:\n"
        debug_info += f"{data['common_nest']}\n"
        
        debug_info += "```"
        await interaction.response.send_message(debug_info)

    @app_commands.command(name='test_help', description='Show help for test commands')
    async def test_help(self, interaction: discord.Interaction):
        """Show help for test commands"""
        help_text = """
**🔧 Testing Commands:**
`/test_sing <@user>` - Test the sing command with debug output
`/test_reset_daily` - Reset all daily actions
`/test_reset_songs` - Reset all daily songs
`/test_show_all` - Show all debug information
`/test_status` - Check your current status
"""
        await interaction.response.send_message(help_text)

    @app_commands.command(name='test_cleanup', description='Clean up old data (older than 30 days)')
    async def test_cleanup(self, interaction: discord.Interaction):
        """Clean up old data (older than 30 days)"""
        log_debug("test_cleanup called")
        data = load_data()
        
        today = get_current_date()
        cutoff_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        # Clean up daily actions
        cleaned_actions = 0
        for user_id in data["daily_actions"]:
            user_actions = data["daily_actions"][user_id]
            original_len = len(user_actions)
            data["daily_actions"][user_id] = {
                k: v for k, v in user_actions.items() 
                if k == f"actions_{today}" or k > f"actions_{cutoff_date}"
            }
            cleaned_actions += original_len - len(data["daily_actions"][user_id])
        
        # Clean up daily songs
        cleaned_songs = 0
        original_songs = len(data.get("daily_songs", {}))
        data["daily_songs"] = {
            k: v for k, v in data.get("daily_songs", {}).items()
            if k == today or k > cutoff_date
        }
        cleaned_songs = original_songs - len(data["daily_songs"])
        
        save_data(data)
        await interaction.response.send_message(f"Cleanup complete!\nRemoved {cleaned_actions} old action records and {cleaned_songs} old song records.")

    @app_commands.command(name='test_hatch_egg', description='Force hatch an egg for a user')
    @app_commands.describe(target_user='The user whose egg to hatch (optional)')
    async def test_hatch_egg(self, interaction: discord.Interaction, target_user: discord.User = None):
        """Force hatch an egg for a user (for testing purposes)"""
        target_user = target_user or interaction.user
        log_debug(f"test_hatch_egg called by {interaction.user.id} for {target_user.id}")
        data = load_data()
        nest = get_personal_nest(data, target_user.id)
        
        if not nest["egg"]:
            await interaction.response.send_message(f"{target_user.display_name} does not have an egg to hatch! 🥚")
            return
        
        nest["egg"]["brooding_progress"] = 10  # Force hatch
        bird_species = select_random_bird_species()
        chick = {
            "commonName": bird_species["commonName"],
            "scientificName": bird_species["scientificName"]
        }
        nest["chicks"].append(chick)
        nest["egg"] = None
        save_data(data)
        
        await interaction.response.send_message(
            f"🐣 **Forced Hatch!** {target_user.display_name}'s egg has hatched into a **{chick['commonName']}** ({chick['scientificName']})!\n"
        )

    @app_commands.command(name='test_reset_nest', description='Reset a user\'s nest to an initial state')
    @app_commands.describe(target_user='The user whose nest to reset (optional)')
    async def test_reset_nest(self, interaction: discord.Interaction, target_user: discord.User = None):
        """Reset a user's nest to an initial state (for testing purposes)"""
        target_user = target_user or interaction.user
        log_debug(f"test_reset_nest called by {interaction.user.id} for {target_user.id}")
        data = load_data()
        data["personal_nests"][str(target_user.id)] = {
            "twigs": 90,
            "seeds": 50,
            "name": "Some Bird's Nest",
            "egg": None,
            "chicks": []
        }
        save_data(data)
        await interaction.response.send_message(f"✅ {target_user.display_name}'s nest has been reset to its initial state.")

async def setup(bot):
    await bot.add_cog(TestCommands(bot))