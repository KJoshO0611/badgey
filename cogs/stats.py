import discord
from discord.ext import commands
from discord import app_commands
import logging
import asyncio
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Literal, Union
from config import CONFIG
from utils.helpers import has_required_role

# Import our enhanced stats visualization module
from utils.stats_vis import generate_cairo_stats

logger = logging.getLogger('badgey.Stats')

# Database setup for tracking statistics
DB_PATH = 'stats.db'

class StatsDB:
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
            channel_id INTEGER NOT NULL,
            guild_id INTEGER NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            message_count INTEGER DEFAULT 1
        )
        ''')
        
        # Voice activity tracking
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS voice_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            guild_id INTEGER NOT NULL,
            start_time TIMESTAMP NOT NULL,
            end_time TIMESTAMP,
            duration INTEGER  -- Duration in seconds
        )
        ''')
        
        # Indices for faster queries
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_message_user ON message_stats (user_id, timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_message_channel ON message_stats (channel_id, timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_voice_user ON voice_stats (user_id, start_time)')
        
        conn.commit()
        conn.close()
    
    def record_message(self, user_id, channel_id, guild_id, timestamp=None):
        """Record a message sent by a user"""
        if timestamp is None:
            timestamp = datetime.now()
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            'INSERT INTO message_stats (user_id, channel_id, guild_id, timestamp) VALUES (?, ?, ?, ?)',
            (user_id, channel_id, guild_id, timestamp)
        )
        
        conn.commit()
        conn.close()
    
    def record_voice_join(self, user_id, channel_id, guild_id, timestamp=None):
        """Record when a user joins a voice channel"""
        if timestamp is None:
            timestamp = datetime.now()
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            'INSERT INTO voice_stats (user_id, channel_id, guild_id, start_time) VALUES (?, ?, ?, ?)',
            (user_id, channel_id, guild_id, timestamp)
        )
        
        conn.commit()
        conn.close()
        return cursor.lastrowid
    
    def record_voice_leave(self, entry_id, timestamp=None):
        """Record when a user leaves a voice channel"""
        if timestamp is None:
            timestamp = datetime.now()
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get the start time
        cursor.execute('SELECT start_time FROM voice_stats WHERE id = ?', (entry_id,))
        result = cursor.fetchone()
        
        if result:
            start_time = datetime.fromisoformat(result[0])
            duration = int((timestamp - start_time).total_seconds())
            
            cursor.execute(
                'UPDATE voice_stats SET end_time = ?, duration = ? WHERE id = ?',
                (timestamp, duration, entry_id)
            )
            
        conn.commit()
        conn.close()
    
    def get_message_count(self, user_id, guild_id, start_date=None, end_date=None):
        """Get message count for a user within a date range"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = 'SELECT COUNT(*) FROM message_stats WHERE user_id = ? AND guild_id = ?'
        params = [user_id, guild_id]
        
        if start_date:
            query += ' AND timestamp >= ?'
            params.append(start_date)
        
        if end_date:
            query += ' AND timestamp <= ?'
            params.append(end_date)
        
        cursor.execute(query, params)
        count = cursor.fetchone()[0]
        
        conn.close()
        return count
    
    def get_voice_duration(self, user_id, guild_id, start_date=None, end_date=None):
        """Get total voice chat duration for a user within a date range"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = 'SELECT SUM(duration) FROM voice_stats WHERE user_id = ? AND guild_id = ? AND duration IS NOT NULL'
        params = [user_id, guild_id]
        
        if start_date:
            query += ' AND start_time >= ?'
            params.append(start_date)
        
        if end_date:
            query += ' AND end_time <= ?'
            params.append(end_date)
        
        cursor.execute(query, params)
        result = cursor.fetchone()[0]
        
        conn.close()
        return result or 0  # Return 0 if no voice activity
    
    def get_top_channels(self, user_id, guild_id, limit=5, start_date=None, end_date=None):
        """Get user's top channels by message count"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = '''
        SELECT channel_id, COUNT(*) as message_count 
        FROM message_stats 
        WHERE user_id = ? AND guild_id = ?
        '''
        params = [user_id, guild_id]
        
        if start_date:
            query += ' AND timestamp >= ?'
            params.append(start_date)
        
        if end_date:
            query += ' AND timestamp <= ?'
            params.append(end_date)
        
        query += ' GROUP BY channel_id ORDER BY message_count DESC LIMIT ?'
        params.append(limit)
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        
        conn.close()
        return results
    
    def get_message_history(self, user_id, guild_id, days=30, custom_start=None, custom_end=None):
        """Get daily message counts for chart data with optional custom date range"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Calculate the date range
        if custom_start and custom_end:
            start_date = custom_start
            end_date = custom_end
        else:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
        
        # Query to get daily message counts
        query = '''
        SELECT date(timestamp) as day, COUNT(*) as count
        FROM message_stats
        WHERE user_id = ? AND guild_id = ? AND timestamp >= ? AND timestamp <= ?
        GROUP BY day
        ORDER BY day ASC
        '''
        
        cursor.execute(query, (user_id, guild_id, start_date, end_date))
        results = cursor.fetchall()
        
        conn.close()
        
        # Convert to dict with all days (including zeros)
        day_counts = {}
        current_date = start_date
        while current_date <= end_date:
            day_str = current_date.strftime('%Y-%m-%d')
            day_counts[day_str] = 0
            current_date += timedelta(days=1)
        
        # Fill in actual counts
        for day, count in results:
            day_counts[day] = count
        
        return day_counts
    
    def get_voice_history(self, user_id, guild_id, days=30, custom_start=None, custom_end=None):
        """Get daily voice duration for chart data with optional custom date range"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Calculate the date range
        if custom_start and custom_end:
            start_date = custom_start
            end_date = custom_end
        else:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
        
        # Query to get daily voice durations
        query = '''
        SELECT date(start_time) as day, SUM(duration)/3600.0 as hours
        FROM voice_stats
        WHERE user_id = ? AND guild_id = ? AND start_time >= ? AND end_time <= ? AND duration IS NOT NULL
        GROUP BY day
        ORDER BY day ASC
        '''
        
        cursor.execute(query, (user_id, guild_id, start_date, end_date))
        results = cursor.fetchall()
        
        conn.close()
        
        # Convert to dict with all days (including zeros)
        day_hours = {}
        current_date = start_date
        while current_date <= end_date:
            day_str = current_date.strftime('%Y-%m-%d')
            day_hours[day_str] = 0
            current_date += timedelta(days=1)
        
        # Fill in actual hours
        for day, hours in results:
            day_hours[day] = hours
        
        return day_hours
        
    def get_message_rank(self, user_id, guild_id, start_date=None, end_date=None):
        """Get user's message rank in the guild"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # First, get all user message counts
        query = '''
        SELECT user_id, COUNT(*) as message_count
        FROM message_stats
        WHERE guild_id = ?
        '''
        params = [guild_id]
        
        if start_date:
            query += ' AND timestamp >= ?'
            params.append(start_date)
        
        if end_date:
            query += ' AND timestamp <= ?'
            params.append(end_date)
        
        query += ' GROUP BY user_id ORDER BY message_count DESC'
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        
        # Find user's rank
        rank = "#0"
        for i, (uid, count) in enumerate(results, 1):
            if uid == user_id:
                rank = f"#{i}"
                break
        
        conn.close()
        return rank
        
    def get_voice_rank(self, user_id, guild_id, start_date=None, end_date=None):
        """Get user's voice rank in the guild"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # First, get all user voice durations
        query = '''
        SELECT user_id, SUM(duration) as voice_time
        FROM voice_stats
        WHERE guild_id = ? AND duration IS NOT NULL
        '''
        params = [guild_id]
        
        if start_date:
            query += ' AND start_time >= ?'
            params.append(start_date)
        
        if end_date:
            query += ' AND end_time <= ?'
            params.append(end_date)
        
        query += ' GROUP BY user_id ORDER BY voice_time DESC'
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        
        # Find user's rank
        rank = "#0"
        for i, (uid, duration) in enumerate(results, 1):
            if uid == user_id:
                rank = f"#{i}"
                break
        
        conn.close()
        return rank

class StatsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = StatsDB()
        self.voice_sessions = {}  # Track active voice sessions: {(user_id, guild_id): entry_id}
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Record message statistics"""
        # Skip bot messages
        if message.author.bot:
            return
            
        # Record the message
        self.db.record_message(
            message.author.id,
            message.channel.id,
            message.guild.id if message.guild else 0
        )
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Track voice channel activity"""
        # Skip bots
        if member.bot:
            return
            
        user_id = member.id
        guild_id = member.guild.id
        user_key = (user_id, guild_id)
        
        # User joined a voice channel
        if before.channel is None and after.channel is not None:
            entry_id = self.db.record_voice_join(user_id, after.channel.id, guild_id)
            self.voice_sessions[user_key] = entry_id
            
        # User left a voice channel
        elif before.channel is not None and after.channel is None:
            if user_key in self.voice_sessions:
                entry_id = self.voice_sessions.pop(user_key)
                self.db.record_voice_leave(entry_id)
                
        # User switched voice channels
        elif before.channel != after.channel:
            # Record leaving the old channel
            if user_key in self.voice_sessions:
                entry_id = self.voice_sessions.pop(user_key)
                self.db.record_voice_leave(entry_id)
            
            # Record joining the new channel
            entry_id = self.db.record_voice_join(user_id, after.channel.id, guild_id)
            self.voice_sessions[user_key] = entry_id
    
    @app_commands.command(name="stats", description="Display user activity statistics")
    @app_commands.describe(
        user="User to show stats for (defaults to yourself)",
        start_date="Start date (format: YYYY-MM-DD)",
        end_date="End date (format: YYYY-MM-DD)",
        days="Number of days to look back (7, 30, 90, or 'all') - ignored if dates specified",
        timezone="Timezone for the report (default: UTC)"
    )
    @app_commands.choices(days=[
        app_commands.Choice(name="7 days", value="7"),
        app_commands.Choice(name="30 days", value="30"),
        app_commands.Choice(name="90 days", value="90"),
        app_commands.Choice(name="All time", value="all")
    ])
    async def stats_command(
        self, 
        interaction: discord.Interaction, 
        user: Optional[discord.Member] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days: Optional[Literal["7", "30", "90", "all"]] = "30",
        timezone: Optional[str] = "UTC"
    ):
        await interaction.response.defer()
        
        # Use the command invoker if no user is specified
        target_user = user or interaction.user
        guild = interaction.guild
        
        try:
            # Calculate date range based on specific dates or days parameter
            if start_date and end_date:
                try:
                    # Parse the provided dates
                    start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
                    end_date_obj = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1) - timedelta(seconds=1)  # Include entire end date (23:59:59)
                    lookback_days = (end_date_obj - start_date_obj).days + 1
                except ValueError:
                    await interaction.followup.send("Invalid date format. Please use YYYY-MM-DD (e.g., 2023-12-31)")
                    return
            else:
                # Use days parameter
                if days.lower() == "all":
                    lookback_days = 365  # Use a year as "all" for practicality
                else:
                    lookback_days = int(days)
                
                # Calculate date range
                end_date_obj = datetime.now()
                start_date_obj = end_date_obj - timedelta(days=lookback_days)
            
            # Get message counts for different time periods
            day_count = self.db.get_message_count(
                target_user.id, guild.id, 
                end_date_obj - timedelta(days=1), end_date_obj
            )
            
            week_count = self.db.get_message_count(
                target_user.id, guild.id, 
                end_date_obj - timedelta(days=7), end_date_obj
            )
            
            month_count = self.db.get_message_count(
                target_user.id, guild.id, 
                end_date_obj - timedelta(days=30), end_date_obj
            )
            
            # Get voice durations for different time periods
            day_voice = self.db.get_voice_duration(
                target_user.id, guild.id, 
                end_date_obj - timedelta(days=1), end_date_obj
            )
            
            week_voice = self.db.get_voice_duration(
                target_user.id, guild.id, 
                end_date_obj - timedelta(days=7), end_date_obj
            )
            
            month_voice = self.db.get_voice_duration(
                target_user.id, guild.id, 
                end_date_obj - timedelta(days=30), end_date_obj
            )
            
            # Convert voice seconds to hours
            day_voice_hours = day_voice / 3600
            week_voice_hours = week_voice / 3600
            month_voice_hours = month_voice / 3600
            
            # Get top channels
            top_channels_raw = self.db.get_top_channels(
                target_user.id, guild.id,
                limit=5, start_date=start_date_obj, end_date=end_date_obj
            )
            
            # Format top channels data
            top_channels = []
            for channel_id, msg_count in top_channels_raw:
                channel = guild.get_channel(channel_id)
                if channel:
                    channel_name = channel.name
                    top_channels.append((channel_name, msg_count))
                else:
                    top_channels.append((f"Unknown ({channel_id})", msg_count))
            
            # Get message and voice history for chart
            if start_date and end_date:
                message_history = self.db.get_message_history(target_user.id, guild.id, 
                                                          custom_start=start_date_obj, custom_end=end_date_obj)
                voice_history = self.db.get_voice_history(target_user.id, guild.id, 
                                                       custom_start=start_date_obj, custom_end=end_date_obj)
            else:
                message_history = self.db.get_message_history(target_user.id, guild.id, lookback_days)
                voice_history = self.db.get_voice_history(target_user.id, guild.id, lookback_days)
                
            # Get rank information
            message_rank = self.db.get_message_rank(
                target_user.id, guild.id, 
                start_date=start_date_obj, end_date=end_date_obj
            )
            
            voice_rank = self.db.get_voice_rank(
                target_user.id, guild.id, 
                start_date=start_date_obj, end_date=end_date_obj
            )
            
            # Prepare data for the image generator
            stats_data = {
                'message_day': day_count,
                'message_week': week_count,
                'message_month': month_count,
                'voice_day': day_voice_hours,
                'voice_week': week_voice_hours,
                'voice_month': month_voice_hours,
                'server_rank': "#1",  # Placeholder, replace with actual server rank if needed
                'message_rank': message_rank,
                'voice_rank': voice_rank,
                'top_channels': top_channels[:5],
                'message_history': message_history,
                'voice_history': voice_history,
                'start_date': start_date_obj,
                'end_date': end_date_obj,
                'lookback_days': lookback_days,
                'timezone': timezone
            }
            
            # Generate the enhanced Cairo stats image
            stats_image = await generate_cairo_stats(target_user, guild, stats_data)
            
            # Create minimal embed to go with the image
            if start_date and end_date:
                date_desc = f"Activity from {start_date_obj.strftime('%b %d, %Y')} to {end_date_obj.strftime('%b %d, %Y')}"
            else:
                date_desc = f"Last {lookback_days} days of activity"
                
            embed = discord.Embed(
                title=f"Activity Statistics for {target_user.display_name}",
                description=date_desc,
                color=discord.Color.blue()
            )
            
            # Send the image with minimal embed
            file = discord.File(stats_image, filename="stats.png")
            embed.set_image(url="attachment://stats.png")
            
            await interaction.followup.send(embed=embed, file=file)
            
        except Exception as e:
            logger.error(f"Error generating stats: {e}", exc_info=True)
            await interaction.followup.send(f"Error generating statistics: {str(e)}")
    
    @app_commands.command(name="clear_stats", description="Clear statistics data")
    @app_commands.describe(
        target="What statistics to clear",
        user="User to clear stats for (admin only, defaults to yourself)",
        start_date="Start date to clear from (format: YYYY-MM-DD)",
        end_date="End date to clear to (format: YYYY-MM-DD)"
    )
    async def clear_stats(
        self, 
        interaction: discord.Interaction,
        target: Literal["messages", "voice", "all"],
        user: Optional[discord.Member] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ):
        # Check permissions if trying to clear another user's stats
        if user and user.id != interaction.user.id:
            if not has_required_role(interaction.user, CONFIG['REQUIRED_ROLES']):
                await interaction.response.send_message(
                    "You don't have permission to clear other users' statistics.",
                    ephemeral=True
                )
                return
        
        # Use command invoker if no user specified
        target_user = user or interaction.user
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Parse date range if provided
            date_filter = ""
            params = [target_user.id]
            
            if start_date and end_date:
                try:
                    # Parse the provided dates
                    parsed_start = datetime.strptime(start_date, "%Y-%m-%d")
                    parsed_end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1) - timedelta(seconds=1)
                    date_filter = " AND timestamp BETWEEN ? AND ?"
                    params.extend([parsed_start, parsed_end])
                except ValueError:
                    await interaction.followup.send("Invalid date format. Please use YYYY-MM-DD (e.g., 2023-12-31)", ephemeral=True)
                    return
            
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            if target == "messages" or target == "all":
                cursor.execute(
                    f"DELETE FROM message_stats WHERE user_id = ?{date_filter}",
                    params
                )
            
            if target == "voice" or target == "all":
                # For voice stats, we check overlap with the date range
                voice_params = [target_user.id]
                voice_filter = ""
                
                if start_date and end_date:
                    voice_filter = " AND (start_time BETWEEN ? AND ? OR end_time BETWEEN ? AND ?)"
                    voice_params.extend([parsed_start, parsed_end, parsed_start, parsed_end])
                
                cursor.execute(
                    f"DELETE FROM voice_stats WHERE user_id = ?{voice_filter}",
                    voice_params
                )
                
            conn.commit()
            conn.close()
            
            # Create success message
            if start_date and end_date:
                await interaction.followup.send(
                    f"Successfully cleared {target} statistics for {target_user.display_name} between {start_date} and {end_date}.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"Successfully cleared all {target} statistics for {target_user.display_name}.",
                    ephemeral=True
                )
            
        except Exception as e:
            logger.error(f"Error clearing stats: {e}")
            await interaction.followup.send(f"Error clearing statistics: {str(e)}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(StatsCog(bot))