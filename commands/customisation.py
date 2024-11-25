from discord.ext import commands
from data.storage import load_data, save_data
from data.models import get_personal_nest
from utils.logging import log_debug

class CustomisationCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='rename_nest', aliases=['name_nest'])
    async def rename_nest(self, ctx, *, new_name: str):
        """Rename your personal nest"""
        log_debug(f"rename_nest called by {ctx.author.id} with name: {new_name}")
        
        # Input validation
        if len(new_name) > 256:
            await ctx.send("❌ Nest name must be 256 characters or less!")
            return
            
        if len(new_name) < 1:
            await ctx.send("❌ Please provide a name for your nest!")
            return

        data = load_data()
        nest = get_personal_nest(data, ctx.author.id)
        
        # Store the old name for the confirmation message
        old_name = nest.get("name", "Unnamed Nest")
        
        # Update the nest name
        nest["name"] = new_name
        save_data(data)
        
        await ctx.send(f"🪹 Renamed your nest from \"{old_name}\" to \"{new_name}\"!")

async def setup(bot):
    await bot.add_cog(CustomisationCommands(bot))
