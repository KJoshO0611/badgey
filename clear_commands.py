import discord

TOKEN = "MTM0Nzg0MDI4Mjg0MTg0NTgzMQ.GTiQfT.XPQnh-4OVM-Lpvt1Qy7-vIZeAJm8lGZdogXgKo"
bot = discord.Client(intents=discord.Intents.default())
tree = discord.app_commands.CommandTree(bot)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    
    # Delete all global commands
    await tree.sync()  # Syncs with no global commands, effectively removing them
    print("All global commands deleted.")

bot.run(TOKEN)