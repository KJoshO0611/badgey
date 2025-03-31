import discord
from discord.ext import commands
from discord import app_commands
import logging
import asyncio
import json
import time
import random
from datetime import datetime, timedelta
from config import CONFIG
from utils.db_utilsv2 import get_quiz_questions, record_user_score, get_quiz_name

# Add these imports if not already present
import functools
import backoff
from typing import Dict, Set, Deque
from collections import deque

logger = logging.getLogger('badgey.timed_quiz')

# Setup for rate limiting
class RateLimiter:
    """Rate limiter for button interactions"""
    def __init__(self):
        self.cooldowns: Dict[int, float] = {}  # player_id: timestamp
        self.interaction_queue: Dict[int, Deque] = {}  # player_id: queue of interactions
        self.processing: Set[int] = set()  # Set of player_ids currently being processed
        self.default_cooldown = 0.5  # seconds
        
    def is_rate_limited(self, player_id: int) -> bool:
        """Check if a player is currently rate limited"""
        if player_id in self.cooldowns:
            if time.time() - self.cooldowns[player_id] < self.default_cooldown:
                return True
        return False
    
    def update_timestamp(self, player_id: int):
        """Update the last interaction timestamp for a player"""
        self.cooldowns[player_id] = time.time()
    
    def add_to_queue(self, player_id: int, callback_func, *args, **kwargs):
        """Add an interaction to the queue for processing"""
        if player_id not in self.interaction_queue:
            self.interaction_queue[player_id] = deque()
        
        # Store the callback and arguments
        self.interaction_queue[player_id].append((callback_func, args, kwargs))
        
    async def process_queue(self, player_id: int):
        """Process the queue for a specific player"""
        if player_id in self.processing:
            return  # Already processing this player's queue
        
        self.processing.add(player_id)
        
        try:
            while player_id in self.interaction_queue and self.interaction_queue[player_id]:
                # Wait for cooldown if needed
                if self.is_rate_limited(player_id):
                    await asyncio.sleep(self.default_cooldown)
                
                # Get the next interaction
                callback_func, args, kwargs = self.interaction_queue[player_id].popleft()
                
                # Update timestamp
                self.update_timestamp(player_id)
                
                # Execute the callback
                try:
                    await callback_func(*args, **kwargs)
                except Exception as e:
                    logging.error(f"Error processing queued interaction: {e}")
                
                # Small delay between processing items
                await asyncio.sleep(0.1)
                
            # Clear empty queues
            if player_id in self.interaction_queue and not self.interaction_queue[player_id]:
                del self.interaction_queue[player_id]
                
        finally:
            self.processing.remove(player_id)


class QuizRegistrationView(discord.ui.View):
    """View for players to register for an upcoming quiz"""
    def __init__(self, start_time, quiz_id, quiz_name):
        super().__init__(timeout=None)  # No timeout since we'll handle it manually
        self.registered_players = {}  # {player_id: player_interaction}
        self.start_time = start_time
        self.quiz_id = quiz_id
        self.quiz_name = quiz_name
        self.message = None
        self.is_closed = False
        self.quiz_started = False  # New flag to track if quiz has started
        self.update_lock = asyncio.Lock()  # Add lock for updating messages

    @discord.ui.button(label="Register for Quiz", style=discord.ButtonStyle.primary)
    async def register_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle player registration"""
        if self.is_closed:
            await interaction.response.send_message("Registration is now closed.", ephemeral=True)
            return
            
        player_id = interaction.user.id
        if player_id in self.registered_players:
            await interaction.response.send_message("You're already registered for this quiz!", ephemeral=True)
        else:
            # Store the player's interaction for later use
            self.registered_players[player_id] = interaction
            
            await interaction.response.send_message(
                f"You've registered for **{self.quiz_name}**! The quiz will start at {self.start_time.strftime('%H:%M:%S')}.\n"
                f"You'll receive your personal quiz interface when the quiz begins.",
                ephemeral=True
            )
            
            # Update the registration message with current count
            await self.update_registration_message()
    
    @discord.ui.button(label="Recover Quiz Interface", style=discord.ButtonStyle.secondary, row=1)
    async def recover_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle recovery of dismissed quiz interfaces"""
        player_id = interaction.user.id
        
        # Only show this button after quiz has started
        if not self.quiz_started:
            await interaction.response.send_message(
                "The quiz hasn't started yet. Please wait for it to begin.",
                ephemeral=True
            )
            return
            
        # Check if player is registered
        if player_id not in self.registered_players:
            await interaction.response.send_message(
                "You're not registered for this quiz. You can't recover an interface.",
                ephemeral=True
            )
            return
            
        # Let the parent controller handle the recovery by passing along this interaction
        if hasattr(self, 'parent_controller') and self.parent_controller:
            await self.parent_controller.recover_player_interface(player_id, interaction)
        else:
            await interaction.response.send_message(
                "Unable to recover your interface at this time. Please try again.",
                ephemeral=True
            )
            
    async def update_registration_message(self):
        """Update the registration message with current player count using lock"""
        async with self.update_lock:  # Prevent concurrent edits
            if not self.message:
                return
                
            try:
                time_left = self.start_time - datetime.now()
                minutes, seconds = divmod(time_left.seconds, 60)
                
                embed = discord.Embed(
                    title=f"Quiz: {self.quiz_name}",
                    description=f"Starting in: **{minutes}m {seconds}s**",
                    color=discord.Color.blue()
                )
                embed.add_field(name="Registered Players", value=f"**{len(self.registered_players)}** players registered")
                
                # Only show recovery button after quiz has started
                if self.quiz_started:
                    embed.set_footer(text="Quiz in progress. If you accidentally dismissed your quiz interface, click 'Recover Quiz Interface'")
                    # Make sure the recover button is visible
                    self.recover_button.disabled = False
                else:
                    embed.set_footer(text="Click the button below to register!")
                    # Hide the recover button before quiz starts
                    self.recover_button.disabled = True
                
                await self.message.edit(embed=embed, view=self)
            except discord.errors.NotFound:
                logger.warning("Registration message not found")
            except Exception as e:
                logger.error(f"Error updating registration message: {e}")
    
    def close_registration(self):
        """Close registration and disable the button"""
        self.is_closed = True
        self.register_button.disabled = True
        
    def mark_quiz_started(self, controller):
        """Mark that the quiz has started and enable recovery button"""
        self.quiz_started = True
        self.parent_controller = controller
        self.recover_button.disabled = False


# Modify PlayerAnswerButton to use rate limiting
class PlayerAnswerButton(discord.ui.Button):
    """Button for a player to answer the current question with rate limiting"""
    def __init__(self, option_key, option_value, parent_view):
        # Generate a unique ID for each button instance
        unique_id = f"answer_{option_key}_{random.randint(10000, 99999)}"
        
        super().__init__(
            label=f"{option_key}", 
            style=discord.ButtonStyle.primary, 
            custom_id=unique_id
        )
        self.option_key = option_key
        self.option_value = option_value
        self.parent_view = parent_view
        
    async def callback(self, interaction: discord.Interaction):
        # Immediately defer the interaction to prevent timeouts
        await interaction.response.defer(ephemeral=True)
        
        # Check if this is the right user
        if interaction.user.id != self.parent_view.player_id:
            await interaction.followup.send("This isn't your quiz interface!", ephemeral=True)
            return
        
        # Get the rate limiter from the parent quiz
        rate_limiter = self.parent_view.parent_quiz.rate_limiter
        
        # Check if rate limited
        if rate_limiter.is_rate_limited(interaction.user.id):
            # Queue this interaction for later processing
            rate_limiter.add_to_queue(
                interaction.user.id,
                self.process_answer,
                interaction
            )
            
            # Start queue processing if not already running
            self.parent_view.parent_quiz.create_task(
                rate_limiter.process_queue(interaction.user.id)
            )
            
            await interaction.followup.send("Processing your answer...", ephemeral=True)
        else:
            # Process immediately
            rate_limiter.update_timestamp(interaction.user.id)
            await self.process_answer(interaction)
    
    @backoff.on_exception(
        backoff.expo,
        discord.errors.HTTPException,
        max_tries=3,
        giveup=lambda e: e.code == 50027  # Give up on invalid webhook token
    )
    async def process_answer(self, interaction):
        """Process the answer with retry logic"""
        # Check if player has already answered this question
        question_id = self.parent_view.question_data[0]
        if (question_id in self.parent_view.parent_quiz.player_answers and 
            self.parent_view.player_id in self.parent_view.parent_quiz.player_answers[question_id]):
            await interaction.followup.send("You've already answered this question!", ephemeral=True)
            return

        # Check if the quiz is still in progress
        if self.parent_view.parent_quiz.quiz_status != "in_progress":
            await interaction.followup.send("This question is no longer active!", ephemeral=True)
            return
        
        # Lock the view to prevent multiple answers during processing
        for item in self.parent_view.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True

        self.parent_view.has_answered = True
        time_taken = time.time() - self.parent_view.start_time
        
        correct_answer = self.parent_view.question_data[4]
        max_score = self.parent_view.question_data[5]
        
        try:
            # Record answer
            await self.parent_view.parent_quiz.record_player_answer(
                self.parent_view.player_id, 
                self.parent_view.question_data[0],  # question_id
                self.option_key, 
                correct_answer, 
                time_taken,
                max_score
            )
            
            # Update the view to show it's disabled
            if self.parent_view.message:
                try:
                    await self.parent_view.message.edit(view=self.parent_view)
                except discord.errors.NotFound:
                    # Message may have been deleted
                    pass
                    
            # Create response message with explanation if available and answer was wrong
            response_message = ""
            if self.option_key != correct_answer:
                response_message = f"❌ Incorrect. The correct answer is: {correct_answer}"
                
                # Add explanation if available
                if len(self.parent_view.question_data) > 6 and self.parent_view.question_data[6]:
                    response_message += f"\n\n**Explanation:** {self.parent_view.question_data[6]}"
            else:
                response_message = "✅ Correct!"
                
            # Send the combined message with explanation included
            try:
                await interaction.followup.send(
                    response_message,
                    ephemeral=True
                )
            except Exception as e:
                logger.error(f"Failed to send answer response: {e}")
                    
        except Exception as e:
            logging.error(f"Error recording answer: {e}")
            await interaction.followup.send("There was an error recording your answer. Please try again or use the recovery button.", ephemeral=True)
            # Re-enable buttons in case of error
            for item in self.parent_view.children:
                if isinstance(item, discord.ui.Button):
                    item.disabled = False
            if self.parent_view.message:
                try:
                    await self.parent_view.message.edit(view=self.parent_view)
                except discord.errors.NotFound:
                    pass


class PlayerAnswerView(discord.ui.View):
    """Individual view for a player to answer the current question"""
    def __init__(self, player_id, question_data, timer, parent_quiz):
        super().__init__(timeout=timer)
        self.player_id = player_id
        self.question_data = question_data
        self.parent_quiz = parent_quiz
        self.has_answered = False
        self.start_time = time.time()
        self.message = None  # Will be set after the message is sent
        
        # Parse options and add buttons
        options = json.loads(question_data[3])
        for key, value in options.items():
            self.add_item(PlayerAnswerButton(key, value, self))
        
    async def on_timeout(self):
        """Handle timeout if player doesn't answer"""
        if not self.has_answered and self.message:
            for item in self.children:
                if isinstance(item, discord.ui.Button):
                    item.disabled = True
            
            # We don't edit the message here as the parent_quiz will handle it
            # during the next question or end of timer
            self.has_answered = True

class TimedQuizController:
    """Controller for the timed quiz game with improved concurrency handling"""
    def __init__(self, channel, quiz_id, start_time, timer=20):
        # Original initialization code remains the same
        self.channel = channel
        self.quiz_id = quiz_id
        self.start_time = start_time
        self.timer = timer
        self.questions = []
        self.registration_view = None
        self.player_scores = {}  # {player_id: score}
        self.player_answers = {}  # {question_id: {player_id: {"answer": answer, "time": time}}}
        self.quiz_name = None
        self.announcement_message = None
        self.question_message = None
        self.player_quiz_messages = {}  # {player_id: message}
        self.current_question_index = -1
        self.current_question_data = None
        self.quiz_status = "not_started"
        
        # Add rate limiter
        self.rate_limiter = RateLimiter()
        
        # Enhanced locking strategy
        self.player_answer_lock = asyncio.Lock()
        self.player_interface_lock = {}  # Will be created per player as needed
        self.message_edit_locks = {}  # {message_id: lock} for preventing concurrent edits
    
    # Improved error handling decorator
    def catch_and_log(func):
        """Decorator for catching and logging errors in asynchronous functions with retry logic"""
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            max_retries = 3
            retry_delay = 1.0
            
            for attempt in range(max_retries):
                try:
                    return await func(self, *args, **kwargs)
                except discord.errors.NotFound:
                    # Message not found or deleted - no point retrying
                    logging.warning(f"{func.__name__} - Discord message not found")
                    return None
                except discord.errors.Forbidden:
                    # Missing permissions - no point retrying
                    logging.error(f"{func.__name__} - Missing permissions to perform action")
                    return None
                except discord.errors.HTTPException as e:
                    if e.code == 50027:  # Invalid Webhook Token
                        # No point retrying
                        return None
                    elif e.code == 429:  # Rate limited
                        # Calculate retry after time
                        retry_after = e.response.headers.get('Retry-After', retry_delay)
                        retry_after = float(retry_after) if retry_after else retry_delay
                        logging.warning(f"{func.__name__} - Rate limited, retrying in {retry_after} seconds")
                        await asyncio.sleep(retry_after)
                        # Increase delay for next attempt
                        retry_delay *= 2
                        continue
                    else:
                        # Other HTTP error
                        logging.error(f"{func.__name__} - Discord API error: {e}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2
                            continue
                        return None
                except Exception as e:
                    logging.error(f"{func.__name__} - Unexpected error: {e}", exc_info=True)
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    return None
            return None
        return wrapper
    
        # Add this method for safe message editing
    async def safe_message_edit(self, message, **kwargs):
        """Thread-safe message editing with lock per message"""
        if not message:
            return False
            
        # Get or create lock for this message
        message_id = str(message.id)
        if message_id not in self.message_edit_locks:
            self.message_edit_locks[message_id] = asyncio.Lock()
            
        async with self.message_edit_locks[message_id]:
            try:
                await message.edit(**kwargs)
                return True
            except discord.errors.NotFound:
                # Message was deleted
                if message_id in self.message_edit_locks:
                    del self.message_edit_locks[message_id]
                return False
            except discord.errors.HTTPException as e:
                if e.code == 50027:  # Invalid Webhook Token
                    if message_id in self.message_edit_locks:
                        del self.message_edit_locks[message_id]
                    return False
                elif e.code == 429:  # Rate limited
                    retry_after = e.response.headers.get('Retry-After', 1.0)
                    retry_after = float(retry_after) if retry_after else 1.0
                    await asyncio.sleep(retry_after)
                    # Try once more
                    await message.edit(**kwargs)
                    return True
                else:
                    logging.error(f"HTTP error editing message: {e}")
                    return False
            except Exception as e:
                logging.error(f"Error editing message: {e}")
                return False

    async def initialize(self):
        """Initialize the quiz by loading questions and quiz name."""
        try:
            # Get quiz details
            quiz_result = await get_quiz_name(self.quiz_id)
            if not quiz_result:
                return False
                
            # Extract quiz name and creator info
            self.quiz_name = quiz_result[0]
            self.creator_id = quiz_result[1] if len(quiz_result) > 1 else None
            self.creator_username = quiz_result[2] if len(quiz_result) > 2 and quiz_result[2] else "Unknown"
            
            # Get questions
            self.questions = await get_quiz_questions(self.quiz_id)
            if not self.questions:
                logger.error(f"No questions found for quiz {self.quiz_id}")
                return False
                
            logger.info(f"Scheduled quiz {self.quiz_id} initialized with {len(self.questions)} questions")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize scheduled quiz: {e}")
            return False
    
        # Add a task tracking mechanism to prevent stray tasks
    def create_task(self, coro):
        """Create and track a task"""
        task = asyncio.create_task(coro)
        if not hasattr(self, '_pending_tasks'):
            self._pending_tasks = []
        self._pending_tasks.append(task)
        task.add_done_callback(lambda t: self._pending_tasks.remove(t) if t in self._pending_tasks else None)
        return task
    
    async def start_registration(self):
        """Start the registration phase"""
        # Create registration view
        self.registration_view = QuizRegistrationView(self.start_time, self.quiz_id, self.quiz_name)
        
        # Create and send registration announcement
        embed = discord.Embed(
            title=f"Upcoming Quiz: {self.quiz_name}",
            description=f"Starting at: **{self.start_time.strftime('%H:%M:%S')}**",
            color=discord.Color.blue()
        )
        embed.add_field(name="Registered Players", value="**0** players registered")
        embed.set_footer(text="Click the button below to register!")
        
        self.announcement_message = await self.channel.send(embed=embed, view=self.registration_view)
        self.registration_view.message = self.announcement_message
        
        # Start countdown timer as a tracked task, not blocking the function
        async def countdown_task():
            while datetime.now() < self.start_time and not self.registration_view.is_closed:
                time_left = self.start_time - datetime.now()
                if time_left.total_seconds() <= 0:
                    break
                        
                await self.registration_view.update_registration_message()
                    
                # Update every 15 seconds, or every second in the last 10 seconds
                if time_left.total_seconds() <= 10:
                    await asyncio.sleep(1)
                else:
                    await asyncio.sleep(10)
        
        # Create the countdown task but don't wait for it to complete
        self.create_task(countdown_task())
    
    async def close_registration(self):
        """Close registration and prepare for quiz start"""
        self.registration_view.close_registration()
        await self.registration_view.update_registration_message()
        
        # If no players registered, cancel quiz
        if not self.registration_view.registered_players:
            await self.channel.send(f"Quiz **{self.quiz_name}** has been cancelled due to no participants.")
            return False
            
        # Create player score tracking
        for player_id in self.registration_view.registered_players:
            self.player_scores[player_id] = 0
            
        # Announcement that quiz is starting
        start_embed = discord.Embed(
            title=f"Quiz Starting: {self.quiz_name}",
            description=f"**{len(self.registration_view.registered_players)}** players will be participating.",
            color=discord.Color.green()
        )
        self.question_message = await self.channel.send(embed=start_embed)
        
        # Tell the registration view that the quiz has started (enables recovery button)
        self.registration_view.mark_quiz_started(self)
        await self.registration_view.update_registration_message()
        
        # Send each registered player their initial quiz interface
        for player_id, interaction in self.registration_view.registered_players.items():
            try:
                # Create initial message with welcome text
                message = await interaction.followup.send(
                    "Your quiz interface is ready! Questions will appear here.",
                    ephemeral=True
                )
                # Store the message object for later updates
                self.player_quiz_messages[player_id] = message
            except Exception as e:
                logger.error(f"Error sending interface notice to player {player_id}: {e}")
        
        # Allow players to see the message before starting
        await asyncio.sleep(3)
        
        return True
    
    # Make sure to include the rate_limiter in the TimedQuizController initialization and cleanups
    async def cleanup(self):
        """Clean up resources when quiz ends"""
        # Original cleanup code...
        self.player_quiz_messages.clear()
        
        # Clear any pending tasks
        if hasattr(self, '_pending_tasks'):
            for task in self._pending_tasks:
                if not task.done():
                    task.cancel()
                    
            # Wait for tasks to complete cancellation
            for task in self._pending_tasks:
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logging.error(f"Error cancelling task: {e}")
        
        # Clear locks
        self.player_interface_lock.clear()
        self.message_edit_locks.clear()
        
        # Clear rate limiter data
        self.rate_limiter.cooldowns.clear()
        self.rate_limiter.interaction_queue.clear()
        self.rate_limiter.processing.clear()
        
        # Set quiz as finished
        self.quiz_status = "finished"
        logging.info(f"Quiz {self.quiz_id} cleanup complete")

    # Modify run_quiz to use cleanup
    async def run_quiz(self):
        """Run the quiz with proper resource management"""
        self._pending_tasks = []
        should_cleanup = True  # Flag to control cleanup
        
        try:
            if not await self.initialize():
                await self.channel.send("Failed to initialize quiz. Please try again.")
                return
                    
            # Start registration phase
            await self.start_registration()
            
            # Wait until start_time before closing registration
            now = datetime.now()
            if now < self.start_time:
                wait_time = (self.start_time - now).total_seconds()
                logger.info(f"Waiting {wait_time} seconds until quiz start time")
                await asyncio.sleep(wait_time)
            
            # Close registration and prepare quiz
            if not await self.close_registration():
                # Don't call cleanup here, let the finally block handle it
                return
                    
            # Run through questions
            for i, question_data in enumerate(self.questions):
                await self.show_question(i, question_data)
                    
            # Show final results
            await self.show_results()
        except Exception as e:
            logger.error(f"Error running quiz: {e}", exc_info=True)
            try:
                await self.channel.send("An error occurred during the quiz. The quiz has been terminated.")
            except Exception:
                pass
        finally:
            # Always clean up resources
            if should_cleanup:
                await self.cleanup()
    
    async def show_question(self, index, question_data):
        """Show the current question and update individual player interfaces"""
        # Update the current question tracking
        self.current_question_index = index
        self.current_question_data = question_data
        self.quiz_status = "in_progress"
        
        question_id = question_data[0]
        question_text = question_data[2]
        options = json.loads(question_data[3])
        
        # Reset player answers for this question
        self.player_answers[question_id] = {}
        
        # Create question embed
        embed = discord.Embed(
            title=f"Question {index + 1}/{len(self.questions)}", 
            description=question_text, 
            color=discord.Color.blue()
        )
        
        # Add options as fields
        for key, value in options.items():
            embed.add_field(name=key, value=value, inline=False)
        
        embed.set_footer(text=f"Time remaining: {self.timer} seconds")
        
        # Update the main question message
        await self.question_message.edit(embed=embed)
        
        # Update each player's interface with the new question
        for player_id in self.player_quiz_messages:
            await self.update_player_interface(player_id)
        
        # Timer countdown
        time_left = self.timer
        while time_left > 0:
            # Update every 5 seconds or when time is low
            if time_left % 5 == 0 or time_left <= 5:
                embed.set_footer(text=f"Time remaining: {time_left} seconds")
                await self.question_message.edit(embed=embed)
            await asyncio.sleep(1)
            time_left -= 1
        
        # Question time is up - update the question message
        embed.set_footer(text="Time's up! ⌛")
        await self.question_message.edit(embed=embed)
        
        # Show correct answer
        self.quiz_status = "showing_answer"
        correct_answer = question_data[4]
        answer_embed = discord.Embed(
            title=f"Answer to Question {index + 1}",
            description=f"The correct answer was: **{correct_answer}**",
            color=discord.Color.gold()
        )
        
        # Calculate how many players got it right
        question_answers = self.player_answers.get(question_id, {})
        correct_count = sum(1 for player_data in question_answers.values() 
                           if player_data.get("answer") == correct_answer)
        
        answer_embed.add_field(
            name="Statistics", 
            value=f"{correct_count}/{len(self.registration_view.registered_players)} players answered correctly"
        )
        
        await self.question_message.edit(embed=answer_embed)
        
        # Update all player interfaces to show the correct answer
        for player_id in list(self.player_quiz_messages.keys()):  # Use list() to avoid modification during iteration
            await self.show_answer_to_player(player_id, question_id, correct_answer)
        
        # Short pause between questions
        await asyncio.sleep(3)

    # Update record_player_answer with improved locking and retry logic
    async def record_player_answer(self, player_id, question_id, answer, correct_answer, time_taken, max_score):
        """Record a player's answer and update score with improved concurrency handling"""
        async with self.player_answer_lock:
            # Check again if player already answered (might have changed while waiting for lock)
            if (question_id in self.player_answers and 
                player_id in self.player_answers[question_id]):
                logging.warning(f"Race condition caught: Player {player_id} already answered question {question_id}")
                return
                
            if question_id not in self.player_answers:
                self.player_answers[question_id] = {}
                    
            # Record the answer and time
            self.player_answers[question_id][player_id] = {
                "answer": answer, 
                "time": time_taken
            }
            
            # Update score if correct
            if answer == correct_answer:
                time_penalty_ratio = max(0, 1 - (time_taken / self.timer))
                scored_points = int(max_score * time_penalty_ratio)
                
                if player_id not in self.player_scores:
                    self.player_scores[player_id] = 0
                        
                self.player_scores[player_id] += scored_points
                logging.debug(f"Player {player_id} scored {scored_points} points on question {question_id}")

        # Get or create player-specific lock
        if player_id not in self.player_interface_lock:
            self.player_interface_lock[player_id] = asyncio.Lock()
            
        # Update the player's message - separate lock per player
        async with self.player_interface_lock[player_id]:
            player_message = self.player_quiz_messages.get(player_id)
            if player_message:
                if answer == correct_answer:
                    time_penalty_ratio = max(0, 1 - (time_taken / self.timer))
                    scored_points = int(max_score * time_penalty_ratio)
                    await self.safe_message_edit(
                        player_message,
                        content=f"✅ Correct! You earned {scored_points} points.", 
                        view=None  # Remove the buttons
                    )
                else:
                    await self.safe_message_edit(
                        player_message,
                        content=f"❌ Incorrect.", 
                        view=None  # Remove the buttons
                    )

    # Update update_player_interface to use safe_message_edit
    @catch_and_log
    async def update_player_interface(self, player_id):
        """Update a player's interface with the current question with improved concurrency handling"""
        if self.current_question_index < 0 or not self.current_question_data:
            # No active question
            return False
                
        # Check if we have a message for this player
        player_message = self.player_quiz_messages.get(player_id)
        if not player_message:
            # No message to update
            return False
        
        # Get or create player-specific lock
        if player_id not in self.player_interface_lock:
            self.player_interface_lock[player_id] = asyncio.Lock()
            
        # Use the lock to prevent concurrent edits
        async with self.player_interface_lock[player_id]:
            # Get question data
            question_id = self.current_question_data[0]
            question_text = self.current_question_data[2]
            
            # Check if player already answered this question
            already_answered = (question_id in self.player_answers and 
                      player_id in self.player_answers[question_id])
            
            # Create a new view for the current question
            view = PlayerAnswerView(player_id, self.current_question_data, self.timer, self)
            
            # If player already answered, disable all buttons
            if already_answered:
                for item in view.children:
                    if isinstance(item, discord.ui.Button):
                        item.disabled = True
            
            # Update the existing message with the new question and view
            content = f"Question {self.current_question_index + 1}: {question_text}"
            if already_answered:
                player_answer = self.player_answers[question_id][player_id]["answer"]
                content += f"\n\nYou already answered: {player_answer}"
                
            success = await self.safe_message_edit(
                player_message,
                content=content,
                view=view,
                embed=None  # Remove any previous embeds
            )
            
            if success:
                # Store the view's message reference for timeout handling
                view.message = player_message
                return True
            else:
                # Message edit failed, remove from tracking
                self.player_quiz_messages.pop(player_id, None)
                return False

    @catch_and_log
    async def show_answer_to_player(self, player_id, question_id, correct_answer):
        """Show the answer for the current question to a player"""
        player_message = self.player_quiz_messages.get(player_id)
        if not player_message:
            return False
            
        player_answer = ""
        if question_id in self.player_answers and player_id in self.player_answers[question_id]:
            answer = self.player_answers[question_id][player_id]["answer"]
            if answer == correct_answer:
                player_answer = f"✅ Your answer: {answer} (Correct!)"
            else:
                player_answer = f"❌ Your answer: {answer} (Incorrect. Correct: {correct_answer})"
        else:
            player_answer = f"⌛ You didn't answer in time. Correct answer: {correct_answer}"
            
        try:
            # Disable any buttons and show the answer
            await player_message.edit(
                content=player_answer,
                view=None  # Remove the view with buttons
            )
            return True
        except Exception as e:
            logger.error(f"Error updating result for player {player_id}: {e}")
            # If we can't edit the message, it may have been dismissed
            self.player_quiz_messages.pop(player_id, None)
            return False

    async def recover_player_interface(self, player_id, interaction):
        """Recover a player's quiz interface if it was dismissed"""
        # First, check if the player is registered
        if player_id not in self.registration_view.registered_players:
            await interaction.response.send_message(
                "You're not registered for this quiz.",
                ephemeral=True
            )
            return
            
        # Create a new message
        try:
            await interaction.response.defer(ephemeral=True)
            
            if self.quiz_status == "finished":
                # Quiz is over, show final results
                message = await interaction.followup.send(
                    "Here are your quiz results:",
                    ephemeral=True
                )
                self.player_quiz_messages[player_id] = message
                await self.show_player_final_results(player_id)
                
            elif self.quiz_status == "showing_answer" and self.current_question_data:
                # Currently showing an answer, recreate the answer view
                message = await interaction.followup.send(
                    "Recovering your quiz interface...",
                    ephemeral=True
                )
                self.player_quiz_messages[player_id] = message
                
                correct_answer = self.current_question_data[4]
                question_id = self.current_question_data[0]
                await self.show_answer_to_player(player_id, question_id, correct_answer)
                
            elif self.quiz_status == "in_progress" and self.current_question_data:
                # Currently showing a question, recreate the question view
                question_id = self.current_question_data[0]
                already_answered = (question_id in self.player_answers and 
                                player_id in self.player_answers[question_id])
                                
                if already_answered:
                    player_answer = self.player_answers[question_id][player_id]["answer"]
                    message = await interaction.followup.send(
                        f"Recovering your quiz interface... You already answered this question with: {player_answer}",
                        ephemeral=True
                    )
                else:
                    message = await interaction.followup.send(
                        "Recovering your quiz interface...",
                        ephemeral=True
                    )
                    
                self.player_quiz_messages[player_id] = message
                
                # Update with current question
                await self.update_player_interface(player_id)
            else:
                # Quiz hasn't started questions yet or is in an unknown state
                message = await interaction.followup.send(
                    f"Your quiz interface has been recovered. Please wait for the quiz to continue.",
                    ephemeral=True
                )
                self.player_quiz_messages[player_id] = message
                
        except Exception as e:
            logger.error(f"Error recovering interface for player {player_id}: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An error occurred while recovering your quiz interface. Please try again.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "An error occurred while recovering your quiz interface. Please try again.",
                    ephemeral=True
                )

    @catch_and_log
    async def show_player_final_results(self, player_id, interaction=None):
        """Show final results to a specific player"""
        # Get player's score and rank
        player_score = self.player_scores.get(player_id, 0)
        
        # Sort players by score to find rank
        sorted_scores = sorted(self.player_scores.items(), key=lambda x: x[1], reverse=True)
        player_rank = next((idx+1 for idx, (pid, _) in enumerate(sorted_scores) if pid == player_id), 0)
        
        # Create final results embed
        rank_text = f"🥇 1st place" if player_rank == 1 else f"🥈 2nd place" if player_rank == 2 else f"🥉 3rd place" if player_rank == 3 else f"{player_rank}th place"
                
        final_embed = discord.Embed(
            title=f"Quiz Complete: {self.quiz_name}",
            description=f"Your final score: **{player_score} points**",
            color=discord.Color.gold()
        )
        
        final_embed.add_field(name="Your ranking", value=rank_text)
        
        # Add creator info if available
        if hasattr(self, 'creator_username') and self.creator_username:
            final_embed.add_field(
                name="Quiz Creator",
                value=self.creator_username,
                inline=False
            )
        
        # Either update existing message or send a new one through interaction
        if interaction:
            # This is a recovery via interaction - interaction should already be deferred
            # and we should use followup, not response directly
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)
                await interaction.followup.send(
                    embed=final_embed,
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    embed=final_embed,
                    ephemeral=True
                )
        else:
            # Update existing message
            player_message = self.player_quiz_messages.get(player_id)
            if player_message:
                try:
                    await player_message.edit(content="", embed=final_embed, view=None)
                except Exception as e:
                    logger.error(f"Error sending final results to player {player_id}: {e}")

    async def show_results(self):
        """Show final results and record scores"""
        self.quiz_status = "finished"
        
        if not self.player_scores:
            await self.channel.send("No scores to display.")
            return
            
        # Sort players by score
        sorted_scores = sorted(self.player_scores.items(), key=lambda x: x[1], reverse=True)
        
        # Create results embed
        embed = discord.Embed(
            title=f"Quiz Results: {self.quiz_name}",
            description="Here are the final scores:",
            color=discord.Color.gold()
        )
        
        # Add creator info if available
        if hasattr(self, 'creator_username') and self.creator_username:
            embed.add_field(
                name="Quiz Creator",
                value=self.creator_username,
                inline=False
            )
        
        # Add player scores
        for rank, (player_id, score) in enumerate(sorted_scores, 1):
            player = self.channel.guild.get_member(player_id)
            player_name = player.display_name if player else f"Player {player_id}"
            
            # Special formatting for top 3
            if rank <= 3:
                medal = ["🥇", "🥈", "🥉"][rank-1]
                embed.add_field(
                    name=f"{medal} {rank}. {player_name}",
                    value=f"**{score} points**",
                    inline=False
                )
            else:
                embed.add_field(
                    name=f"{rank}. {player_name}",
                    value=f"{score} points",
                    inline=True
                )
        
        # Update registration message to indicate quiz is complete
        if self.registration_view and self.registration_view.message:
            complete_embed = discord.Embed(
                title=f"Quiz Complete: {self.quiz_name}",
                description="This quiz has ended. See results below.",
                color=discord.Color.green()
            )
            
            # Add creator info to the complete message too
            if hasattr(self, 'creator_username') and self.creator_username:
                complete_embed.add_field(
                    name="Created by",
                    value=self.creator_username,
                    inline=False
                )
            
            # Clear all items (buttons) from the view
            self.registration_view.clear_items()
            
            # Update the message with the new embed and the cleared view
            await self.registration_view.message.edit(embed=complete_embed, view=self.registration_view)
        
        # Update each player's interface with their final result
        for player_id in list(self.player_quiz_messages.keys()):
            await self.show_player_final_results(player_id)
                
        # Record scores in database
        for player_id, score in self.player_scores.items():
            player = self.channel.guild.get_member(player_id)
            if player:
                await record_user_score(player_id, player.name, self.quiz_id, score)
        
        # Send results
        await self.question_message.edit(embed=embed)
