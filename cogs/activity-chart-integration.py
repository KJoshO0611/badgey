import discord
from discord.ext import commands
from discord import app_commands, File
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import seaborn as sns
import numpy as np
import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta
import logging
from typing import Optional, Dict, List, Tuple, Union, Any
from scipy.interpolate import make_interp_spline
from config import CONFIG
from utils.helpers import has_required_role

# Configure logger
logger = logging.getLogger('badgey.activity_charts')

# Define color scheme to match Discord's dark theme
COLORS = {
    'background': '#2a2a2a',
    'grid': '#3a3a3a',
    'message': '#4CAF50',  # Green for messages
    'voice': '#E91E63',    # Pink for voice
    'text': '#ffffff',     # White for text
    'subtext': '#bbbbbb'   # Light gray for subtext
}

class ActivityChartCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @staticmethod
    def create_activity_chart(
        message_data: Dict[str, int], 
        voice_data: Dict[str, float],
        username: str,
        days: int,
        width: int = 800,
        height: int = 400
    ) -> BytesIO:
        """
        Create a beautiful activity chart using Seaborn
        
        Args:
            message_data: Dictionary mapping dates to message counts
            voice_data: Dictionary mapping dates to voice hours
            username: The username to display in the title
            days: Number of days shown in the chart
            width: Width of the chart in pixels
            height: Height of the chart in pixels
            
        Returns:
            BytesIO: Image buffer containing the chart
        """
        try:
            # Configure style
            sns.set(style="darkgrid")
            plt.style.use("dark_background")
            
            # Convert data to pandas DataFrame for easier plotting
            df = pd.DataFrame({
                'date': list(message_data.keys()),
                'messages': list(message_data.values()),
                'voice_hours': list(voice_data.values())
            })
            
            # Check if we have enough data
            if len(df) < 2:
                return ActivityChartCog.create_fallback_chart(
                    f"Insufficient data for {username}", width, height
                )
            
            # Convert string dates to datetime objects
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            
            # Create the figure with specific size (dpi=100 means 100 pixels per inch)
            fig, ax1 = plt.subplots(figsize=(width/100, height/100), dpi=100)
            fig.patch.set_facecolor(COLORS['background'])
            ax1.set_facecolor(COLORS['background'])
            
            # Set up primary axis for message data
            ax1.grid(color=COLORS['grid'], linestyle='-', linewidth=0.5, alpha=0.7)
            
            # Create dates array for smoothing
            dates_array = np.array([(d - df['date'].min()).days for d in df['date']])
            
            # Smooth the message data if we have enough points
            if len(df) > 5 and sum(df['messages']) > 0:
                try:
                    # Use spline interpolation for smoother curves
                    x_smooth = np.linspace(dates_array.min(), dates_array.max(), 200)
                    message_smooth = make_interp_spline(dates_array, df['messages'])(x_smooth)
                    dates_smooth = df['date'].min() + pd.to_timedelta(x_smooth, unit='D')
                    
                    # Plot the smoothed message line
                    ax1.plot(dates_smooth, message_smooth, color=COLORS['message'], 
                             linewidth=2.5, alpha=0.9, label='Messages')
                    
                    # Add light fill below the line
                    ax1.fill_between(dates_smooth, 0, message_smooth, 
                                    color=COLORS['message'], alpha=0.1)
                except Exception as e:
                    logger.error(f"Error smoothing message data: {e}")
                    # Fallback to regular line if smoothing fails
                    ax1.plot(df['date'], df['messages'], color=COLORS['message'], 
                             linewidth=2.5, alpha=0.9, label='Messages')
            else:
                # Regular line for few data points
                ax1.plot(df['date'], df['messages'], color=COLORS['message'], 
                         linewidth=2.5, alpha=0.9, marker='o', markersize=4, label='Messages')
            
            # Configure y-axis for messages
            ax1.set_ylabel('Messages', color=COLORS['message'], fontweight='bold')
            ax1.tick_params(axis='y', labelcolor=COLORS['message'])
            
            # Set up secondary axis for voice data
            ax2 = ax1.twinx()
            
            # Smooth the voice data if we have enough points
            if len(df) > 5 and sum(df['voice_hours']) > 0:
                try:
                    # Use spline interpolation for voice data
                    x_smooth = np.linspace(dates_array.min(), dates_array.max(), 200)
                    voice_smooth = make_interp_spline(dates_array, df['voice_hours'])(x_smooth)
                    dates_smooth = df['date'].min() + pd.to_timedelta(x_smooth, unit='D')
                    
                    # Plot the smoothed voice line
                    ax2.plot(dates_smooth, voice_smooth, color=COLORS['voice'], 
                             linewidth=2.5, alpha=0.9, label='Voice Hours')
                    
                    # Add light fill below the line
                    ax2.fill_between(dates_smooth, 0, voice_smooth, 
                                    color=COLORS['voice'], alpha=0.1)
                except Exception as e:
                    logger.error(f"Error smoothing voice data: {e}")
                    # Fallback to regular line
                    ax2.plot(df['date'], df['voice_hours'], color=COLORS['voice'], 
                             linewidth=2.5, alpha=0.9, label='Voice Hours')
            else:
                # Regular line for few data points
                ax2.plot(df['date'], df['voice_hours'], color=COLORS['voice'], 
                         linewidth=2.5, alpha=0.9, marker='o', markersize=4, label='Voice Hours')
                         
            # Configure y-axis for voice hours
            ax2.set_ylabel('Voice Hours', color=COLORS['voice'], fontweight='bold')
            ax2.tick_params(axis='y', labelcolor=COLORS['voice'])
            
            # X-axis formatting
            date_format = '%b %d' if days <= 90 else '%b'
            ax1.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter(date_format))
            
            if days > 180:  # > 6 months
                # Use monthly ticks for longer periods
                ax1.xaxis.set_major_locator(plt.matplotlib.dates.MonthLocator())
            elif days > 60:  # 2-6 months
                # Bi-weekly ticks
                ax1.xaxis.set_major_locator(plt.matplotlib.dates.WeekdayLocator(interval=2))
            elif days > 30:  # 1-2 months
                # Weekly ticks
                ax1.xaxis.set_major_locator(plt.matplotlib.dates.WeekdayLocator())
            else:  # < 1 month
                # Show roughly 10 ticks for shorter time ranges
                ax1.xaxis.set_major_locator(plt.matplotlib.dates.DayLocator(interval=max(1, days//10)))
            
            plt.xticks(rotation=30)
            
            # Set tick colors
            for label in ax1.get_xticklabels():
                label.set_color(COLORS['text'])
            
            # Add title
            plt.title(f"Activity for {username} - Last {days} Days", color=COLORS['text'])
            
            # Create custom legend
            legend_elements = [
                plt.Line2D([0], [0], color=COLORS['message'], lw=2, label='Messages'),
                plt.Line2D([0], [0], color=COLORS['voice'], lw=2, label='Voice Hours')
            ]
            ax1.legend(handles=legend_elements, loc='upper right', framealpha=0.3)
            
            # Layout adjustments
            plt.tight_layout()
            
            # Convert figure to bytes
            buf = BytesIO()
            plt.savefig(buf, format='png', facecolor=fig.get_facecolor(), transparent=False, bbox_inches='tight')
            buf.seek(0)
            plt.close(fig)  # Close the figure to prevent memory leaks
            
            return buf
            
        except Exception as e:
            logger.error(f"Error creating activity chart: {e}")
            return ActivityChartCog.create_fallback_chart(
                f"Error generating chart: {str(e)[:30]}...", width, height
            )
    
    @staticmethod
    def create_fallback_chart(message: str, width: int = 800, height: int = 400) -> BytesIO:
        """Create a simple fallback chart when the main chart generation fails"""
        fig, ax = plt.subplots(figsize=(width/100, height/100), dpi=100)
        fig.patch.set_facecolor(COLORS['background'])
        ax.set_facecolor(COLORS['background'])
        
        # Add message
        ax.text(0.5, 0.5, message, ha='center', va='center', fontsize=14, color=COLORS['text'])
        
        # Remove axes
        ax.set_xticks([])
        ax.set_yticks([])
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_visible(False)
        ax.spines['left'].set_visible(False)
        
        # Convert to bytes
        buf = BytesIO()
        plt.savefig(buf, format='png', facecolor=fig.get_facecolor(), transparent=False)
        buf.seek(0)
        plt.close(fig)
        
        return buf
    
    @app_commands.command(name="activity", description="Show your Discord activity chart")
    @app_commands.describe(
        user="The user to show activity for (defaults to yourself)",
        days="Number of days to show (default: 30)"
    )
    async def activity_chart(
        self, 
        interaction: discord.Interaction, 
        user: Optional[discord.Member] = None,
        days: Optional[int] = 30
    ):
        """Command to display a user's activity chart"""
        await interaction.response.defer()
        
        # Limit to reasonable values
        days = min(max(7, days), 365)
        
        # Default to the command invoker
        target_user = user or interaction.user
        
        try:
            from cogs.stats import StatsDB
            
            # Initialize DB connection
            stats_db = StatsDB()
            
            # Get message history
            message_data = stats_db.get_message_history(target_user.id, interaction.guild.id, days)
            
            # Get voice history
            voice_data = stats_db.get_voice_history(target_user.id, interaction.guild.id, days)
            
            # Create the chart
            chart_image = self.create_activity_chart(
                message_data, 
                voice_data,
                target_user.display_name,
                days
            )
            
            # Create embed for better presentation
            embed = discord.Embed(
                title=f"Activity Chart for {target_user.display_name}",
                description=f"Showing activity over the last {days} days",
                color=0x4CAF50  # Green color matching the message line
            )
            
            # Get some statistics to include
            total_messages = sum(message_data.values())
            total_voice_hours = sum(voice_data.values())
            
            embed.add_field(
                name="Total Messages", 
                value=f"{total_messages:,}", 
                inline=True
            )
            
            embed.add_field(
                name="Voice Chat", 
                value=f"{total_voice_hours:.1f} hours", 
                inline=True
            )
            
            embed.set_footer(text="Green = Messages | Pink = Voice Hours")
            
            # Send the chart as a file with the embed
            file = File(chart_image, filename="activity_chart.png")
            embed.set_image(url="attachment://activity_chart.png")
            
            await interaction.followup.send(embed=embed, file=file)
            
        except ImportError:
            await interaction.followup.send(
                "Stats tracking module is not available. Please contact an administrator.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error generating activity chart: {e}")
            await interaction.followup.send(
                f"An error occurred while generating the activity chart: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="voice_stats", description="Show voice activity statistics")
    @app_commands.describe(
        user="The user to show voice stats for (defaults to yourself)",
        days="Number of days to include (default: 30)"
    )
    async def voice_stats(
        self, 
        interaction: discord.Interaction, 
        user: Optional[discord.Member] = None,
        days: Optional[int] = 30
    ):
        """Command to display voice chat statistics"""
        await interaction.response.defer()
        
        # Limit to reasonable values
        days = min(max(7, days), 365)
        
        # Default to the command invoker
        target_user = user or interaction.user
        
        try:
            from cogs.stats import StatsDB
            
            # Initialize DB connection
            stats_db = StatsDB()
            
            # Get voice history
            voice_data = stats_db.get_voice_history(target_user.id, interaction.guild.id, days)
            
            # Create embed with voice stats
            embed = discord.Embed(
                title=f"Voice Activity Stats for {target_user.display_name}",
                description=f"Voice activity over the last {days} days",
                color=0xE91E63  # Pink color matching the voice line
            )
            
            # Calculate key metrics
            total_hours = sum(voice_data.values())
            avg_daily = total_hours / min(len(voice_data), days)
            active_days = sum(1 for hours in voice_data.values() if hours > 0)
            active_percent = (active_days / len(voice_data)) * 100 if voice_data else 0
            
            # Add metrics to embed
            embed.add_field(name="Total Voice Time", value=f"{total_hours:.1f} hours", inline=True)
            embed.add_field(name="Daily Average", value=f"{avg_daily:.2f} hours", inline=True)
            embed.add_field(name="Active Days", value=f"{active_days}/{len(voice_data)} ({active_percent:.0f}%)", inline=True)
            
            # Get voice rank
            voice_rank = stats_db.get_voice_rank(target_user.id, interaction.guild.id)
            embed.add_field(name="Server Rank", value=voice_rank, inline=True)
            
            # Create a simple chart of voice activity
            if sum(voice_data.values()) > 0:
                chart_buf = self.create_activity_chart(
                    {key: 0 for key in voice_data.keys()},  # Empty message data
                    voice_data,  # Only voice data
                    target_user.display_name,
                    days,
                    width=800,
                    height=300
                )
                
                # Attach the chart
                file = File(chart_buf, filename="voice_stats.png")
                embed.set_image(url="attachment://voice_stats.png")
                
                await interaction.followup.send(embed=embed, file=file)
            else:
                embed.add_field(
                    name="No Voice Activity", 
                    value="No voice activity recorded in the specified time period.",
                    inline=False
                )
                await interaction.followup.send(embed=embed)
                
        except ImportError:
            await interaction.followup.send(
                "Stats tracking module is not available. Please contact an administrator.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error generating voice stats: {e}")
            await interaction.followup.send(
                f"An error occurred while generating voice statistics: {str(e)}",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(ActivityChartCog(bot))