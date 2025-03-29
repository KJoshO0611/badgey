import time
import logging
import asyncio
from collections import defaultdict
from typing import Dict, List, Any, Optional
import json
from datetime import datetime, timedelta

logger = logging.getLogger('badgey.analytics')

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
        self.quiz_durations: List[float] = []  # List of quiz durations in seconds
        self.question_durations: List[float] = []  # List of question answer times in seconds
        self.quiz_scores: List[int] = []  # List of scores
        
        # Usage metrics
        self.popular_quizzes = defaultdict(int)  # quiz_id -> count
        self.user_participation = defaultdict(int)  # user_id -> count
        self.guild_usage = defaultdict(int)  # guild_id -> count
        self.hourly_usage = defaultdict(int)  # hour (0-23) -> count
        self.daily_usage = defaultdict(int)  # day of week (0-6) -> count
        
        # Performance tracking
        self.db_query_times: List[float] = []  # Database query times in seconds
        self.command_response_times: Dict[str, List[float]] = defaultdict(list)  # command -> list of response times
        
        # Error tracking
        self.errors = defaultdict(int)  # error type -> count
        self.last_errors: List[Dict[str, Any]] = []  # Recent errors with details
        
        # Lock for thread safety
        self.lock = asyncio.Lock()
        
        # Start time for uptime calculation
        self.start_time = time.time()
        
        logger.info("Quiz analytics initialized")
        
    async def record_quiz_start(self, user_id: int, quiz_id: int, guild_id: Optional[int] = None):
        """
        Record the start of a quiz
        
        Args:
            user_id (int): Discord user ID
            quiz_id (int): Quiz ID
            guild_id (Optional[int]): Discord guild ID (if applicable)
        """
        async with self.lock:
            self.quizzes_started += 1
            self.popular_quizzes[quiz_id] += 1
            self.user_participation[user_id] += 1
            
            if guild_id:
                self.guild_usage[guild_id] += 1
                
            # Track usage patterns by time
            now = datetime.now()
            self.hourly_usage[now.hour] += 1
            self.daily_usage[now.weekday()] += 1
            
            logger.debug(f"Recorded quiz start: user={user_id}, quiz={quiz_id}, guild={guild_id}")
            
    async def record_quiz_completion(self, user_id: int, quiz_id: int, duration: float, score: int):
        """
        Record the completion of a quiz
        
        Args:
            user_id (int): Discord user ID
            quiz_id (int): Quiz ID
            duration (float): Duration of the quiz in seconds
            score (int): Final score
        """
        async with self.lock:
            self.quizzes_completed += 1
            self.quiz_durations.append(duration)
            self.quiz_scores.append(score)
            
            # Limit stored durations and scores to avoid memory issues
            if len(self.quiz_durations) > 1000:
                self.quiz_durations = self.quiz_durations[-1000:]
            if len(self.quiz_scores) > 1000:
                self.quiz_scores = self.quiz_scores[-1000:]
                
            logger.debug(f"Recorded quiz completion: user={user_id}, quiz={quiz_id}, duration={duration:.2f}s, score={score}")
                
    async def record_answer(self, is_correct: bool, time_taken: float = 0.0):
        """
        Record a question answer
        
        Args:
            is_correct (bool): Whether the answer was correct
            time_taken (float): Time taken to answer in seconds
        """
        async with self.lock:
            self.questions_answered += 1
            if is_correct:
                self.correct_answers += 1
                
            if time_taken > 0:
                self.question_durations.append(time_taken)
                
                # Limit stored durations to avoid memory issues
                if len(self.question_durations) > 1000:
                    self.question_durations = self.question_durations[-1000:]
                    
    async def record_command(self, command_name: str, response_time: float):
        """
        Record a command execution
        
        Args:
            command_name (str): Name of the command
            response_time (float): Response time in seconds
        """
        async with self.lock:
            self.command_response_times[command_name].append(response_time)
            
            # Limit stored response times to avoid memory issues
            if len(self.command_response_times[command_name]) > 100:
                self.command_response_times[command_name] = self.command_response_times[command_name][-100:]
                
    async def record_db_query(self, query_time: float):
        """
        Record a database query
        
        Args:
            query_time (float): Query execution time in seconds
        """
        async with self.lock:
            self.db_query_times.append(query_time)
            
            # Limit stored query times to avoid memory issues
            if len(self.db_query_times) > 1000:
                self.db_query_times = self.db_query_times[-1000:]
                
    async def record_error(self, error_type: str, error_details: Dict[str, Any]):
        """
        Record an error
        
        Args:
            error_type (str): Type of error
            error_details (Dict[str, Any]): Details about the error
        """
        async with self.lock:
            self.errors[error_type] += 1
            
            # Add timestamp to error details
            error_details['timestamp'] = datetime.now().isoformat()
            
            # Add to recent errors
            self.last_errors.append(error_details)
            
            # Limit stored errors to avoid memory issues
            if len(self.last_errors) > 100:
                self.last_errors = self.last_errors[-100:]
                
            logger.debug(f"Recorded error: {error_type}")
                
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get analytics statistics
        
        Returns:
            Dict[str, Any]: Dictionary of statistics
        """
        # Calculate derived metrics
        completion_rate = (self.quizzes_completed / self.quizzes_started) * 100 if self.quizzes_started > 0 else 0
        correct_rate = (self.correct_answers / self.questions_answered) * 100 if self.questions_answered > 0 else 0
        avg_duration = sum(self.quiz_durations) / len(self.quiz_durations) if self.quiz_durations else 0
        avg_score = sum(self.quiz_scores) / len(self.quiz_scores) if self.quiz_scores else 0
        avg_question_time = sum(self.question_durations) / len(self.question_durations) if self.question_durations else 0
        
        # Calculate uptime
        uptime_seconds = time.time() - self.start_time
        days, remainder = divmod(uptime_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{int(days)}d {int(hours)}h {int(minutes)}m {int(seconds)}s"
        
        # Get top items
        top_quizzes = dict(sorted(self.popular_quizzes.items(), key=lambda x: x[1], reverse=True)[:10])
        top_users = dict(sorted(self.user_participation.items(), key=lambda x: x[1], reverse=True)[:10])
        top_guilds = dict(sorted(self.guild_usage.items(), key=lambda x: x[1], reverse=True)[:10])
        
        # Database performance
        avg_db_query_time = sum(self.db_query_times) / len(self.db_query_times) if self.db_query_times else 0
        
        # Command performance
        command_performance = {}
        for cmd, times in self.command_response_times.items():
            if times:
                command_performance[cmd] = {
                    'avg_time': sum(times) / len(times),
                    'min_time': min(times),
                    'max_time': max(times),
                    'count': len(times)
                }
        
        return {
            # General metrics
            "quizzes_started": self.quizzes_started,
            "quizzes_completed": self.quizzes_completed,
            "completion_rate": completion_rate,
            "questions_answered": self.questions_answered,
            "correct_answers": self.correct_answers,
            "correct_rate": correct_rate,
            
            # Performance metrics
            "avg_quiz_duration": avg_duration,
            "avg_score": avg_score,
            "avg_question_time": avg_question_time,
            
            # Usage metrics
            "top_quizzes": top_quizzes,
            "active_users": len(self.user_participation),
            "top_users": top_users,
            "top_guilds": top_guilds,
            
            # Time metrics
            "hourly_usage": dict(self.hourly_usage),
            "daily_usage": dict(self.daily_usage),
            
            # System metrics
            "uptime": uptime_str,
            "uptime_seconds": uptime_seconds,
            
            # Performance metrics
            "avg_db_query_time": avg_db_query_time,
            "command_performance": command_performance,
            
            # Error metrics
            "error_counts": dict(self.errors),
            "recent_errors_count": len(self.last_errors)
        }
        
    def export_to_json(self) -> str:
        """
        Export analytics data to JSON string
        
        Returns:
            str: JSON string of analytics data
        """
        return json.dumps(self.get_statistics(), indent=2)
    
    def reset(self):
        """Reset all analytics data"""
        self.__init__()

# Initialize global instance
quiz_analytics = QuizAnalytics() 