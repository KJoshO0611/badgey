import logging
import asyncio
import aiomysql
from typing import Optional, List, Tuple, Dict, Any, Union
from config import CONFIG
import json

logger = logging.getLogger('badgey.db_utilsv2')

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

async def setup_db() -> None:
    """
    Initialize database connection and create necessary tables
    
    Raises:
        DatabaseConnectionError: If database connection fails
    """
    try:
        conn = await get_db_connection()
        async with conn.cursor() as cursor:
            # Create tables if they don't exist
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS quizzes (
                    quiz_id INT AUTO_INCREMENT PRIMARY KEY,
                    quiz_name TEXT NOT NULL,
                    creator_id BIGINT NOT NULL,
                    creation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS questions (
                    question_id INT AUTO_INCREMENT PRIMARY KEY,
                    quiz_id INT NOT NULL,
                    question_text TEXT NOT NULL,
                    options JSON NOT NULL,
                    correct_answer TEXT NOT NULL,
                    score INT NOT NULL,
                    FOREIGN KEY (quiz_id) REFERENCES quizzes(quiz_id) ON DELETE CASCADE
                )
            """)

            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_scores (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    user_name VARCHAR(255) NOT NULL,
                    quiz_id INT NOT NULL,
                    score INT NOT NULL,
                    completion_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_user_quiz (user_id, quiz_id),
                    FOREIGN KEY (quiz_id) REFERENCES quizzes(quiz_id) ON DELETE CASCADE
                )
            """)
        logger.info("Database setup completed successfully")
        conn.close()
    except Exception as e:
        logger.error(f"Failed to setup database: {str(e)}")
        raise DatabaseConnectionError(f"Failed to setup database: {str(e)}")

# GET functions
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

async def get_question(question_id: int) -> Optional[Tuple]:
    """
    Get a specific question by ID
    """
    try:
        query = """
            SELECT question_id, quiz_id, question_text, options, correct_answer, score
            FROM questions
            WHERE question_id = %s
        """
        return await fetch_one(query, (question_id,))
    except DatabaseQueryError as e:
        logger.error(f"Failed to get question: {str(e)}")
        return None

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
            SELECT user_id, user_name, quiz_id, score
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

async def get_all_quizzes() -> List[Tuple]:
    """
    Get all quizzes from the database
    
    Returns:
        List[Tuple]: List of (quiz_id, quiz_name) tuples
    """
    try:
        query = "SELECT quiz_id, quiz_name FROM quizzes ORDER BY quiz_id ASC"
        return await fetch_all(query)
    except DatabaseQueryError as e:
        logger.error(f"Failed to get all quizzes: {str(e)}")
        return []

async def get_leaderboards(limit: int, parsed_quiz_ids: Optional[List[int]] = None) -> List[Dict[str, Any]]:
    """
    Get leaderboard data with optional quiz filtering
    
    Args:
        limit (int): Maximum number of results to return
        parsed_quiz_ids (Optional[List[int]]): List of quiz IDs to filter by
        
    Returns:
        List[Dict[str, Any]]: Leaderboard data as dictionaries
    """
    try:
        # Base query
        query = """
            SELECT 
                user_name,
                SUM(score) as total_score 
            FROM 
                user_scores
        """
        
        # Prepare parameters
        params = []
        
        # Add quiz ID filtering if specified
        if parsed_quiz_ids:
            # Create placeholders for each quiz ID
            id_placeholders = ','.join(['%s'] * len(parsed_quiz_ids))
            query += f" WHERE quiz_id IN ({id_placeholders}) "
            params.extend(parsed_quiz_ids)
        
        # Complete the query
        query += """
            GROUP BY 
                user_name
            ORDER BY 
                total_score DESC 
            LIMIT %s
        """
        
        # Add limit to params
        params.append(limit)
        
        # Execute query and convert to dictionaries
        results = await fetch_all(query, tuple(params))
        return [{"user_name": row[0], "total_score": row[1]} for row in results]
    except DatabaseQueryError as e:
        logger.error(f"Failed to get leaderboards: {str(e)}")
        return []

# UPDATE/EDIT functions
async def edit_question(question_id: int, question_text: Optional[str] = None, 
                        options: Optional[Union[dict, str]] = None, 
                        correct_answer: Optional[str] = None, 
                        score: Optional[int] = None) -> bool:
    """
    Edit an existing question's details
    
    Args:
        question_id (int): ID of the question to edit
        question_text (Optional[str]): New question text
        options (Optional[Union[dict, str]]): New options as dict or JSON string
        correct_answer (Optional[str]): New correct answer
        score (Optional[int]): New score value
        
    Returns:
        bool: True if successful, False otherwise
        
    Raises:
        DatabaseQueryError: If query execution fails
    """
    # Handle options formatting
    options_json = None
    if options:
        if isinstance(options, dict):
            options_json = json.dumps(options)
        elif isinstance(options, str):
            try:
                # Check if it's already valid JSON
                json.loads(options)
                options_json = options
            except json.JSONDecodeError:
                # Not valid JSON, so encode it
                options_json = json.dumps(options)
        else:
            options_json = json.dumps({})  # Default to empty options

    try:
        # Build query dynamically based on provided parameters
        query = "UPDATE questions SET "
        params = []
        
        if question_text:
            query += "question_text = %s, "
            params.append(question_text)
        if options_json:
            query += "options = %s, "
            params.append(options_json)
        if correct_answer:
            query += "correct_answer = %s, "
            params.append(correct_answer)
        if score:
            query += "score = %s, "
            params.append(score)
        
        # Remove trailing comma and space
        query = query.rstrip(', ')
        
        # Add WHERE clause
        query += " WHERE question_id = %s"
        params.append(question_id)
        
        # Execute the query
        await execute_query(query, tuple(params))
        return True
    except DatabaseQueryError as e:
        logger.error(f"Failed to edit question {question_id}: {str(e)}")
        return False

async def update_question(question_id: int, text: str, options: dict, 
                          correct_answer: str, points: int) -> bool:
    """
    Update an existing question
    
    Args:
        question_id (int): ID of the question to update
        text (str): New question text
        options (dict): New options as dictionary
        correct_answer (str): New correct answer
        points (int): New score value
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        options_json = json.dumps(options)
        query = """
            UPDATE questions 
            SET question_text = %s, options = %s, correct_answer = %s, score = %s 
            WHERE question_id = %s
        """
        await execute_query(query, (text, options_json, correct_answer, points, question_id))
        return True
    except DatabaseQueryError as e:
        logger.error(f"Failed to update question {question_id}: {str(e)}")
        return False

async def update_quiz_name(quiz_id: int, new_name: str) -> bool:
    """
    Update a quiz's name
    
    Args:
        quiz_id (int): ID of the quiz
        new_name (str): New name for the quiz
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Check if quiz exists
        check_query = "SELECT quiz_id FROM quizzes WHERE quiz_id = %s"
        result = await fetch_one(check_query, (quiz_id,))
        
        if not result:
            logger.warning(f"Attempted to update non-existent quiz: {quiz_id}")
            return False
        
        # Update quiz name
        update_query = "UPDATE quizzes SET quiz_name = %s WHERE quiz_id = %s"
        await execute_query(update_query, (new_name, quiz_id))
        return True
    except DatabaseQueryError as e:
        logger.error(f"Failed to update quiz name for quiz {quiz_id}: {str(e)}")
        return False

# INSERT functions
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

async def add_quiz(quiz_name: str, creator_id: str) -> int:
    """
    Add a new quiz to the database
    """
    try:
        # First check if a similar quiz already exists
        check_query = "SELECT quiz_id FROM quizzes WHERE quiz_name = %s AND creator_id = %s ORDER BY quiz_id DESC LIMIT 1"
        existing = await fetch_one(check_query, (quiz_name,creator_id,))
        if existing:
            logger.info(f"Quiz '{quiz_name}' already exists with ID {existing[0]}")
            return existing[0]
        
        # Insert the new quiz
        query = "INSERT INTO quizzes (quiz_name,creator_id) VALUES (%s,%s)"
        result = await execute_query(query, (quiz_name,creator_id,))
        
        # Check if row was inserted
        if hasattr(result, 'rowcount') and result.rowcount > 0:
            logger.info(f"Quiz '{quiz_name}' inserted successfully")
        else:
            logger.warning(f"Quiz '{quiz_name}' insert reported no rows affected")
        
        # Get the new quiz ID
        quiz_id_query = "SELECT LAST_INSERT_ID()"
        result = await fetch_one(quiz_id_query)
        
        id_value = result[0] if result else -1
        logger.info(f"LAST_INSERT_ID() returned: {id_value}")
        
        if id_value <= 0:
            # Try alternative approach
            alternative_query = "SELECT quiz_id FROM quizzes WHERE quiz_name = %s AND creator_id = %s ORDER BY quiz_id DESC LIMIT 1"
            alt_result = await fetch_one(alternative_query, (quiz_name,creator_id,))
            if alt_result:
                logger.info(f"Alternative query found ID: {alt_result[0]}")
                return alt_result[0]
                
        return id_value
    except DatabaseQueryError as e:
        logger.error(f"Failed to add quiz: {str(e)}")
        return -1

async def add_question(quiz_id: int, question_text: str, options: Union[dict, str],
                       correct_answer: str, score: int) -> bool:
    """
    Add a new question to the database
    
    Args:
        quiz_id (int): ID of the quiz
        question_text (str): Question text
        options (dict or str): Question options as dictionary or JSON string
        correct_answer (str): Correct answer
        score (int): Question score
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Check if options is already a JSON string
        if isinstance(options, dict):
            options_json = json.dumps(options)
        else:
            options_json = options  # Already a JSON string
            
        query = """
            INSERT INTO questions (quiz_id, question_text, options, correct_answer, score)
            VALUES (%s, %s, %s, %s, %s)
        """
        await execute_query(query, (quiz_id, question_text, options_json, correct_answer, score))
        return True
    except DatabaseQueryError as e:
        logger.error(f"Failed to add question: {str(e)}")
        return False

# DELETE functions
async def delete_quiz(quiz_id: int) -> bool:
    """
    Delete a quiz and all associated data
    
    Args:
        quiz_id (int): ID of the quiz to delete
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Delete the quiz
        await execute_query("DELETE FROM quizzes WHERE quiz_id = %s", (quiz_id,))
        
        logger.info(f"Quiz {quiz_id}, questions and score deleted successfully")
        return True
    except DatabaseQueryError as e:
        logger.error(f"Failed to delete quiz {quiz_id}: {str(e)}")
        return False

async def delete_scores(user_id: Optional[str] = None, quiz_id: Optional[str] = None) -> int:
    """
    Delete user scores from the database based on filters
    
    Args:
        user_id (Optional[str]): The user ID or 'all' to delete all users' scores
        quiz_id (Optional[str]): The quiz ID or 'all' to delete scores from all quizzes
        
    Returns:
        int: Number of rows affected or -1 if operation failed
        
    Raises:
        DatabaseQueryError: If query execution fails
    """
    try:
        query = "DELETE FROM user_scores WHERE 1=1"
        params = []
        
        # Add user filter if specified
        if user_id and user_id.lower() != "all":
            query += " AND user_id = %s"
            params.append(int(user_id))
        
        # Add quiz filter if specified
        if quiz_id and quiz_id.lower() != "all":
            query += " AND quiz_id = %s"
            params.append(int(quiz_id))
        
        # Get connection and execute
        conn = await get_db_connection()
        async with conn.cursor() as cursor:
            await cursor.execute(query, tuple(params))
            rows_affected = cursor.rowcount
        conn.close()
        
        logger.info(f"Deleted {rows_affected} score records")
        return rows_affected
    except Exception as e:
        logger.error(f"Failed to delete scores: {str(e)}")
        raise DatabaseQueryError(f"Failed to delete scores: {str(e)}")

# CHECK Functions
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
    
async def check_quiz_exists(parsed_quiz_ids: List[int]) -> List[Dict[str, Any]]:
    """
    Check if specified quizzes exist
    
    Args:
        parsed_quiz_ids (List[int]): List of quiz IDs to check
        
    Returns:
        List[Dict[str, Any]]: Existing quiz data as dictionaries
    """
    try:
        if not parsed_quiz_ids:
            return []
            
        # Create placeholders for each quiz ID
        id_placeholders = ','.join(['%s'] * len(parsed_quiz_ids))
        query = f"SELECT quiz_id, quiz_name FROM quizzes WHERE quiz_id IN ({id_placeholders})"
        
        # Execute query and convert to dictionaries
        results = await fetch_all(query, tuple(parsed_quiz_ids))
        return [{"quiz_id": row[0], "quiz_name": row[1]} for row in results]
    except DatabaseQueryError as e:
        logger.error(f"Failed to check quiz existence: {str(e)}")
        return []
    
# Helper function for executing multiple queries as a transaction
async def execute_transaction(queries: List[Tuple[str, Tuple]]) -> bool:
    """
    Execute multiple queries as a transaction with retry logic
    
    Args:
        queries (List[Tuple[str, Tuple]]): List of (query, params) tuples
        
    Returns:
        bool: True if transaction was successful, False otherwise
    """
    conn = None
    try:
        conn = await get_db_connection()
        
        # Disable autocommit to start a transaction
        await conn.cursor().execute("SET autocommit = 0")
        
        # Execute all queries
        for query, params in queries:
            async with conn.cursor() as cursor:
                await cursor.execute(query, params)
        
        # Commit the transaction
        await conn.cursor().execute("COMMIT")
        
        # Re-enable autocommit
        await conn.cursor().execute("SET autocommit = 1")
        
        logger.info(f"Transaction of {len(queries)} queries completed successfully")
        return True
    except Exception as e:
        # Rollback on error
        if conn:
            await conn.cursor().execute("ROLLBACK")
            await conn.cursor().execute("SET autocommit = 1")
        
        logger.error(f"Transaction failed: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()