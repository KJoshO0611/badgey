import discord
from discord.ext import commands
from discord import app_commands
import logging
from config import CONFIG
from datetime import datetime, timedelta
from models.quiz_view import QuizView
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
        
    @commands.command(name="start_quiz")
    async def start_quiz(self, ctx, quiz_id: int):
        """Start a quiz (Traditional command)"""
        if not has_required_role(ctx.author, CONFIG['REQUIRED_ROLES']):
            await ctx.send("Uh-oh! You don't have permission to use this command! Guess someone's not in charge here! Hehehe!", delete_after=5)
            return
        
        # Send an initial message to create a message object we can edit later
        message = await ctx.send("Loading quiz...")
        
        # Create the view with the message instead of ctx
        view = QuizView(message, quiz_id)
        await view.initialize(message, quiz_id)
        
        # Check if questions loaded successfully
        if not hasattr(view, 'questions') or not view.questions:
            await message.edit(content="No questions found for this quiz.")
            return
            
        # Update the view's message reference
        view.message = message
        
        # Start showing questions
        await view.show_question()
    
    # Slash command version of start_quiz
    @app_commands.command(name="start_quiz", description="Start a quiz")
    @app_commands.describe(quiz_id="The ID of the quiz to start")
    async def slash_start_quiz(self, interaction: discord.Interaction, quiz_id: int, timer: int):
        if not has_required_role(interaction.user, CONFIG['REQUIRED_ROLES']):
            await interaction.response.send_message("Uh-oh! You don't have permission to use this command! Guess someone's not in charge here! Hehehe!", ephemeral=True)
            return
        
        # Defer response to buy time for loading
        await interaction.response.defer()
        
        # Create initial response
        message = await interaction.followup.send("Loading quiz...")
        
        # Create the view with the message
        view = QuizView(message, quiz_id, timer)
        await view.initialize(message, quiz_id)
        
        # Check if questions loaded successfully
        if not hasattr(view, 'questions') or not view.questions:
            await message.edit(content="No questions found for this quiz.")
            return
            
        view.message = message
        await view.show_question()

    @app_commands.command(name="take_quiz", description="Take a quiz individually")
    @app_commands.describe(
        quiz_id="The ID of the quiz to take",
        mode="Quiz mode: regular, ephemeral, or dm"
    )
    @app_commands.choices(mode=[
        app_commands.Choice(name="Regular", value="regular"),
        app_commands.Choice(name="Ephemeral", value="ephemeral"),
        app_commands.Choice(name="Direct Message", value="dm")
    ])
    async def take_quiz(self, interaction: discord.Interaction, quiz_id: int, mode: str = "regular"):
        # Defer response to buy time for loading
        await interaction.response.defer(ephemeral=(mode == "ephemeral" or mode == "dm"))

        timer = 20
        
        try:
            # Check if the quiz exists
            quiz_result = await get_quiz_name(quiz_id)
            if not quiz_result:
                await interaction.followup.send("That quiz doesn't exist. Use /list_quizzes to see available quizzes.", ephemeral=(mode == "ephemeral" or mode == "dm"))
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
            
            # Handle different quiz modes
            if mode == "regular":
                # Regular (public) quiz
                message = await interaction.followup.send(f"Loading quiz: {quiz_name}...")
                
                view = IndividualQuizView(
                    interaction.user.id, 
                    message, 
                    quiz_id, 
                    timer, 
                    interaction.user.name
                )
                await view.initialize(message, quiz_id)
                
                if not hasattr(view, 'questions') or not view.questions:
                    await message.edit(content="No questions found for this quiz.")
                    return
                    
                await view.show_question()
                
            elif mode == "ephemeral":
                logger.info(f"User {interaction.user.id} requested quiz {quiz_id} with {timer}s timer")
                
                # Validate timer
                if timer < 5 or timer > 300:
                    await interaction.followup.send(
                        "Timer must be between 5 and 300 seconds.", 
                        ephemeral=True
                    )
                    return
                
                # Add to queue and let the queue system handle the rest
                await quiz_queue.add_request(
                    interaction.user.id,
                    interaction,
                    quiz_id,
                    timer,
                    interaction.user.display_name
                )
                
            elif mode == "dm":
                # DM quiz - Send in direct messages and report back to channel
                # Validate input
                if timer < 5 or timer > 120:
                    await interaction.followup.send("Timer must be between 5 and 120 seconds.", ephemeral=True)
                    return
                    
                user_id = interaction.user.id
                channel_id = interaction.channel_id
                user = interaction.user
                user_name = interaction.user.display_name
                
                try:
                    # Add user to queue with the new method
                    success, message = await self.queue.add_to_queue(
                        user_id, channel_id, user, quiz_id, timer, user_name)
                    
                    await interaction.followup.send(message, ephemeral=True)
                    
                except Exception as e:
                    logger.error(f"Error adding user to quiz queue: {e}")
                    await interaction.followup.send("There was an error starting the quiz. Please try again later.", ephemeral=True)
                    
        except Exception as e:
            logger.error(f"Error starting quiz: {e}")
            await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=(mode == "ephemeral" or mode == "dm"))
        
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
