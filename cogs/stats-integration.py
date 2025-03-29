import discord
from discord.ext import commands
from discord import app_commands, File
import logging
import asyncio
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from config import CONFIG
from utils.helpers import has_required_role
from utils.enhanced_stats_visualization import generate_cairo_stats, create_activity_chart, create_channels_chart
from utils.comparison_charts import create_comparison_chart, create_activity_heatmap, create_radar_comparison, create_bar_comparison

logger = logging.getLogger('badgey.StatsIntegration')

class StatsIntegrationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @app_commands.command(name="activity_heatmap", description="View your activity patterns by time of day and day of week")
    @app_commands.guild_only()
    @app_commands.describe(
        user="User to show activity heatmap for (defaults to yourself)",
        days="Number of days to analyze (default: 30)"
    )
    async def activity_heatmap_command(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None,
        days: Optional[int] = 30
    ):
        """Display a heatmap of user activity patterns"""
        await interaction.response.defer()
        
        # Default to command invoker
        target_user = user or interaction.user
        
        # Limit days to reasonable values
        days = min(max(7, days), 180)
        
        try:
            from cogs.stats import StatsDB
            stats_db = StatsDB()
            
            # Get raw activity data with timestamps
            # Note: This requires a new method in StatsDB that returns timestamp data
            # For example:
            # activity_data = stats_db.get_activity_timestamps(target_user.id, interaction.guild.id, days)
            
            # Since we need to modify the StatsDB class to support this new feature,
            # we'll use placeholder data for now
            # In a real implementation, we would return a list of timestamp tuples from the database
            
            # Create a placeholder description
            embed = discord.Embed(
                title=f"Activity Patterns for {target_user.display_name}",
                description=f"This command requires an update to the database schema to track message timestamps.\n\nOnce implemented, it will show when {target_user.display_name} is most active during the week.",
                color=discord.Color.blue()
            )
            
            await interaction.followup.send(embed=embed)
            
        except ImportError:
            await interaction.followup.send(
                "Stats tracking module is not available. Please contact an administrator.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error generating activity heatmap: {e}")
            await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)
            
    @app_commands.command(name="detailed_compare", description="Perform a detailed activity comparison between two users")
    @app_commands.guild_only()
    @app_commands.describe(
        user1="First user to compare",
        user2="Second user to compare (defaults to yourself)",
        days="Number of days to include in comparison (7-180)"
    )
    async def activity_heatmap_command(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None,
        days: Optional[int] = 30
    ):
        """Display a heatmap of user activity patterns"""
        await interaction.response.defer()
        
        # Default to command invoker
        target_user = user or interaction.user
        
        # Limit days to reasonable values
        days = min(max(7, days), 180)
        
        try:
            from cogs.stats import StatsDB
            stats_db = StatsDB()
            
            # Get raw activity data with timestamps
            # Note: This requires a new method in StatsDB that returns timestamp data
            # For example:
            # activity_data = stats_db.get_activity_timestamps(target_user.id, interaction.guild.id, days)
            
            # Since we need to modify the StatsDB class to support this new feature,
            # we'll use placeholder data for now
            # In a real implementation, we would return a list of timestamp tuples from the database
            
            # Create a placeholder description
            embed = discord.Embed(
                title=f"Activity Patterns for {target_user.display_name}",
                description=f"This command requires an update to the database schema to track message timestamps.\n\nOnce implemented, it will show when {target_user.display_name} is most active during the week.",
                color=discord.Color.blue()
            )
            
            await interaction.followup.send(embed=embed)
            
        except ImportError:
            await interaction.followup.send(
                "Stats tracking module is not available. Please contact an administrator.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error generating activity heatmap: {e}")
            await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)
    
    @app_commands.command(name="profile", description="Show a user's detailed profile with activity visualization")
    @app_commands.guild_only()
    @app_commands.describe(
        user1="First user to compare",
        user2="Second user to compare (defaults to yourself)",
        days="Number of days to include in comparison (7-180)"
    )
    async def detailed_compare_command(
        self,
        interaction: discord.Interaction,
        user1: discord.Member,
        user2: Optional[discord.Member] = None,
        days: Optional[int] = 30
    ):
        """Provides a detailed comparison between two users with multiple visualizations"""
        await interaction.response.defer()
        
        # Default second user to command invoker
        user2 = user2 or interaction.user
        
        # Ensure we're not comparing the same user
        if user1.id == user2.id:
            await interaction.followup.send("You can't compare a user with themselves.", ephemeral=True)
            return
        
        # Limit days to reasonable values
        days = min(max(7, days), 180)
        
        try:
            from cogs.stats import StatsDB
            stats_db = StatsDB()
            
            # Get message and voice data for both users
            user1_messages = stats_db.get_message_history(user1.id, interaction.guild.id, days)
            user1_voice = stats_db.get_voice_history(user1.id, interaction.guild.id, days)
            
            user2_messages = stats_db.get_message_history(user2.id, interaction.guild.id, days)
            user2_voice = stats_db.get_voice_history(user2.id, interaction.guild.id, days)
            
            # Get top channels for both users
            user1_channels = stats_db.get_top_channels(
                user1.id, interaction.guild.id, limit=5
            )
            
            user2_channels = stats_db.get_top_channels(
                user2.id, interaction.guild.id, limit=5
            )
            
            # Calculate detailed statistics
            user1_msg_total = sum(user1_messages.values())
            user2_msg_total = sum(user2_messages.values())
            
            user1_voice_total = sum(user1_voice.values())
            user2_voice_total = sum(user2_voice.values())
            
            user1_active_msg_days = sum(1 for count in user1_messages.values() if count > 0)
            user2_active_msg_days = sum(1 for count in user2_messages.values() if count > 0)
            
            user1_active_voice_days = sum(1 for hours in user1_voice.values() if hours > 0)
            user2_active_voice_days = sum(1 for hours in user2_voice.values() if hours > 0)
            
            user1_avg_msgs = user1_msg_total / max(user1_active_msg_days, 1)
            user2_avg_msgs = user2_msg_total / max(user2_active_msg_days, 1)
            
            user1_avg_voice = user1_voice_total / max(user1_active_voice_days, 1)
            user2_avg_voice = user2_voice_total / max(user2_active_voice_days, 1)
            
            # Create the initial embed with summary
            embed = discord.Embed(
                title=f"Detailed Comparison: {user1.display_name} vs {user2.display_name}",
                description=f"Analysis over the last {days} days",
                color=discord.Color.blue()
            )
            
            # Add summary statistics to the embed
            embed.add_field(
                name=f"{user1.display_name}",
                value=f"Messages: **{user1_msg_total}**\n"
                      f"Voice: **{user1_voice_total:.1f}h**\n"
                      f"Active days: **{user1_active_msg_days}/{days}**\n"
                      f"Avg msgs/day: **{user1_avg_msgs:.1f}**",
                inline=True
            )
            
            embed.add_field(
                name=f"{user2.display_name}",
                value=f"Messages: **{user2_msg_total}**\n"
                      f"Voice: **{user2_voice_total:.1f}h**\n"
                      f"Active days: **{user2_active_msg_days}/{days}**\n"
                      f"Avg msgs/day: **{user2_avg_msgs:.1f}**",
                inline=True
            )
            
            # Calculate percentage differences
            diff_msgs = ((user1_msg_total / max(user2_msg_total, 1)) - 1) * 100
            diff_voice = ((user1_voice_total / max(user2_voice_total, 1)) - 1) * 100
            diff_active = ((user1_active_msg_days / max(user2_active_msg_days, 1)) - 1) * 100
            diff_avg = ((user1_avg_msgs / max(user2_avg_msgs, 1)) - 1) * 100
            
            # Format the differences with arrows
            diff_msgs_str = f"↑ {diff_msgs:.1f}%" if diff_msgs > 0 else f"↓ {abs(diff_msgs):.1f}%"
            diff_voice_str = f"↑ {diff_voice:.1f}%" if diff_voice > 0 else f"↓ {abs(diff_voice):.1f}%"
            diff_active_str = f"↑ {diff_active:.1f}%" if diff_active > 0 else f"↓ {abs(diff_active):.1f}%"
            diff_avg_str = f"↑ {diff_avg:.1f}%" if diff_avg > 0 else f"↓ {abs(diff_avg):.1f}%"
            
            embed.add_field(
                name="Differences",
                value=f"Messages: **{diff_msgs_str}**\n"
                      f"Voice: **{diff_voice_str}**\n"
                      f"Active days: **{diff_active_str}**\n"
                      f"Avg msgs/day: **{diff_avg_str}**",
                inline=True
            )
            
            # Add avatars
            embed.set_thumbnail(url=user1.display_avatar.url)
            
            # Create the comparison charts
            # Message activity chart
            msg_chart = create_comparison_chart(
                user1_messages, user2_messages,
                user1.display_name, user2.display_name,
                metric_type='messages',
                width=800,
                height=400
            )
            
            # Send the initial embed with message chart
            msg_file = discord.File(msg_chart, filename="message_comparison.png")
            embed.set_image(url="attachment://message_comparison.png")
            await interaction.followup.send(embed=embed, file=msg_file)
            
            # Create and send the radar chart
            categories = ["Messages", "Voice Hours", "Daily Messages",
                         "Daily Voice", "Activity Rate", "Channel Diversity"]
            
            # Normalize values for radar chart
            max_msg = max(user1_msg_total, user2_msg_total, 1)
            max_voice = max(user1_voice_total, user2_voice_total, 1)
            max_daily_msg = max(user1_avg_msgs, user2_avg_msgs, 1)
            max_daily_voice = max(user1_avg_voice, user2_avg_voice, 1)
            
            # Calculate channel diversity (unique channels with activity)
            user1_channels_count = len(user1_channels)
            user2_channels_count = len(user2_channels)
            max_channels = max(user1_channels_count, user2_channels_count, 1)
            
            # Activity rate (active days / total days)
            user1_activity_rate = user1_active_msg_days / days
            user2_activity_rate = user2_active_msg_days / days
            
            user1_values = [
                user1_msg_total / max_msg * 100,
                user1_voice_total / max_voice * 100,
                user1_avg_msgs / max_daily_msg * 100,
                user1_avg_voice / max_daily_voice * 100,
                user1_activity_rate * 100,
                user1_channels_count / max_channels * 100
            ]
            
            user2_values = [
                user2_msg_total / max_msg * 100,
                user2_voice_total / max_voice * 100,
                user2_avg_msgs / max_daily_msg * 100,
                user2_avg_voice / max_daily_voice * 100,
                user2_activity_rate * 100,
                user2_channels_count / max_channels * 100
            ]
            
            radar_chart = create_radar_comparison(
                user1_values, user2_values,
                user1.display_name, user2.display_name,
                categories,
                width=600,
                height=500
            )
            
            # Create radar embed
            radar_embed = discord.Embed(
                title=f"Activity Metrics Comparison",
                description=f"Normalized comparison of activity metrics",
                color=discord.Color.gold()
            )
            
            radar_file = discord.File(radar_chart, filename="radar_chart.png")
            radar_embed.set_image(url="attachment://radar_chart.png")
            
            # Send the radar chart
            await interaction.followup.send(embed=radar_embed, file=radar_file)
            
            # Create a bar chart for channel comparison
            # Merge channels from both users, keeping top 5
            all_channels = {}
            
            for channel, count in user1_channels:
                channel_name = channel if len(channel) <= 10 else channel[:8] + "..."
                if channel_name not in all_channels:
                    all_channels[channel_name] = [count, 0]  # [user1_count, user2_count]
                else:
                    all_channels[channel_name][0] = count
            
            for channel, count in user2_channels:
                channel_name = channel if len(channel) <= 10 else channel[:8] + "..."
                if channel_name not in all_channels:
                    all_channels[channel_name] = [0, count]  # [user1_count, user2_count]
                else:
                    all_channels[channel_name][1] = count
            
            # Sort by total activity and take top 6
            top_channels = sorted(all_channels.items(), key=lambda x: sum(x[1]), reverse=True)[:6]
            
            # Prepare data for bar chart
            channel_names = [c[0] for c in top_channels]
            user1_counts = [c[1][0] for c in top_channels]
            user2_counts = [c[1][1] for c in top_channels]
            
            # Create the bar chart
            bar_chart = create_bar_comparison(
                user1_counts, user2_counts,
                user1.display_name, user2.display_name,
                channel_names,
                title="Top Channels Comparison",
                width=800,
                height=400
            )
            
            # Create bar chart embed
            bar_embed = discord.Embed(
                title=f"Channel Activity Comparison",
                description=f"Message counts in top channels",
                color=discord.Color.green()
            )
            
            bar_file = discord.File(bar_chart, filename="channel_comparison.png")
            bar_embed.set_image(url="attachment://channel_comparison.png")
            
            # Send the bar chart
            await interaction.followup.send(embed=bar_embed, file=bar_file)
            
        except ImportError:
            await interaction.followup.send(
                "Stats tracking module is not available. Please contact an administrator.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error in detailed compare command: {e}")
            await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)
    @app_commands.describe(
        user="User to show profile for (defaults to yourself)",
        days="Number of days to look back (7, 30, 90, or 'all')",
        timezone="Timezone for the report (default: UTC)"
    )
    @app_commands.choices(days=[
        app_commands.Choice(name="7 days", value="7"),
        app_commands.Choice(name="30 days", value="30"),
        app_commands.Choice(name="90 days", value="90"),
        app_commands.Choice(name="All time", value="all")
    ])
    async def profile_command(
        self, 
        interaction: discord.Interaction, 
        user: Optional[discord.Member] = None,
        days: Optional[str] = "30",
        timezone: Optional[str] = "UTC"
    ):
        """Display a user's complete profile with enhanced visualizations"""
        await interaction.response.defer()
        
        # Default to command invoker if no user specified
        target_user = user or interaction.user
        
        try:
            from cogs.stats import StatsDB
            
            # Initialize DB
            stats_db = StatsDB()
            
            # Calculate lookback days
            if days.lower() == "all":
                lookback_days = 365  # Cap at a year for practicality
            else:
                lookback_days = int(days)
            
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=lookback_days)
            
            # Get message counts
            day_count = stats_db.get_message_count(
                target_user.id, interaction.guild.id, 
                end_date - timedelta(days=1), end_date
            )
            
            week_count = stats_db.get_message_count(
                target_user.id, interaction.guild.id, 
                end_date - timedelta(days=7), end_date
            )
            
            month_count = stats_db.get_message_count(
                target_user.id, interaction.guild.id, 
                end_date - timedelta(days=30), end_date
            )
            
            # Get voice durations
            day_voice = stats_db.get_voice_duration(
                target_user.id, interaction.guild.id, 
                end_date - timedelta(days=1), end_date
            )
            
            week_voice = stats_db.get_voice_duration(
                target_user.id, interaction.guild.id, 
                end_date - timedelta(days=7), end_date
            )
            
            month_voice = stats_db.get_voice_duration(
                target_user.id, interaction.guild.id, 
                end_date - timedelta(days=30), end_date
            )
            
            # Convert to hours
            day_voice_hours = day_voice / 3600
            week_voice_hours = week_voice / 3600
            month_voice_hours = month_voice / 3600
            
            # Get top channels
            top_channels = stats_db.get_top_channels(
                target_user.id, interaction.guild.id,
                limit=5, start_date=start_date, end_date=end_date
            )
            
            # Get message and voice history
            message_history = stats_db.get_message_history(
                target_user.id, interaction.guild.id, lookback_days
            )
            
            voice_history = stats_db.get_voice_history(
                target_user.id, interaction.guild.id, lookback_days
            )
            
            # Get rank info
            message_rank = stats_db.get_message_rank(
                target_user.id, interaction.guild.id, 
                start_date=start_date, end_date=end_date
            )
            
            voice_rank = stats_db.get_voice_rank(
                target_user.id, interaction.guild.id, 
                start_date=start_date, end_date=end_date
            )
            
            # Compile stats data
            stats_data = {
                'message_day': day_count,
                'message_week': week_count,
                'message_month': month_count,
                'voice_day': day_voice_hours,
                'voice_week': week_voice_hours,
                'voice_month': month_voice_hours,
                'message_rank': message_rank,
                'voice_rank': voice_rank,
                'top_channels': top_channels[:5],
                'message_history': message_history,
                'voice_history': voice_history,
                'start_date': start_date,
                'end_date': end_date,
                'lookback_days': lookback_days,
                'timezone': timezone
            }
            
            # Generate the enhanced profile image
            profile_image = await generate_cairo_stats(target_user, interaction.guild, stats_data)
            
            # Create minimal embed
            date_desc = f"Activity from {start_date.strftime('%b %d, %Y')} to {end_date.strftime('%b %d, %Y')}"
            
            embed = discord.Embed(
                title=f"Profile & Activity for {target_user.display_name}",
                description=date_desc,
                color=discord.Color.blue()
            )
            
            # Send the profile
            file = discord.File(profile_image, filename="profile.png")
            embed.set_image(url="attachment://profile.png")
            
            await interaction.followup.send(embed=embed, file=file)
            
        except ImportError:
            await interaction.followup.send(
                "Stats tracking module is not properly installed. Please contact an administrator.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error generating profile: {e}", exc_info=True)
            await interaction.followup.send(f"Error generating profile: {str(e)}")
    
    @app_commands.command(name="compare", description="Compare activity between two users")
    @app_commands.guild_only()
    @app_commands.describe(
        user1="First user to compare",
        user2="Second user to compare (defaults to yourself)",
        days="Number of days to include in comparison"
    )
    async def compare_command(
        self,
        interaction: discord.Interaction,
        user1: discord.Member,
        user2: Optional[discord.Member] = None,
        days: Optional[int] = 30
    ):
        """Compare activity statistics between two users"""
        await interaction.response.defer()
        
        # Default second user to command invoker
        user2 = user2 or interaction.user
        
        # Ensure we're not comparing the same user
        if user1.id == user2.id:
            await interaction.followup.send("You can't compare a user with themselves.", ephemeral=True)
            return
        
        # Limit days to reasonable values
        days = min(max(7, days), 180)
        
        try:
            from cogs.stats import StatsDB
            stats_db = StatsDB()
            
            # Get message and voice data for both users
            user1_messages = stats_db.get_message_history(user1.id, interaction.guild.id, days)
            user1_voice = stats_db.get_voice_history(user1.id, interaction.guild.id, days)
            
            user2_messages = stats_db.get_message_history(user2.id, interaction.guild.id, days)
            user2_voice = stats_db.get_voice_history(user2.id, interaction.guild.id, days)
            
            # Calculate combined statistics
            user1_msg_total = sum(user1_messages.values())
            user2_msg_total = sum(user2_messages.values())
            
            user1_voice_total = sum(user1_voice.values())
            user2_voice_total = sum(user2_voice.values())
            
            # Create comparison embed
            embed = discord.Embed(
                title=f"Activity Comparison: {user1.display_name} vs {user2.display_name}",
                description=f"Comparison over the last {days} days",
                color=discord.Color.gold()
            )
            
            # Add message comparison
            embed.add_field(
                name="Messages",
                value=f"{user1.mention}: **{user1_msg_total}**\n{user2.mention}: **{user2_msg_total}**",
                inline=True
            )
            
            # Add voice comparison
            embed.add_field(
                name="Voice Hours",
                value=f"{user1.mention}: **{user1_voice_total:.1f}**\n{user2.mention}: **{user2_voice_total:.1f}**",
                inline=True
            )
            
            # Create activity visualization
            # We'll create separate charts for messages and voice activity
            
            # Get message ranks
            user1_msg_rank = stats_db.get_message_rank(user1.id, interaction.guild.id)
            user2_msg_rank = stats_db.get_message_rank(user2.id, interaction.guild.id)
            
            embed.add_field(
                name="Message Rank",
                value=f"{user1.mention}: {user1_msg_rank}\n{user2.mention}: {user2_msg_rank}",
                inline=True
            )
            
            # Create categories for the radar chart
            categories = ["Messages", "Voice Hours", "Average Daily Messages",
                        "Average Voice Hours", "Active Message Days", "Active Voice Days"]
            
            # Calculate values for each category
            user1_active_msg_days = sum(1 for count in user1_messages.values() if count > 0)
            user2_active_msg_days = sum(1 for count in user2_messages.values() if count > 0)
            
            user1_active_voice_days = sum(1 for hours in user1_voice.values() if hours > 0)
            user2_active_voice_days = sum(1 for hours in user2_voice.values() if hours > 0)
            
            # Scale values to be comparable on radar chart
            user1_values = [
                user1_msg_total / max(user1_msg_total, user2_msg_total, 1) * 100,
                user1_voice_total / max(user1_voice_total, user2_voice_total, 1) * 100,
                (user1_msg_total / max(days, 1)) / max(user1_msg_total/max(days, 1), user2_msg_total/max(days, 1), 1) * 100,
                (user1_voice_total / max(days, 1)) / max(user1_voice_total/max(days, 1), user2_voice_total/max(days, 1), 1) * 100,
                user1_active_msg_days / max(days, 1) * 100,
                user1_active_voice_days / max(days, 1) * 100
            ]
            
            user2_values = [
                user2_msg_total / max(user1_msg_total, user2_msg_total, 1) * 100,
                user2_voice_total / max(user1_voice_total, user2_voice_total, 1) * 100,
                (user2_msg_total / max(days, 1)) / max(user1_msg_total/max(days, 1), user2_msg_total/max(days, 1), 1) * 100,
                (user2_voice_total / max(days, 1)) / max(user1_voice_total/max(days, 1), user2_voice_total/max(days, 1), 1) * 100,
                user2_active_msg_days / max(days, 1) * 100,
                user2_active_voice_days / max(days, 1) * 100
            ]
            
            # Create a radar comparison chart
            radar_chart = create_radar_comparison(
                user1_values, user2_values,
                user1.display_name, user2.display_name,
                categories
            )
            
            # Create a bar chart for key metrics
            bar_categories = ["Total Messages", "Voice Hours", "Active Days"]
            bar_user1 = [user1_msg_total, user1_voice_total, user1_active_msg_days]
            bar_user2 = [user2_msg_total, user2_voice_total, user2_active_msg_days]
            
            bar_chart = create_bar_comparison(
                bar_user1, bar_user2,
                user1.display_name, user2.display_name,
                bar_categories,
                title="Key Metrics Comparison"
            )
            
            # Send message comparison chart
            msg_chart = create_comparison_chart(
                user1_messages, user2_messages,
                user1.display_name, user2.display_name,
                metric_type='messages'
            )
            
            # Create voice comparison chart
            voice_chart = create_comparison_chart(
                user1_voice, user2_voice,
                user1.display_name, user2.display_name,
                metric_type='voice'
            )
            
            # Send the message activity chart as a file attachment
            msg_file = discord.File(msg_chart, filename="message_comparison.png")
            embed.set_image(url="attachment://message_comparison.png")
            comparison_msg = await interaction.followup.send(embed=embed, file=msg_file)
            
            # Create a second embed for the voice chart
            voice_embed = discord.Embed(
                title=f"Voice Activity: {user1.display_name} vs {user2.display_name}",
                description=f"Voice activity over the last {days} days",
                color=discord.Color.purple()
            )
            
            voice_file = discord.File(voice_chart, filename="voice_comparison.png")
            voice_embed.set_image(url="attachment://voice_comparison.png")
            
            # Send the voice activity chart
            await interaction.followup.send(embed=voice_embed, file=voice_file)
            
            # Create a third embed for the radar chart
            radar_embed = discord.Embed(
                title=f"Overall Activity Comparison",
                description=f"Relative activity metrics comparison",
                color=discord.Color.gold()
            )
            
            radar_file = discord.File(radar_chart, filename="radar_comparison.png")
            radar_embed.set_image(url="attachment://radar_comparison.png")
            
            # Send the radar chart
            await interaction.followup.send(embed=radar_embed, file=radar_file)
            
            # Create a fourth embed for the bar chart
            bar_embed = discord.Embed(
                title=f"Key Metrics Comparison",
                description=f"Direct comparison of key activity metrics",
                color=discord.Color.blue()
            )
            
            bar_file = discord.File(bar_chart, filename="bar_comparison.png")
            bar_embed.set_image(url="attachment://bar_comparison.png")
            
            # Send the bar chart
            await interaction.followup.send(embed=bar_embed, file=bar_file)
            embed.set_image(url="attachment://message_comparison.png")
            comparison_msg = await interaction.followup.send(embed=embed, file=msg_file)
            
            # Create a second embed for the voice chart
            voice_embed = discord.Embed(
                title=f"Voice Activity: {user1.display_name} vs {user2.display_name}",
                description=f"Voice activity over the last {days} days",
                color=discord.Color.purple()
            )
            
            voice_file = discord.File(voice_chart, filename="voice_comparison.png")
            voice_embed.set_image(url="attachment://voice_comparison.png")
            
            # Send the voice activity chart
            await interaction.followup.send(embed=voice_embed, file=voice_file)
            
        except ImportError:
            await interaction.followup.send(
                "Stats tracking module is not available. Please contact an administrator.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error in compare command: {e}")
            await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(StatsIntegrationCog(bot))