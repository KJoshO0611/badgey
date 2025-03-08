import discord
from discord import app_commands
from discord.ext import commands
import logging
import asyncio
import time
import json
from config import CONFIG
from utils.db_utils import get_quiz_questions, record_user_score, get_quiz_name

logger = logging.getLogger('badgey.individual_quiz')

class IndividualQuizView(discord.ui.View):
    """View for displaying individual quiz questions and handling responses"""
    def __init__(self, user_id, message, quiz_id, timer,user_name=None):
        super().__init__(timeout=None)  # No timeout to prevent view expiration
        self.quiz_id = quiz_id
        self.user_id = user_id  # Store the user ID who is taking this quiz
        self.user_name = user_name  # Store the username when available
        self.score = 0  # Track the user's score
        self.index = 0
        self.message = message
        self.questions = []
        self.timer_task = timer
        self.lock = asyncio.Lock()
        self.start_time = None  # To track when each question is displayed
        self.current_timer = None  # To store the current timer task
        self.transitioning = False  # Flag to prevent multiple transitions

    async def initialize(self, message, quiz_id):
        """Initialize the quiz by loading questions"""
        logger.debug(f"Initializing individual quiz {quiz_id} for user {self.user_id}")
        
        self.questions = await get_quiz_questions(quiz_id)
        if not self.questions:
            logger.error(f"No questions found for quiz {quiz_id}")
            return False
        
        self.quiz_id = quiz_id
        self.score = 0
        self.index = 0
        self.message = message
        
        logger.info(f"Individual quiz {quiz_id} initialized with {len(self.questions)} questions for user {self.user_id}")
        return True

    async def end_quiz(self):
        """Ends the quiz and displays results"""
        # Cancel any running timer
        if self.current_timer:
            self.current_timer.cancel()
            
        # Get quiz name
        quiz_result = await get_quiz_name(self.quiz_id)
        quiz_name = quiz_result[0] if quiz_result else f"Quiz {self.quiz_id}"
        
        # Create results embed
        embed = discord.Embed(
            title="Quiz Results",
            description=f"You've completed: {quiz_name}",
            color=discord.Color.gold()
        )
        
        embed.add_field(
            name="Your Score",
            value=f"**{self.score}** points",
            inline=False
        )
        
        total_questions = len(self.questions)
        embed.add_field(
            name="Questions",
            value=f"Completed {total_questions} questions",
            inline=False
        )
        
        # Send results
        await self.message.edit(content="Quiz finished!", embed=embed, view=None)
    
        # Record score in database
        try:
            # Use the stored username if available
            username = self.user_name if hasattr(self, 'user_name') and self.user_name else f"User-{self.user_id}"
            await record_user_score(self.user_id, username, self.quiz_id, self.score)
            logger.info(f"Recorded score for {username}: {self.score} points in quiz {self.quiz_id}")
        except Exception as e:
            logger.error(f"Error recording quiz score: {e}")

    def cancel_timer(self):
        """Cancel the current timer if one exists"""
        if self.current_timer:
            self.current_timer.cancel()
            self.current_timer = None

    async def run_question_timer(self, embed):
        """Run a timer for the current question"""
        try:
            time_left = self.timer_task
            while time_left > 0:
                # Update only every 3 seconds or when time is low
                if time_left % 3 == 0 or time_left <= 5:
                    embed.set_footer(text=f"Time left: {time_left} seconds ⏳")
                    try:
                        await self.message.edit(embed=embed)
                    except discord.errors.NotFound:
                        # Message might have been deleted
                        return
                
                await asyncio.sleep(1)
                time_left -= 1
                
                # Check if we're transitioning to prevent timer from continuing
                if self.transitioning:
                    return
            
            # Time's up, move to next question if not already transitioning
            if not self.transitioning:
                self.transitioning = True
                
                # Disable buttons after time is up
                if self.children:
                    for child in self.children:
                        if isinstance(child, discord.ui.Button):
                            child.disabled = True
                
                embed.add_field(
                    name="Time's up!",
                    value="Moving to next question...",
                    inline=False
                )
                
                try:
                    await self.message.edit(embed=embed, view=self)
                    await asyncio.sleep(2)
                except discord.errors.NotFound:
                    # Message might have been deleted
                    return
                
                # Move to next question
                self.index += 1
                self.transitioning = False
                await self.show_question()
        except asyncio.CancelledError:
            # Timer was cancelled, do nothing
            pass

    async def show_question(self):
        """Display the current question to the user"""
        # Cancel any existing timer
        self.cancel_timer()
        
        if not self.questions:
            logger.error("No questions available to display")
            await self.message.edit(content="No questions found for this quiz. Please check the database.")
            return
        
        if self.index >= len(self.questions):
            await self.end_quiz()
            return

        question_data = self.questions[self.index]
        question_text = question_data[2]
        options = json.loads(question_data[3])
        
        # Create question embed
        embed = discord.Embed(
            title=f"Question {self.index + 1}/{len(self.questions)}", 
            description=question_text, 
            color=discord.Color.blue()
        )
        
        # Add options as fields
        for key, value in options.items():
            embed.add_field(name=key, value=value, inline=False)
        
        # Clear previous buttons and add new ones
        self.clear_items()
        for key in options.keys():
            button = IndividualQuizButton(key, question_data, self)
            self.add_item(button)

        # Set the start time for this question
        self.start_time = time.time()
        self.transitioning = False
        
        # Show the question
        try:
            await self.message.edit(content=None, embed=embed, view=self)
            
            # Start a new timer
            self.current_timer = asyncio.create_task(self.run_question_timer(embed))
        except discord.errors.NotFound:
            # Message might have been deleted
            return

class IndividualQuizButton(discord.ui.Button):
    """Button for individual quiz answers"""
    def __init__(self, key, question_data, quiz_view):
        super().__init__(label=key, style=discord.ButtonStyle.primary)
        self.key = key
        self.question_data = question_data
        self.quiz_view = quiz_view

    async def callback(self, interaction: discord.Interaction):
        # Only the quiz owner can interact with these buttons
        if interaction.user.id != self.quiz_view.user_id:
            await interaction.response.send_message("This quiz is not for you!", ephemeral=True)
            return
        
        # If already transitioning, ignore clicks
        if self.quiz_view.transitioning:
            await interaction.response.defer()
            return
            
        self.quiz_view.transitioning = True
        
        # Cancel the timer
        self.quiz_view.cancel_timer()
        
        async with self.quiz_view.lock:
            max_score = self.question_data[5]  # Maximum possible score for the question
            total_time = self.quiz_view.timer_task  # Total time allowed for the question
            
            # Disable all buttons to prevent multiple answers
            for child in self.quiz_view.children:
                if isinstance(child, discord.ui.Button):
                    child.disabled = True
            
            # Calculate time taken to answer
            time_taken = time.time() - self.quiz_view.start_time
            
            # Check if answer is correct and award points
            embed = interaction.message.embeds[0]
            
            if self.key == self.question_data[4]:  # Correct answer
                # Linear scaling: score decreases as time increases
                time_penalty_ratio = max(0, 1 - (time_taken / total_time))
                scored_points = int(max_score * time_penalty_ratio)
                
                self.quiz_view.score += scored_points
                
                # Update button style to show it was correct
                self.style = discord.ButtonStyle.success
                
                # Add feedback
                embed.add_field(
                    name="Correct! ✅",
                    value=f"You earned {scored_points} points",
                    inline=False
                )
                
                logger.debug(f"User {interaction.user.name} answered correctly, awarded {scored_points} points. Time penalty: {time_penalty_ratio}")
            else:
                # Wrong answer
                self.style = discord.ButtonStyle.danger
                
                # Find the correct button and highlight it
                for child in self.quiz_view.children:
                    if isinstance(child, discord.ui.Button) and child.label == self.question_data[4]:
                        child.style = discord.ButtonStyle.success
                
                # Add feedback
                embed.add_field(
                    name="Incorrect! ❌",
                    value=f"The correct answer was {self.question_data[4]}",
                    inline=False
                )
            
            # Add a "Next" button
            next_button = discord.ui.Button(label="Next Question", style=discord.ButtonStyle.primary)
            
            async def next_callback(next_interaction):
                if next_interaction.user.id != self.quiz_view.user_id:
                    await next_interaction.response.send_message("This quiz is not for you!", ephemeral=True)
                    return
                
                await next_interaction.response.defer()
                
                # Move to the next question
                self.quiz_view.index += 1
                self.quiz_view.transitioning = False
                await self.quiz_view.show_question()
            
            next_button.callback = next_callback
            self.quiz_view.add_item(next_button)
            
            # Update message with disabled answer buttons, feedback, and next button
            await interaction.response.edit_message(embed=embed, view=self.quiz_view)