import discord
from discord.ext import commands
from discord import app_commands
import logging
from config import CONFIG
from datetime import datetime, timedelta
from models.solo_quiz import IndividualQuizView
from models.solo_quiz_ephemeral import EphemeralQuizView
from models.solo_quiz_dm import DMQuizView
from models.scheduled_quiz import TimedQuizController
from utils.helpers import has_required_role
from utils.db_utilsv2 import get_quiz_name, has_taken_quiz, set_guild_setting
from models.solo_quiz_ephemeral import quiz_queue
from models.solo_quiz_dm import QuizQueue

logger = logging.getLogger('badgey.quiz_creation')

class QuizPlayCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = QuizQueue()
    
    @commands.Cog.listener()
    async def on_ready(self):
        # Start the queue processing task
        self.bot.loop.create_task(self.queue.process_queue(self.bot))
        logger.info("Quiz queue processor started")
        
    @app_commands.command(name="take_quiz", description="Take a quiz individually")
    @app_commands.describe(
        quiz_id="The ID of the quiz to take",
        mode="Quiz mode: ephemeral or dm",
        #timer="Time in seconds for each question (default: 20)"
    )
    @app_commands.choices(mode=[
        app_commands.Choice(name="Ephemeral", value="ephemeral"),
        app_commands.Choice(name="Direct Message", value="dm")
    ])
    async def take_quiz(self, interaction: discord.Interaction, quiz_id: int, mode: str):
        # Hardcoded timer, mode comes from parameter
        timer = 20

        # Defer response based on selected mode
        await interaction.response.defer(ephemeral=(mode == "ephemeral" or mode == "dm"))
        
        try:
            # Check if the quiz exists
            quiz_result = await get_quiz_name(quiz_id)
            if not quiz_result:
                # Keep error message ephemeral regardless of mode
                await interaction.followup.send("That quiz doesn't exist. Use /list_quizzes to see available quizzes.", ephemeral=True)
                return
                
            quiz_name = quiz_result[0]
            
            # Check if the user has already taken this quiz
            already_taken = await has_taken_quiz(interaction.user.id, quiz_id)
            if already_taken:
                # Keep this message ephemeral
                await interaction.followup.send(
                    f"You've already completed the quiz: **{quiz_name}**. Each quiz can only be taken once.",
                    ephemeral=True
                )
                return
            
            if mode == "ephemeral":
                # Use ephemeral mode with fixed timer
                logger.info(f"User {interaction.user.id} requested quiz {quiz_id} with {timer}s timer (ephemeral mode)")
                
                # No timer validation needed
                
                # Add to queue
                await quiz_queue.add_request(
                    interaction.user.id,
                    interaction,
                    quiz_id,
                    timer, # Use the hardcoded timer
                    interaction.user.display_name
                )

            elif mode == "dm":
                 # DM quiz - Send in direct messages and report back to channel
                 # No timer validation needed
                    
                 user_id = interaction.user.id
                 channel_id = interaction.channel_id
                 user = interaction.user
                 user_name = interaction.user.display_name
                 logger.info(f"User {interaction.user.id} requested quiz {quiz_id} with {timer}s timer (DM mode)")
                
                 try:
                     # Add user to queue with the new method, including guild_id
                     success, message = await self.queue.add_to_queue(
                         user_id, channel_id, interaction.guild.id, user, quiz_id, timer, user_name)
                    
                     # Send confirmation ephemerally
                     await interaction.followup.send(message, ephemeral=True)
                    
                 except Exception as e:
                     logger.error(f"Error adding user to quiz queue: {e}")
                     await interaction.followup.send("There was an error starting the quiz. Please try again later.", ephemeral=True)
                            
        except Exception as e:
            logger.error(f"Error starting quiz: {e}")
            # Ensure general error messages are ephemeral
            try:
                await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)
            except discord.errors.InteractionResponded: # If defer already failed/timed out
                logger.warning(f"Could not send error followup for quiz {quiz_id} to user {interaction.user.id}")
        
    @app_commands.command(name="schedule_quiz", description="Schedule a quiz to start at a specific time")
    @app_commands.describe(
        quiz_id="The ID of the quiz to schedule",
        minutes="Minutes until the quiz starts (default: 5)",
        timer="Time in seconds for each question (default: 20)"
    )
    async def schedule_quiz(self, interaction: discord.Interaction, quiz_id: int, minutes: int = 5, timer: int = 20):
        if not minutes or minutes < 1:
            minutes = 5
        if not timer or timer < 10:
            timer = 20
            
        # Calculate start time
        start_time = datetime.now() + timedelta(minutes=minutes)
        
        await interaction.response.defer()
        
        # Create quiz controller
        quiz_controller = TimedQuizController(
            channel=interaction.channel,
            quiz_id=quiz_id,
            start_time=start_time,
            timer=timer
        )
        
        # Initialize to check if quiz exists
        if not await quiz_controller.initialize():
            await interaction.followup.send("Failed to find the specified quiz. Please check the quiz ID.")
            return
        
        # Acknowledge the command
        await interaction.followup.send(
            f"Quiz **{quiz_controller.quiz_name}** has been scheduled to start in {minutes} minutes. " +
            f"Registration is now open!"
        )
        
        # Run the quiz in background task
        self.bot.loop.create_task(quiz_controller.run_quiz())    

    @app_commands.command(name="set_results_channel", description="Set the channel for reporting DM quiz results")
    @app_commands.describe(channel="The channel to report quiz results to")
    async def set_results_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Set the channel where DM quiz results should be reported"""
        if not interaction.guild:
             await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
             return
             
        if not has_required_role(interaction.user, CONFIG['REQUIRED_ROLES']): # Keep role check based on global config or move role config to DB too?
            await interaction.response.send_message("You don't have permission to use this command!", ephemeral=True)
            return
            
        # Store the setting in the database for this specific guild
        guild_id = interaction.guild.id
        setting_key = 'quiz_results_channel_id'
        setting_value = str(channel.id)
        
        try:
            await set_guild_setting(guild_id, setting_key, setting_value)
            await interaction.response.send_message(
                f"Quiz results channel has been set to {channel.mention} for this server. Results from DM quizzes will be reported here.",
                ephemeral=True
            )
        except Exception as e: # Catch potential DB errors
             logger.error(f"Failed to set results channel for guild {guild_id}: {e}")
             await interaction.response.send_message("Failed to save the results channel setting. Please try again later.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(QuizPlayCog(bot))
