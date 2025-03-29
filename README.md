# Badgey Quiz Bot

A feature-rich Discord bot for creating and managing interactive quizzes.

## Features

- **Quiz Management**
  - Create, edit, and delete quizzes
  - Add questions with options, correct answers, and explanations
  - Edit existing questions

- **Quiz Taking**
  - Take quizzes through ephemeral messages (visible only to you)
  - Timed questions with point degradation
  - Instant feedback on answers
  - Explanations for incorrect answers
  - Leaderboards for competitive quiz taking

- **Scheduled Quizzes**
  - Set up quizzes to run at specific times
  - Automated announcements and participation tracking

- **Performance and Reliability**
  - Connection pooling for database efficiency
  - Timed caching for frequently accessed data
  - Comprehensive error handling and retry logic
  - Resource management for optimal performance

- **Monitoring and Analytics**
  - Health check endpoints for monitoring
  - Usage analytics and statistics
  - Performance tracking

## Installation

### Prerequisites

- Python 3.8 or higher
- MySQL/MariaDB database
- Discord Bot Token

### Setup

1. **Clone the repository**

```bash
git clone https://github.com/yourusername/badgey-quiz-bot.git
cd badgey-quiz-bot
```

2. **Install dependencies**

```bash
pip install -r requirements.txt
```

3. **Create environment file**

Create a `.env` file in the root directory with the following variables:

```
TOKEN=your_discord_bot_token
GUILDID=your_guild_id_1,your_guild_id_2
PREFIX=-
DBHOST=localhost
DBPORT=3306
DBUSER=database_user
DBPASSWORD=database_password
DBNAME=badgey
```

4. **Initialize the database**

The bot will automatically set up the database tables on first run.

5. **Running the bot**

```bash
python main.py
```

### Docker Setup

1. **Build the Docker image**

```bash
docker build -t badgey-bot .
```

2. **Run the Docker container**

```bash
docker run -d --name badgey -p 8080:8080 --env-file .env badgey-bot
```

## Usage

### Bot Commands

| Command | Description | Required Role |
|---------|-------------|--------------|
| `/create_quiz` | Create a new quiz | Admin, Quiz Creators, Community Managers |
| `/add_question` | Add a question to a quiz | Admin, Quiz Creators, Community Managers |
| `/edit_question` | Edit an existing question | Admin, Quiz Editors, Community Managers |
| `/delete_quiz` | Delete a quiz | Admin, Community Managers |
| `/take_quiz` | Take a quiz | Everyone |
| `/list_quizzes` | List available quizzes | Everyone |
| `/leaderboard` | View quiz leaderboards | Everyone |
| `/schedule_quiz` | Schedule a quiz for later | Admin, Event Managers, Community Managers |
| `/sync` | Sync commands with Discord | Admin |

### Creating a Quiz

1. Use `/create_quiz name:My Quiz` to create a new quiz
2. Use `/add_question quiz_id:1 question:What is 2+2? options:{"A":"1", "B":"2", "C":"3", "D":"4"} correct_answer:D score:10 explanation:Basic addition` to add questions

### Taking a Quiz

1. Use `/take_quiz quiz_id:1` to start a quiz
2. Answer the questions within the time limit
3. View your results at the end

## Architecture

### Components

- **Main Bot** (`main.py`): Entry point and command handling
- **Database Utilities** (`utils/db_utilsv2.py`): Database operations with caching
- **Quiz Views** (`models/solo_quiz_ephemeral.py`, etc.): UI for quiz interaction
- **Analytics** (`utils/analytics.py`): Usage tracking and statistics
- **Health Monitoring** (`utils/health_check.py`): Health endpoints for monitoring

### Database Schema

- **quizzes**: Stores quiz metadata
- **questions**: Stores quiz questions with options and answers
- **user_scores**: Tracks user performance on quizzes

## Configuration

The bot uses a configuration system defined in `config.py`. Configuration is loaded from environment variables and can be reloaded at runtime.

### Required Environment Variables

- `TOKEN`: Discord bot token
- `GUILDID`: Comma-separated list of guild IDs
- `DBHOST`: Database host
- `DBPORT`: Database port
- `DBUSER`: Database username
- `DBPASSWORD`: Database password
- `DBNAME`: Database name

### Optional Environment Variables

- `PREFIX`: Command prefix for text commands (default: `-`)

## Permissions

The permission system is managed in `utils/permissions.py`. You can customize role requirements for different commands by editing the `COMMAND_PERMISSIONS` dictionary.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.