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
from utils.db_utilsv2 import get_quiz_name, has_taken_quiz
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
    )
    async def take_quiz(self, interaction: discord.Interaction, quiz_id: int):
        # Hardcoded defaults
        mode = "ephemeral"
        timer = 20

        # Defer response ephemerally
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Check if the quiz exists
            quiz_result = await get_quiz_name(quiz_id)
            if not quiz_result:
                await interaction.followup.send("That quiz doesn't exist. Use /list_quizzes to see available quizzes.", ephemeral=True)
                return
                
            quiz_name = quiz_result[0]
            
            # Check if the user has already taken this quiz
            already_taken = await has_taken_quiz(interaction.user.id, quiz_id)
            if already_taken:
                await interaction.followup.send(
                    f"You've already completed the quiz: **{quiz_name}**. Each quiz can only be taken once.",
                    ephemeral=True
                )
                return
            
            # Always use ephemeral mode with fixed timer
            logger.info(f"User {interaction.user.id} requested quiz {quiz_id} with {timer}s timer (ephemeral mode)")
            
            # No timer validation needed as it's hardcoded
            
            # Add to queue and let the queue system handle the rest
            await quiz_queue.add_request(
                interaction.user.id,
                interaction,
                quiz_id,
                timer, # Use the hardcoded timer
                interaction.user.display_name
            )
                            
        except Exception as e:
            logger.error(f"Error starting quiz: {e}")
            # Ensure error messages are ephemeral
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
        if not has_required_role(interaction.user, CONFIG['REQUIRED_ROLES']):
            await interaction.response.send_message("You don't have permission to use this command!", ephemeral=True)
            return
            
        # You would typically store this in a database or config
        # For this example, we'll just store it in CONFIG
        CONFIG['QUIZ_RESULTS_CHANNEL'] = channel.id
        
        await interaction.response.send_message(
            f"Quiz results channel has been set to {channel.mention}. Results from DM quizzes will be reported here.",
            ephemeral=True
        )        

async def setup(bot):
    await bot.add_cog(QuizPlayCog(bot))
