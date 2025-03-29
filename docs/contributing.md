# Contributing to Badgey Quiz Bot

Thank you for your interest in contributing to Badgey Quiz Bot! This document provides guidelines and instructions for contributing to the project.

## Code of Conduct

By participating in this project, you agree to uphold our Code of Conduct:

- Be respectful and inclusive
- Use welcoming and inclusive language
- Be collaborative and constructive
- Focus on what is best for the community
- Show empathy towards other community members

## How to Contribute

There are many ways to contribute to Badgey Quiz Bot:

1. **Report Bugs**: Create issues for bugs you encounter
2. **Suggest Features**: Propose new features or improvements
3. **Improve Documentation**: Help improve or translate documentation
4. **Write Code**: Implement features or fix bugs
5. **Review Pull Requests**: Help review and test other contributions

## Development Workflow

### Setup Development Environment

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/your-username/badgey-quiz-bot.git
   cd badgey-quiz-bot
   ```
3. Set up a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
5. Set up the database as described in the [README](../README.md)
6. Create a `.env` file with your Discord development bot token

### Making Changes

1. Create a new branch for your feature or bugfix:
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-bugfix-name
   ```
2. Make your changes following the style and quality guidelines
3. Add or update tests as needed
4. Update documentation to reflect your changes
5. Commit your changes with clear, descriptive commit messages:
   ```bash
   git commit -m "Add feature: description of the change"
   ```

### Testing Your Changes

1. Run any existing tests:
   ```bash
   # If there's a test command, add it here
   ```
2. Test the bot manually by running:
   ```bash
   python main.py
   ```
3. Verify that your changes work as expected and don't break existing functionality

### Submitting a Pull Request

1. Push your changes to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```
2. Create a pull request from your fork to the main repository
3. In your pull request description:
   - Clearly describe the problem and solution
   - Include any relevant issue numbers
   - List any dependencies or breaking changes
4. Wait for the maintainers to review your PR
5. Address any feedback and make requested changes

## Coding Guidelines

### Code Style

- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) for Python code
- Use meaningful variable, function, and class names
- Include docstrings for all functions, classes, and modules
- Keep functions focused on a single responsibility
- Limit line length to 100 characters

### Documentation

- Add detailed docstrings to all public functions and classes
- Document parameters, return values, and exceptions
- Include usage examples for complex functionality
- Update relevant documentation files when adding new features

### Error Handling

- Use appropriate exception handling
- Log errors with context information
- Don't silently catch exceptions without proper handling
- Use custom exceptions where appropriate

### Testing

- Write tests for new functionality
- Ensure tests cover edge cases
- Make sure all tests pass before submitting a PR

## Commit Guidelines

- Write clear, descriptive commit messages
- Use the present tense ("Add feature" not "Added feature")
- Reference issue numbers when applicable
- Keep commits focused on a single change
- Make frequent, smaller commits rather than large ones

### Commit Message Format

```
<type>: <subject>

[optional body]

[optional footer(s)]
```

Types:
- feat: A new feature
- fix: A bug fix
- docs: Documentation only changes
- style: Changes that do not affect the meaning of the code
- refactor: A code change that neither fixes a bug nor adds a feature
- perf: A code change that improves performance
- test: Adding missing tests or correcting existing tests
- chore: Changes to the build process or auxiliary tools

Example:
```
feat: Add team quiz functionality

Implement team-based quiz challenges where multiple users can participate as a team.
Teams get points collectively and see a shared leaderboard.

Closes #123
```

## Pull Request Review Process

1. A maintainer will review your PR
2. They may request changes or clarification
3. Once approved, a maintainer will merge the PR
4. Your contribution will be part of the next release

## Project Structure

Understanding the project structure will help you make meaningful contributions:

```
badgey-quiz-bot/
├── cogs/                 # Discord command modules
├── models/               # UI and data models
├── utils/                # Utility functions and helpers
│   ├── db_utilsv2.py     # Database operations
│   ├── permissions.py    # Permission handling
│   ├── analytics.py      # Usage analytics
│   └── health_check.py   # Health monitoring
├── docs/                 # Documentation
├── main.py               # Application entry point
├── config.py             # Configuration handling
├── requirements.txt      # Python dependencies
└── dockerfile            # Docker configuration
```

## Feature Requests and Bug Reports

### Feature Requests

When proposing a new feature:

1. Check if the feature already exists or has been requested
2. Clearly describe the feature and its benefits
3. Provide examples of how the feature would be used
4. Consider how the feature fits into the existing architecture

### Bug Reports

When reporting a bug:

1. Check if the bug has already been reported
2. Provide a clear description of the bug
3. Include steps to reproduce the bug
4. Describe the expected behavior
5. Include logs, screenshots, or other relevant information
6. Mention your environment (OS, Python version, etc.)

## Release Process

The project follows semantic versioning (MAJOR.MINOR.PATCH):

- MAJOR: Incompatible API changes
- MINOR: Backwards-compatible functionality
- PATCH: Backwards-compatible bug fixes

The maintainers will handle versioning and releases.

## Community

Join our Discord community to discuss development, get help, or share ideas:

[Discord Invitation Link]

## Attribution

Contributors will be acknowledged in the project's documentation and release notes.

## License

By contributing to this project, you agree that your contributions will be licensed under the project's [MIT License](../LICENSE). 