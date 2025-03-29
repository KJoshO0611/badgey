# Badgey Quiz Bot Documentation

Welcome to the Badgey Quiz Bot documentation. This comprehensive guide will help you understand, deploy, and extend the bot's functionality.

## Table of Contents

### Getting Started
- [Installation and Setup](../README.md#installation)
- [Basic Usage](../README.md#usage)
- [Command Reference](../README.md#usage)

### Architecture
- [Database Structure](database.md)
- [Quiz System Architecture](quiz_system.md)
- [Analytics and Monitoring](monitoring.md)

### Deployment
- [Docker Deployment Guide](docker.md)

### Development
- [Creating Custom Quiz Types](extending.md)
- [Contributing Guidelines](contributing.md)

## Key Features

Badgey Quiz Bot provides a robust platform for creating and managing interactive quizzes on Discord:

- Interactive quiz taking with ephemeral messages
- Timed questions with score degradation
- Leaderboards and user statistics
- Explanations for incorrect answers
- Optimized database with caching and connection pooling
- Comprehensive analytics and health monitoring
- Docker deployment with security and performance optimizations

## System Requirements

- Python 3.8 or higher
- MySQL/MariaDB database
- Discord Bot Token with proper permissions
- Docker (optional, for containerized deployment)

## Quick Start

1. Clone the repository
2. Set up environment variables in `.env`
3. Install dependencies with `pip install -r requirements.txt`
4. Run the bot with `python main.py`

See the [README](../README.md) for more detailed instructions.

## Support and Community

For support, bug reports, or feature requests:

1. Open an issue on GitHub
2. Join our Discord community server
3. Check the existing documentation for solutions

## License

This project is licensed under the MIT License - see the [LICENSE](../LICENSE) file for details. 