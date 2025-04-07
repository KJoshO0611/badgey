import discord
from discord.ext import commands
from discord import app_commands
import logging
import asyncio
from config import CONFIG
from utils.helpers import has_required_role
from utils.db_utilsv2 import delete_scores
import datetime
import typing
import io
import csv

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

    @commands.command(name="cleandm")
    async def clean_dm(self, ctx, limit: int = 50):
        """Deletes the bot's messages in DMs while handling rate limits."""
        if ctx.guild is None:  # Ensure it runs only in DMs
            deleted = 0
            async for message in ctx.channel.history(limit=limit):
                if message.author == self.bot.user:
                    try:
                        await message.delete()
                        deleted += 1
                        await asyncio.sleep(0.5)  # Prevent rate limits (2 deletes/sec)
                    except discord.errors.HTTPException:
                        await ctx.send("Rate limited! Try again later.", delete_after=5)
                        break  # Stop execution if rate-limited
            await ctx.send(f"Deleted {deleted} bot messages!", delete_after=5)

    @app_commands.command(name="convo")
    async def convo(self, interaction: discord.Interaction, message: str, avatar:str):
        
        if not has_required_role(interaction.user, CONFIG['REQUIRED_ROLES']):
            await interaction.response.send_message("Uh-oh! You don't have permission to use this command! Guess someone's not in charge here! Hehehe!", delete_after=5)
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

    @app_commands.command(name="get_logs")
    @app_commands.describe(
        start_date="Start date for logs (YYYY-MM-DD)",
        end_date="End date for logs (YYYY-MM-DD)",
        channel="Optional: Text channel or Forum to get logs from (defaults to all)"
    )
    async def get_logs(self, interaction: discord.Interaction, start_date: str, end_date: str, channel: typing.Optional[typing.Union[discord.TextChannel, discord.ForumChannel]]):
        """Fetches chat logs as a CSV file from channels/forums and their threads/posts."""

        if not has_required_role(interaction.user, CONFIG['REQUIRED_ROLES']):
            await interaction.response.send_message("Uh-oh! You don't have permission to use this command!", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=False, thinking=True)

        try:
            # Validate and parse dates
            try:
                start_dt = datetime.datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc)
                end_dt = datetime.datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=datetime.timezone.utc)
            except ValueError:
                await interaction.followup.send("Invalid date format. Please use YYYY-MM-DD.", ephemeral=True)
                return

            if start_dt > end_dt:
                await interaction.followup.send("Start date cannot be after end date.", ephemeral=True)
                return

            all_messages = []
            guild = interaction.guild
            target_text_channels = []
            target_forum_channels = []
            processed_items = 0
            total_items = 0 # We'll calculate this later

            # --- Determine target channels/forums ---
            if channel:
                if isinstance(channel, discord.TextChannel):
                    if channel.permissions_for(guild.me).read_message_history:
                        target_text_channels.append(channel)
                    else:
                         await interaction.followup.send(f"I don't have permission to read history in {channel.mention}.", ephemeral=True)
                         return
                elif isinstance(channel, discord.ForumChannel):
                     if channel.permissions_for(guild.me).read_message_history: # Check forum level permission
                        target_forum_channels.append(channel)
                     else:
                         await interaction.followup.send(f"I don't have permission to read posts in the forum {channel.mention}.", ephemeral=True)
                         return
                else:
                    # Should not happen with Union type hint, but good practice
                    await interaction.followup.send("Invalid channel type specified. Please select a text channel or forum.", ephemeral=True)
                    return
            else:
                # Fetch all accessible text channels
                target_text_channels = [ch for ch in guild.text_channels if ch.permissions_for(guild.me).read_message_history]
                # Fetch all accessible forum channels
                target_forum_channels = [fc for fc in guild.forums if fc.permissions_for(guild.me).read_message_history]

            if not target_text_channels and not target_forum_channels:
                 await interaction.followup.send("No accessible text channels or forums found to fetch logs from.", ephemeral=True)
                 return

            total_items = len(target_text_channels) + len(target_forum_channels) # Initial count

            # --- Process Text Channels ---
            for current_channel in target_text_channels:
                processed_items += 1
                logger.info(f"Processing Text Channel {processed_items}/{total_items}: {current_channel.name} ({current_channel.id})")
                # Fetch logs from the main channel
                channel_messages = await self._fetch_and_format_logs(current_channel, start_dt, end_dt)
                all_messages.extend(channel_messages)

                # Fetch logs from active threads in the text channel
                try:
                    # Using guild.active_threads + filter for compatibility
                    guild_threads = await guild.active_threads()
                    channel_threads = [t for t in guild_threads if t.parent_id == current_channel.id]

                    for thread in channel_threads:
                        if thread.permissions_for(guild.me).read_message_history:
                           logger.info(f"Processing thread: {thread.name} ({thread.id}) in channel {current_channel.name}")
                           thread_messages = await self._fetch_and_format_logs(thread, start_dt, end_dt)
                           all_messages.extend(thread_messages)
                        else:
                           logger.warning(f"Skipping thread {thread.name} due to missing permissions.")
                except discord.Forbidden:
                    logger.warning(f"Missing permissions to list threads in text channel {current_channel.name}")
                except discord.HTTPException as e:
                     logger.error(f"HTTP error fetching threads for text channel {current_channel.name}: {e}")

            # --- Process Forum Channels ---
            for forum_channel in target_forum_channels:
                processed_items += 1
                logger.info(f"Processing Forum {processed_items}/{total_items}: {forum_channel.name} ({forum_channel.id})")
                forum_posts = []
                 # Fetch active posts (threads)
                try:
                    forum_posts.extend(forum_channel.threads) # Active threads are directly available
                except Exception as e: # Broad catch in case of unexpected issues
                     logger.error(f"Error fetching active posts for forum {forum_channel.name}: {e}")

                # Fetch archived posts (threads) within the date range
                # Note: archived_threads might be slow if there are many
                try:
                    async for thread in forum_channel.archived_threads(limit=None, after=start_dt, before=end_dt):
                         # Check if already included (though unlikely for active/archived overlap by ID)
                         if thread.id not in [p.id for p in forum_posts]:
                             forum_posts.append(thread)
                except discord.Forbidden:
                     logger.warning(f"Missing permissions to view archived posts in forum {forum_channel.name}")
                except discord.HTTPException as e:
                     logger.error(f"HTTP error fetching archived posts for forum {forum_channel.name}: {e}")
                except Exception as e:
                     logger.error(f"Unexpected error fetching archived posts for forum {forum_channel.name}: {e}")


                for post in forum_posts:
                    if post.created_at >= start_dt and post.created_at <= end_dt: # Ensure post itself is within range
                        if post.permissions_for(guild.me).read_message_history:
                            logger.info(f"Processing forum post: {post.name} ({post.id}) in forum {forum_channel.name}")
                            post_messages = await self._fetch_and_format_logs(post, start_dt, end_dt)
                            all_messages.extend(post_messages)
                        else:
                            logger.warning(f"Skipping forum post {post.name} due to missing read history permissions.")
                    # else: # Optional: Log skipped posts outside date range
                    #    logger.debug(f"Skipping forum post {post.name} created at {post.created_at}, outside date range.")


            # Sort messages chronologically
            all_messages.sort(key=lambda x: datetime.datetime.strptime(x['Timestamp'], "%Y-%m-%d %H:%M:%S UTC"))

            # Prepare CSV file
            if not all_messages:
                await interaction.followup.send("No logs found for the specified criteria.", ephemeral=True)
                return

            output = io.StringIO()
            headers = ["Timestamp", "Author", "AuthorID", "Channel", "Thread", "Content", "Reactions", "Attachments"]
            writer = csv.DictWriter(output, fieldnames=headers)
            writer.writeheader()
            writer.writerows(all_messages)

            output.seek(0)
            csv_content = output.getvalue()
            output.close()

            channel_name_part = channel.name if channel else 'all'
            log_filename = f"logs_{start_date}_to_{end_date}_{channel_name_part}.csv"
            log_bytes = csv_content.encode('utf-8')

            # Check file size (Discord limit is 25MB)
            if len(log_bytes) > 25 * 1024 * 1024:
                 await interaction.followup.send("Log file is too large (>25MB) to upload. Please narrow your date range or specify a channel/forum.", ephemeral=True)
                 return

            file = discord.File(io.BytesIO(log_bytes), filename=log_filename)
            await interaction.followup.send("Here are the logs you requested!", file=file)

        except discord.errors.NotFound:
             await interaction.followup.send("Interaction expired or could not be found.", ephemeral=True)
        except discord.Forbidden as e:
            logger.error(f"Permission error in get_logs: {e}")
            await interaction.followup.send(f"I seem to be missing permissions to perform this action. Check channel/forum/thread permissions. Error: {e}", ephemeral=True)
        except Exception as e:
            logger.error(f"Error fetching logs: {e}", exc_info=True)
            try:
                 await interaction.followup.send(f"Oops! Something went wrong while fetching logs: {str(e)}", ephemeral=True)
            except discord.errors.InteractionResponded:
                 logger.warning("Interaction already responded to when trying to send error message.")
                 print(f"Error in get_logs for interaction {interaction.id}: {e}")

    # Helper function to fetch and format logs from a channel/thread
    async def _fetch_and_format_logs(self, source, start_dt, end_dt):
        messages_data = []
        channel_name = source.name
        is_thread = isinstance(source, discord.Thread)
        thread_name = source.name if is_thread else None
        parent_channel_name = source.parent.name if is_thread else channel_name

        try:
            async for message in source.history(limit=None, after=start_dt, before=end_dt, oldest_first=True):
                # Format reactions
                reaction_str = ", ".join([f"{reaction.emoji}: {reaction.count}" for reaction in message.reactions])
                reaction_str = f"[{reaction_str}]" if reaction_str else ""

                # Format attachments
                attachment_urls = [att.url for att in message.attachments]
                attachment_str = "\n".join(attachment_urls) # Separate multiple URLs with newlines

                messages_data.append({
                    "Timestamp": message.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
                    "Author": str(message.author),
                    "AuthorID": message.author.id,
                    "Channel": parent_channel_name,
                    "Thread": thread_name,
                    "Content": message.clean_content,
                    "Reactions": reaction_str,
                    "Attachments": attachment_str # Add attachment URLs here
                })
        except discord.Forbidden:
            logger.warning(f"Missing permissions to read history for {channel_name}{f' (thread in {parent_channel_name})' if is_thread else ''}")
        except discord.HTTPException as e:
             logger.error(f"HTTP error fetching history for {channel_name}{f' (thread in {parent_channel_name})' if is_thread else ''}: {e}")
        return messages_data

async def setup(bot):
    await bot.add_cog(AdminCog(bot))