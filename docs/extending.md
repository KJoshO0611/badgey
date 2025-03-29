# Extending Badgey Quiz Bot

This guide explains how to extend Badgey Quiz Bot with custom features, particularly how to create new quiz types.

## Overview

Badgey Quiz Bot is designed with extensibility in mind. You can add new quiz types, custom commands, or integrate with external services by following the patterns established in the codebase.

## Creating a Custom Quiz Type

The bot currently supports ephemeral quizzes (visible only to the quiz taker in the channel). You might want to add new quiz types such as:

- Team-based quizzes
- Public quizzes visible to all channel members
- Image-based quizzes
- Voice quizzes with audio clues

### Step 1: Create a New Quiz View Class

Start by creating a new file in the `models` directory. For example, `models/team_quiz.py`:

```python
import discord
from discord.ext import commands
import logging
import asyncio
import time
import json
from collections import deque

from config import CONFIG
from utils.db_utilsv2 import get_quiz_questions, record_user_score, get_quiz_name
from utils.analytics import quiz_analytics

logger = logging.getLogger('badgey.team_quiz')

class TeamQuizView(discord.ui.View):
    """View for team-based quiz challenges"""
    
    def __init__(self, creator_id, interaction, quiz_id, timer, team_name):
        super().__init__(timeout=None)
        self.quiz_id = quiz_id
        self.creator_id = creator_id
        self.team_name = team_name
        self.score = 0
        self.index = 0
        self.interaction = interaction
        self.questions = []
        self.timer_task = timer
        self.lock = asyncio.Lock()
        self.start_time = None
        self.current_timer = None
        self.team_members = set()  # Track team members
        self.team_answers = {}  # Track member answers for each question
        
        # Record quiz start in analytics
        asyncio.create_task(self._record_quiz_start())
    
    async def _record_quiz_start(self):
        """Record quiz start in analytics"""
        try:
            guild_id = self.interaction.guild_id if self.interaction.guild else None
            await quiz_analytics.record_quiz_start(self.creator_id, self.quiz_id, guild_id)
        except Exception as e:
            logger.error(f"Error recording quiz start in analytics: {e}")
    
    # Implement required methods similar to EphemeralQuizView
    # ...
```

### Step 2: Create Quiz Buttons

Create button classes for your new quiz type:

```python
class TeamQuizButton(discord.ui.Button):
    """Button for team quiz answers"""
    
    def __init__(self, key, question_data, quiz_view):
        super().__init__(label=key, style=discord.ButtonStyle.primary)
        self.key = key
        self.question_data = question_data
        self.quiz_view = quiz_view
    
    async def callback(self, interaction: discord.Interaction):
        # Custom logic for team quiz buttons
        # ...
```

### Step 3: Create Commands

Add commands to use your new quiz type by creating a new file in the `cogs` directory or modifying an existing one:

```python
@app_commands.command(name="team_quiz", description="Start a team-based quiz")
@app_commands.describe(
    quiz_id="The ID of the quiz to take",
    team_name="Name for your team",
    timer="Time in seconds for each question"
)
async def team_quiz_command(self, interaction: discord.Interaction, quiz_id: int, team_name: str, timer: int = 30):
    """Command to start a team-based quiz"""
    # Implementation
    # ...
```

### Step 4: Register Your Commands

Update the `setup` function in your cog file to register the new commands:

```python
async def setup(bot):
    await bot.add_cog(TeamQuizCog(bot))
```

## Creating a Custom Question Type

The standard question type is text-based with multiple-choice answers. You might want to create new question types such as:

- Image-based questions
- True/False questions
- Open-ended questions
- Matching questions

### Step 1: Extend the Database Schema

You'll need to modify the database schema in `utils/db_utilsv2.py` to support your new question type:

```python
async def setup_db() -> None:
    """Initialize the database tables"""
    # Existing code...
    
    # Add a new table for image questions
    await execute_query('''
    CREATE TABLE IF NOT EXISTS image_questions (
        question_id INT AUTO_INCREMENT PRIMARY KEY,
        quiz_id INT,
        question_text TEXT,
        image_url VARCHAR(255),
        options TEXT,
        correct_answer VARCHAR(255),
        score INT DEFAULT 10,
        explanation TEXT,
        FOREIGN KEY (quiz_id) REFERENCES quizzes(quiz_id) ON DELETE CASCADE
    )
    ''')
```

### Step 2: Create Database Functions

Add functions to interact with your new question type:

```python
async def add_image_question(quiz_id: int, question_text: str, image_url: str, 
                            options: Union[dict, str], correct_answer: str, 
                            score: int = 10, explanation: str = None) -> bool:
    """
    Add an image-based question to a quiz
    
    Args:
        quiz_id (int): Quiz ID
        question_text (str): Question text
        image_url (str): URL to the question image
        options (Union[dict, str]): Question options as dict or JSON string
        correct_answer (str): Correct option key
        score (int, optional): Maximum points. Defaults to 10.
        explanation (str, optional): Explanation for incorrect answers. Defaults to None.
        
    Returns:
        bool: True if successful, False otherwise
    """
    # Implementation
    # ...
```

### Step 3: Create UI Components

Modify or create new UI components to display your question type:

```python
class ImageQuestionView(discord.ui.View):
    """View for displaying image-based questions"""
    
    def __init__(self, user_id, interaction, quiz_id, timer):
        # Initialize like other quiz views
        # ...
    
    async def show_question(self):
        """Display the current image question"""
        question_data = self.questions[self.index]
        question_text = question_data[2]
        image_url = question_data[3]
        
        # Create embed with image
        embed = discord.Embed(
            title=f"Question {self.index + 1}/{len(self.questions)}", 
            description=question_text, 
            color=discord.Color.blue()
        )
        embed.set_image(url=image_url)
        
        # Add options and buttons
        # ...
```

## Integrating External Services

You might want to integrate with external services such as:

- Image generation APIs for visual quizzes
- Translation services for multilingual quizzes
- Text-to-speech for accessibility

### Example: Integrating with an Image API

```python
import aiohttp

async def get_image_for_question(question_text: str) -> str:
    """
    Generate an image for a question using an external API
    
    Args:
        question_text (str): The question text
        
    Returns:
        str: URL to the generated image
    """
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api.example.com/generate-image",
            json={"prompt": question_text}
        ) as response:
            if response.status == 200:
                data = await response.json()
                return data["image_url"]
            else:
                logger.error(f"Failed to generate image: {await response.text()}")
                return None
```

## Best Practices for Extensions

1. **Follow Existing Patterns**: Study the existing code and follow similar patterns for consistency.

2. **Error Handling**: Always include proper error handling with logging.

3. **Analytics Integration**: Integrate with the analytics system to track usage of your new features.

4. **Documentation**: Document your extensions thoroughly in the code and update the documentation files.

5. **Resource Management**: Ensure proper cleanup of resources, especially with timers and asyncio tasks.

6. **Testing**: Test your extensions thoroughly before deploying to production.

## Extension Ideas

Here are some ideas for extending Badgey Quiz Bot:

1. **Quiz Categories**: Add support for categorizing quizzes by topic.

2. **Quiz Templates**: Create pre-defined templates for common quiz types.

3. **Achievement System**: Implement achievements and badges for quiz participants.

4. **Quiz Challenges**: Create time-limited quiz challenges or tournaments.

5. **Accessibility Features**: Add options for users with different accessibility needs.

6. **Internationalization**: Add support for multiple languages.

7. **Integration with Learning Platforms**: Connect with platforms like Khan Academy or Coursera.

## Contributing Extensions

If you develop a useful extension, consider contributing it back to the main project:

1. Fork the repository
2. Create a feature branch
3. Develop your extension
4. Add tests and documentation
5. Submit a pull request with a clear description of your extension

See the [Contributing Guidelines](contributing.md) for more details. 