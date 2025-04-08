import discord
from discord.ext import commands
import logging
import asyncio
import time
import json
from config import CONFIG
from utils.db_utilsv2 import get_quiz_questions, record_user_score, get_quiz_name

logger = logging.getLogger('badgey.solo_quiz_dm')

class QuizQueue:
    """Manages a queue of users waiting to take quizzes with rate limiting"""
    def __init__(self):
        self.queue = []  # List of (user_id, channel_id, guild_id, user, quiz_id, timer, user_name) tuples
        self.active_quizzes = {}  # Map of user_id to timestamp of when they started
        self.cooldown = 300  # Cooldown period in seconds (5 minutes)
        self.lock = asyncio.Lock()
    
    async def add_to_queue(self, user_id, channel_id, guild_id, user, quiz_id, timer, user_name=None):
        """Add a user to the quiz queue if they're not on cooldown"""
        async with self.lock:
            current_time = time.time()
            
            # Check if user is on cooldown
            if user_id in self.active_quizzes:
                last_quiz_time = self.active_quizzes[user_id]
                time_elapsed = current_time - last_quiz_time
                
                if time_elapsed < self.cooldown:
                    time_remaining = int(self.cooldown - time_elapsed)
                    return False, f"You need to wait {time_remaining} seconds before starting another quiz."
            
            # Add user to queue
            self.queue.append((user_id, channel_id, guild_id, user, quiz_id, timer, user_name))
            position = len(self.queue)
            
            return True, f"You've been added to the quiz queue. Position: {position}"
    
    async def process_queue(self, bot):
        """Process the quiz queue periodically"""
        while True:
            try:
                async with self.lock:
                    if self.queue:
                        # Process the next item in queue
                        user_id, channel_id, user, quiz_id, timer, user_name = self.queue[0]
                        self.queue.pop(0)
                        
                        # Mark as active
                        self.active_quizzes[user_id] = time.time()
                        
                        # Start the quiz for this user
                        try:
                            # Create the quiz view
                            quiz_view = DMQuizView(user_id, channel_id, user, bot, quiz_id, timer, user_name)
                            success = await quiz_view.initialize(quiz_id)
                            
                            if success:
                                # Start the quiz in a background task
                                bot.loop.create_task(quiz_view.run_quiz())
                            else:
                                # Clean up failed initializations
                                if user_id in self.active_quizzes:
                                    del self.active_quizzes[user_id]
                        except Exception as e:
                            logger.error(f"Error starting quiz for user {user_id}: {e}")
                            try:
                                await user.send(f"Sorry, there was an error starting your quiz: {str(e)}")
                            except:
                                pass
                            # Clean up on error
                            if user_id in self.active_quizzes:
                                del self.active_quizzes[user_id]
                    
                    # Clean up expired cooldowns
                    current_time = time.time()
                    expired = [uid for uid, start_time in self.active_quizzes.items() 
                              if current_time - start_time > self.cooldown]
                    
                    for uid in expired:
                        del self.active_quizzes[uid]
                
            except Exception as e:
                logger.error(f"Error processing quiz queue: {e}")
            
            # Check the queue every 5 seconds
            await asyncio.sleep(5)

class DMQuizView:
    """View for displaying individual quiz questions and handling responses in direct messages"""
    def __init__(self, user_id, channel_id, user, bot, quiz_id, timer, user_name=None):
        self.quiz_id = quiz_id
        self.user_id = user_id
        self.user_name = user_name or f"User-{user_id}"
        self.channel_id = channel_id
        self.user = user
        self.bot = bot
        self.score = 0
        self.current_index = 0
        self.questions = []
        self.timer_duration = timer
        self.current_message = None
        self.quiz_instance_id = f"{user_id}_{int(time.time())}"
        self.is_running = False
        self.view = None
        self.answered = False  # Track if the current question has been answered
        self._quiz_ended = False  # Flag to track if quiz has been ended
        self._auto_end_task = None  # Store the auto-end task for cancellation
    
    async def initialize(self, quiz_id):
        """Initialize the quiz by loading questions"""
        try:
            # Get quiz questions
            self.questions = await get_quiz_questions(quiz_id)
            if not self.questions:
                logger.error(f"No questions found for quiz {quiz_id}")
                await self.user.send(f"Sorry, no questions found for quiz ID {quiz_id}.")
                return False
            
            # Get quiz name
            quiz_result = await get_quiz_name(quiz_id)
            quiz_name = quiz_result[0] if quiz_result else f"Quiz {quiz_id}"
            
            # Send initial message
            try:
                self.current_message = await self.user.send(
                    f"Starting quiz: **{quiz_name}**\n\n"
                    f"This quiz has {len(self.questions)} questions.\n"
                    f"You will have {self.timer_duration} seconds for each question.\n"
                    f"Click 'Start Quiz' when you're ready!"
                )
                
                # Create a simple start button
                view = discord.ui.View(timeout=300)  # 5 minute timeout
                start_button = discord.ui.Button(label="Start Quiz", style=discord.ButtonStyle.success)
                
                async def start_quiz_callback(interaction):
                    if interaction.user.id != self.user_id:
                        await interaction.response.send_message("This quiz is not for you!", ephemeral=True)
                        return
                    
                    await interaction.response.defer()
                    self.is_running = True
                    await self.current_message.edit(content="Quiz starting...", view=None)
                
                start_button.callback = start_quiz_callback
                view.add_item(start_button)
                
                await self.current_message.edit(view=view)
                logger.info(f"DM quiz {quiz_id} initialized with {len(self.questions)} questions for user {self.user_id}")
                return True
                
            except discord.Forbidden:
                logger.error(f"Cannot send DM to user {self.user_id} - DMs disabled")
                return False
                
        except Exception as e:
            logger.error(f"Failed to initialize quiz: {e}")
            return False
    
    async def run_quiz(self):
        """Run the entire quiz as a background task"""
        # Wait for user to start the quiz
        while not self.is_running:
            await asyncio.sleep(1)
        
        try:
            # Start showing questions
            for i in range(len(self.questions)):
                self.current_index = i
                
                # Show current question
                await self.show_question()
                
                # Wait for this question to complete before moving to the next one
                while self.current_index == i and self.is_running:
                    await asyncio.sleep(0.5)
                
                # If quiz was terminated, break out
                if not self.is_running:
                    break
                    
            # All questions completed
            if self.is_running:
                await self.end_quiz()
        except Exception as e:
            logger.error(f"Error running quiz: {e}")
            try:
                await self.user.send("Sorry, there was an error running your quiz. Please try again later.")
            except:
                pass
    
    async def show_question(self):
        """Display the current question to the user via DM"""
        if self.current_index >= len(self.questions):
            await self.end_quiz()
            return
        
        try:
            # Reset the answered flag for the new question
            self.answered = False
            
            question_data = self.questions[self.current_index]
            question_text = question_data[2]
            options = json.loads(question_data[3])
            correct_answer = question_data[4]
            max_score = question_data[5]
            
            # Create a unique ID for this specific question instance
            question_instance_id = f"{self.quiz_instance_id}_{self.current_index}"
            
            # Create a new discord View for this question
            view = discord.ui.View(timeout=self.timer_duration + 5)  # Add a small buffer to timeout
            
            # Create question embed
            embed = discord.Embed(
                title=f"Question {self.current_index + 1}/{len(self.questions)}", 
                description=question_text, 
                color=discord.Color.blue()
            )
            
            # Add options as fields
            for key, value in options.items():
                embed.add_field(name=key, value=value, inline=False)
            
            embed.set_footer(text=f"Time left: {self.timer_duration} seconds ⏳ | Quiz ID: {question_instance_id}")
            
            # Add button for each option
            for key in options.keys():
                button = discord.ui.Button(
                    label=key, 
                    style=discord.ButtonStyle.primary, 
                    custom_id=f"answer_{question_instance_id}_{key}"
                )
                
                async def make_callback(btn_key):
                    async def answer_callback(interaction):
                        # First, verify this is the right user
                        if interaction.user.id != self.user_id:
                            await interaction.response.send_message("This quiz is not for you!", ephemeral=True)
                            return
                        
                        # Check if the question has already been answered by extracting the question ID from custom_id
                        interaction_id_parts = interaction.data.get('custom_id', '').split('_')
                        if len(interaction_id_parts) >= 3:
                            # Extract the quiz and question IDs from the custom_id
                            interaction_quiz_id = '_'.join(interaction_id_parts[1:-1])
                            if f"{self.quiz_instance_id}_{self.current_index}" != interaction_quiz_id:
                                await interaction.response.send_message(
                                    "This question has already been answered or is not active.",
                                    ephemeral=True
                                )
                                return
                        
                        # Check if we've already processed an answer for this question
                        if self.answered:
                            await interaction.response.send_message(
                                "You've already answered this question!",
                                ephemeral=True
                            )
                            return
                            
                        # Mark as answered immediately to prevent double-clicks
                        self.answered = True
                        
                        # Acknowledge interaction immediately
                        await interaction.response.defer()
                        
                        # Stop the timer
                        self.is_running = False
                        
                        # Process the answer
                        start_time = time.time() - (self.timer_duration - float(embed.footer.text.split()[2]))
                        await self.process_answer(
                            interaction.message,
                            btn_key,
                            correct_answer,
                            max_score,
                            start_time
                        )
                    return answer_callback
                
                button.callback = await make_callback(key)
                view.add_item(button)
            
            # Send/update the message
            if self.current_message:
                try:
                    self.current_message = await self.current_message.edit(content=None, embed=embed, view=view)
                except discord.NotFound:
                    self.current_message = await self.user.send(embed=embed, view=view)
            else:
                self.current_message = await self.user.send(embed=embed, view=view)
            
            # Save the current view for reference
            self.view = view
            
            # Run timer in the background
            asyncio.create_task(self.run_timer(self.current_message, embed, self.current_index, question_instance_id))
            
        except Exception as e:
            logger.error(f"Error showing question: {e}")
            try:
                await self.user.send(f"Error showing question: {str(e)}")
            except:
                pass
    
    async def run_timer(self, message, embed, question_index, question_instance_id):
        """Run a timer for the current question"""
        try:
            # Set initial time
            time_left = self.timer_duration
            
            # Only run timer while question is active and hasn't been answered
            while time_left > 0 and self.is_running and self.current_index == question_index and not self.answered:
                # Update timer every 3 seconds or when time is low
                if time_left % 3 == 0 or time_left <= 5:
                    embed.set_footer(text=f"Time left: {time_left} seconds ⏳ | Quiz ID: {question_instance_id}")
                    try:
                        await message.edit(embed=embed)
                    except (discord.NotFound, discord.Forbidden):
                        # Message was deleted or can't be edited
                        return
                
                await asyncio.sleep(1)
                time_left -= 1
            
                # If the timer ran out and question is still active, process timeout
                if time_left <= 0 and self.is_running and self.current_index == question_index and not self.answered:
                    self.is_running = False
                    self.answered = True
                    
                    # Show timeout message
                    embed.add_field(
                        name="Time's up!",
                        value=f"The correct answer was {self.questions[question_index][4]}",
                        inline=False
                    )
                    
                    # Disable buttons
                    if self.view:
                        for item in self.view.children:
                            if isinstance(item, discord.ui.Button):
                                item.disabled = True
                    
                    # Check if this is the last question
                    is_last_question = question_index == len(self.questions) - 1
                    
                    if is_last_question:
                        # Add End Quiz button
                        next_view = discord.ui.View()
                        end_button = discord.ui.Button(
                            label="End Quiz", 
                            style=discord.ButtonStyle.success,
                            custom_id=f"end_{question_instance_id}"
                        )
                        
                        async def end_callback(interaction):
                            if interaction.user.id != self.user_id:
                                await interaction.response.send_message("This quiz is not for you!", ephemeral=True)
                                return
                            
                            # Verify this is for the current question
                            interaction_id = interaction.data.get('custom_id', '').split('_', 1)[1]
                            if question_instance_id != interaction_id:
                                await interaction.response.send_message(
                                    "This button is no longer active.",
                                    ephemeral=True
                                )
                                return
                            
                            await interaction.response.defer()
                            # End the quiz
                            await self.end_quiz()
                        
                        end_button.callback = end_callback
                        next_view.add_item(end_button)
                        
                        # Add message about auto-ending
                        embed.add_field(
                            name="Quiz Completion",
                            value="This is the final question. Press 'End Quiz' to see your results. The quiz will automatically end in 60 seconds.",
                            inline=False
                        )
                        
                        # Create a task to automatically end the quiz after timeout
                        self._auto_end_task = asyncio.create_task(self.auto_end_quiz(60))
                    else:
                        # Add Next Question button for non-last questions
                        next_view = discord.ui.View()
                        next_button = discord.ui.Button(
                            label="Next Question", 
                            style=discord.ButtonStyle.primary,
                            custom_id=f"next_{question_instance_id}"
                        )
                        
                        async def next_callback(interaction):
                            if interaction.user.id != self.user_id:
                                await interaction.response.send_message("This quiz is not for you!", ephemeral=True)
                                return
                            
                            # Verify this is for the current question
                            interaction_id = interaction.data.get('custom_id', '').split('_', 1)[1]
                            if question_instance_id != interaction_id:
                                await interaction.response.send_message(
                                    "This button is no longer active.",
                                    ephemeral=True
                                )
                                return
                            
                            await interaction.response.defer()
                            # Move to next question
                            self.is_running = True
                            self.current_index += 1
                            # Add this line to explicitly trigger the next question
                            asyncio.create_task(self.show_question())
                        
                        next_button.callback = next_callback
                        next_view.add_item(next_button)
                    
                    try:
                        await message.edit(embed=embed, view=next_view)
                    except (discord.NotFound, discord.Forbidden):
                        pass
            
        except Exception as e:
            logger.error(f"Error in timer: {e}")
        
    async def process_answer(self, message, chosen_answer, correct_answer, max_score, start_time):
        """Process a user's answer"""
        try:
            # Calculate time taken
            time_taken = time.time() - start_time
            time_ratio = max(0, 1 - (time_taken / self.timer_duration))
            
            # Get the current embed
            embed = message.embeds[0].copy()
            
            # Get the question instance ID from the footer
            footer_text = embed.footer.text
            question_instance_id = footer_text.split(" | Quiz ID: ")[1] if " | Quiz ID: " in footer_text else self.quiz_instance_id
            
            # Create new view with disabled buttons
            new_view = discord.ui.View()
            
            # Add buttons matching the original options but disabled
            for child in self.view.children:
                if isinstance(child, discord.ui.Button) and child.custom_id and child.custom_id.startswith("answer_"):
                    key = child.label
                    button = discord.ui.Button(
                        label=key, 
                        style=discord.ButtonStyle.primary if key != chosen_answer and key != correct_answer else
                            discord.ButtonStyle.success if key == correct_answer else
                            discord.ButtonStyle.danger,
                        disabled=True
                    )
                    new_view.add_item(button)
            
            # Check if the answer is correct
            is_correct = chosen_answer == correct_answer
            
            if is_correct:
                # Award points with time penalty
                points = int(max_score * time_ratio)
                self.score += points
                
                # Add feedback
                embed.add_field(
                    name="Correct! ✅",
                    value=f"You earned {points} points",
                    inline=False
                )
            else:
                # Wrong answer
                embed.add_field(
                    name="Incorrect! ❌",
                    value=f"The correct answer was {correct_answer}",
                    inline=False
                )
                
                # Add explanation if available
                if len(self.questions[self.current_index]) > 6 and self.questions[self.current_index][6]:  # Check if explanation exists
                    embed.add_field(
                        name="Explanation",
                        value=self.questions[self.current_index][6],
                        inline=False
                    )
            
            # Check if this is the last question
            is_last_question = self.current_index == len(self.questions) - 1
            
            if is_last_question:
                # Add End Quiz button for the last question
                end_button = discord.ui.Button(
                    label="End Quiz", 
                    style=discord.ButtonStyle.success,
                    custom_id=f"end_{question_instance_id}"
                )
                
                async def end_callback(interaction):
                    if interaction.user.id != self.user_id:
                        await interaction.response.send_message("This quiz is not for you!", ephemeral=True)
                        return
                    
                    # Verify this is for the current question
                    interaction_id = interaction.data.get('custom_id', '').split('_', 1)[1]
                    if question_instance_id != interaction_id:
                        await interaction.response.send_message(
                            "This button is no longer active.",
                            ephemeral=True
                        )
                        return
                    
                    await interaction.response.defer()
                    # End the quiz
                    await self.end_quiz()
                
                end_button.callback = end_callback
                new_view.add_item(end_button)
                
                # Set timeout to automatically end the quiz after 60 seconds
                embed.add_field(
                    name="Quiz Completion",
                    value="This is the final question. Press 'End Quiz' to see your results. The quiz will automatically end in 60 seconds.",
                    inline=False
                )
                
                # Create a task to automatically end the quiz after timeout
                self._auto_end_task = asyncio.create_task(self.auto_end_quiz(60))
                
            else:
                # Add next button for non-last questions
                next_button = discord.ui.Button(
                    label="Next Question", 
                    style=discord.ButtonStyle.primary,
                    custom_id=f"next_{question_instance_id}"
                )
                
                async def next_callback(interaction):
                    if interaction.user.id != self.user_id:
                        await interaction.response.send_message("This quiz is not for you!", ephemeral=True)
                        return
                    
                    # Verify this is for the current question
                    interaction_id = interaction.data.get('custom_id', '').split('_', 1)[1]
                    if question_instance_id != interaction_id:
                        await interaction.response.send_message(
                            "This button is no longer active.",
                            ephemeral=True
                        )
                        return
                    
                    await interaction.response.defer()
                    # Move to next question
                    self.is_running = True
                    self.current_index += 1
                    # Add this line to explicitly trigger the next question
                    asyncio.create_task(self.show_question())
                
                next_button.callback = next_callback
                new_view.add_item(next_button)
                    
            # Update the message
            try:
                await message.edit(embed=embed, view=new_view)
            except (discord.NotFound, discord.Forbidden):
                # Try sending a new message if edit fails
                await self.user.send("Your previous question couldn't be updated. Here's the result:", embed=embed, view=new_view)
            
        except Exception as e:
            logger.error(f"Error processing answer: {e}")
            try:
                # Send a new message as fallback
                await self.user.send(f"There was an error processing your answer, but we've recorded it. Moving to the next question.")
                self.is_running = True
                self.current_index += 1
            except:
                pass
    
    async def end_quiz(self):
        """End the quiz and show results"""
        try:
            # Set flag to indicate quiz is finished to prevent other processes from interfering
            self.is_running = False
            
            # Check if we've already ended this quiz
            if hasattr(self, '_quiz_ended') and self._quiz_ended:
                logger.info(f"Quiz {self.quiz_instance_id} has already ended, ignoring duplicate end call")
                return
            
            # Mark quiz as ended immediately to prevent race conditions
            self._quiz_ended = True
            logger.info(f"Marked quiz {self.quiz_instance_id} as ended")
            
            # Cancel any pending auto-end timer
            if hasattr(self, '_auto_end_task') and self._auto_end_task:
                self._auto_end_task.cancel()
                self._auto_end_task = None
                logger.info(f"Cancelled auto-end task for quiz {self.quiz_instance_id}")
            
            logger.info(f"Ending quiz {self.quiz_instance_id} for user {self.user_id}")
            
            # First, update the last question message if it exists
            if self.current_message:
                try:
                    # Create a completely new embed instead of copying the old one
                    clean_embed = discord.Embed(
                        title="Quiz Complete",
                        description="Thank you for participating in this quiz! Your results are below.",
                        color=discord.Color.green()
                    )
                    
                    # Update the message with the clean embed and no buttons
                    await self.current_message.edit(embed=clean_embed, view=None)
                    
                    logger.info(f"Updated final question message for user {self.user_id}")
                except Exception as e:
                    logger.error(f"Failed to update last question message: {e}")
            
            # Get quiz details
            quiz_result = await get_quiz_name(self.quiz_id)
            quiz_name = quiz_result[0] if quiz_result else f"Quiz {self.quiz_id}"
            creator_username = quiz_result[2] if quiz_result and len(quiz_result) > 2 and quiz_result[2] else "Unknown"
            
            # Create results embed for DM
            dm_embed = discord.Embed(
                title="Quiz Results",
                description=f"You've completed: {quiz_name}",
                color=discord.Color.gold()
            )
            
            dm_embed.add_field(
                name="Your Score",
                value=f"**{self.score}** points",
                inline=False
            )
            
            total_questions = len(self.questions)
            dm_embed.add_field(
                name="Questions",
                value=f"Completed {total_questions} questions",
                inline=False
            )
            
            # Add creator info
            dm_embed.add_field(
                name="Quiz Creator",
                value=creator_username,
                inline=False
            )
            
            # Add instance ID to track this specific quiz
            dm_embed.set_footer(text=f"Quiz ID: {self.quiz_instance_id}")
            
            # Send DM results
            try:
                await self.user.send(content="Quiz finished!", embed=dm_embed)
            except Exception as e:
                logger.error(f"Failed to send final results DM: {e}")
            
            # Now send results to the server channel
            try:
                channel = self.bot.get_channel(self.channel_id)
                if channel:
                    server_embed = discord.Embed(
                        title="Quiz Completed",
                        description=f"{self.user.mention} has completed: **{quiz_name}**",
                        color=discord.Color.gold()
                    )
                    
                    server_embed.add_field(
                        name="Score",
                        value=f"**{self.score}** points",
                        inline=True
                    )
                    
                    server_embed.add_field(
                        name="Questions",
                        value=f"Completed {total_questions} questions",
                        inline=True
                    )
                    
                    server_embed.add_field(
                        name="Created by",
                        value=creator_username,
                        inline=True
                    )
                    
                    await channel.send(embed=server_embed)
                    logger.info(f"Reported quiz results for {self.user_name} to channel {self.channel_id}")
            except Exception as e:
                logger.error(f"Error reporting quiz results to channel: {e}")
        
            # Record score in database
            try:
                username = self.user_name
                await record_user_score(self.user_id, username, self.quiz_id, self.score)
                logger.info(f"Recorded score for {username}: {self.score} points in quiz {self.quiz_id}")
            except Exception as e:
                logger.error(f"Error recording quiz score: {e}")
                
        except Exception as e:
            logger.error(f"Error ending quiz: {e}")
            # Even if there was an error, we should try to record the score
            try:
                await record_user_score(self.user_id, self.user_name, self.quiz_id, self.score)
                logger.info(f"Recorded score after error for {self.user_name}: {self.score} points in quiz {self.quiz_id}")
            except:
                pass

    async def auto_end_quiz(self, timeout_seconds):
        """Automatically end the quiz after a timeout period if not ended by user"""
        try:
            # Immediately check if the quiz has already been ended manually
            if hasattr(self, '_quiz_ended') and self._quiz_ended:
                logger.info(f"Quiz {self.quiz_instance_id} was already manually ended, skipping auto-end")
                return
                
            # Wait for the specified timeout period
            await asyncio.sleep(timeout_seconds)
            
            # Check again if the quiz has already been ended manually
            if hasattr(self, '_quiz_ended') and self._quiz_ended:
                logger.info(f"Quiz {self.quiz_instance_id} was manually ended during wait period, skipping auto-end")
                return
            
            # Check if we're still on the last question
            if self.current_index == len(self.questions) - 1:
                logger.info(f"Auto-ending quiz for user {self.user_id} after {timeout_seconds} second timeout")
                
                # Force the quiz to end by setting running to false
                self.is_running = False
                
                # Send a message to the user
                try:
                    await self.user.send("The quiz has automatically ended due to inactivity. Here are your results:")
                except:
                    logger.error(f"Failed to send auto-end message to user {self.user_id}")
                    
                # Directly call end_quiz without any further conditions
                await self.end_quiz()
        except asyncio.CancelledError:
            # Task was cancelled, just exit silently
            logger.debug(f"Auto-end task was cancelled for quiz {self.quiz_instance_id}")
            return
        except Exception as e:
            logger.error(f"Error in auto_end_quiz: {e}")
            # Try to force end the quiz even if there was an error
            try:
                self.is_running = False
                await self.end_quiz()
            except Exception as inner_e:
                logger.error(f"Failed to force end quiz after error: {inner_e}")