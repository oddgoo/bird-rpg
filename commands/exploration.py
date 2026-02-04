from discord.ext import commands
from discord import app_commands
import discord
import data.storage as db
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
            # Australia - Towns & Localities
            "Category:Localities_in_Queensland",
            "Category:Towns_in_Victoria_(state)",
            "Category:Towns_in_New_South_Wales",
            "Category:Towns_in_Western_Australia",
            "Category:Towns_in_Tasmania",
            "Category:Towns_in_South_Australia",
            "Category:Localities_in_Western_Australia",
            "Category:Localities_in_the_Northern_Territory",
            # Australia - National Parks & Protected Areas
            "Category:National_parks_of_Australia",
            "Category:National_parks_of_Queensland",
            "Category:National_parks_of_New_South_Wales",
            "Category:National_parks_of_Victoria_(Australia)",
            "Category:National_parks_of_Western_Australia",
            "Category:National_parks_of_Tasmania",
            "Category:Nature_reserves_of_New_South_Wales",
            "Category:Protected_areas_of_Australia",
            "Category:Marine_parks_of_Australia",
            # Australia - Bird & Wildlife Areas
            "Category:Important_Bird_Areas_of_Australia",
            "Category:Important_Bird_Areas_of_Queensland",
            "Category:Important_Bird_Areas_of_New_South_Wales",
            "Category:Important_Bird_Areas_of_Victoria_(Australia)",
            "Category:Important_Bird_Areas_of_Western_Australia",
            "Category:Important_Bird_Areas_of_South_Australia",
            "Category:Important_Bird_Areas_of_the_Northern_Territory",
            "Category:Ramsar_sites_in_Australia",
            # Australia - Waterways
            "Category:Rivers_of_Australia",
            "Category:Rivers_of_New_South_Wales",
            "Category:Rivers_of_Queensland",
            "Category:Rivers_of_Victoria_(Australia)",
            "Category:Lakes_of_Australia",
            "Category:Lakes_of_New_South_Wales",
            "Category:Lakes_of_South_Australia",
            "Category:Lakes_of_Western_Australia",
            "Category:Wetlands_of_Australia",
            "Category:Wetlands_of_New_South_Wales",
            "Category:Wetlands_of_Queensland",
            # Australia - Coastal
            "Category:Beaches_of_Australia",
            "Category:Beaches_of_New_South_Wales",
            "Category:Beaches_of_Queensland",
            "Category:Beaches_of_Victoria_(Australia)",
            "Category:Headlands_of_New_South_Wales",
            "Category:Headlands_of_Victoria_(Australia)",
            "Category:Bays_of_Australia",
            "Category:Reefs_of_Australia",
            "Category:Capes_of_Australia",
            # Australia - Mountains & Ranges
            "Category:Mountains_of_Australia",
            "Category:Mountains_of_New_South_Wales",
            "Category:Mountains_of_Tasmania",
            "Category:Mountains_of_Victoria_(Australia)",
            "Category:Mountain_ranges_of_Australia",
            # Australia - Forests & Deserts
            "Category:Forests_of_Australia",
            "Category:Rainforests_of_Australia",
            "Category:Deserts_of_Australia",
            # Australia - Other Landforms
            "Category:Caves_of_Australia",
            "Category:Waterfalls_of_Australia",
            "Category:Valleys_of_Australia",
            "Category:Plains_of_Australia",
            # Australia - Heritage
            "Category:World_Heritage_Sites_in_Australia",
            # New Zealand - Towns & Cities
            "Category:Cities_in_New_Zealand",
            "Category:Towns_in_New_Zealand",
            "Category:Populated_places_in_the_Auckland_Region",
            "Category:Populated_places_in_the_Canterbury_Region",
            "Category:Populated_places_in_the_Waikato_Region",
            # New Zealand - Parks & Protected Areas
            "Category:National_parks_of_New_Zealand",
            "Category:Protected_areas_of_New_Zealand",
            "Category:Nature_reserves_of_New_Zealand",
            # New Zealand - Bird Areas
            "Category:Important_Bird_Areas_of_New_Zealand",
            "Category:Bird_sanctuaries_of_New_Zealand",
            # New Zealand - Waterways
            "Category:Rivers_of_New_Zealand",
            "Category:Lakes_of_New_Zealand",
            "Category:Wetlands_of_New_Zealand",
            # New Zealand - Coastal & Marine
            "Category:Beaches_of_New_Zealand",
            "Category:Bays_of_New_Zealand",
            "Category:Harbours_of_New_Zealand",
            # New Zealand - Mountains & Forests
            "Category:Mountains_of_New_Zealand",
            "Category:Volcanoes_of_New_Zealand",
            "Category:Forests_of_New_Zealand",
            "Category:Valleys_of_New_Zealand",
            # New Zealand - Other
            "Category:Caves_of_New_Zealand",
            "Category:Waterfalls_of_New_Zealand",
            "Category:Islands_of_New_Zealand",
            "Category:World_Heritage_Sites_in_New_Zealand",
            # Papua New Guinea
            "Category:Geography_of_Papua_New_Guinea",
            "Category:Mountains_of_Papua_New_Guinea",
            "Category:Rivers_of_Papua_New_Guinea",
            "Category:Islands_of_Papua_New_Guinea",
            "Category:National_parks_of_Papua_New_Guinea",
            "Category:Volcanoes_of_Papua_New_Guinea",
            "Category:Forests_of_Papua_New_Guinea",
            # Fiji
            "Category:Geography_of_Fiji",
            "Category:Islands_of_Fiji",
            "Category:Rivers_of_Fiji",
            "Category:National_parks_of_Fiji",
            "Category:Beaches_of_Fiji",
            # Vanuatu
            "Category:Geography_of_Vanuatu",
            "Category:Islands_of_Vanuatu",
            "Category:Volcanoes_of_Vanuatu",
            # Samoa & Tonga
            "Category:Geography_of_Samoa",
            "Category:Islands_of_Samoa",
            "Category:Geography_of_Tonga",
            "Category:Islands_of_Tonga",
            # Solomon Islands
            "Category:Geography_of_the_Solomon_Islands",
            "Category:Islands_of_the_Solomon_Islands",
            "Category:Rivers_of_the_Solomon_Islands",
            # Other Pacific Islands
            "Category:Geography_of_Kiribati",
            "Category:Geography_of_Tuvalu",
            "Category:Geography_of_Palau",
            "Category:Islands_of_the_Marshall_Islands",
            "Category:Geography_of_New_Caledonia",
            "Category:Islands_of_French_Polynesia",
            "Category:Islands_of_the_Cook_Islands",
            "Category:Geography_of_Nauru",
            "Category:Geography_of_Niue",
        ]

        headers = {
            "User-Agent": "BirdRPGBot/1.0 (https://github.com/bird-rpg; bird-rpg-bot@example.com)",
            "Accept": "application/json",
        }
        async with aiohttp.ClientSession(headers=headers) as session:
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
                    body = await response.text()
                    log_debug(f"Non-200 status code from categorymembers request. Body: {body[:500]}")
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
    @app_commands.choices(region=[
        app_commands.Choice(name='Oceania', value='oceania'),
    ])
    async def explore(self, interaction: discord.Interaction, region: app_commands.Choice[str], amount: int):
        await interaction.response.defer()
        try:
            region_value = region.value
            log_debug(f"explore called by {interaction.user.id} for {amount} in {region_value}")

            if amount < 1:
                await interaction.followup.send("Please specify a positive number of exploration points to add! 🗺️")
                return

            remaining_actions = await get_remaining_actions(interaction.user.id)
            if remaining_actions <= 0:
                await interaction.followup.send(f"You've used all your actions for today! Come back in {get_time_until_reset()}! 🌙")
                return

            # Limit amount to remaining actions
            amount = min(amount, remaining_actions)

            # Add exploration points and record actions
            new_total = await db.increment_exploration(region_value, amount)
            await record_actions(interaction.user.id, amount, "explore")

            remaining = await get_remaining_actions(interaction.user.id)

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
                    value=f"Added {amount} exploration {'point' if amount == 1 else 'points'} to {region_value}!\n"
                          f"Total exploration in {region_value}: {new_total} points\n"
                          f"You have {remaining} {'action' if remaining == 1 else 'actions'} remaining today."
                )
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send(f"Added {amount} exploration {'point' if amount == 1 else 'points'} to {region_value}! 🗺️\n"
                              f"Total exploration in {region_value}: {new_total} points\n"
                              f"You have {remaining} {'action' if remaining == 1 else 'actions'} remaining today.")
        except Exception as e:
            log_debug(f"Error in explore command: {str(e)}")

async def setup(bot):
    await bot.add_cog(ExplorationCommands(bot))
