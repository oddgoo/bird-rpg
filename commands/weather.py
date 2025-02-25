from discord.ext import commands, tasks
from discord import app_commands
import discord
import aiohttp
from datetime import datetime, time
import pytz

from data.storage import load_data, save_data
from utils.logging import log_debug
from utils.time_utils import get_australian_time

class WeatherCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.weather_task.start()  # Start the scheduled task
        
    def cog_unload(self):
        self.weather_task.cancel()  # Properly cancel task when cog is unloaded
        
    @tasks.loop(minutes=60)
    async def weather_task(self):
        """Check time and send weather updates if it's 9 AM Melbourne time"""
        melbourne_time = get_australian_time()
        
        # Only send between 9:00 and 9:59 AM
        if melbourne_time.hour == 9 and melbourne_time.minute < 60:
            log_debug("Sending daily weather update")
            weather_message = await self.fetch_weather()
            await self.send_to_configured_channels(weather_message)
    
    @weather_task.before_loop
    async def before_weather_task(self):
        """Wait until the bot is ready before starting the task"""
        await self.bot.wait_until_ready()
        
    @app_commands.command(name='weather', description='Get the current weather in Naarm/Melbourne')
    async def weather_command(self, interaction: discord.Interaction):
        """Show current weather in Melbourne"""
        log_debug(f"weather command called by {interaction.user.id}")
        
        await interaction.response.defer()  # This gives us more time to fetch the data
        
        weather_message = await self.fetch_weather()
        await interaction.followup.send(weather_message)
    
    @app_commands.command(name='set_weather_channel', description='Set the channel for daily weather updates')
    @app_commands.describe(channel='The channel to send weather updates to')
    @app_commands.checks.has_permissions(manage_channels=True)
    async def set_weather_channel(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        """Set which channel should receive daily weather updates"""
        log_debug(f"set_weather_channel called by {interaction.user.id}")
        
        data = load_data()
        
        # Initialize weather_channels if it doesn't exist
        if "weather_channels" not in data:
            data["weather_channels"] = {}
        
        guild_id = str(interaction.guild.id)
        
        if channel is None:
            # If no channel specified, remove the setting
            if guild_id in data["weather_channels"]:
                del data["weather_channels"][guild_id]
                save_data(data)
                await interaction.response.send_message("❌ Weather updates disabled for this server.")
            else:
                await interaction.response.send_message("❓ Weather updates were not configured for this server.")
        else:
            # Check if we have permission to send messages in this channel
            permissions = channel.permissions_for(interaction.guild.me)
            if not permissions.send_messages:
                await interaction.response.send_message(f"❌ I don't have permission to send messages in {channel.mention}!")
                return
                
            # Set the channel
            data["weather_channels"][guild_id] = str(channel.id)
            save_data(data)
            
            await interaction.response.send_message(f"✅ Daily weather updates will be sent to {channel.mention} at 9 AM Naarm/Melbourne time.")
    
    async def fetch_weather(self):
        """Fetch weather data from Open-Meteo API"""
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": -37.8142,  # Melbourne coordinates
            "longitude": 144.9632,
            "daily": "weathercode,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max",
            "timezone": "Australia/Sydney",
            "forecast_days": 1
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return self.format_weather_message(data)
                else:
                    log_debug(f"Error fetching weather: {response.status}")
                    return "Could not fetch weather information today."

    def format_weather_message(self, data):
        """Format weather data into a nice message"""
        try:
            # Extract data
            date = data["daily"]["time"][0]
            weather_code = data["daily"]["weathercode"][0]
            temp_max = data["daily"]["temperature_2m_max"][0]
            temp_min = data["daily"]["temperature_2m_min"][0]
            precip_sum = data["daily"]["precipitation_sum"][0]
            precip_prob = data["daily"]["precipitation_probability_max"][0]
            
            # Get weather emoji and description
            weather_info = self.get_weather_description(weather_code)
            
            # Format message
            message = f"**🌦️ Good morning everybird! Today's weather in Naarm is: {date}** {weather_info['emoji']}\n\n"
            message += f"**Conditions:** {weather_info['description']}\n"
            message += f"**Temperature:** {temp_min}°C to {temp_max}°C\n"
            
            if precip_prob > 0:
                message += f"**Chance of Rain:** {precip_prob}%\n"
                if precip_sum > 0:
                    message += f"**Expected Rainfall:** {precip_sum} mm\n"
            
            message += "\n*Have an eggcelent day!* 🐦"
            
            return message
        except Exception as e:
            log_debug(f"Error formatting weather: {e}")
            return "Weather information is available, but could not be formatted properly."

    def get_weather_description(self, code):
        """Convert WMO weather code to emoji and description"""
        # WMO Weather interpretation codes (WW)
        # https://open-meteo.com/en/docs
        weather_codes = {
            0: {"emoji": "☀️", "description": "Clear sky"},
            1: {"emoji": "🌤️", "description": "Mainly clear"},
            2: {"emoji": "⛅", "description": "Partly cloudy"},
            3: {"emoji": "☁️", "description": "Overcast"},
            45: {"emoji": "🌫️", "description": "Fog"},
            48: {"emoji": "🌫️", "description": "Depositing rime fog"},
            51: {"emoji": "🌦️", "description": "Light drizzle"},
            53: {"emoji": "🌦️", "description": "Moderate drizzle"},
            55: {"emoji": "🌧️", "description": "Dense drizzle"},
            56: {"emoji": "🌨️", "description": "Light freezing drizzle"},
            57: {"emoji": "🌨️", "description": "Dense freezing drizzle"},
            61: {"emoji": "🌦️", "description": "Slight rain"},
            63: {"emoji": "🌧️", "description": "Moderate rain"},
            65: {"emoji": "🌧️", "description": "Heavy rain"},
            66: {"emoji": "🌨️", "description": "Light freezing rain"},
            67: {"emoji": "🌨️", "description": "Heavy freezing rain"},
            71: {"emoji": "❄️", "description": "Slight snow fall"},
            73: {"emoji": "❄️", "description": "Moderate snow fall"},
            75: {"emoji": "❄️", "description": "Heavy snow fall"},
            77: {"emoji": "❄️", "description": "Snow grains"},
            80: {"emoji": "🌦️", "description": "Slight rain showers"},
            81: {"emoji": "🌧️", "description": "Moderate rain showers"},
            82: {"emoji": "🌧️", "description": "Violent rain showers"},
            85: {"emoji": "🌨️", "description": "Slight snow showers"},
            86: {"emoji": "🌨️", "description": "Heavy snow showers"},
            95: {"emoji": "⛈️", "description": "Thunderstorm"},
            96: {"emoji": "⛈️", "description": "Thunderstorm with slight hail"},
            99: {"emoji": "⛈️", "description": "Thunderstorm with heavy hail"}
        }
        
        return weather_codes.get(code, {"emoji": "❓", "description": "Unknown"})
    
    async def send_to_configured_channels(self, weather_message):
        """Send weather message to all configured channels"""
        data = load_data()
        
        # Initialize weather_channels if it doesn't exist
        if "weather_channels" not in data:
            data["weather_channels"] = {}
        
        sent_count = 0
        error_count = 0
        
        # Send to configured channels only
        for guild_id, channel_id in data["weather_channels"].items():
            try:
                guild = self.bot.get_guild(int(guild_id))
                if not guild:
                    continue
                    
                channel = guild.get_channel(int(channel_id))
                if not channel:
                    continue
                    
                await channel.send(weather_message)
                log_debug(f"Sent weather to {guild.name} in #{channel.name}")
                sent_count += 1
                
            except Exception as e:
                log_debug(f"Error sending weather to guild {guild_id}: {e}")
                error_count += 1
        
        log_debug(f"Weather update complete. Sent to {sent_count} servers. Errors: {error_count}")

async def setup(bot):
    await bot.add_cog(WeatherCommands(bot))
