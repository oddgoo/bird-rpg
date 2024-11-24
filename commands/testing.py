from discord.ext import commands
import discord

from datetime import datetime
from config.config import DEBUG
from data.storage import load_data, save_data
from data.models import (
    get_personal_nest, get_remaining_actions, add_bonus_actions,
    has_been_sung_to, has_been_sung_to_by, record_song,
    record_actions, get_common_nest
)
from utils.logging import log_debug

class TestCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    async def cog_check(self, ctx):
        """Only allow these commands if DEBUG is True"""
        return DEBUG

    @commands.command(name='test_reset_daily')
    async def test_reset_daily(self, ctx):
        """Reset all daily actions"""
        log_debug("test_reset_daily called")
        data = load_data()
        data["daily_actions"] = {}
        save_data(data)
        await ctx.send("🔄 Reset all daily actions for testing")

    @commands.command(name='test_status')
    async def test_status(self, ctx):
        """Show detailed status for current user"""
        log_debug(f"test_status called by {ctx.author.id}")
        data = load_data()
        user_id = str(ctx.author.id)
        
        personal_nest = get_personal_nest(data, user_id)
        
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
        status += f"Bonus actions: {actions_data['bonus']}\n"
        status += f"Has been sung to: {'✅' if has_been_sung_to(data, user_id) else '❌'}"
        
        await ctx.send(status)

    @commands.command(name='test_sing')
    async def test_sing(self, ctx, target_user: discord.Member):
        """Test version of sing command with debug output"""
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

    @commands.command(name='test_reset_songs')
    async def test_reset_songs(self, ctx):
        """Reset the daily songs tracking"""
        log_debug("test_reset_songs called")
        data = load_data()
        data["daily_songs"] = {}
        save_data(data)
        await ctx.send("🔄 Reset all daily songs for testing")

    @commands.command(name='test_show_all')
    async def test_show_all(self, ctx):
        """Show all relevant data for testing"""
        log_debug("test_show_all called")
        data = load_data()
        today = datetime.now().strftime('%Y-%m-%d')
        
        debug_info = "**🔍 Debug Information:**\n```\n"
        
        # Show daily actions
        debug_info += "Daily Actions:\n"
        for user_id, actions in data["daily_actions"].items():
            user = ctx.guild.get_member(int(user_id))
            user_name = user.display_name if user else user_id
            debug_info += f"User {user_name}: {actions}\n"
        
        # Show daily songs
        debug_info += "\nDaily Songs:\n"
        if today in data.get("daily_songs", {}):
            for target_id, singers in data["daily_songs"][today].items():
                target = ctx.guild.get_member(int(target_id))
                target_name = target.display_name if target else target_id
                
                singer_names = []
                for singer_id in singers:
                    singer = ctx.guild.get_member(int(singer_id))
                    singer_names.append(singer.display_name if singer else singer_id)
                    
                debug_info += f"User {target_name} was sung to by: {', '.join(singer_names)}\n"
        else:
            debug_info += "No songs today\n"
            
        debug_info += "\nCommon Nest:\n"
        debug_info += f"{data['common_nest']}\n"
        
        debug_info += "```"
        await ctx.send(debug_info)

    @commands.command(name='test_help')
    async def test_help(self, ctx):
        """Show help for test commands"""
        help_text = """
**🔧 Testing Commands:**
`!test_sing <@user>` - Test the sing command with debug output
`!test_reset_daily` - Reset all daily actions
`!test_reset_songs` - Reset all daily songs
`!test_show_all` - Show all debug information
`!test_status` - Check your current status
"""
        await ctx.send(help_text)

    @commands.command(name='test_cleanup')
    async def test_cleanup(self, ctx):
        """Clean up old data (older than 30 days)"""
        log_debug("test_cleanup called")
        data = load_data()
        
        today = datetime.now().strftime('%Y-%m-%d')
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
        await ctx.send(f"Cleanup complete!\nRemoved {cleaned_actions} old action records and {cleaned_songs} old song records.")

async def setup(bot):
    await bot.add_cog(TestCommands(bot))