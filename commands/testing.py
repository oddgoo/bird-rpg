from discord.ext import commands
from discord import app_commands
import discord
from datetime import datetime, timedelta

from config.config import DEBUG
import data.storage as db
from data.models import (
    get_remaining_actions, add_bonus_actions,
    record_actions, select_random_bird_species
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
        # Use a far-future cutoff to delete everything
        await db.delete_old_daily_actions("9999-12-31")
        await interaction.response.send_message("🔄 Reset all daily actions for testing")

    @app_commands.command(name='test_status', description='Show detailed status for current user')
    async def test_status(self, interaction: discord.Interaction):
        """Show detailed status for current user"""
        log_debug(f"test_status called by {interaction.user.id}")
        user_id = str(interaction.user.id)

        player = await db.load_player(user_id)
        today = get_current_date()
        actions_data = await db.get_daily_actions(user_id, today)

        status = f"**Your Status:**\n"
        status += f"🪹 Twigs: {player.get('twigs', 0)}\n"
        status += f"🌰 Seeds: {player.get('seeds', 0)}\n"
        status += "\n**Today's Actions:**\n"

        used = actions_data["used"] if actions_data else 0
        bonus = actions_data.get("bonus", 0) if actions_data else 0
        total_actions = 3 + bonus
        status += f"Actions used today: {used}/{total_actions}\n"
        status += f"Bonus actions: {bonus}\n"
        sung_to = await db.has_been_sung_to(user_id, today)
        status += f"Has been sung to: {'✅' if sung_to else '❌'}"

        await interaction.response.send_message(status)

    @app_commands.command(name='test_sing', description='Test version of sing command with debug output')
    @app_commands.describe(target_user='The user to test sing to')
    async def test_sing(self, interaction: discord.Interaction, target_user: discord.User):
        """Test version of sing command with debug output"""
        log_debug(f"test_sing command called by {interaction.user.id} for user {target_user.id}")
        today = get_current_date()

        # Show current state before singing
        remaining_before = await get_remaining_actions(target_user.id)
        was_sung_to = await db.has_been_sung_to_by(interaction.user.id, target_user.id, today)
        singer_remaining = await get_remaining_actions(interaction.user.id)

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
        await db.record_song(interaction.user.id, target_user.id, today)
        await add_bonus_actions(target_user.id, 3)
        await record_actions(interaction.user.id, 1)

        # Show state after singing
        remaining_after = await get_remaining_actions(target_user.id)
        is_sung_to = await db.has_been_sung_to_by(interaction.user.id, target_user.id, today)
        singer_remaining_after = await get_remaining_actions(interaction.user.id)

        await interaction.followup.send(f"TEST - After singing:\n"
                      f"Target user remaining actions: {remaining_after}\n"
                      f"Singer remaining actions: {singer_remaining_after}\n"
                      f"Has been sung to by singer: {is_sung_to}")

    @app_commands.command(name='test_reset_songs', description='Reset the daily songs tracking')
    async def test_reset_songs(self, interaction: discord.Interaction):
        """Reset the daily songs tracking"""
        log_debug("test_reset_songs called")
        # Use a far-future cutoff to delete everything
        await db.delete_old_songs("9999-12-31")
        await interaction.response.send_message("🔄 Reset all daily songs for testing")

    @app_commands.command(name='test_show_all', description='Show all relevant data for testing')
    async def test_show_all(self, interaction: discord.Interaction):
        """Show all relevant data for testing"""
        log_debug("test_show_all called")
        today = get_current_date()

        players = await db.load_all_players()

        debug_info = "**🔍 Debug Information:**\n```\n"

        # Show daily actions
        debug_info += "Daily Actions:\n"
        for player in players:
            user_id = str(player.get("user_id", ""))
            actions = await db.get_daily_actions(user_id, today)
            if actions:
                user = interaction.guild.get_member(int(user_id))
                user_name = user.display_name if user else user_id
                debug_info += f"User {user_name}: {actions}\n"

        # Show daily songs
        debug_info += "\nDaily Songs:\n"
        has_songs = False
        for player in players:
            user_id = str(player.get("user_id", ""))
            sung_to = await db.has_been_sung_to(user_id, today)
            if sung_to:
                has_songs = True
                target = interaction.guild.get_member(int(user_id))
                target_name = target.display_name if target else user_id
                debug_info += f"User {target_name} was sung to today\n"

        if not has_songs:
            debug_info += "No songs today\n"

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

        cutoff_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

        # Clean up old data via DB functions
        await db.delete_old_daily_actions(cutoff_date)
        await db.delete_old_songs(cutoff_date)
        await db.delete_old_brooding(cutoff_date)

        await interaction.response.send_message(f"Cleanup complete!\nRemoved records older than {cutoff_date}.")

    @app_commands.command(name='test_hatch_egg', description='Force hatch an egg for a user')
    @app_commands.describe(target_user='The user whose egg to hatch (optional)')
    async def test_hatch_egg(self, interaction: discord.Interaction, target_user: discord.User = None):
        """Force hatch an egg for a user (for testing purposes)"""
        target_user = target_user or interaction.user
        log_debug(f"test_hatch_egg called by {interaction.user.id} for {target_user.id}")
        user_id = str(target_user.id)

        egg = await db.get_egg(user_id)

        if not egg:
            await interaction.response.send_message(f"{target_user.display_name} does not have an egg to hatch! 🥚")
            return

        bird_species = await select_random_bird_species()
        common_name = bird_species["commonName"]
        scientific_name = bird_species["scientificName"]
        await db.add_bird(user_id, common_name, scientific_name)
        await db.delete_egg(user_id)

        await interaction.response.send_message(
            f"🐣 **Forced Hatch!** {target_user.display_name}'s egg has hatched into a **{common_name}** ({scientific_name})!\n"
        )

    @app_commands.command(name='test_reset_nest', description='Reset a user\'s nest to an initial state')
    @app_commands.describe(target_user='The user whose nest to reset (optional)')
    async def test_reset_nest(self, interaction: discord.Interaction, target_user: discord.User = None):
        """Reset a user's nest to an initial state (for testing purposes)"""
        target_user = target_user or interaction.user
        log_debug(f"test_reset_nest called by {interaction.user.id} for {target_user.id}")
        user_id = str(target_user.id)

        await db.update_player(user_id,
            twigs=90,
            seeds=50,
            nest_name="Some Bird's Nest",
        )
        # Delete egg if present
        await db.delete_egg(user_id)
        # Remove all birds
        birds = await db.get_player_birds(user_id)
        for bird in birds:
            await db.remove_bird(bird["id"])

        await interaction.response.send_message(f"✅ {target_user.display_name}'s nest has been reset to its initial state.")

async def setup(bot):
    await bot.add_cog(TestCommands(bot))
