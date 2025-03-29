import discord
from discord.ui import View, Button
import json
import asyncio
import logging
import time
from config import CONFIG
from utils.helpers import get_random_quiz_response
from utils.db_utilsv2 import record_user_score, get_quiz_questions, add_quiz, add_question

logger = logging.getLogger('badgey.quiz')

class QuizButton(Button):
    """Button for quiz answers"""
    def __init__(self, key, question_data, quiz_view):
        super().__init__(label=key, style=discord.ButtonStyle.primary)
        self.key = key
        self.question_data = question_data
        self.quiz_view = quiz_view
        self.start_time = time.time()  # Record when the question is first displayed

    async def callback(self, interaction: discord.Interaction):
        async with self.quiz_view.lock:
            user = interaction.user
            question_id = self.question_data[0]
            max_score = self.question_data[5]  # Maximum possible score for the question
            total_time = self.quiz_view.timer_task  # Total time allowed for the question

            # Check if user already answered this question
            if question_id not in self.quiz_view.user_attempts:
                self.quiz_view.user_attempts[question_id] = set()

            if user.id in self.quiz_view.user_attempts[question_id]:
                await interaction.response.send_message(get_random_quiz_response(), ephemeral=True)
                return

            await interaction.response.defer()

            # Mark user as having answered
            self.quiz_view.user_attempts[question_id].add(user.id)

            # Initialize user score if needed
            if user not in self.quiz_view.user_scores:
                self.quiz_view.user_scores[user] = 0

            # Calculate time taken to answer
            time_taken = time.time() - self.start_time

            # Check if answer is correct and award points
            if self.key == self.question_data[4]:
                # Linear scaling: score decreases as time increases
                time_penalty_ratio = max(0, 1 - (time_taken / total_time))
                scored_points = int(max_score * time_penalty_ratio)
                
                self.quiz_view.user_scores[user] += scored_points

                ##logger.debug(f"User {user.name} answered correctly, awarded {self.question_data[5]} points. Time penalty: {time_penalty_ratio}")

class QuizView(View):
    """View for displaying quiz questions and handling responses"""
    def __init__(self, message, quiz_id, timer):
        super().__init__()
        self.quiz_id = quiz_id
        self.user_scores = {}  # Tracks scores
        self.user_attempts = {}  # Tracks who answered each question
        self.index = 0
        self.message = message  # Store message instead of interaction
        self.questions = []
        self.timer_task = timer
        self.lock = asyncio.Lock()  # Add a lock for synchronization

    def disable_buttons(self):
        """Disables all buttons to prevent further interactions"""
        for child in self.children:
            if isinstance(child, Button):
                child.disabled = True
    
    async def end_quiz(self):
        """Ends the quiz and displays results"""
        # Sort users by score in descending order
        sorted_scores = sorted(self.user_scores.items(), key=lambda x: x[1], reverse=True)
        
        # Create results text
        results = "\n".join([f"{user.mention}: {score}" for user, score in sorted_scores])
        
        # Create results embed
        embed = discord.Embed(
            title="Quiz Results",
            description="Here are the final scores:",
            color=discord.Color.gold()
        )
        
        # Add fields for top 3 or fewer if less than 3 participants
        for i, (user, score) in enumerate(sorted_scores[:5], 1):
            embed.add_field(
                name=f"{i}. {user.display_name} | {score} points",
                value="",
                inline=False
            )
        
        # Send results - use message.edit instead of interaction
        await self.message.edit(content="Quiz finished!", embed=embed, view=None)
        
        # Record scores in database
        for user, score in self.user_scores.items():
            await record_user_score(user.id, user.name,self.quiz_id, score)
            #logger.info(f"Recorded score for user {user.name}: {score} points in quiz {self.quiz_id}. Penalty:")

    async def initialize(self, message, quiz_id):
        """Initialize the quiz by loading questions"""
        ##logger.debug(f"Initializing quiz {quiz_id}")
        
        self.questions = await get_quiz_questions(quiz_id)
        if not self.questions:
            #logger.error(f"No questions found for quiz {quiz_id}")
            return False
        
        self.quiz_id = quiz_id
        self.user_scores = {}
        self.index = 0
        self.message = message
        
        #logger.info(f"Quiz {quiz_id} initialized with {len(self.questions)} questions")
        return True

    async def show_question(self):
        """Display the current question to users"""
        if not self.questions:
            ###logger.error("No questions available to display")
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
            self.add_item(QuizButton(key, question_data, self))

        # Show the question - use message.edit instead of interaction
        await self.message.edit(content=None, embed=embed, view=self)
        
        # Timer countdown (10 seconds per question)
        time_left = self.timer_task
        while time_left > 0:
            # Update only every 3 seconds or when time is low
            if time_left % 3 == 0 or time_left <= 5:
                embed.set_footer(text=f"Time left: {time_left} seconds ⏳")
                await self.message.edit(embed=embed)
            await asyncio.sleep(1)
            time_left -= 1
        
        # Disable buttons after time is up
        if self.children:
            self.disable_buttons()
            await self.message.edit(view=self)
        
        # Move to next question
        self.index += 1
        await self.show_question()

class QuizCreationView(View):
    """View for creating a new quiz"""
    def __init__(self, interaction: discord.Interaction):
        super().__init__()
        self.interaction = interaction
        self.questions = []
        self.quiz_name = ""
        self.quiz_id = None

    @discord.ui.button(label="Start Quiz Creation", style=discord.ButtonStyle.success)
    async def start_quiz(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Enter the name of the quiz:", ephemeral=True)
        
        try:
            quiz_name_msg = await interaction.client.wait_for(
                "message", 
                check=lambda m: m.author == interaction.user,
                timeout=60.0
            )
            
            quiz_id = await add_quiz(quiz_name_msg.content, interaction.user.id)
            
            await interaction.followup.send(
                f"Quiz '{quiz_name_msg.content}' created! Now add questions.", 
                ephemeral=True
            )
            
            self.quiz_id = quiz_id
            self.quiz_name = quiz_name_msg.content
            logger.info(f"Quiz '{self.quiz_name}' created with ID {self.quiz_id}")
            
        except asyncio.TimeoutError:
            await interaction.followup.send("Quiz creation timed out. Please try again.", ephemeral=True)

    @discord.ui.button(label="Add Question", style=discord.ButtonStyle.primary)
    async def add_question(self, interaction: discord.Interaction, button: Button):
        if not self.quiz_id:
            await interaction.response.send_message("Please start quiz creation first.", ephemeral=True)
            return
            
        await interaction.response.send_message("Enter the question text:", ephemeral=True)
        
        try:
            # Get question text
            question_text = await interaction.client.wait_for(
                "message", 
                check=lambda m: m.author == interaction.user,
                timeout=120.0
            )
            
            # Get options
            await interaction.followup.send("Enter options (e.g. A:Option 1 B:Option 2):", ephemeral=True)
            options_message = await interaction.client.wait_for(
                "message", 
                check=lambda m: m.author == interaction.user,
                timeout=120.0
            )
            
            from utils.helpers import parse_options
            try:
                options = parse_options(options_message.content)
            except ValueError:
                await interaction.followup.send("Invalid format. Please enter options as 'A:Option 1 B:Option 2'.", ephemeral=True)
                return
            
            # Get correct answer
            await interaction.followup.send("Enter the correct answer (A, B, C, etc.):", ephemeral=True)
            correct_answer = await interaction.client.wait_for(
                "message", 
                check=lambda m: m.author == interaction.user,
                timeout=60.0
            )
            
            # Get score value
            await interaction.followup.send("Enter the score for this question:", ephemeral=True)
            score = await interaction.client.wait_for(
                "message", 
                check=lambda m: m.author == interaction.user,
                timeout=60.0
            )
            
            try:
                score_value = int(score.content)
            except ValueError:
                await interaction.followup.send("Score must be a number. Using default value of 10.", ephemeral=True)
                score_value = 10
            
            # Get explanation
            await interaction.followup.send("Enter an explanation for the correct answer (optional):", ephemeral=True)
            try:
                explanation = await interaction.client.wait_for(
                    "message", 
                    check=lambda m: m.author == interaction.user,
                    timeout=60.0
                )
                explanation_text = explanation.content
            except asyncio.TimeoutError:
                explanation_text = None
            
            # Add question to database
            await add_question(
                self.quiz_id, 
                question_text.content, 
                options, 
                correct_answer.content, 
                score_value,
                explanation_text
            )
            
            await interaction.followup.send(
                "Question added successfully! Add more or finish.", 
                ephemeral=True
            )
            
            #logger.info(f"Question added to quiz {self.quiz_id}")
            
        except asyncio.TimeoutError:
            await interaction.followup.send("Question creation timed out. You can try again.", ephemeral=True)