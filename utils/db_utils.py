import aiomysql
import logging
import json
from config import CONFIG
import asyncio

logger = logging.getLogger('badgey.db')

# Global database pool
pool = None

pending_operations = []
MAX_RETRIES = 5
db_lock = asyncio.Lock()

async def setup_db():
    """Initialize database connection pool and create necessary tables"""
    global pool
    logger.info(f"Connecting to MySQL: Host={CONFIG['DB']['HOST']}, User={CONFIG['DB']['USER']}, Database={CONFIG['DB']['DATABASE']}")

    try:
        pool = await aiomysql.create_pool(
            host=CONFIG['DB']['HOST'],
            port=CONFIG['DB']['PORT'],
            user=CONFIG['DB']['USER'],
            password=CONFIG['DB']['PASSWORD'],
            db=CONFIG['DB']['DATABASE'],
            autocommit=True,
            connect_timeout=10,
            pool_recycle=300,
            maxsize=15  # Adjust based on your needs
        )
        
        async with pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cursor:
                # Create tables if they don't exist
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS quizzes (
                        quiz_id INT AUTO_INCREMENT PRIMARY KEY,
                        quiz_name TEXT NOT NULL
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
                        user_id BIGINT NOT NULL,
                        quiz_id INT NOT NULL,
                        score INT NOT NULL,
                        PRIMARY KEY (user_id, quiz_id),
                        FOREIGN KEY (quiz_id) REFERENCES quizzes(quiz_id) ON DELETE CASCADE
                    )
                """)
        logger.info("Database setup completed successfully")
    except Exception as e:
        logger.error(f"Failed to connect to MySQL: {e}")
        raise

async def on_resumed():
    """Handle reconnection events"""
    logging.info("Bot RESUMED connection. Checking for pending database operations...")
    if pending_operations:
        logging.info(f"Found {len(pending_operations)} pending operations to process")
        await retry_pending_operations()

async def retry_pending_operations():
    """Process any pending database operations"""
    global pending_operations
    
    if not pending_operations:
        return
        
    async with db_lock:
        operations_to_retry = pending_operations.copy()
        successful_ops = []
        
        for operation in operations_to_retry:
            try:
                func_name = operation["function"]
                args = operation["args"]
                kwargs = operation["kwargs"]
                
                # Call the appropriate function
                if func_name == "record_user_score":
                    await record_user_score(*args, **kwargs)
                elif func_name == "add_question":
                    await add_question(*args, **kwargs)
                
                # Mark as successful
                successful_ops.append(operation)
                logging.info(f"Successfully processed pending {func_name} operation")
                
            except Exception as e:
                logging.error(f"Failed to process pending operation: {e}")
                # Keep in queue for next retry
        
        # Remove successful operations
        for op in successful_ops:
            if op in pending_operations:
                pending_operations.remove(op)

async def safe_db_operation(func_name, *args, **kwargs):
    """
    Execute a database operation with retry logic
    If it fails, store it for later retry
    """
    retries = 0
    while retries < MAX_RETRIES:
        try:
            # Call the original function based on name
            if func_name == "record_user_score":
                return await _record_user_score(*args, **kwargs)
            elif func_name == "add_question":
                return await _add_question(*args, **kwargs)
            else:
                logging.error(f"Unknown function name: {func_name}")
                return None
        except aiomysql.OperationalError as e:
            if "database is locked" in str(e):
                # Database is locked, wait and retry
                logging.warning(f"Database locked, retrying operation {func_name} (attempt {retries+1}/{MAX_RETRIES})")
                retries += 1
                await asyncio.sleep(0.5 * (2 ** retries))  # Exponential backoff
            else:
                # Other operational error, queue for later
                logging.error(f"Database error in {func_name}: {e}")
                pending_operations.append({
                    "function": func_name,
                    "args": args,
                    "kwargs": kwargs
                })
                return None
        except Exception as e:
            # Unexpected error, queue for later
            logging.error(f"Unexpected error in {func_name}: {e}")
            pending_operations.append({
                "function": func_name,
                "args": args,
                "kwargs": kwargs
            })
            return None
    
    # If we exhausted retries, queue the operation
    logging.warning(f"Max retries reached for {func_name}, queueing for later")
    pending_operations.append({
        "function": func_name,
        "args": args,
        "kwargs": kwargs
    })
    return None

async def create_quiz(quiz_name):
    """Create a new quiz in the database"""
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("INSERT INTO quizzes (quiz_name) VALUES (%s)", (quiz_name,))
            return cursor.lastrowid

async def _add_question(quiz_id, question_text, options, correct_answer, score):
    """Add a question to a quiz"""
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                "INSERT INTO questions (quiz_id, question_text, options, correct_answer, score) VALUES (%s, %s, %s, %s, %s)",
                (quiz_id, question_text, options, correct_answer, score)
            )

async def add_question(quiz_id, question_text, options, correct_answer, score): # Public API functions with safety wrappers
    """Add a question to a quiz"""
    return await safe_db_operation("add_question", quiz_id, question_text, options, correct_answer, score)    

async def get_quiz_questions(quiz_id):
    """Get all questions for a specific quiz"""
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT question_id, quiz_id, question_text, options, correct_answer, score FROM questions WHERE quiz_id = %s", (quiz_id,))
            return await cursor.fetchall()

async def _record_user_score(user_id, user_name, quiz_id, score):
    """Record or update a user's score for a quiz"""
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                "REPLACE INTO user_scores (user_id, user_name, quiz_id, score) VALUES (%s, %s, %s, %s)",
                (user_id, user_name, quiz_id, score)
            )

async def record_user_score(user_id, user_name, quiz_id, score): # Public API functions with safety wrappers
    """Record or update a user's score for a quiz"""
    return await safe_db_operation("record_user_score", user_id, user_name, quiz_id, score)    

async def edit_question(question_id, question_text=None, options=None, correct_answer=None, score=None):
    """Edit a question's details"""

    """Update an existing question"""
    # Check if options is already a JSON string or a dict
    if isinstance(options, dict):
        options_json = json.dumps(options)
    elif isinstance(options, str):
        # If it's a string, check if it's already valid JSON
        try:
            # Try to parse it - if successful, it's already JSON
            json.loads(options)
            options_json = options
        except json.JSONDecodeError:
            # Not valid JSON, so encode it
            options_json = json.dumps(options)
    else:
        options_json = json.dumps({})  # Default to empty options


    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            query = "UPDATE questions SET "
            params = []
            if question_text:
                query += "question_text = %s, "
                params.append(question_text)
            if options:
                query += "options = %s, "
                params.append(options_json)
            if correct_answer:
                query += "correct_answer = %s, "
                params.append(correct_answer)
            if score:
                query += "score = %s, "
                params.append(score)
            
            query = query.rstrip(', ')
            query += " WHERE question_id = %s"
            params.append(question_id)
            
            await cursor.execute(query, params)

async def get_all_user_attempts(quiz_id):
    """Get all user scores"""
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT user_id, score FROM user_scores Where quiz_id = %s", (quiz_id))
            return await cursor.fetchall()
        
async def get_all_quizzes():
    """Get all quizzes from the database"""
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT quiz_id, quiz_name FROM quizzes ORDER BY quiz_id DESC")
            return await cursor.fetchall()

async def get_question(question_id):
    """Get a specific question from the database"""
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                "SELECT question_id, question_text, options, correct_answer, score FROM questions WHERE question_id = %s", 
                (question_id,)
            )
            return await cursor.fetchone()

async def update_question(question_id, text, options, correct_answer, points):
    """Update an existing question"""
    options_json = json.dumps(options)
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                "UPDATE questions SET question_text = %s, options = %s, correct_answer = %s, score = %s WHERE question_id = %s",
                (text, options_json, correct_answer, points, question_id)
            )
            return True

async def update_quiz_name(quiz_id, new_name):
    """Update a quiz's name"""
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            # Check if quiz exists
            await cursor.execute("SELECT quiz_id FROM quizzes WHERE quiz_id = %s", (quiz_id,))
            
            if not await cursor.fetchone():
                return False
            
            # Update quiz name
            await cursor.execute(
                "UPDATE quizzes SET quiz_name = %s WHERE quiz_id = %s",
                (new_name, quiz_id)
            )
            return True

async def get_quiz_name(quiz_id):
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT quiz_name FROM quizzes WHERE quiz_id = %s", (quiz_id,))
                return await cursor.fetchone()

async def get_leaderboards(limit, parsed_quiz_ids=None):
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
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
            
            await cursor.execute(query, params)
            return await cursor.fetchall()

async def check_quiz_exists(parsed_quiz_ids):
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            # Create placeholders for each quiz ID
            id_placeholders = ','.join(['%s'] * len(parsed_quiz_ids))
            query = f"SELECT quiz_id, quiz_name FROM quizzes WHERE quiz_id IN ({id_placeholders})"
            await cursor.execute(query, parsed_quiz_ids)
            return await cursor.fetchall()

async def delete_quiz(quiz_id):
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("DELETE FROM questions WHERE quiz_id = %s", (quiz_id,))
                await cursor.execute("DELETE FROM quizzes WHERE quiz_id = %s", (quiz_id,))
                logger.info("Quiz deleted")
                return True
            
    except Exception as e:
        logger.info(f"Error deleting quiz: {e}")
        return False

async def has_taken_quiz(user_id, quiz_id):
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT COUNT(*) FROM user_scores WHERE user_id = %s AND quiz_id = %s",
                    (user_id, quiz_id)
                )
                result = await cursor.fetchone()
                return result[0] > 0 if result else False
            
    except Exception as e:
        logger.error(f"Database error checking previous quiz attempts: {e}")
        return False  # Default to False in case of error

async def delete_scores(user_id=None, quiz_id=None):
    """
    Delete user scores from the database based on user_id and quiz_id parameters.
    
    Parameters:
    user_id (str, optional): The user ID or 'all' to delete all users' scores
    quiz_id (str, optional): The quiz ID or 'all' to delete scores from all quizzes
    
    Returns:
    int: Number of rows deleted
    """
    query = "DELETE FROM user_scores WHERE 1=1"
    params = []
    
    if user_id and user_id.lower() != "all":
        query += " AND user_id = %s"
        params.append(int(user_id))
    
    if quiz_id and quiz_id.lower() != "all":
        query += " AND quiz_id = %s"
        params.append(int(quiz_id))
    
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(query, params)
                return cursor.rowcount
    except Exception as e:
        logger.error(f"Error deleting user scores: {e}")
        raise

async def close_db_pool():
    """Close the database connection pool"""
    if pool:
        pool.close()
        await pool.wait_closed()
        logger.info("Database connection closed")