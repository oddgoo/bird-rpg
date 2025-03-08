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


MILESTONE_THRESHOLDS = [30,75,150,300,600,1200,2400,4800,6700,10000]

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
            value="It will boost studies by 1%!",
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
            
        # Load research progress
        research_progress = load_research_progress()
        
        # Filter out authors who have reached the maximum threshold
        available_authors = []
        for entity in research_entities:
            author_name = entity["author"]
            current_progress = research_progress.get(author_name, 0)
            
            # Skip authors who have reached the maximum threshold
            if current_progress < MILESTONE_THRESHOLDS[-1]:
                available_authors.append(entity)
        
        # Sort available authors alphabetically by author name
        available_authors.sort(key=lambda x: x["author"])
        
        # Check if there are any available authors
        if not available_authors:
            await interaction.response.send_message(
                "All authors have reached their maximum research threshold! The research is complete. 🎓",
                ephemeral=True
            )
            return
            
        # Randomly select an author from available authors
        random_author_data = random.choice(available_authors)
        author_name = random_author_data["author"]
        
        # Randomly select a quote from that author
        random_quote = random.choice(random_author_data["quotes"])
        
        # Create a dropdown with all authors
        options = []
        # Sort research entities by author name for the dropdown
        sorted_entities = sorted(research_entities, key=lambda x: x["author"])
        for entity in sorted_entities:
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
        
        # Calculate bonus from released birds
        released_birds_bonus = 0
        released_birds_text = ""
        if "released_birds" in data:
            total_released_birds = sum(bird["count"] for bird in data["released_birds"])
            if total_released_birds > 0:
                base_points = actions * 2  # If correct
                released_birds_bonus = round(base_points * (total_released_birds / 100))
                released_birds_text = f" (+{released_birds_bonus} from {total_released_birds} released birds)"
        
        embed.add_field(
            name="Reward",
            value=f"If correct: {actions * 2}{released_birds_text} study points",
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
            
            # Calculate base points earned
            base_points = invested_actions * 2 if is_correct else invested_actions
            
            # Calculate bonus from released birds
            released_birds_bonus = 0
            if "released_birds" in data:
                # Sum up all counts in released_birds array
                total_released_birds = sum(bird["count"] for bird in data["released_birds"])
                # Each bird adds +1% bonus
                released_birds_bonus = base_points * (total_released_birds / 100)
                
            # Apply the bonus to the base points and round to integer
            points_earned = round(base_points + released_birds_bonus)
            
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
            
            # Calculate milestone information
            current_progress = research_progress[correct_author]
            milestone_info = self.get_milestone_info(correct_author, current_progress, research_entities)
            
            # Create bonus text if there's a bonus
            bonus_text = ""
            if "released_birds" in data and sum(bird["count"] for bird in data["released_birds"]) > 0:
                total_released_birds = sum(bird["count"] for bird in data["released_birds"])
                bonus_text = f"\n\n**Released Birds Bonus**: +{total_released_birds}% (+{round(released_birds_bonus)} points from {total_released_birds} birds)"
            
            result_embed.add_field(
                name=f"{correct_author} Study Progress",
                value=f"{current_progress} points{bonus_text}",
                inline=False
            )
            
            # Add milestone information
            result_embed.add_field(
                name="Next Milestone",
                value=milestone_info,
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
            
            # Create bonus text for public message
            public_bonus_text = ""
            if "released_birds" in data and sum(bird["count"] for bird in data["released_birds"]) > 0:
                total_released_birds = sum(bird["count"] for bird in data["released_birds"])
                public_bonus_text = f" (includes +{total_released_birds}% bonus from released birds)"
            
            public_embed.add_field(
                name="Study Points Earned",
                value=f"**{points_earned}** points{public_bonus_text}",
                inline=True
            )
            
            public_embed.add_field(
                name=f"Total {correct_author} Study Progress",
                value=f"**{research_progress[correct_author]}** points",
                inline=True
            )
            
            # Add milestone information to public message
            public_embed.add_field(
                name="Next Milestone",
                value=milestone_info,
                inline=False
            )
            
            # Send the public message in the channel
            await interaction.channel.send(embed=public_embed)
            
        # Set the callback for the select menu
        select.callback = select_callback
        
    def get_milestone_info(self, author_name, current_progress, research_entities):
        """Get information about the next milestone for an author"""
        # Find the author in research entities
        author_data = None
        for entity in research_entities:
            if entity["author"] == author_name:
                author_data = entity
                break
                
        if not author_data:
            return "Unknown author"
            
        # Find the current milestone index
        current_milestone_index = 0
        for i, threshold in enumerate(MILESTONE_THRESHOLDS):
            if current_progress < threshold:
                current_milestone_index = i
                break
            elif i == len(MILESTONE_THRESHOLDS) - 1:
                # If we've reached the last threshold
                return f"Maximum milestone reached! ({current_progress}/{MILESTONE_THRESHOLDS[-1]} points)"
                
        # Get the next milestone threshold and effect
        next_threshold = MILESTONE_THRESHOLDS[current_milestone_index]
        next_milestone = author_data["milestones"][current_milestone_index]
        points_needed = next_threshold - current_progress
        
        return f"**{next_milestone}** ({current_progress}/{next_threshold} points, {points_needed} more needed)"

async def setup(bot):
    await bot.add_cog(ResearchCommands(bot))
