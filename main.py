import discord
from discord.ext import commands
import os
import logging
import asyncio
import sys
import traceback
from config import CONFIG
from utils.health_check import start_health_server, set_bot_ready

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join('logs', 'badgey.log'))
    ]
)
logger = logging.getLogger('badgey')

# Start health check server
start_health_server()

class BadgeyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(
            command_prefix=CONFIG['PREFIX'],
            intents=intents,
            status=discord.Status.online
        )
        
    async def setup_hook(self):
        # Set up global exception handler
        loop = asyncio.get_event_loop()
        loop.set_exception_handler(self.handle_asyncio_exception)
        
        # Load all cogs
        logger.info("Token loaded from config")
        await self.load_cogs()
        
        # Set up database
        from utils.db_utilsv2 import setup_db
        await setup_db()
        
        # Sync commands with Discord
        await self.sync_commands_with_retries(CONFIG['GUILD_ID'])
        
        # No need to sync commands with Discord for text commands
        logger.info("Text commands ready to use")
    
    def handle_asyncio_exception(self, loop, context):
        """Handle uncaught exceptions in the asyncio event loop"""
        exception = context.get('exception')
        if exception:
            if isinstance(exception, Exception):
                logger.error(f"Unhandled exception: {exception}", exc_info=exception)
            else:
                logger.error(f"Unhandled exception: {exception}")
        else:
            msg = context.get('message')
            if msg:
                logger.error(f"Unhandled asyncio error: {msg}")
            else:
                logger.error(f"Unknown asyncio error: {context}")
    
    async def load_cogs(self):
        """Load all cogs with error handling and logging"""
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py') and not filename.startswith('_'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    logger.info(f"Loaded cog: {filename}")
                except Exception as e:
                    logger.error(f"Failed to load cog {filename}: {e}", exc_info=True)
    
    async def sync_commands_with_retries(self, guild_ids, max_retries=3):
        """Sync commands with guilds with retry logic"""
        successful_guilds = []
        failed_guilds = []
        
        for guild_id in guild_ids:
            success = False
            for attempt in range(max_retries):
                try:
                    logger.info(f"Attempting to sync commands to guild ID: {guild_id} (attempt {attempt+1}/{max_retries})")
                    guild = discord.Object(id=guild_id)
                    self.tree.copy_global_to(guild=guild)
                    await self.tree.sync(guild=guild)
                    logger.info(f"Synced commands to guild {guild_id}")
                    successful_guilds.append(guild_id)
                    success = True
                    break
                except discord.Forbidden:
                    logger.error(f"Missing permissions to sync commands to guild {guild_id}")
                    failed_guilds.append(guild_id)
                    break  # No point retrying permission errors
                except Exception as e:
                    logger.warning(f"Failed to sync commands to guild {guild_id} (attempt {attempt+1}): {e}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    else:
                        failed_guilds.append(guild_id)
            
            if not success and guild_id not in failed_guilds:
                failed_guilds.append(guild_id)
        
        if successful_guilds:
            logger.info(f"Successfully synced commands to {len(successful_guilds)} guilds")
        if failed_guilds:
            logger.warning(f"Failed to sync commands to {len(failed_guilds)} guilds: {failed_guilds}")

    async def on_ready(self):
        logger.info(f'Logged in as {self.user} (ID: {self.user.id})')
        await self.change_presence(
            status=discord.Status.online,
            activity=discord.Game(name="Monitoring Comms!")
        )
        # Mark bot as ready in health check
        set_bot_ready(True)
    
    async def on_error(self, event_method, *args, **kwargs):
        """Global error handler for Discord events"""
        exc_type, exc_value, exc_traceback = sys.exc_info()
        
        # Log the error
        logger.error(f"Error in {event_method}: {exc_value}")
        logger.error(f"Full traceback: {''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))}")
        
        # If the error happened in a guild, try to send an error message to the owner
        if args and hasattr(args[0], 'guild') and args[0].guild:
            try:
                guild = args[0].guild
                owner = guild.owner
                if owner:
                    await owner.send(f"An error occurred in {event_method} on your server {guild.name}. "
                                    f"Please contact the bot developers with this information: {exc_value}")
            except Exception as e:
                logger.error(f"Failed to notify guild owner about error: {e}")

    async def on_command_error(self, ctx, error):
        """Handle command errors"""
        if isinstance(error, commands.CommandNotFound):
            await ctx.send("Oopsie! Unknown command, buddy! Try using a valid one, or I'll get reeeal frustrated! Hehe!")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"You forgot a required argument: `{error.param.name}`")
        elif isinstance(error, commands.BadArgument):
            await ctx.send(f"Bad argument: {error}")
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send("You don't have permission to use this command!")
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send(f"I don't have the permissions to do that! I need: {', '.join(error.missing_permissions)}")
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"This command is on cooldown. Try again in {error.retry_after:.2f} seconds.")
        else:
            logger.error(f"Command error: {error}", exc_info=error)
            await ctx.send(f"An error occurred: {str(error)}")

async def main():
    # Make sure logs directory exists
    if not os.path.exists('logs'):
        os.makedirs('logs')
        
    # Set bot not ready until fully initialized
    set_bot_ready(False)
        
    bot = BadgeyBot()
    
    try:
        await bot.start(CONFIG['TOKEN'])
    except KeyboardInterrupt:
        logger.info("Shutdown initiated")
        await bot.close()
    except Exception as e:
        logger.critical(f"Fatal error during bot startup: {e}", exc_info=e)
        # Try to clean up resources
        try:
            if hasattr(bot, 'close'):
                await bot.close()
        except:
            pass
        
        # Exit with error code
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutdown by keyboard interrupt")
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=e)
        sys.exit(1)