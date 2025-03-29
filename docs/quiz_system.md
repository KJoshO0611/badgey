# Quiz System Architecture

This document details the architecture and implementation of the Badgey Quiz Bot's quiz system.

## Overview

The quiz system is built around several key components:

1. **Quiz Models**: Different view classes that handle quiz presentation and interaction
2. **Quiz Queue**: System for managing concurrent quiz sessions
3. **Database Layer**: Backend storage for quizzes, questions, and scores
4. **Command Interface**: Slash commands for interacting with the quiz system

## Quiz Models

### EphemeralQuizView

Located in `models/solo_quiz_ephemeral.py`, this is the primary quiz interface that uses ephemeral messages (visible only to the player).

Key features:
- Questions are presented one at a time
- Includes timer with visual countdown
- Automatically advances to the next question after answer
- Displays correct/incorrect feedback immediately
- Shows explanations for incorrect answers
- Final results are shared publicly in the channel

The view uses Discord UI components (buttons) for interactive answering.

```python
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
        ...
```

### EphemeralQuizButton

Companion class to `EphemeralQuizView` that handles button interactions for answering questions.

```python
class EphemeralQuizButton(discord.ui.Button):
    """Button for ephemeral quiz answers with error handling"""
    def __init__(self, key, question_data, quiz_view):
        super().__init__(label=key, style=discord.ButtonStyle.primary)
        self.key = key
        self.question_data = question_data
        self.quiz_view = quiz_view
        
    async def callback(self, interaction: discord.Interaction):
        # Handle user answer
        ...
```

### Quiz Flow

1. **Initialization**:
   - User triggers quiz with `/take_quiz` command
   - Quiz is added to queue
   - Questions are loaded from the database

2. **Question Display**:
   - Question text and options are shown as an embed
   - Timer starts counting down
   - User selects an answer by clicking a button

3. **Answer Processing**:
   - Button colors change to indicate correct (green) and incorrect (red) answers
   - Score is updated based on correctness and time taken
   - For incorrect answers, an explanation is shown if available
   - "Next Question" button appears

4. **Quiz Completion**:
   - After final question, "End Quiz" button appears
   - When quiz ends (manually or automatically), results are shown
   - Score is recorded in the database
   - Public results are posted in the channel

## Quiz Queue System

To manage concurrent quiz sessions efficiently, a queue system is implemented:

```python
class QuizQueue:
    """Manages quiz requests and enforces rate limiting"""
    def __init__(self, max_concurrent=5, cooldown_seconds=30):
        self.active_quizzes = {}  # user_id -> quiz_instance
        self.queue = deque()  # Queue of pending quiz requests
        self.max_concurrent = max_concurrent
        self.cooldown_seconds = cooldown_seconds
        self.user_cooldowns = {}  # user_id -> timestamp when cooldown expires
        self.lock = asyncio.Lock()
    ...
```

Key features:
- Limits the number of concurrent quizzes (default: 5)
- Enforces cooldown between quiz attempts (default: 30 seconds)
- Prevents users from starting multiple quizzes simultaneously
- Queues excess requests for processing when slots become available

## Timeouts and Auto-Ending

The quiz system includes robust timeout handling:

1. **Question Timeouts**:
   - Each question has a timer (default varies by quiz)
   - If the timer expires without an answer, the question is marked incorrect
   - The quiz advances to the next question automatically

2. **Quiz Auto-Ending**:
   - After the last question, a 2-minute auto-end timer starts
   - If the user doesn't click "End Quiz", the quiz completes automatically
   - Cancellation mechanism ensures no duplicate endings

```python
async def auto_end_quiz(self, timeout_seconds=60):
    """Automatically end the quiz after a specified timeout if user doesn't end it manually"""
    try:
        await asyncio.sleep(timeout_seconds)
        
        # Check if quiz has already ended
        if self.user_id not in quiz_queue.active_quizzes or self._is_ended:
            return
        
        logger.info(f"Auto-ending quiz for user {self.user_id} after {timeout_seconds} seconds of inactivity")
        
        # End the quiz
        await self.end_quiz()
    except asyncio.CancelledError:
        # Task was cancelled normally (user ended quiz manually)
        logger.debug(f"Auto-end timer cancelled for user {self.user_id}")
        pass
    ...
```

## Error Handling and Resilience

The quiz system incorporates extensive error handling:

1. **Connection Issues**:
   - Retry logic for database operations
   - Message interaction failures are caught and handled gracefully

2. **Resource Management**:
   - Proper timer cancellation prevents memory leaks
   - Resource cleanup on quiz completion

3. **Recovery Mechanisms**:
   - Recovery from Discord API failures
   - Fallback options when messages can't be updated

```python
# Example of retry logic:
retries = 0
while retries < self.max_retries:
    try:
        # Operation
        break
    except Exception as e:
        retries += 1
        logger.warning(f"Error in operation (attempt {retries}/{self.max_retries}): {e}")
        await asyncio.sleep(2 ** retries)  # Exponential backoff
```

## Analytics Integration

The quiz system integrates with the analytics module to track:

- Quiz starts and completions
- Question answer times and correctness
- Score distributions
- User participation patterns

```python
async def _record_quiz_start(self):
    """Record quiz start in analytics"""
    try:
        guild_id = self.interaction.guild_id if self.interaction.guild else None
        await quiz_analytics.record_quiz_start(self.user_id, self.quiz_id, guild_id)
    except Exception as e:
        logger.error(f"Error recording quiz start in analytics: {e}")
```

## Performance Optimization

Several optimizations are implemented to ensure good performance:

1. **Efficient Resource Use**:
   - Message updates are batched to reduce API calls
   - Timer updates occur at strategic intervals (every 3 seconds)

2. **Lock Management**:
   - Asyncio locks prevent race conditions
   - Fine-grained locking minimizes contention

3. **Memory Management**:
   - Proper cleanup of resources
   - Cancellation of pending tasks when no longer needed

## Design Patterns

The quiz system employs several design patterns:

1. **Model-View-Controller (MVC)**:
   - Models: Database entities (quizzes, questions)
   - Views: Quiz display classes (EphemeralQuizView)
   - Controllers: Commands and callback handlers

2. **Factory Method**:
   - QuizQueue acts as a factory for creating quiz instances

3. **Observer Pattern**:
   - Quiz system observes user interactions and timer events

4. **Command Pattern**:
   - Button callbacks encapsulate actions as objects

## Extension Points

The quiz system is designed for extensibility:

1. **New Quiz Modes**:
   - Create new quiz view classes following similar patterns
   - Reuse common components like question loading and scoring

2. **Custom Question Types**:
   - The system can be extended to support different question formats
   - Additional UI components can be added for new interaction types

3. **Integration Points**:
   - Analytics hooks throughout the quiz flow
   - Standardized result formatting for different display contexts 