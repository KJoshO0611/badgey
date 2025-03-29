import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import seaborn as sns
import numpy as np
import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta
from scipy.interpolate import make_interp_spline
import logging

logger = logging.getLogger('badgey.comparison_charts')

# Define colors for consistent visuals
COLORS = {
    'background': '#2a2a2a',
    'grid': '#3a3a3a',
    'user1': '#4CAF50',  # Green
    'user2': '#5865F2',  # Discord blue
    'text': '#ffffff',   # White
    'subtext': '#bbbbbb' # Light gray
}

def create_comparison_chart(
    user1_data, user2_data,
    user1_name, user2_name,
    metric_type='messages',
    width=800, height=400
):
    """
    Create a comparison chart for two users
    
    Args:
        user1_data: Dictionary of dates to values for first user
        user2_data: Dictionary of dates to values for second user
        user1_name: Name of first user
        user2_name: Name of second user
        metric_type: Type of metric ('messages' or 'voice')
        width: Width of chart
        height: Height of chart
        
    Returns:
        BytesIO: Image buffer containing the chart
    """
    try:
        # Check if we have enough data
        if not user1_data or not user2_data:
            return create_fallback_chart(
                "Insufficient data for comparison", width, height
            )
            
        # Set style
        sns.set(style="darkgrid")
        
        # Create figure
        fig, ax = plt.subplots(figsize=(width/100, height/100), dpi=100)
        fig.patch.set_facecolor(COLORS['background'])
        ax.set_facecolor(COLORS['background'])
        
        # Find the union of all dates
        all_dates = sorted(set(list(user1_data.keys()) + list(user2_data.keys())))
        
        # Convert to pandas DataFrames with date index
        df1 = pd.DataFrame({
            'date': all_dates,
            'value': [user1_data.get(date, 0) for date in all_dates]
        })
        
        df2 = pd.DataFrame({
            'date': all_dates,
            'value': [user2_data.get(date, 0) for date in all_dates]
        })
        
        # Convert string dates to datetime
        df1['date'] = pd.to_datetime(df1['date'])
        df2['date'] = pd.to_datetime(df2['date'])
        
        # Sort by date
        df1 = df1.sort_values('date')
        df2 = df2.sort_values('date')
        
        # Prepare for smoothing
        user1_dates = df1['date'].values
        user1_values = df1['value'].values
        
        user2_dates = df2['date'].values
        user2_values = df2['value'].values
        
        # Convert dates to numeric values for interpolation
        user1_x = np.array([(d - user1_dates[0]).astype('timedelta64[D]').astype(int) for d in user1_dates])
        user2_x = np.array([(d - user2_dates[0]).astype('timedelta64[D]').astype(int) for d in user2_dates])
        
        # Smooth data if we have enough points
        try:
            if len(user1_x) > 5 and np.sum(user1_values) > 0:
                # Create smoother points
                smooth_x = np.linspace(user1_x.min(), user1_x.max(), 200)
                smooth_values = make_interp_spline(user1_x, user1_values)(smooth_x)
                smooth_dates = user1_dates[0] + pd.to_timedelta(smooth_x, 'D')
                
                # Plot user1 data
                ax.plot(smooth_dates, smooth_values, color=COLORS['user1'], 
                        linewidth=2.5, alpha=0.9, label=user1_name)
                ax.fill_between(smooth_dates, 0, smooth_values, 
                               color=COLORS['user1'], alpha=0.2)
            else:
                # Use original data if we can't smooth
                ax.plot(user1_dates, user1_values, color=COLORS['user1'], 
                        linewidth=2.5, alpha=0.9, marker='o', markersize=3, label=user1_name)
                
            if len(user2_x) > 5 and np.sum(user2_values) > 0:
                # Create smoother points
                smooth_x = np.linspace(user2_x.min(), user2_x.max(), 200)
                smooth_values = make_interp_spline(user2_x, user2_values)(smooth_x)
                smooth_dates = user2_dates[0] + pd.to_timedelta(smooth_x, 'D')
                
                # Plot user2 data
                ax.plot(smooth_dates, smooth_values, color=COLORS['user2'], 
                        linewidth=2.5, alpha=0.9, label=user2_name)
                ax.fill_between(smooth_dates, 0, smooth_values, 
                               color=COLORS['user2'], alpha=0.2)
            else:
                # Use original data if we can't smooth
                ax.plot(user2_dates, user2_values, color=COLORS['user2'], 
                        linewidth=2.5, alpha=0.9, marker='o', markersize=3, label=user2_name)
                
        except Exception as e:
            # Fallback to simple line plot if smoothing fails
            logger.error(f"Smoothing failed: {e}")
            ax.plot(user1_dates, user1_values, color=COLORS['user1'], 
                    linewidth=2, label=user1_name)
            ax.plot(user2_dates, user2_values, color=COLORS['user2'],
                    linewidth=2, label=user2_name)
                    
        # Format the chart
        if metric_type == 'messages':
            y_label = 'Messages'
            title = 'Message Activity Comparison'
        else:  # voice
            y_label = 'Voice Hours'
            title = 'Voice Activity Comparison'
            
        # Add labels
        ax.set_ylabel(y_label, color=COLORS['text'], fontweight='bold')
        ax.set_title(title, color=COLORS['text'], fontsize=14, pad=10)
        
        # Format x-axis based on date range
        all_dates = list(pd.to_datetime(user1_dates)) + list(pd.to_datetime(user2_dates))
        min_date = min(all_dates)
        max_date = max(all_dates)
        date_range = (max_date - min_date).days
        
        if date_range > 90:  # > 3 months
            ax.xaxis.set_major_locator(plt.matplotlib.dates.MonthLocator())
            date_format = '%b'  # Month abbreviated name
        elif date_range > 30:  # 1-3 months
            ax.xaxis.set_major_locator(plt.matplotlib.dates.WeekdayLocator(interval=2))
            date_format = '%b %d'  # Month and day
        else:  # < 1 month
            ax.xaxis.set_major_locator(plt.matplotlib.dates.DayLocator(interval=max(1, date_range//7)))
            date_format = '%b %d'  # Month and day
            
        # Apply date formatter
        date_formatter = plt.matplotlib.dates.DateFormatter(date_format)
        ax.xaxis.set_major_formatter(date_formatter)
        plt.xticks(rotation=30)
        
        # Set all text to white for dark theme
        ax.tick_params(colors=COLORS['text'])
        for spine in ax.spines.values():
            spine.set_color(COLORS['grid'])
            
        # Add grid for better readability
        ax.grid(color=COLORS['grid'], linestyle='-', linewidth=0.5, alpha=0.7)
        
        # Add a legend
        legend = ax.legend(
            loc='upper left',
            framealpha=0.7,
            facecolor=COLORS['background'],
            edgecolor=COLORS['grid']
        )
        
        # Set legend text color
        for text in legend.get_texts():
            text.set_color(COLORS['text'])
        
        # Add totals to the chart
        user1_total = sum(user1_values)
        user2_total = sum(user2_values)
        
        totals_text = f"{user1_name}: {user1_total:,.0f} total\n{user2_name}: {user2_total:,.0f} total"
        if metric_type == 'voice':
            totals_text = f"{user1_name}: {user1_total:.1f} hours\n{user2_name}: {user2_total:.1f} hours"
            
        ax.text(
            0.98, 0.05, totals_text,
            transform=ax.transAxes,
            ha='right', va='bottom',
            color=COLORS['text'],
            bbox=dict(
                facecolor=COLORS['background'],
                alpha=0.7,
                edgecolor=COLORS['grid'],
                boxstyle='round,pad=0.5'
            )
        )
        
        # Adjust layout
        plt.tight_layout()
        
        # Convert to image
        buf = BytesIO()
        plt.savefig(buf, format='png', facecolor=fig.get_facecolor(), transparent=False)
        buf.seek(0)
        plt.close(fig)
        
        return buf
        
    except Exception as e:
        logger.error(f"Error creating comparison chart: {e}")
        return create_fallback_chart(
            f"Error generating comparison chart: {str(e)[:30]}...", width, height
        )
        
def create_fallback_chart(message, width, height):
    """Create a simple fallback chart when the main chart generation fails"""
    plt.figure(figsize=(width/100, height/100), dpi=100)
    ax = plt.gca()
    
    # Set background color
    fig = plt.gcf()
    fig.patch.set_facecolor(COLORS['background'])
    ax.set_facecolor(COLORS['background'])
    
    # Add message
    plt.text(0.5, 0.5, message, 
             horizontalalignment='center',
             verticalalignment='center',
             fontsize=12,
             color=COLORS['text'],
             transform=ax.transAxes)
    
    # Remove axis ticks and labels
    plt.xticks([])
    plt.yticks([])
    
    # Add placeholder grid
    ax.grid(False)
    
    # Add placeholder axes
    ax.axhline(y=0.8, xmin=0.1, xmax=0.9, color=COLORS['grid'], linewidth=1)
    ax.axvline(x=0.1, ymin=0.2, ymax=0.8, color=COLORS['grid'], linewidth=1)
    
    # Remove spines
    for spine in ax.spines.values():
        spine.set_visible(False)
    
    # Convert to bytes
    buf = BytesIO()
    plt.savefig(buf, format='png', facecolor=fig.get_facecolor(), bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)
    
    return buf

def create_activity_heatmap(user_data, user_name, days=30, width=800, height=400):
    """
    Create a heatmap showing activity patterns by day of week and hour of day
    
    Args:
        user_data: List of (timestamp, count) tuples for the user's activity
        user_name: Name of the user
        days: Number of days to include in the heatmap
        width: Width of chart in pixels
        height: Height of chart in pixels
        
    Returns:
        BytesIO: Image buffer containing the heatmap
    """
    try:
        # Check if we have enough data
        if not user_data or len(user_data) < 10:
            return create_fallback_chart(
                "Insufficient data for activity heatmap", width, height
            )
            
        # Set style
        sns.set(style="darkgrid")
        
        # Create figure
        fig, ax = plt.subplots(figsize=(width/100, height/100), dpi=100)
        fig.patch.set_facecolor(COLORS['background'])
        ax.set_facecolor(COLORS['background'])
        
        # Convert data to DataFrame with day and hour columns
        df = pd.DataFrame(user_data, columns=['timestamp', 'count'])
        
        # Convert timestamps to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Extract day of week and hour
        df['day'] = df['timestamp'].dt.day_name()
        df['hour'] = df['timestamp'].dt.hour
        
        # Create pivot table for heatmap
        pivot = df.pivot_table(
            index='day', 
            columns='hour', 
            values='count', 
            aggfunc='sum',
            fill_value=0
        )
        
        # Order days correctly
        days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        pivot = pivot.reindex(days_order)
        
        # Create the heatmap
        sns.heatmap(
            pivot, 
            cmap='viridis',
            ax=ax,
            cbar_kws={'label': 'Activity Count'},
            linewidths=0.5,
            linecolor='#333333'
        )
        
        # Set labels
        ax.set_title(f"Activity Pattern for {user_name}", color=COLORS['text'], fontsize=14)
        ax.set_xlabel("Hour of Day", color=COLORS['text'])
        ax.set_ylabel("Day of Week", color=COLORS['text'])
        
        # Format hours to show AM/PM
        hour_labels = [f"{h%12 or 12}{' AM' if h<12 else ' PM'}" for h in range(24)]
        ax.set_xticklabels(hour_labels, rotation=45)
        
        # Set tick colors for dark theme
        ax.tick_params(colors=COLORS['text'])
        
        # Colorbar label color
        cbar = ax.collections[0].colorbar
        cbar.ax.yaxis.label.set_color(COLORS['text'])
        cbar.ax.tick_params(colors=COLORS['text'])
        
        # Adjust layout
        plt.tight_layout()
        
        # Convert to image
        buf = BytesIO()
        plt.savefig(buf, format='png', facecolor=fig.get_facecolor(), transparent=False)
        buf.seek(0)
        plt.close(fig)
        
        return buf
        
    except Exception as e:
        logger.error(f"Error creating activity heatmap: {e}")
        return create_fallback_chart(
            f"Error generating heatmap: {str(e)[:30]}...", width, height
        )