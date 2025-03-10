import discord
from discord.ext import commands
import logging
import csv
from config import CONFIG
from utils.helpers import has_required_role
from utils.db_utilsv2 import get_quiz_scores

logger = logging.getLogger('badgey.data_export')

class DataExportCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="beam")
    async def beam(self, ctx, quiz_id):
        if not has_required_role(ctx.author, CONFIG['REQUIRED_ROLES']):
            await ctx.send("Uh-oh! You don't have permission to use this command! Guess someone's not in charge here! Hehehe!", delete_after=5)
            return
        
        data = await get_quiz_scores(quiz_id)
        
        with open("quiz_data.csv", "w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["player_id", "player name", "quiz_id", "Score"])
            writer.writerows(data)
        await ctx.send("Database exported to quiz_data.csv", file=discord.File("quiz_data.csv"))

async def setup(bot):
    await bot.add_cog(DataExportCog(bot))