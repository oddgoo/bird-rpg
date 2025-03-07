from discord.ext import commands
from discord import app_commands
import discord
import aiohttp
import urllib.parse
import os
import json
import random

from data.storage import load_data, save_data, load_research_progress, save_research_progress
from data.models import get_personal_nest, load_bird_species, get_remaining_actions, record_actions
from config.config import SPECIES_IMAGES_DIR, DATA_PATH
from utils.logging import log_debug

class ResearchCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @app_commands.command(name='graduate_bird', description='Release a bird from your nest')
    @app_commands.describe(bird_name='Common or scientific name of the bird to release')
    async def graduate_bird(self, interaction: discord.Interaction, bird_name: str):
        """Release a bird from your nest and add it to the released birds collection"""
        log_debug(f"graduate_bird called by {interaction.user.id} for bird: {bird_name}")
        
        # Defer the response since this might take a while
        await interaction.response.defer()
        
        data = load_data()
        nest = get_personal_nest(data, interaction.user.id)
        
        # Check if chicks array exists
        if "chicks" not in nest or not nest["chicks"]:
            await interaction.followup.send("You don't have any birds in your nest to release.", ephemeral=True)
            return
            
        # Find the bird in the user's nest
        bird_to_release = None
        bird_index = -1
        
        for i, bird in enumerate(nest["chicks"]):
            if bird["commonName"].lower() == bird_name.lower() or bird["scientificName"].lower() == bird_name.lower():
                bird_to_release = bird
                bird_index = i
                break
                
        if bird_to_release is None:
            await interaction.followup.send(f"You don't have a bird named '{bird_name}' in your nest. Please check the name and try again.", ephemeral=True)
            return
            
        # Remove the bird from the user's nest
        removed_bird = nest["chicks"].pop(bird_index)
        
        # Initialize released_birds array if it doesn't exist
        if "released_birds" not in data:
            data["released_birds"] = []
            
        # Check if the bird already exists in released_birds
        found = False
        for released_bird in data["released_birds"]:
            if released_bird["scientificName"] == removed_bird["scientificName"]:
                released_bird["count"] += 1
                found = True
                break
                
        # If not found, add it to released_birds
        if not found:
            data["released_birds"].append({
                "scientificName": removed_bird["scientificName"],
                "commonName": removed_bird["commonName"],
                "count": 1
            })
            
        # Save data
        save_data(data)
        
        # Create embed
        embed = discord.Embed(
            title="🕊️ Bird Graduated!",
            description=f" **{removed_bird['commonName']}** (*{removed_bird['scientificName']}*) has graduated from your nest!",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Research",
            value="It is doing something that it not yet fully understood.",
            inline=False
        )
        
        embed.add_field(
            name="Birds Remaining",
            value=f"You now have {len(nest['chicks'])} {'bird' if len(nest['chicks']) == 1 else 'birds'} in your nest.",
            inline=False
        )
        
        embed.add_field(
            name="View Nest",
            value=f"[Click Here](https://bird-rpg.onrender.com/user/{interaction.user.id})",
            inline=False
        )
        
        # Get the image path and check if it exists
        image_path = await self.fetch_bird_image_path(removed_bird['scientificName'])
        
        if image_path and os.path.exists(image_path):
            # Send the file as an attachment with the embed
            file = discord.File(image_path, filename=f"{removed_bird['scientificName']}.jpg")
            embed.set_image(url=f"attachment://{removed_bird['scientificName']}.jpg")
            await interaction.followup.send(file=file, embed=embed)
        else:
            # If image doesn't exist, send embed without image
            await interaction.followup.send(embed=embed)
        
    async def fetch_bird_image_path(self, scientific_name):
        """Fetches the bird image file path."""
        # Check if this is a special bird
        bird_species = load_bird_species()
        for bird in bird_species:
            if bird["scientificName"] == scientific_name and bird.get("rarity") == "Special":
                # For special birds, return the local image path
                special_bird_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                                                'static', 'images', 'special-birds', f"{scientific_name}.png")
                return special_bird_path
                
        # For regular birds and manifested birds, check the species_images directory
        image_filename = f"{urllib.parse.quote(scientific_name)}.jpg"
        image_path = os.path.join(SPECIES_IMAGES_DIR, image_filename)
        return image_path
        
    @app_commands.command(name='study', description='Invest actions into studying')
    @app_commands.describe(actions='Number of actions to invest in study')
    async def study(self, interaction: discord.Interaction, actions: int):
        """Invest actions into studying research and test your knowledge"""
        log_debug(f"study command called by {interaction.user.id} with {actions} actions")
        
        # Validate actions
        if actions <= 0:
            await interaction.response.send_message("You must invest at least 1 action to study! 📚", ephemeral=True)
            return
            
        # Check if user has enough actions
        data = load_data()
        remaining_actions = get_remaining_actions(data, interaction.user.id)
        
        if remaining_actions < actions:
            await interaction.response.send_message(
                f"You don't have enough actions! You need {actions} but only have {remaining_actions} remaining. 🌙",
                ephemeral=True
            )
            return
            
        # Record the actions used
        record_actions(data, interaction.user.id, actions, "study")
        save_data(data)
        
        # Load research entities
        research_entities_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'research_entities.json')
        with open(research_entities_path, 'r', encoding='utf-8') as f:
            research_entities = json.load(f)
            
        # Randomly select an author
        random_author_data = random.choice(research_entities)
        author_name = random_author_data["author"]
        
        # Randomly select a quote from that author
        random_quote = random.choice(random_author_data["quotes"])
        
        # Create a dropdown with all authors
        options = []
        for entity in research_entities:
            options.append(
                discord.SelectOption(
                    label=entity["author"],
                    description=f"Select if you think this is a quote by {entity['author']}",
                    value=entity["author"]
                )
            )
            
        # Create the select menu
        select = discord.ui.Select(
            placeholder="Who is the author?",
            options=options,
            custom_id=f"study_select_{interaction.user.id}_{author_name}_{actions}"
        )
        
        # Create the view with the select menu
        view = discord.ui.View(timeout=300)  # 5 minute timeout
        view.add_item(select)
        
        # Create the embed
        embed = discord.Embed(
            title="📚 Research Study Session",
            description=f"**Quote:**\n\n*\"{random_quote}\"*\n\nWho do you think wrote this? Select from the dropdown below.",
            color=discord.Color.purple()
        )
        
        embed.add_field(
            name="Actions Invested",
            value=f"{actions} {'action' if actions == 1 else 'actions'}",
            inline=True
        )
        
        embed.add_field(
            name="Reward",
            value=f"If correct: {actions * 2} study points",
            inline=True
        )
        
        # Send the message with the view
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
        # Define what happens when the select menu is used
        async def select_callback(select_interaction):
            # Check if the interaction is from the same user
            if select_interaction.user.id != interaction.user.id:
                await select_interaction.response.send_message("This isn't your study session!", ephemeral=True)
                return
                
            # Get the selected author
            selected_author = select_interaction.data["values"][0]
            
            # Get the correct author from the custom_id
            correct_author = select_interaction.data["custom_id"].split("_")[3]
            
            # Get the actions invested from the custom_id
            invested_actions = int(select_interaction.data["custom_id"].split("_")[4])
            
            # Check if the answer is correct
            is_correct = selected_author == correct_author
            
            # Calculate points earned
            points_earned = invested_actions * 2 if is_correct else invested_actions
            
            # Load research progress
            research_progress = load_research_progress()
            
            # Update the research progress for the correct author
            if correct_author not in research_progress:
                research_progress[correct_author] = 0
                
            research_progress[correct_author] += points_earned
            
            # Save research progress
            save_research_progress(research_progress)
            
            # Create result embed
            result_embed = discord.Embed(
                title="📚 Study Results",
                color=discord.Color.green() if is_correct else discord.Color.red()
            )
            
            if is_correct:
                result_embed.description = f"**Correct!** That quote was indeed written by **{correct_author}**.\n\nYou earned **{points_earned}** study points!"
            else:
                result_embed.description = f"**Incorrect!** That quote was actually written by **{correct_author}**, not {selected_author}.\n\nYou earned **{points_earned}** study points for your effort."
            
            result_embed.add_field(
                name=f"{correct_author} Study Progress",
                value=f"{research_progress[correct_author]} points",
                inline=False
            )
            
            # Disable all items in the view
            for item in view.children:
                item.disabled = True
                
            # Update the ephemeral message with the result
            await select_interaction.response.edit_message(embed=result_embed, view=view)
            
            # Send a public message regardless of whether the answer was correct
            public_embed = discord.Embed(
                title="📚 Research Study",
                description=f"<@{interaction.user.id}> studied a quote by **{correct_author}**!",
                color=discord.Color.blue()
            )
            
            public_embed.add_field(
                name="Quote",
                value=f"*\"{random_quote}\"*",
                inline=False
            )
            
            public_embed.add_field(
                name="Study Points Earned",
                value=f"**{points_earned}** points",
                inline=True
            )
            
            public_embed.add_field(
                name=f"Total {correct_author} Study Progress",
                value=f"**{research_progress[correct_author]}** points",
                inline=True
            )
            
            # Send the public message in the channel
            await interaction.channel.send(embed=public_embed)
            
        # Set the callback for the select menu
        select.callback = select_callback

async def setup(bot):
    await bot.add_cog(ResearchCommands(bot))
