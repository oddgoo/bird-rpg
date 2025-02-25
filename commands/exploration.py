from discord.ext import commands
from discord import app_commands
import discord
from data.storage import load_data, save_data
from data.models import get_remaining_actions, record_actions
from utils.logging import log_debug
from utils.time_utils import get_time_until_reset
import aiohttp
import random

VALID_REGIONS = ['oceania']

class ExplorationCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    async def get_random_oceania_location(self):
        """Fetch a random location from Oceania using Wikipedia's API (only the first request)."""
        categories = [
            "Category:Geography_of_Australia",
            "Category:Environment_of_Australia",
            "Category:Localities_in_Queensland",
            "Category:Towns_in_Victoria_(state)",
            "Category:Towns_in_New_South_Wales",
            "Category:Towns_in_Western_Australia",
            "Category:Towns_in_Tasmania",
            "Category:Towns_in_South_Australia",
            "Category:Protected_areas_of_Australia",
            "Category:Australia_geography_stubs",
            "Category:Geography_of_New_Zealand",
            "Category:Cities_in_New_Zealand",
            "Category:Protected_areas_of_New_Zealand",
            "Category:Papua_New_Guinea_geography_stubs",
            "Category:Fiji_geography_stubs",
            "Category:Vanuatu_geography_stubs",
        ]
        
        async with aiohttp.ClientSession() as session:
            category = random.choice(categories)
            log_debug(f"Category: {category}")

            url = "https://en.wikipedia.org/w/api.php"
            params = {
                "action": "query",
                "list": "categorymembers",
                "cmtitle": category,
                "cmtype": "page",
                "cmlimit": "500",
                "format": "json"
            }
            log_debug(f"Requesting categorymembers URL: {url}, params: {params}")

            async with session.get(url, params=params) as response:
                log_debug(f"Categorymembers response status: {response.status}")
                if response.status != 200:
                    log_debug("Non-200 status code from categorymembers request.")
                    return None

                data = await response.json()
                log_debug(f"Categorymembers data received: {data}")

                if not data.get("query", {}).get("categorymembers"):
                    log_debug("No categorymembers found, returning None.")
                    return None

                page = random.choice(data["query"]["categorymembers"])
                log_debug(f"Selected page: {page}")

                # Return just the page title and a link to the Wikipedia page
                return {
                    "title": f"You visited: {page['title']}!",
                    "description": "View the Wikipedia page to learn more!",
                    "url": f"https://en.wikipedia.org/wiki/{page['title'].replace(' ', '_')}",
                    "image": None
                }

    @app_commands.command(name='explore', description='Explore a region to find locations')
    @app_commands.describe(
        region='The region to explore',
        amount='Number of exploration points to add'
    )
    async def explore(self, interaction: discord.Interaction, region: str, amount: int = 1):
        try:
            log_debug(f"explore called by {interaction.user.id} for {amount} in {region}")
            region = region.lower()

            if region not in VALID_REGIONS:
                await interaction.response.send_message(f"That region isn't available for exploration yet! Currently available: {', '.join(VALID_REGIONS)}")
                return

            data = load_data()

            if amount < 1:
                await interaction.response.send_message("Please specify a positive number of exploration points to add! 🗺️")
                return

            remaining_actions = get_remaining_actions(data, interaction.user.id)
            if remaining_actions <= 0:
                await interaction.response.send_message(f"You've used all your actions for today! Come back in {get_time_until_reset()}! 🌙")
                return

            # Initialize exploration data if it doesn't exist
            if "exploration" not in data:
                data["exploration"] = {}
            if region not in data["exploration"]:
                data["exploration"][region] = 0
            
            # Limit amount to remaining actions
            amount = min(amount, remaining_actions)
            
            # Add exploration points
            data["exploration"][region] += amount
            record_actions(data, interaction.user.id, amount, "explore")

            save_data(data)
            remaining = get_remaining_actions(data, interaction.user.id)
            
            # Get a random location and create an embed
            location = await self.get_random_oceania_location()
            if location:
                log_debug("Creating embed with location data:")
                log_debug(f"Title: {location['title']}")
                log_debug(f"Description length: {len(location.get('description', ''))}")
                log_debug(f"URL: {location['url']}")
                
                embed = discord.Embed(
                    title=f"📍{location['title']}",
                    description=location.get('description', '')[:495] + ("..." if len(location.get('description', '')) > 500 else ""),
                    url=location['url'],
                    color=0x3498db
                )
                if location.get('image'):
                    embed.set_thumbnail(url=location['image'])
                embed.add_field(
                    name="Exploration Summary",
                    value=f"Added {amount} exploration {'point' if amount == 1 else 'points'} to {region}!\n"
                          f"Total exploration in {region}: {data['exploration'][region]} points\n"
                          f"You have {remaining} {'action' if remaining == 1 else 'actions'} remaining today."
                )
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message(f"Added {amount} exploration {'point' if amount == 1 else 'points'} to {region}! 🗺️\n"
                              f"Total exploration in {region}: {data['exploration'][region]} points\n"
                              f"You have {remaining} {'action' if remaining == 1 else 'actions'} remaining today.")
        except Exception as e:
            log_debug(f"Error in explore command: {str(e)}")

async def setup(bot):
    await bot.add_cog(ExplorationCommands(bot))

