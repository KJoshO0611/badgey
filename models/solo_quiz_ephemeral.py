import discord
from discord.ext import commands
from discord import app_commands
import logging
import asyncio
import time
import json
import random
import string
from collections import deque
from config import CONFIG
from utils.db_utilsv2 import get_quiz_questions, record_user_score, get_quiz_name

logger = logging.getLogger('badgey.solo_quiz_ephemeral')

# Rate limiting and queuing system
class QuizQueue:
    """Manages quiz requests and enforces rate limiting"""
    def __init__(self, max_concurrent=5, cooldown_seconds=30):
        self.active_quizzes = {}  # user_id -> quiz_instance
        self.queue = deque()  # Queue of pending quiz requests
        self.max_concurrent = max_concurrent
        self.cooldown_seconds = cooldown_seconds
        self.user_cooldowns = {}  # user_id -> timestamp when cooldown expires
        self.lock = asyncio.Lock()
    
    async def add_request(self, user_id, interaction, quiz_id, timer, user_name=None):
        """Add a quiz request to the queue"""
        async with self.lock:
            # Check if user is on cooldown
            if user_id in self.user_cooldowns and self.user_cooldowns[user_id] > time.time():
                remaining = int(self.user_cooldowns[user_id] - time.time())
                await interaction.response.send_message(
                    f"Please wait {remaining} seconds before starting another quiz.", 
                    ephemeral=True
                )
                return False
            
            # Check if user already has an active quiz
            if user_id in self.active_quizzes:
                await interaction.response.send_message(
                    "You already have an active quiz. Please finish it before starting a new one.",
                    ephemeral=True
                )
                return False
            
            # Queue the request
            request = {
                'user_id': user_id,
                'interaction': interaction,
                'quiz_id': quiz_id,
                'timer': timer,
                'user_name': user_name
            }
            
            self.queue.append(request)
            
            # If interaction hasn't been responded to yet
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True, thinking=True)
            
            # Process the queue
            asyncio.create_task(self.process_queue())
            return True
    
    async def process_queue(self):
        """Process queued quiz requests"""
        async with self.lock:
            # Check if we can start more quizzes
            while len(self.active_quizzes) < self.max_concurrent and self.queue:
                # Get the next request
                request = self.queue.popleft()
                
                # Create and start the quiz
                quiz_view = EphemeralQuizView(
                    request['user_id'],
                    request['interaction'],
                    request['quiz_id'],
                    request['timer'],
                    request['user_name']
                )
                
                # Initialize the quiz
                success = await quiz_view.initialize(request['quiz_id'])
                if success:
                    self.active_quizzes[request['user_id']] = quiz_view
                    asyncio.create_task(quiz_view.show_question())
                    logger.info(f"Started quiz for user {request['user_id']} (Active quizzes: {len(self.active_quizzes)})")
                else:
                    # If initialization failed, inform the user
                    try:
                        await request['interaction'].followup.send(
                            "Failed to start the quiz. Please try again later.",
                            ephemeral=True
                        )
                    except Exception as e:
                        logger.error(f"Error sending failure message: {e}")
    
    async def finish_quiz(self, user_id):
        """Mark a quiz as completed and apply cooldown"""
        async with self.lock:
            if user_id in self.active_quizzes:
                del self.active_quizzes[user_id]
                
                # Apply cooldown
                self.user_cooldowns[user_id] = time.time() + self.cooldown_seconds
                logger.info(f"User {user_id} finished quiz. Cooldown applied for {self.cooldown_seconds} seconds")
                
                # Process queue again in case there are waiting requests
                asyncio.create_task(self.process_queue())

# Global quiz queue instance
quiz_queue = QuizQueue()

class EphemeralQuizView(discord.ui.View):
    """View for displaying individual quiz questions and handling responses in ephemeral messages"""
    def __init__(self, user_id, interaction, quiz_id, timer, user_name=None):
        super().__init__(timeout=None)
        self.quiz_id = quiz_id
        self.user_id = user_id
        self.user_name = user_name
        self.score = 0
        self.index = 0
        self.interaction = interaction
        self.questions = []
        self.timer_task = timer
        self.lock = asyncio.Lock()
        self.start_time = None
        self.current_timer = None
        self.auto_end_timer = None  # Added for auto-ending quiz
        self.transitioning = False
        self.latest_response = None  # Store the latest interaction response
        self.message_id = self._generate_message_id()  # Unique message ID for this quiz instance
        self.retry_count = 0  # Counter for retries
        self.max_retries = 3  # Maximum number of retries for operations
    
    def _generate_message_id(self):
        """Generate a unique message ID for this quiz instance"""
        timestamp = int(time.time())
        random_part = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        return f"quiz-{self.user_id}-{timestamp}-{random_part}"

    async def initialize(self, quiz_id):
        """Initialize the quiz by loading questions with retry logic"""
        logger.debug(f"Initializing ephemeral quiz {quiz_id} for user {self.user_id}")
        
        retries = 0
        while retries < self.max_retries:
            try:
                self.questions = await get_quiz_questions(quiz_id)
                if not self.questions:
                    logger.error(f"No questions found for quiz {quiz_id}")
                    return False
                
                self.quiz_id = quiz_id
                self.score = 0
                self.index = 0
                
                logger.info(f"Ephemeral quiz {quiz_id} initialized with {len(self.questions)} questions for user {self.user_id}")
                return True
            
            except Exception as e:
                retries += 1
                logger.warning(f"Error initializing quiz (attempt {retries}/{self.max_retries}): {e}")
                
                if retries >= self.max_retries:
                    logger.error(f"Failed to initialize quiz after {self.max_retries} attempts")
                    return False
                
                # Exponential backoff: wait 2^retries seconds before trying again
                await asyncio.sleep(2 ** retries)
        
        return False

    async def end_quiz(self):
        """Ends the quiz, displays results, and notifies the queue manager"""
        # Cancel any running timer
        if self.current_timer:
            self.current_timer.cancel()
                
        # Get quiz name with retry logic
        quiz_name = f"Quiz {self.quiz_id}"  # Default name
        retries = 0
        while retries < self.max_retries:
            try:
                quiz_result = await get_quiz_name(self.quiz_id)
                if quiz_result:
                    quiz_name = quiz_result[0]
                break
            except Exception as e:
                retries += 1
                logger.warning(f"Error getting quiz name (attempt {retries}/{self.max_retries}): {e}")
                await asyncio.sleep(2 ** retries)
        
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
        
        # Add unique identifier to footer
        embed.set_footer(text=f"Quiz ID: {self.message_id}")
        
        # Update the last question with a thank you message
        thank_you_embed = discord.Embed(
            title="Thank You for Participating!",
            description=f"You've completed the quiz '{quiz_name}'. Your results are being sent to the channel.",
            color=discord.Color.green()
        )
        
        # Create an empty view with no buttons to replace the current view
        empty_view = discord.ui.View()
        
        # Edit the question message with the thank you message and no buttons
        retries = 0
        while retries < self.max_retries:
            try:
                if self.latest_response:
                    await self.latest_response.edit(content=None, embed=thank_you_embed, view=empty_view)
                break
            except discord.errors.NotFound:
                logger.warning(f"Message not found when sending thank you message.")
                break
            except Exception as e:
                retries += 1
                logger.warning(f"Error sending thank you message (attempt {retries}/{self.max_retries}): {e}")
                if retries >= self.max_retries:
                    logger.error(f"Failed to send thank you message after {self.max_retries} attempts")
                await asyncio.sleep(2 ** retries)
        
        # Send public results in the channel (non-ephemeral)
        # Create a public results embed
        public_embed = discord.Embed(
            title="Quiz Completed",
            description=f"<@{self.user_id}> completed: {quiz_name}",
            color=discord.Color.gold()
        )
        
        public_embed.add_field(
                        name="Score",
            value=f"**{self.score}** points",
            inline=True
        )
                    
        public_embed.add_field(
            name="Questions",
            value=f"Completed {total_questions} questions",
            inline=True
        )
        
        # Add unique identifier to footer
        #public_embed.set_footer(text=f"Quiz ID: {self.message_id}")
        
        # Send public results to the channel
        retries = 0
        while retries < self.max_retries:
            try:
                await self.interaction.channel.send(
                    embed=public_embed
                )
                logger.info(f"Sent public quiz results for user {self.user_id} in channel {self.interaction.channel.id}")
                break
            except Exception as e:
                retries += 1
                logger.warning(f"Error sending public quiz results (attempt {retries}/{self.max_retries}): {e}")
                if retries >= self.max_retries:
                    logger.error(f"Failed to send public quiz results after {self.max_retries} attempts")
                await asyncio.sleep(2 ** retries)
        
        # Send ephemeral results as well for the user's reference
        retries = 0
        while retries < self.max_retries:
            try:
                await self.interaction.followup.send(content="Quiz finished! Results have been posted in the channel.", embed=embed, ephemeral=True)
                break
            except discord.errors.NotFound:
                # Message was likely deleted
                logger.warning(f"Interaction not found when sending quiz results.")
                break
            except Exception as e:
                retries += 1
                logger.warning(f"Error sending ephemeral quiz results (attempt {retries}/{self.max_retries}): {e}")
                if retries >= self.max_retries:
                    logger.error(f"Failed to send ephemeral quiz results after {self.max_retries} attempts")
                await asyncio.sleep(2 ** retries)
        
        # Record score in database with retry logic
        retries = 0
        while retries < self.max_retries:
            try:
                username = self.user_name if hasattr(self, 'user_name') and self.user_name else f"User-{self.user_id}"
                await record_user_score(self.user_id, username, self.quiz_id, self.score)
                logger.info(f"Recorded score for {username}: {self.score} points in quiz {self.quiz_id}")
                break
            except Exception as e:
                retries += 1
                logger.warning(f"Error recording quiz score (attempt {retries}/{self.max_retries}): {e}")
                if retries >= self.max_retries:
                    logger.error(f"Failed to record quiz score after {self.max_retries} attempts: {e}")
                await asyncio.sleep(2 ** retries)
        
        # Notify the queue manager that this quiz is done
        await quiz_queue.finish_quiz(self.user_id)

    async def auto_end_quiz(self, timeout_seconds=60):
        """Automatically end the quiz after a specified timeout if user doesn't end it manually"""
        try:
            await asyncio.sleep(timeout_seconds)
            
            # Check if quiz has already ended
            if self.user_id not in quiz_queue.active_quizzes:
                return
            
            logger.info(f"Auto-ending quiz for user {self.user_id} after {timeout_seconds} seconds of inactivity")
            
            # Update the last question embed to thank the player
            thank_embed = discord.Embed(
                title="Quiz Auto-Completed",
                description="Your quiz has been automatically completed due to inactivity. Results are being sent to the channel.",
                color=discord.Color.yellow()
            )
            
            # Create an empty view with no buttons
            empty_view = discord.ui.View()
            
            # Try to update the message if it exists
            if self.latest_response:
                try:
                    await self.latest_response.edit(embed=thank_embed, view=empty_view)
                except Exception as e:
                    logger.warning(f"Failed to update message during auto-end: {e}")
            
            # End the quiz
            await self.end_quiz()
        
        except asyncio.CancelledError:
            # Task was cancelled normally (user ended quiz manually)
            pass
        except Exception as e:
            logger.error(f"Error in auto-end quiz timer: {e}")

    def cancel_timer(self):
        """Cancel the current timer if one exists"""
        if self.current_timer:
            self.current_timer.cancel()
            self.current_timer = None
        
        # Also cancel auto_end_timer if it exists
        if hasattr(self, 'auto_end_timer') and self.auto_end_timer:
            self.auto_end_timer.cancel()
            self.auto_end_timer = None

    async def run_question_timer(self, embed):
        """Run a timer for the current question with error handling"""
        try:
            time_left = self.timer_task
            while time_left > 0:
                # Update only every 3 seconds or when time is low
                if time_left % 3 == 0 or time_left <= 5:
                    embed.set_footer(text=f"Time left: {time_left} seconds ⏳ | ID: {self.message_id}")
                    try:
                        if self.latest_response:
                            await self.latest_response.edit(embed=embed)
                    except discord.errors.NotFound:
                        logger.warning(f"Message {self.message_id} not found during timer update.")
                        return
                    except Exception as e:
                        logger.warning(f"Error updating timer: {e}")
                        # Continue without failing the timer
                
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
                    if self.latest_response:
                        await self.latest_response.edit(embed=embed, view=self)
                    await asyncio.sleep(2)
                except discord.errors.NotFound:
                    logger.warning(f"Message {self.message_id} not found when time's up.")
                    return
                except Exception as e:
                    logger.warning(f"Error updating message after time's up: {e}")
                
                # Move to next question
                self.index += 1
                self.transitioning = False
                await self.show_question()
        except asyncio.CancelledError:
            # Normal cancellation, just exit
            pass
        except Exception as e:
            logger.error(f"Unexpected error in timer: {e}")

    async def show_question(self):
        """Display the current question to the user with retry logic"""
        self.cancel_timer()
        
        if not self.questions:
            logger.error("No questions available to display")
            await self.interaction.followup.send(content="No questions found for this quiz. Please check the database.", ephemeral=True)
            await quiz_queue.finish_quiz(self.user_id)
            return
        
        if self.index >= len(self.questions):
            await self.end_quiz()
            return

        question_data = self.questions[self.index]
        question_text = question_data[2]
        
        # Safely parse options with error handling
        try:
            options = json.loads(question_data[3])
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in question options: {question_data[3]}")
            options = {"A": "Error loading options", "B": "Please report this issue"}
        
        # Create question embed
        embed = discord.Embed(
            title=f"Question {self.index + 1}/{len(self.questions)}", 
            description=question_text, 
            color=discord.Color.blue()
        )
        
        # Add options as fields
        for key, value in options.items():
            embed.add_field(name=key, value=value, inline=False)
        
        # Add the unique ID to the footer
        embed.set_footer(text=f"ID: {self.message_id}")
        
        # Clear previous buttons and add new ones
        self.clear_items()
        for key in options.keys():
            button = EphemeralQuizButton(key, question_data, self)
            self.add_item(button)

        # Set the start time for this question
        self.start_time = time.time()
        self.transitioning = False
        
        # Show the question with retry logic
        retries = 0
        while retries < self.max_retries:
            try:
                if self.latest_response:
                    await self.latest_response.edit(content=None, embed=embed, view=self)
                else:
                    self.latest_response = await self.interaction.followup.send(embed=embed, view=self, ephemeral=True)
                
                # Start a new timer
                self.current_timer = asyncio.create_task(self.run_question_timer(embed))
                break
            except discord.errors.NotFound:
                logger.warning(f"Message not found when showing question {self.index + 1}. Creating new message.")
                # Try to send a new message
                self.latest_response = None
                try:
                    self.latest_response = await self.interaction.followup.send(embed=embed, view=self, ephemeral=True)
                    # Start a new timer
                    self.current_timer = asyncio.create_task(self.run_question_timer(embed))
                    break
                except Exception as inner_e:
                    logger.error(f"Error creating new message: {inner_e}")
            except Exception as e:
                retries += 1
                logger.warning(f"Error showing question (attempt {retries}/{self.max_retries}): {e}")
                
                if retries >= self.max_retries:
                    logger.error(f"Failed to show question after {self.max_retries} attempts")
                    # Try to gracefully end the quiz
                    await self.end_quiz()
                    return
                
                await asyncio.sleep(2 ** retries)

class EphemeralQuizButton(discord.ui.Button):
    """Button for ephemeral quiz answers with error handling"""
    def __init__(self, key, question_data, quiz_view):
        super().__init__(label=key, style=discord.ButtonStyle.primary)
        self.key = key
        self.question_data = question_data
        self.quiz_view = quiz_view

    # Modify the callback method in EphemeralQuizButton class
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
            try:
                # Get maximum score with default fallback
                max_score = 10  # Default score
                try:
                    max_score = int(self.question_data[5])
                except (IndexError, TypeError, ValueError):
                    logger.warning(f"Invalid max score for question, using default of {max_score}")
                
                total_time = self.quiz_view.timer_task  # Total time allowed
                
                # Disable all buttons to prevent multiple answers
                for child in self.quiz_view.children:
                    if isinstance(child, discord.ui.Button):
                        child.disabled = True
                
                # Calculate time taken to answer
                time_taken = time.time() - self.quiz_view.start_time
                
                # Check if answer is correct and award points
                embed = interaction.message.embeds[0]
                
                correct_answer = self.question_data[4]
                if self.key == correct_answer:  # Correct answer
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
                    
                    logger.debug(f"User {interaction.user.id} answered correctly, awarded {scored_points} points. Time penalty: {time_penalty_ratio}")
                else:
                    # Wrong answer
                    self.style = discord.ButtonStyle.danger
                    
                    # Find the correct button and highlight it
                    for child in self.quiz_view.children:
                        if isinstance(child, discord.ui.Button) and child.label == correct_answer:
                            child.style = discord.ButtonStyle.success
                    
                    # Add feedback
                    embed.add_field(
                        name="Incorrect! ❌",
                        value=f"The correct answer was {correct_answer}",
                        inline=False
                    )
                
                # Update the footer with the unique ID
                embed.set_footer(text=f"ID: {self.quiz_view.message_id}")
                
                # Check if this is the last question
                is_last_question = self.quiz_view.index == len(self.quiz_view.questions) - 1
                
                # Add either "Next Question" or "End Quiz" button based on whether this is the last question
                if is_last_question:
                    end_button = discord.ui.Button(label="End Quiz", style=discord.ButtonStyle.primary)
                    #
                    async def end_callback(end_interaction):
                        if end_interaction.user.id != self.quiz_view.user_id:
                            await end_interaction.response.send_message("This quiz is not for you!", ephemeral=True)
                            return
                        
                        await end_interaction.response.defer()
                        
                        # Update the last question embed to thank the player
                        thank_embed = discord.Embed(
                            title="Thank You!",
                            description="Thanks for completing the quiz. Your final results are coming up!",
                            color=discord.Color.green()
                        )
                        
                        # Create an empty view with no buttons
                        empty_view = discord.ui.View()
                        
                        try:
                            await end_interaction.message.edit(embed=thank_embed, view=empty_view)
                        except Exception as e:
                            logger.error(f"Error updating thank you message: {e}")
                        
                        # End the quiz
                        self.quiz_view.transitioning = False
                        await self.quiz_view.end_quiz()
                    
                    end_button.callback = end_callback
                    self.quiz_view.add_item(end_button)
                else:
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
                
                # Update message with retry logic
                try:
                    await interaction.response.edit_message(embed=embed, view=self.quiz_view)
                    self.quiz_view.latest_response = await interaction.original_response()
                    
                    # Start auto-end timer if this is the last question
                    if is_last_question:
                        # Auto-end the quiz after 2 minutes if user doesn't manually end it
                        self.quiz_view.auto_end_timer = asyncio.create_task(self.quiz_view.auto_end_quiz(120))
                    
                except discord.errors.NotFound:
                    logger.warning(f"Message not found when updating answer. Attempting to create new message.")
                    try:
                        self.quiz_view.latest_response = await interaction.followup.send(
                            content="Your answer has been recorded.", 
                            embed=embed, 
                            view=self.quiz_view,
                            ephemeral=True
                        )
                        
                        # Start auto-end timer if this is the last question
                        if is_last_question:
                            # Auto-end the quiz after 2 minutes if user doesn't manually end it
                            self.quiz_view.auto_end_timer = asyncio.create_task(self.quiz_view.auto_end_quiz(120))
                    
                    except Exception as e:
                        logger.error(f"Failed to create new message after NotFound error: {e}")
                except Exception as e:
                    logger.error(f"Error updating message after answer: {e}")
                    # Try to defer and continue anyway
                    try:
                        await interaction.response.defer()
                    except:
                        pass
            
            except Exception as e:
                logger.error(f"Unhandled error in button callback: {e}")
                self.quiz_view.transitioning = False
                try:
                    await interaction.response.send_message(
                        "An error occurred processing your answer. Please try again or restart the quiz.",
                        ephemeral=True
                    )
                except:
                    pass