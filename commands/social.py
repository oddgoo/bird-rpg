from discord.ext import commands
from discord import app_commands
import discord

from data.storage import load_data, save_data
from data.models import get_personal_nest
from utils.logging import log_debug

class SocialCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='entrust', description='Give one of your birds to another user')
    @app_commands.describe(
        bird_name='The common name of the bird to give',
        target_user='The user to give the bird to'
    )
    async def entrust(self, interaction: discord.Interaction, bird_name: str, target_user: discord.User):
        try:
            # Don't allow giving birds to yourself
            if target_user.id == interaction.user.id:
                await interaction.response.send_message("❌ You can't give a bird to yourself!")
                return

            # Don't allow giving birds to bots
            if target_user.bot:
                await interaction.response.send_message("❌ You can't give birds to bots!")
                return

            log_debug(f"entrust called by {interaction.user.id} giving '{bird_name}' to {target_user.id}")
            data = load_data()

            # Get both nests
            giver_nest = get_personal_nest(data, interaction.user.id)
            receiver_nest = get_personal_nest(data, target_user.id)

            # Find the bird in giver's nest
            bird_to_give = None
            for i, bird in enumerate(giver_nest.get("chicks", [])):
                if bird["commonName"].lower() == bird_name.lower():
                    bird_to_give = giver_nest["chicks"].pop(i)
                    break

            if not bird_to_give:
                await interaction.response.send_message(f"❌ You don't have a {bird_name} in your nest!")
                return

            # Add bird to receiver's nest
            if "chicks" not in receiver_nest:
                receiver_nest["chicks"] = []
            receiver_nest["chicks"].append(bird_to_give)

            save_data(data)

            # Create embed for success message
            embed = discord.Embed(
                title="🤝 Bird Entrusted",
                description=f"**{bird_to_give['commonName']}** (*{bird_to_give['scientificName']}*) has been given to {target_user.mention}!",
                color=discord.Color.green()
            )
            embed.add_field(
                name="From",
                value=f"{interaction.user.display_name}'s Nest ({len(giver_nest['chicks'])} birds remaining)",
                inline=True
            )
            embed.add_field(
                name="To",
                value=f"{target_user.display_name}'s Nest (now has {len(receiver_nest['chicks'])} birds)",
                inline=True
            )

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            log_debug(f"Error in entrust command: {e}")
            await interaction.response.send_message("❌ Usage: /entrust <bird_name> <@user>")

async def setup(bot):
    await bot.add_cog(SocialCommands(bot))
