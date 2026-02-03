import os
import io
from discord.ext import commands
from discord import app_commands
import discord

import data.storage as db
from utils.logging import log_debug
from config.config import MAX_BIRDWATCH_IMAGE_SIZE, ALLOWED_IMAGE_TYPES, ALLOWED_IMAGE_EXTENSIONS


class BirdwatchCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name='birdwatch',
        description='Submit a bird sighting photo to share with the flock'
    )
    @app_commands.describe(
        image='A photo of your bird sighting (png, jpg, gif, or webp, max 25MB)',
        description='Optional description of your sighting'
    )
    async def birdwatch(
        self,
        interaction: discord.Interaction,
        image: discord.Attachment,
        description: str = None
    ):
        await interaction.response.defer()

        user_id = str(interaction.user.id)

        # Ensure player exists
        await db.load_player(user_id)

        # Validate file extension
        _, ext = os.path.splitext(image.filename.lower())
        if ext not in ALLOWED_IMAGE_EXTENSIONS:
            await interaction.followup.send(
                f"Invalid file type `{ext}`. Please upload a png, jpg, gif, or webp image."
            )
            return

        # Validate content type
        if image.content_type and image.content_type.split(";")[0].strip() not in ALLOWED_IMAGE_TYPES:
            await interaction.followup.send(
                f"Invalid image type `{image.content_type}`. Please upload a png, jpg, gif, or webp image."
            )
            return

        # Validate file size
        if image.size > MAX_BIRDWATCH_IMAGE_SIZE:
            size_mb = image.size / (1024 * 1024)
            await interaction.followup.send(
                f"Image is too large ({size_mb:.1f}MB). Maximum size is 25MB."
            )
            return

        try:
            # Download from Discord CDN
            image_data = await image.read()

            # Upload to Supabase Storage (compresses automatically)
            storage_path, public_url, compressed = await db.upload_birdwatch_image(
                user_id, image.filename, image_data
            )

            # Save metadata to database
            await db.save_birdwatch_sighting(
                user_id, public_url, storage_path, image.filename, description
            )

            # Reward inspiration
            await db.increment_player_field(user_id, "inspiration", 3)

            # Build embed with the image as a file attachment
            file = discord.File(io.BytesIO(compressed), filename="birdwatch.jpg")
            embed_desc = f"**{interaction.user.display_name}** spotted something!"
            if description:
                embed_desc += f"\n*{description}*"
            embed_desc += "\n+3 Inspiration"
            embed = discord.Embed(
                title="Bird Sighting Recorded.",
                description=embed_desc,
                color=discord.Color.teal()
            )
            embed.set_image(url="attachment://birdwatch.jpg")
            #embed.set_footer(text=f"Submitted by {interaction.user.display_name}")

            await interaction.followup.send(file=file, embed=embed)

        except Exception as e:
            log_debug(f"Birdwatch error for {user_id}: {e}")
            await interaction.followup.send(
                "Something went wrong saving your sighting. Please try again later."
            )


async def setup(bot):
    await bot.add_cog(BirdwatchCommands(bot))
