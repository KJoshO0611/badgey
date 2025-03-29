# Analytics and Monitoring

This document describes the analytics and health monitoring systems used by Badgey Quiz Bot.

## Analytics System

The bot includes a comprehensive analytics system that tracks usage, performance, and error metrics. This enables data-driven decisions for improving the bot and understanding user behavior.

### Core Components

The analytics system is implemented in `utils/analytics.py` through the `QuizAnalytics` class:

```python
class QuizAnalytics:
    """
    Analytics system for tracking quiz usage and performance
    """
    def __init__(self):
        # General metrics
        self.quizzes_started = 0
        self.quizzes_completed = 0
        self.questions_answered = 0
        self.correct_answers = 0
        
        # Performance metrics
        self.quiz_durations: List[float] = []
        self.question_durations: List[float] = []
        self.quiz_scores: List[int] = []
        
        # Usage metrics
        self.popular_quizzes = defaultdict(int)
        self.user_participation = defaultdict(int)
        self.guild_usage = defaultdict(int)
        self.hourly_usage = defaultdict(int)
        self.daily_usage = defaultdict(int)
        
        # Performance tracking
        self.db_query_times: List[float] = []
        self.command_response_times: Dict[str, List[float]] = defaultdict(list)
        
        # Error tracking
        self.errors = defaultdict(int)
        self.last_errors: List[Dict[str, Any]] = []
        
        # Lock for thread safety
        self.lock = asyncio.Lock()
```

### Tracked Metrics

The analytics system tracks multiple categories of metrics:

#### Usage Metrics

- **Quiz Participation**: Tracks how many quizzes are started and completed
- **User Engagement**: Records which users are taking quizzes and how often
- **Quiz Popularity**: Identifies which quizzes are most frequently taken
- **Temporal Patterns**: Tracks usage by hour of day and day of week
- **Guild Activity**: Measures quiz usage across different Discord servers

#### Performance Metrics

- **Quiz Durations**: How long users spend on quizzes
- **Question Response Times**: How quickly users answer questions
- **Database Performance**: Tracks database query execution times
- **Command Response Times**: Measures how long commands take to execute

#### Error Metrics

- **Error Counts**: Tracks frequency of different error types
- **Recent Errors**: Stores detailed information about recent errors for troubleshooting

### Integration Points

Analytics collection is integrated throughout the codebase:

```python
# Example in solo_quiz_ephemeral.py
async def _record_quiz_start(self):
    """Record quiz start in analytics"""
    try:
        guild_id = self.interaction.guild_id if self.interaction.guild else None
        await quiz_analytics.record_quiz_start(self.user_id, self.quiz_id, guild_id)
    except Exception as e:
        logger.error(f"Error recording quiz start in analytics: {e}")
```

### Thread Safety

All analytics operations use asyncio locks to ensure thread safety:

```python
async def record_quiz_start(self, user_id: int, quiz_id: int, guild_id: Optional[int] = None):
    """Record the start of a quiz"""
    async with self.lock:
        self.quizzes_started += 1
        self.popular_quizzes[quiz_id] += 1
        self.user_participation[user_id] += 1
        # ...
```

### Memory Management

To prevent unbounded memory growth, the analytics system limits the number of entries it keeps for time series data:

```python
# Limit stored durations to avoid memory issues
if len(self.quiz_durations) > 1000:
    self.quiz_durations = self.quiz_durations[-1000:]
```

### Data Export

Analytics data can be exported to JSON format for external analysis:

```python
def export_to_json(self) -> str:
    """
    Export analytics data to JSON string
    
    Returns:
        str: JSON string of analytics data
    """
    return json.dumps(self.get_statistics(), indent=2)
```

### Usage Example

To retrieve analytics data:

```python
from utils.analytics import quiz_analytics

# Get statistics dictionary
stats = quiz_analytics.get_statistics()

# Access specific metrics
completion_rate = stats["completion_rate"]
top_quizzes = stats["top_quizzes"]
```

## Health Monitoring System

The health monitoring system provides real-time information about the bot's operational status. This is especially valuable in containerized environments like Docker.

### HTTP Health Server

The health monitoring system implements a lightweight HTTP server that responds to health check requests. It's implemented in `utils/health_check.py`:

```python
class HealthCheckHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler for health check requests"""
    
    def do_GET(self):
        """Handle GET requests"""
        if self.path == '/health':
            # Get health data
            health_data = self.get_health_data()
            
            # Return appropriate status code based on health
            status_code = 200 if health_data['ready'] else 503
            response = json.dumps(health_data, indent=2)
            
            self._send_response(status_code, 'application/json', response)
        else:
            # Return 404 for other paths
            self._send_response(404, 'text/plain', 'Not Found')
```

### Health Metrics

The health check endpoint reports various system metrics:

- **Status**: Overall health state ('healthy' or 'starting')
- **Uptime**: How long the bot has been running
- **Memory Usage**: Current memory consumption
- **CPU Usage**: Current CPU utilization
- **Thread Count**: Number of active threads
- **Ready State**: Whether the bot is fully initialized and ready

### Docker Integration

The health check system is designed to work with Docker's health check feature:

```dockerfile
# Add healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1
```

This allows Docker to automatically restart the container if the bot becomes unhealthy.

### Bot Readiness

The health check system tracks whether the bot is fully initialized:

```python
def set_bot_ready(ready: bool = True):
    """Set the bot ready status"""
    global bot_ready
    bot_ready = ready
    logger.info(f"Bot ready status set to: {ready}")
```

This is called in the bot's `on_ready` event:

```python
async def on_ready(self):
    logger.info(f'Logged in as {self.user} (ID: {self.user.id})')
    await self.change_presence(
        status=discord.Status.online,
        activity=discord.Game(name="Monitoring Comms!")
    )
    # Mark bot as ready in health check
    set_bot_ready(True)
```

### Using the Health Endpoint

The health endpoint can be accessed with any HTTP client:

```bash
curl http://localhost:8080/health
```

Example response:

```json
{
  "status": "healthy",
  "uptime": "2d 3h 45m 12s",
  "uptime_seconds": 183912,
  "memory_usage_mb": 78.4,
  "cpu_percent": 2.3,
  "thread_count": 8,
  "ready": true
}
```

### External Monitoring

The health endpoint is designed to be compatible with external monitoring tools:

- **Prometheus**: Can scrape the endpoint for metrics
- **Kubernetes**: Can use the endpoint for readiness/liveness probes
- **Docker Swarm**: Can use the health check for service health

## Best Practices

### Analytics

1. **Privacy**: Ensure that all collected data is anonymized and doesn't contain personal information
2. **Performance**: Keep analytics operations lightweight to minimize impact on core functionality
3. **Resilience**: Use try-except blocks when recording analytics to prevent failures from affecting the main application
4. **Data Size**: Limit the amount of data stored in memory and consider periodic exports for long-term storage

### Health Monitoring

1. **Accuracy**: Ensure health checks accurately reflect the actual state of the application
2. **Response Time**: Keep health check responses fast (under 100ms if possible)
3. **Security**: Consider adding basic authentication for production deployments
4. **Resource Usage**: Monitor the health check server's own resource usage to ensure it doesn't impact the main application 