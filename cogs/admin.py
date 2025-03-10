import discord
from discord.ext import commands
from discord import app_commands
import logging
from config import CONFIG
from utils.helpers import has_required_role
from utils.db_utilsv2 import delete_scores

logger = logging.getLogger('badgey.Admin')

class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="setstatus")
    async def setstatus(self, ctx, status: str = None):
        
        if not has_required_role(ctx.author, CONFIG['REQUIRED_ROLES']):
            await ctx.send("Uh-oh! You don't have permission to use this command! Guess someone's not in charge here! Hehehe!", delete_after=5)
            return
        
        if not status:
            await ctx.send("Ooooh! is time for maintenance? let me know if I'm online, idle, DND, or invisible?", delete_after=5)
            return
        
        statuses = {
            "online": discord.Status.online,
            "idle": discord.Status.idle,
            "dnd": discord.Status.dnd,
            "invisible": discord.Status.invisible
        }
        
        status = status.lower()
        if status not in statuses:
            await ctx.send("Ooooh! is time for maintenance? let me know if I'm online, idle, DND, or invisible?", delete_after=5)
            return
        
        try:
            await self.bot.change_presence(status=statuses[status], activity=discord.Game(name="Monitoring Comms!"))
            await ctx.send(f"Beep boop! Badgey's going: {status}")
        except Exception as e:
            await ctx.send(f"You don't control me!: {e}")

    @commands.command(name="send")
    async def send(self, ctx, *, message: str):
        """Replies to a message, sends in a specific channel, or defaults to the current channel."""

        if not has_required_role(ctx.author, CONFIG['REQUIRED_ROLES']):
            await ctx.send("Uh-oh! You don't have permission to use this command! Guess someone's not in charge here! Hehehe!", delete_after=5)
            return
    
        try:
            # If replying to a message, reply to that message
            if ctx.message.reference:
                referenced_message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                await referenced_message.reply(message)
                return  # Stop here so it doesn't send again

            # Check if the first word in the message is a valid channel mention or ID
            words = message.split(" ", 1)  # Split message into first word and the rest
            channel_mention = words[0] if len(words) > 1 else None
            text_message = words[1] if len(words) > 1 else message  # Ensure message still exists

            target_channel = ctx.channel  # Default to the current channel

            # Try resolving the channel (if a mention or ID was given)
            if channel_mention:
                if channel_mention.startswith("<#") and channel_mention.endswith(">"):
                    channel_id = int(channel_mention.strip("<#>"))  # Extract ID from mention
                    target_channel = self.bot.get_channel(channel_id)
                elif channel_mention.isdigit():
                    target_channel = self.bot.get_channel(int(channel_mention))
                else:
                    found_channel = discord.utils.get(ctx.guild.text_channels, name=channel_mention)
                    if found_channel:
                        target_channel = found_channel

                # If channel is invalid, just send in the current channel
                if target_channel is None:
                    target_channel = ctx.channel
                    text_message = message  # Keep full message

            # Send message in resolved channel
            await target_channel.send(text_message)

        except discord.NotFound:
            await ctx.send("I couldn't find that message. Please try again.", delete_after=5)
        except discord.Forbidden:
            await ctx.send("I don't have permission to send messages there.", delete_after=5)
        except discord.HTTPException:
            await ctx.send("Something went wrong while trying to send the message.", delete_after=5)

    @app_commands.command(name="convo")
    async def convo(self, interaction: discord.Interaction, message: str, avatar:str):
        
        if not has_required_role(interaction.user, CONFIG['REQUIRED_ROLES']):
            await interaction.response.send_message("Uh-oh! You don’t have permission to use this command! Guess someone’s not in charge here! Hehehe!", delete_after=5)
            return
       
        try:
            embed = discord.Embed(title="", description=message, color=discord.Color.blurple())
            embed.set_thumbnail(url=avatar)
            await interaction.response.send_message(embed=embed)


        except Exception as e:
            await interaction.response.send_message(f"Oops! Something went wrong: {e}")

    @app_commands.command(name="deletescores")
    @app_commands.describe(
        user_id="User ID to delete scores for (use 'all' for all users)",
        quiz_id="Quiz ID to delete scores for (use 'all' for all quizzes)"
    )
    async def delete_scores_slash(self, interaction: discord.Interaction, user_id: str, quiz_id: str):
        """Delete user scores from the database"""
        
        if not has_required_role(interaction.user, CONFIG['REQUIRED_ROLES']):
            await interaction.response.send_message("Uh-oh! You don't have permission to use this command! Guess someone's not in charge here! Hehehe!", ephemeral=True)
            return
            
        try:
            # Validate inputs
            if user_id.lower() != "all":
                try:
                    int(user_id)
                except ValueError:
                    await interaction.response.send_message("User ID must be a number or 'all'.", ephemeral=True)
                    return
            
            if quiz_id.lower() != "all":
                try:
                    int(quiz_id)
                except ValueError:
                    await interaction.response.send_message("Quiz ID must be a number or 'all'.", ephemeral=True)
                    return
            
            # Delete scores using the db_utils function
            row_count = await delete_scores(user_id, quiz_id)
            
            # Create user-friendly message
            if user_id.lower() == "all" and quiz_id.lower() == "all":
                await interaction.response.send_message(f"All user scores have been deleted! {row_count} records wiped clean! Hehehe!")
            elif user_id.lower() == "all":
                await interaction.response.send_message(f"All user scores for quiz ID {quiz_id} have been deleted! {row_count} records gone! Hehehe!")
            elif quiz_id.lower() == "all":
                await interaction.response.send_message(f"All quiz scores for user ID {user_id} have been deleted! {row_count} records wiped! Hehehe!")
            else:
                await interaction.response.send_message(f"Scores for user ID {user_id} on quiz ID {quiz_id} have been deleted! {row_count} records removed! Hehehe!")
            
            logger.info(f"Admin {interaction.user.name} (ID: {interaction.user.id}) deleted {row_count} user score records. Parameters: user_id={user_id}, quiz_id={quiz_id}")
                
        except Exception as e:
            logger.error(f"Error deleting user scores: {e}")
            await interaction.response.send_message(f"Oopsie! Something went wrong while deleting scores: {str(e)}", ephemeral=True) 

async def setup(bot):
    await bot.add_cog(AdminCog(bot))