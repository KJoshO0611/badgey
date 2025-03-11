import discord
from discord.ext import commands
import os
import logging
import asyncio
from config import CONFIG

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('badgey')

class BadgeyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(
            command_prefix=CONFIG['PREFIX'],
            intents=intents,
            status=discord.Status.online
        )
        
    async def setup_hook(self):
        # Load all cogs
        #logging.info(f"Guild ID: {CONFIG['GUILD_ID']}")
        logging.info("Token loaded from config")

        for filename in os.listdir('./cogs'):
            if filename.endswith('.py') and not filename.startswith('_'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    logger.info(f"Loaded cog: {filename}")
                except Exception as e:
                    logger.error(f"Failed to load cog {filename}: {e}")
        
        try:
            GUILD_IDS = CONFIG['GUILD_ID']

            for guild_id in GUILD_IDS:
                logger.info(f"Attempting to sync commands to guild ID: {guild_id}")
                guild = discord.Object(id=guild_id)
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
                logger.info(f"Synced commands to guild {guild_id}")


            logger.info("Commands synced successfully")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}", exc_info=True)  # This will log the full traceback
                    
        # Set up database
        from utils.db_utilsv2 import setup_db
        await setup_db()
        
        # No need to sync commands with Discord for text commands
        logger.info("Text commands ready to use")

    async def on_ready(self):
        logger.info(f'Logged in as {self.user} (ID: {self.user.id})')
        await self.change_presence(
            status=discord.Status.online,
            activity=discord.Game(name="Monitoring Comms!")
        )


    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            await ctx.send("Oopsie! Unknown command, buddy! Try using a valid one, or I'll get reeeal frustrated! Hehe!")
        else:
            logger.error(f"Command error: {error}")
            # You might want to send a more friendly error message here depending on the error type
            await ctx.send(f"An error occurred: {str(error)}")

async def main():
    bot = BadgeyBot()
    
    try:
        await bot.start(CONFIG['TOKEN'])
    except KeyboardInterrupt:
        logger.info("Shutdown initiated")
        await bot.close()

if __name__ == "__main__":
    asyncio.run(main())