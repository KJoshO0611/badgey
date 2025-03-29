# Database Documentation

This document outlines the database structure and utility functions used by Badgey Quiz Bot.

## Database Schema

### Tables

#### `quizzes` Table

Stores metadata about each quiz.

| Column | Type | Description |
|--------|------|-------------|
| quiz_id | INT AUTO_INCREMENT | Primary key |
| quiz_name | VARCHAR(255) | Name of the quiz |
| creator_id | VARCHAR(255) | Discord ID of the quiz creator |
| created_at | TIMESTAMP | When the quiz was created |

#### `questions` Table

Stores individual questions for quizzes.

| Column | Type | Description |
|--------|------|-------------|
| question_id | INT AUTO_INCREMENT | Primary key |
| quiz_id | INT | Foreign key to quizzes table |
| question_text | TEXT | The question text |
| options | TEXT | JSON string containing options (e.g., {"A": "Option 1", "B": "Option 2"}) |
| correct_answer | VARCHAR(255) | The correct option key (e.g., "A") |
| score | INT | Maximum points for this question |
| explanation | TEXT | Explanation shown when answered incorrectly (optional) |

#### `user_scores` Table

Tracks user scores for each quiz attempt.

| Column | Type | Description |
|--------|------|-------------|
| score_id | INT AUTO_INCREMENT | Primary key |
| user_id | VARCHAR(255) | Discord ID of the user |
| username | VARCHAR(255) | Discord username at time of quiz |
| quiz_id | INT | Foreign key to quizzes table |
| score | INT | Points earned in the quiz |
| timestamp | TIMESTAMP | When the quiz was taken |

## Connection Pooling

The database system utilizes connection pooling to efficiently manage database connections:

```python
async def initialize_pool() -> None:
    """
    Initialize the database connection pool
    """
    global pool
    try:
        pool = await aiomysql.create_pool(
            host=CONFIG['DB']['HOST'],
            port=CONFIG['DB']['PORT'],
            user=CONFIG['DB']['USER'],
            password=CONFIG['DB']['PASSWORD'],
            db=CONFIG['DB']['DATABASE'],
            autocommit=True,
            minsize=1,
            maxsize=10,
            echo=False
        )
        logger.info("Database connection pool initialized")
    except Exception as e:
        logger.critical(f"Failed to initialize database pool: {e}")
        raise DatabaseConnectionError(f"Failed to initialize database pool: {e}")
```

Benefits of connection pooling:
- Reduced connection overhead
- Better resource utilization
- Improved performance under concurrent load

## Timed Caching

Frequently accessed data is cached using a timed caching decorator to reduce database load:

```python
def timed_cache(seconds=300):
    """
    Decorator that caches the result of a function for a specified time period
    
    Args:
        seconds (int): Number of seconds to cache the result for
    """
    def decorator(func):
        cache = {}
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Create a cache key from the function args and kwargs
            key = str(args) + str(kwargs)
            
            # Check if the result is in the cache and not expired
            if key in cache and cache[key]['expires'] > time.time():
                logger.debug(f"Cache hit for {func.__name__}{args}")
                return cache[key]['result']
            
            # Call the function and cache the result
            result = await func(*args, **kwargs)
            cache[key] = {
                'result': result,
                'expires': time.time() + seconds
            }
            logger.debug(f"Cache miss for {func.__name__}{args}, caching result for {seconds}s")
            return result
        
        return wrapper
    return decorator
```

Functions that use caching:
- `get_quiz_name`: Cached for 60 seconds
- `get_quiz_questions`: Cached for 300 seconds (5 minutes)
- `get_all_quizzes`: Cached for 300 seconds (5 minutes)

## Error Handling and Retries

All database operations include retry logic to handle temporary connection issues:

```python
async def execute_query(query: str, params: Tuple = None, retries: int = MAX_RETRIES) -> None:
    """
    Execute a database query with retry logic
    
    Args:
        query (str): SQL query to execute
        params (Tuple, optional): Query parameters. Defaults to None.
        retries (int, optional): Number of retry attempts. Defaults to MAX_RETRIES.
    
    Raises:
        DatabaseQueryError: If the query fails after all retries
    """
    conn = None
    try:
        conn = await get_db_connection()
        async with conn.cursor() as cursor:
            await cursor.execute(query, params)
        return
    except Exception as e:
        if retries > 0:
            logger.warning(f"Database query failed, retrying ({retries} attempts left): {e}")
            await asyncio.sleep(0.5)  # Short delay before retry
            return await execute_query(query, params, retries - 1)
        else:
            logger.error(f"Database query failed after all retries: {e}")
            raise DatabaseQueryError(f"Database query failed: {e}")
    finally:
        if conn:
            await release_connection(conn)
```

## Transaction Support

For operations that require multiple queries to be executed atomically:

```python
async def execute_transaction(queries: List[Tuple[str, Tuple]]) -> bool:
    """
    Execute multiple queries as a single transaction
    
    Args:
        queries (List[Tuple[str, Tuple]]): List of (query, params) tuples
    
    Returns:
        bool: True if transaction was successful, False otherwise
    """
    conn = None
    try:
        conn = await get_db_connection()
        # Disable autocommit to start transaction
        await conn.begin()
        async with conn.cursor() as cursor:
            for query, params in queries:
                await cursor.execute(query, params)
        await conn.commit()
        return True
    except Exception as e:
        logger.error(f"Transaction failed: {e}")
        if conn:
            await conn.rollback()
        return False
    finally:
        if conn:
            await release_connection(conn)
```

## Key Database Functions

### Quiz Management

- `add_quiz(quiz_name, creator_id)`: Create a new quiz
- `update_quiz_name(quiz_id, new_name)`: Rename a quiz
- `delete_quiz(quiz_id)`: Delete a quiz and its questions

### Question Management

- `add_question(quiz_id, question_text, options, correct_answer, score, explanation)`: Add a question to a quiz
- `edit_question(question_id, question_text, options, correct_answer, score)`: Edit an existing question
- `get_quiz_questions(quiz_id)`: Get all questions for a quiz

### Score Tracking

- `record_user_score(user_id, username, quiz_id, score)`: Record a user's score after completing a quiz
- `get_quiz_scores(quiz_id)`: Get all scores for a specific quiz
- `get_leaderboards(limit, parsed_quiz_ids)`: Get the top scores across all or specific quizzes

## Performance Considerations

- Use `get_quiz_questions` to fetch all questions for a quiz at once, rather than individual queries
- Avoid updating questions frequently to leverage caching
- Use `execute_transaction` for operations that modify multiple records to ensure data consistency 