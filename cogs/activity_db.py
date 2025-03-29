import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, Tuple, List, Optional

logger = logging.getLogger('badgey.activity_db')

# Define the database path
DB_PATH = 'activity_stats.db'

class ActivityDatabase:
    """Class to handle activity statistics database operations"""
    
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.setup_database()
    
    def setup_database(self):
        """Create necessary tables if they don't exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Message tracking table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS message_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            guild_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            message_count INTEGER DEFAULT 1,
            UNIQUE(user_id, guild_id, date)
        )
        ''')
        
        # Voice activity tracking
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS voice_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            guild_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            voice_minutes REAL DEFAULT 0,
            UNIQUE(user_id, guild_id, date)
        )
        ''')
        
        # Indices for faster queries
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_message_user ON message_stats (user_id, date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_voice_user ON voice_stats (user_id, date)')
        
        conn.commit()
        conn.close()
        logger.info("Activity database setup complete")
    
    def record_message(self, user_id: int, guild_id: int, date_str: Optional[str] = None):
        """Record a message sent by a user"""
        if date_str is None:
            date_str = datetime.now().strftime('%Y-%m-%d')
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Try to update existing record
            cursor.execute(
                '''
                INSERT INTO message_stats (user_id, guild_id, date, message_count)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(user_id, guild_id, date) 
                DO UPDATE SET message_count = message_count + 1
                ''',
                (user_id, guild_id, date_str)
            )
            
            conn.commit()
        except Exception as e:
            logger.error(f"Error recording message: {e}")
        finally:
            conn.close()
    
    def record_voice_time(self, user_id: int, guild_id: int, minutes: float, date_str: Optional[str] = None):
        """Record voice activity time in minutes"""
        if date_str is None:
            date_str = datetime.now().strftime('%Y-%m-%d')
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Try to update existing record
            cursor.execute(
                '''
                INSERT INTO voice_stats (user_id, guild_id, date, voice_minutes)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, guild_id, date) 
                DO UPDATE SET voice_minutes = voice_minutes + ?
                ''',
                (user_id, guild_id, date_str, minutes, minutes)
            )
            
            conn.commit()
        except Exception as e:
            logger.error(f"Error recording voice time: {e}")
        finally:
            conn.close()
    
    def get_message_data(self, user_id: int, guild_id: int, days: int = 30) -> Dict[str, int]:
        """Get message data for a specific user over a period of days"""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        start_date_str = start_date.strftime('%Y-%m-%d')
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                '''
                SELECT date, message_count 
                FROM message_stats 
                WHERE user_id = ? AND guild_id = ? AND date >= ?
                ORDER BY date ASC
                ''',
                (user_id, guild_id, start_date_str)
            )
            
            results = cursor.fetchall()
            
            # Create a dictionary with all dates in range (including zeros)
            data = {}
            current_date = start_date
            while current_date <= end_date:
                date_str = current_date.strftime('%Y-%m-%d')
                data[date_str] = 0
                current_date += timedelta(days=1)
            
            # Fill in actual data
            for date_str, count in results:
                data[date_str] = count
                
            return data
            
        except Exception as e:
            logger.error(f"Error retrieving message data: {e}")
            return {}
        finally:
            conn.close()
    
    def get_voice_data(self, user_id: int, guild_id: int, days: int = 30) -> Dict[str, float]:
        """Get voice activity data for a specific user over a period of days (in hours)"""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        start_date_str = start_date.strftime('%Y-%m-%d')
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                '''
                SELECT date, voice_minutes 
                FROM voice_stats 
                WHERE user_id = ? AND guild_id = ? AND date >= ?
                ORDER BY date ASC
                ''',
                (user_id, guild_id, start_date_str)
            )
            
            results = cursor.fetchall()
            
            # Create a dictionary with all dates in range (including zeros)
            data = {}
            current_date = start_date
            while current_date <= end_date:
                date_str = current_date.strftime('%Y-%m-%d')
                data[date_str] = 0
                current_date += timedelta(days=1)
            
            # Fill in actual data (convert minutes to hours)
            for date_str, minutes in results:
                data[date_str] = minutes / 60
                
            return data
            
        except Exception as e:
            logger.error(f"Error retrieving voice data: {e}")
            return {}
        finally:
            conn.close()
    
    def get_activity_summary(self, user_id: int, guild_id: int) -> Dict[str, float]:
        """Get summary statistics for a user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Get total messages
            cursor.execute(
                "SELECT SUM(message_count) FROM message_stats WHERE user_id = ? AND guild_id = ?",
                (user_id, guild_id)
            )
            total_messages = cursor.fetchone()[0] or 0
            
            # Get total voice hours
            cursor.execute(
                "SELECT SUM(voice_minutes) FROM voice_stats WHERE user_id = ? AND guild_id = ?",
                (user_id, guild_id)
            )
            total_voice_minutes = cursor.fetchone()[0] or 0
            
            # Get daily averages (last 30 days)
            thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            
            cursor.execute(
                """
                SELECT AVG(message_count) 
                FROM message_stats 
                WHERE user_id = ? AND guild_id = ? AND date >= ?
                """,
                (user_id, guild_id, thirty_days_ago)
            )
            avg_daily_messages = cursor.fetchone()[0] or 0
            
            cursor.execute(
                """
                SELECT AVG(voice_minutes) 
                FROM voice_stats 
                WHERE user_id = ? AND guild_id = ? AND date >= ?
                """,
                (user_id, guild_id, thirty_days_ago)
            )
            avg_daily_voice_minutes = cursor.fetchone()[0] or 0
            
            return {
                'total_messages': total_messages,
                'total_voice_hours': total_voice_minutes / 60,
                'avg_daily_messages': avg_daily_messages,
                'avg_daily_voice_hours': avg_daily_voice_minutes / 60
            }
            
        except Exception as e:
            logger.error(f"Error retrieving activity summary: {e}")
            return {
                'total_messages': 0,
                'total_voice_hours': 0,
                'avg_daily_messages': 0,
                'avg_daily_voice_hours': 0
            }
        finally:
            conn.close()
    
    def get_server_rank(self, user_id: int, guild_id: int) -> Tuple[int, int]:
        """Get user's rank in server by messages and voice activity"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Get message rankings
            cursor.execute(
                """
                SELECT user_id, SUM(message_count) as total_messages
                FROM message_stats
                WHERE guild_id = ?
                GROUP BY user_id
                ORDER BY total_messages DESC
                """,
                (guild_id,)
            )
            
            message_rankings = cursor.fetchall()
            message_rank = next((i+1 for i, (uid, _) in enumerate(message_rankings) if uid == user_id), 0)
            
            # Get voice rankings
            cursor.execute(
                """
                SELECT user_id, SUM(voice_minutes) as total_voice
                FROM voice_stats
                WHERE guild_id = ?
                GROUP BY user_id
                ORDER BY total_voice DESC
                """,
                (guild_id,)
            )
            
            voice_rankings = cursor.fetchall()
            voice_rank = next((i+1 for i, (uid, _) in enumerate(voice_rankings) if uid == user_id), 0)
            
            return (message_rank, voice_rank)
            
        except Exception as e:
            logger.error(f"Error retrieving server rank: {e}")
            return (0, 0)
        finally:
            conn.close()