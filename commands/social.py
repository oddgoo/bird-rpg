from discord.ext import commands
import discord

from data.storage import load_data, save_data
from data.models import get_personal_nest
from utils.logging import log_debug

class SocialCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='entrust')
    async def entrust(self, ctx, *, args):
        """Give one of your birds to another user
        Usage: !entrust <common_bird_name> <@user>"""
        try:
            # Split args into bird name and user mention
            *bird_name_parts, user_mention = args.split()
            bird_name = ' '.join(bird_name_parts)

            # Extract user ID from mention
            if not ctx.message.mentions:
                await ctx.send("❌ Please mention a user to give the bird to!")
                return
            target_user = ctx.message.mentions[0]

            # Don't allow giving birds to yourself
            if target_user.id == ctx.author.id:
                await ctx.send("❌ You can't give a bird to yourself!")
                return

            # Don't allow giving birds to bots
            if target_user.bot:
                await ctx.send("❌ You can't give birds to bots!")
                return

            log_debug(f"entrust called by {ctx.author.id} giving '{bird_name}' to {target_user.id}")
            data = load_data()

            # Get both nests
            giver_nest = get_personal_nest(data, ctx.author.id)
            receiver_nest = get_personal_nest(data, target_user.id)

            # Find the bird in giver's nest
            bird_to_give = None
            for i, bird in enumerate(giver_nest.get("chicks", [])):
                if bird["commonName"].lower() == bird_name.lower():
                    bird_to_give = giver_nest["chicks"].pop(i)
                    break

            if not bird_to_give:
                await ctx.send(f"❌ You don't have a {bird_name} in your nest!")
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
                value=f"{ctx.author.display_name}'s Nest ({len(giver_nest['chicks'])} birds remaining)",
                inline=True
            )
            embed.add_field(
                name="To",
                value=f"{target_user.display_name}'s Nest (now has {len(receiver_nest['chicks'])} birds)",
                inline=True
            )

            await ctx.send(embed=embed)

        except Exception as e:
            log_debug(f"Error in entrust command: {e}")
            await ctx.send("❌ Usage: !entrust <common_bird_name> <@user>")

async def setup(bot):
    await bot.add_cog(SocialCommands(bot))
