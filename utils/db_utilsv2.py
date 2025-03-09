import logging
import asyncio
import aiomysql
from typing import Optional, List, Tuple, Dict, Any, Union
from config import CONFIG

logger = logging.getLogger('badgey.db_utils')

# Define custom exceptions for better error handling
class DatabaseConnectionError(Exception):
    """Exception raised when database connection fails"""
    pass

class DatabaseQueryError(Exception):
    """Exception raised when a database query fails"""
    pass

# Configurable retry parameters
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds
RETRY_BACKOFF_FACTOR = 2  # exponential backoff

async def get_db_connection() -> aiomysql.Connection:
    """
    Establish a database connection with retry logic.
    
    Returns:
        aiomysql.Connection: A database connection
        
    Raises:
        DatabaseConnectionError: If all connection attempts fail
    """
    for attempt in range(MAX_RETRIES):
        try:
            conn = await aiomysql.connect(
                host=CONFIG['DB']['HOST'],
                port=CONFIG['DB']['PORT'],
                user=CONFIG['DB']['USER'],
                password=CONFIG['DB']['PASSWORD'],
                db=CONFIG['DB']['DATABASE'],
                autocommit=True,
                #connect_timeout=10,
                #pool_recycle=300,
                #maxsize=15  # Adjust based on your needs
            )
            return conn
        except Exception as e:
            delay = RETRY_DELAY * (RETRY_BACKOFF_FACTOR ** attempt)
            logger.warning(f"Database connection attempt {attempt+1}/{MAX_RETRIES} failed: {str(e)}. Retrying in {delay}s")
            await asyncio.sleep(delay)
    
    # If we get here, all retries failed
    logger.error(f"All database connection attempts failed")
    raise DatabaseConnectionError("Failed to connect to database after multiple attempts")

async def execute_query(query: str, params: Tuple = None, retries: int = MAX_RETRIES) -> None:
    """
    Execute a database query with retry logic
    
    Args:
        query (str): SQL query to execute
        params (tuple, optional): Parameters for the query
        retries (int, optional): Number of retry attempts
        
    Raises:
        DatabaseQueryError: If all query attempts fail
    """
    conn = None
    for attempt in range(retries):
        try:
            conn = await get_db_connection()
            async with conn.cursor() as cursor:
                await cursor.execute(query, params)
            return
        except Exception as e:
            delay = RETRY_DELAY * (RETRY_BACKOFF_FACTOR ** attempt)
            logger.warning(f"Query execution attempt {attempt+1}/{retries} failed: {str(e)}. Retrying in {delay}s")
            await asyncio.sleep(delay)
        finally:
            if conn:
                conn.close()
    
    logger.error(f"All query execution attempts failed for query: {query}")
    raise DatabaseQueryError(f"Failed to execute query after {retries} attempts")

async def fetch_one(query: str, params: Tuple = None, retries: int = MAX_RETRIES) -> Optional[Tuple]:
    """
    Fetch a single row from the database with retry logic
    
    Args:
        query (str): SQL query to execute
        params (tuple, optional): Parameters for the query
        retries (int, optional): Number of retry attempts
        
    Returns:
        Optional[tuple]: The fetched row or None if no rows found
        
    Raises:
        DatabaseQueryError: If all query attempts fail
    """
    conn = None
    for attempt in range(retries):
        try:
            conn = await get_db_connection()
            async with conn.cursor() as cursor:
                await cursor.execute(query, params)
                result = await cursor.fetchone()
            return result
        except Exception as e:
            delay = RETRY_DELAY * (RETRY_BACKOFF_FACTOR ** attempt)
            logger.warning(f"Fetch attempt {attempt+1}/{retries} failed: {str(e)}. Retrying in {delay}s")
            await asyncio.sleep(delay)
        finally:
            if conn:
                conn.close()
    
    logger.error(f"All fetch attempts failed for query: {query}")
    raise DatabaseQueryError(f"Failed to fetch data after {retries} attempts")

async def fetch_all(query: str, params: Tuple = None, retries: int = MAX_RETRIES) -> List[Tuple]:
    """
    Fetch all rows from the database with retry logic
    
    Args:
        query (str): SQL query to execute
        params (tuple, optional): Parameters for the query
        retries (int, optional): Number of retry attempts
        
    Returns:
        List[tuple]: The fetched rows (empty list if no rows found)
        
    Raises:
        DatabaseQueryError: If all query attempts fail
    """
    conn = None
    for attempt in range(retries):
        try:
            conn = await get_db_connection()
            async with conn.cursor() as cursor:
                await cursor.execute(query, params)
                result = await cursor.fetchall()
            return result
        except Exception as e:
            delay = RETRY_DELAY * (RETRY_BACKOFF_FACTOR ** attempt)
            logger.warning(f"Fetch all attempt {attempt+1}/{retries} failed: {str(e)}. Retrying in {delay}s")
            await asyncio.sleep(delay)
        finally:
            if conn:
                conn.close()
    
    logger.error(f"All fetch all attempts failed for query: {query}")
    raise DatabaseQueryError(f"Failed to fetch all data after {retries} attempts")

async def get_quiz_questions(quiz_id) -> List[Tuple]:
    """
    Get all questions for a specific quiz
    
    Args:
        quiz_id (int): ID of the quiz
        
    Returns:
        List[tuple]: List of question data
    """
    try:
        query = """
            SELECT question_id, quiz_id, question_text, options, correct_answer, score
            FROM questions
            WHERE quiz_id = %s
            Order by question_id ASC
        """
        return await fetch_all(query, (quiz_id,))
    except DatabaseQueryError as e:
        logger.error(f"Failed to get quiz questions: {str(e)}")
        return []
    
async def get_quiz_name(quiz_id: int) -> Optional[Tuple[str]]:
    """
    Get the name of a specific quiz
    
    Args:
        quiz_id (int): ID of the quiz
        
    Returns:
        Optional[Tuple[str]]: Tuple containing quiz name or None if not found
    """
    try:
        query = "SELECT quiz_name FROM quizzes WHERE quiz_id = %s"
        return await fetch_one(query, (quiz_id,))
    except DatabaseQueryError as e:
        logger.error(f"Error fetching quiz name for quiz {quiz_id}: {str(e)}")
        return None

async def get_quiz_scores(quiz_id) -> List[Tuple]:
    """
    Get all scores for a specific quiz
    """
    try:
        query = """
            SELECT user_id, quiz_id, score
            FROM scores
            WHERE quiz_id = %s
            ORDER BY score DESC
        """
        return await fetch_all(query, (quiz_id,))
    except DatabaseQueryError as e:
        logger.error(f"Failed to get quiz scores: {str(e)}")
        return []
    
async def get_user_score(user_id, quiz_id) -> Optional[Tuple]:
    """
    Get a user's score for a specific quiz
    """
    try:
        query = """
            SELECT user_id, quiz_id, score
            FROM scores
            WHERE user_id = %s AND quiz_id = %s
        """
        return await fetch_one(query, (user_id, quiz_id))
    except DatabaseQueryError as e:
        logger.error(f"Failed to get user score: {str(e)}")
        return None

async def get_user_scores(user_id) -> List[Tuple]:
    """
    Get all scores for a specific user
    """
    try:
        query = """
            SELECT user_id, quiz_id, score
            FROM scores
            WHERE user_id = %s
            ORDER BY score DESC
        """
        return await fetch_all(query, (user_id,))
    except DatabaseQueryError as e:
        logger.error(f"Failed to get user scores: {str(e)}")
        return []

async def get_user_scores_by_quiz_name(user_id, quiz_name) -> List[Tuple]:
    """
    Get all scores for a specific user on a specific quiz
    """
    try:
        query = """
            SELECT user_id, quiz_id, score
            FROM scores
            WHERE user_id = %s AND quiz_id = (SELECT quiz_id FROM quizzes WHERE quiz_name = %s)
        """
        return await fetch_all(query, (user_id, quiz_name))
    except DatabaseQueryError as e:
        logger.error(f"Failed to get user scores by quiz name: {str(e)}")
        return []
    
async def record_user_score(user_id: int, username: str, quiz_id: int, score: int) -> bool:
    """
    Record a user's score for a quiz with error handling and retries
    
    Args:
        user_id (int): Discord user ID
        username (str): Discord username
        quiz_id (int): Quiz ID
        score (int): User's score
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Check if the user already has a score for this quiz
        check_query = "SELECT user_id FROM user_scores WHERE user_id = %s AND quiz_id = %s"
        existing_score = await fetch_one(check_query, (user_id, quiz_id))
        
        if existing_score:
            # Update existing score if it's higher
            update_query = """
                UPDATE user_scores 
                SET score = GREATEST(score, %s), 
                    completion_date = NOW() 
                WHERE user_id = %s AND quiz_id = %s
            """
            await execute_query(update_query, (score, user_id, quiz_id))
        else:
            # Insert new score
            insert_query = """
                INSERT INTO user_scores (user_id, user_name, quiz_id, score, completion_date) 
                VALUES (%s, %s, %s, %s, NOW())
            """
            await execute_query(insert_query, (user_id, username, quiz_id, score))
        
        logger.info(f"Successfully recorded score {score} for user {username} (ID: {user_id}) on quiz {quiz_id}")
        return True
    except (DatabaseConnectionError, DatabaseQueryError) as e:
        logger.error(f"Failed to record score for user {username} (ID: {user_id}) on quiz {quiz_id}: {str(e)}")
        return False
    
async def has_taken_quiz(user_id: int, quiz_id: int) -> bool:
    """
    Check if a user has already taken a specific quiz
    
    Args:
        user_id (int): Discord user ID
        quiz_id (int): Quiz ID
        
    Returns:
        bool: True if user has taken the quiz, False otherwise
    """
    try:
        query = "SELECT id FROM user_scores WHERE user_id = %s AND quiz_id = %s"
        result = await fetch_one(query, (user_id, quiz_id))
        return result is not None
    except (DatabaseConnectionError, DatabaseQueryError) as e:
        logger.error(f"Error checking if user {user_id} has taken quiz {quiz_id}: {str(e)}")
        # Default to False on error - better to let the user attempt the quiz than block incorrectly
        return False