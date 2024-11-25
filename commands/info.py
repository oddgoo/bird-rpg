from datetime import datetime
from discord.ext import commands

from data.storage import load_data
from data.models import (
    get_personal_nest, get_common_nest, get_remaining_actions,
    has_been_sung_to, get_singers_today
)
from utils.logging import log_debug
from utils.time_utils import get_time_until_reset
from config.config import DEBUG


class InfoCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='nests')
    async def show_nests(self, ctx):
        log_debug(f"nests command called by {ctx.author.id}")
        data = load_data()
        
        # Get nest info
        personal_nest = get_personal_nest(data, ctx.author.id)
        common_nest = get_common_nest(data)
        remaining_actions = get_remaining_actions(data, ctx.author.id)
        
        # Get total actions available
        today = datetime.now().strftime('%Y-%m-%d')
        actions_data = data["daily_actions"].get(str(ctx.author.id), {}).get(f"actions_{today}", {"used": 0, "bonus": 0})
        if isinstance(actions_data, (int, float)):
            actions_data = {"used": actions_data, "bonus": 0}
        total_actions = 3 + actions_data["bonus"]
        
        # Create status message
        status = "**🏠 Your Nest Status:**\n"
        status += f"```\nTwigs: {personal_nest['twigs']} 🪹\n"
        status += f"Seeds: {personal_nest['seeds']} 🌰\n```\n\n"
        
        status += "**🌇 Common Nest Status:**\n"
        status += f"https://bird-rpg.onrender.com/ \n\n"
            
        status += "**📋 Today's Actions:**\n"
        status += f"Remaining actions: {remaining_actions}/{total_actions}"
        
        # Add song information
        singers = get_singers_today(data, ctx.author.id)
        if singers:
            singer_count = len(singers)
            status += f"\nInspired by {singer_count} {'song' if singer_count == 1 else 'songs'} today! 🎵"
        
        status += f"\nTime until reset: {get_time_until_reset()} 🕒"
        
        await ctx.send(status)

    @commands.command(name='nest_help', aliases=['help'])
    async def help_command(self, ctx):
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
            `!name_nest <name>` - Give your nest a custom name

            **📋 Rules:**
            • You have 3 actions per day total
            • Each twig or seed added counts as one action
            • A nest can only hold as many seeds as it has twigs
            • Moving seeds doesn't count as an action
            • Each bird can only sing to another bird once per day

            Note: If [amount] is not specified, it defaults to 1
            """
        
        if DEBUG:
            help_text += """
                **🔧 Testing Commands:**
                `!test_help`
                """
        
        await ctx.send(help_text)

async def setup(bot):
    await bot.add_cog(InfoCommands(bot))