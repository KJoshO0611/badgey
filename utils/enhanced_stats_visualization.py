import discord
import asyncio
import io
import os
import cairo
import math
from datetime import datetime, timedelta
import aiohttp
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from scipy.interpolate import make_interp_spline

# Enhanced color scheme with transparency for shadows
COLORS = {
    'background': (0.12, 0.12, 0.12, 1),           # Dark background
    'card_bg': (0.16, 0.16, 0.16, 1),              # Card background
    'card_bg_alt': (0.14, 0.14, 0.14, 1),          # Alternative card background
    'text': (1, 1, 1, 1),                          # White text
    'subtext': (0.73, 0.73, 0.73, 1),              # Light gray text
    'accent': (0.345, 0.396, 0.949, 1),            # Discord blurple
    'green': (0.298, 0.686, 0.314, 1),             # Message line color
    'magenta': (0.914, 0.118, 0.388, 1),           # Voice line color
    'shadow': (0, 0, 0, 0.5),                      # Shadow color
    'border': (0.22, 0.22, 0.22, 1),               # Border color
    'highlight': (0.4, 0.4, 0.4, 1),               # Highlight color for rows
    'grid': (0.2, 0.2, 0.2, 0.5)                   # Grid lines
}

# Matplotlib/Seaborn-friendly hex colors
HEX_COLORS = {
    'background': '#1e1e1e',
    'card_bg': '#2a2a2a',
    'text': '#ffffff',
    'subtext': '#bbbbbb',
    'accent': '#5865F2',
    'green': '#4CAF50',
    'magenta': '#E91E63',
    'dark_bg': '#181818',
    'grid': '#333333'
}

# Layout constants
PADDING = 15              # Standard padding between elements
CARD_PADDING = 12         # Internal card padding
CARD_SPACING = 20         # Space between cards
SHADOW_OFFSET = 4         # Shadow offset
SHADOW_BLUR = 8           # Shadow blur radius
BORDER_RADIUS = 12        # Default border radius
SMALL_RADIUS = 6          # Smaller radius for inner elements

async def download_avatar(url, size=96):
    """Download a user's avatar"""
    if not url:
        # Return a blank surface if URL is not available
        return None
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.read()
                    img = Image.open(BytesIO(data))
                    img = img.resize((size, size)).convert("RGBA")
                    
                    # Create circular mask
                    mask = Image.new('L', (size, size), 0)
                    draw = ImageDraw.Draw(mask)
                    draw.ellipse((0, 0, size, size), fill=255)
                    
                    # Apply mask
                    result = Image.new('RGBA', (size, size), (0, 0, 0, 0))
                    result.paste(img, (0, 0), mask)
                    
                    # Convert to bytes for Cairo
                    avatar_bytes = BytesIO()
                    result.save(avatar_bytes, format='PNG')
                    avatar_bytes.seek(0)
                    return avatar_bytes
    except Exception as e:
        print(f"Avatar download error: {e}")
    
    return None

def draw_rounded_rect_with_shadow(ctx, x, y, width, height, radius=BORDER_RADIUS, shadow=True, fill=COLORS['card_bg']):
    """Draw a rounded rectangle with optional drop shadow"""
    if shadow:
        # Draw shadow first (slightly larger, offset, and with blur effect)
        ctx.save()
        ctx.set_source_rgba(*COLORS['shadow'])
        draw_rounded_rect(ctx, x + SHADOW_OFFSET, y + SHADOW_OFFSET, width, height, radius)
        ctx.fill()
        
        # Apply blur effect (simplified approximation)
        for i in range(1, SHADOW_BLUR, 2):
            opacity = 0.3 * (SHADOW_BLUR - i) / SHADOW_BLUR
            ctx.set_source_rgba(0, 0, 0, opacity)
            draw_rounded_rect(ctx, x + i/2, y + i/2, width, height, radius)
            ctx.fill()
        ctx.restore()
    
    # Draw the actual rectangle
    ctx.set_source_rgba(*fill)
    draw_rounded_rect(ctx, x, y, width, height, radius)
    ctx.fill()

def draw_rounded_rect(ctx, x, y, width, height, radius=BORDER_RADIUS):
    """Helper to draw a rounded rectangle path"""
    # Ensure radius doesn't exceed half of width or height
    radius = min(radius, min(width/2, height/2))
    
    # Move to top-right corner
    ctx.new_path()
    ctx.move_to(x + width - radius, y)
    # Top-right corner
    ctx.arc(x + width - radius, y + radius, radius, -math.pi/2, 0)
    # Right side
    ctx.line_to(x + width, y + height - radius)
    # Bottom-right corner
    ctx.arc(x + width - radius, y + height - radius, radius, 0, math.pi/2)
    # Bottom side
    ctx.line_to(x + radius, y + height)
    # Bottom-left corner
    ctx.arc(x + radius, y + height - radius, radius, math.pi/2, math.pi)
    # Left side
    ctx.line_to(x, y + radius)
    # Top-left corner
    ctx.arc(x + radius, y + radius, radius, math.pi, 3*math.pi/2)
    # Top side
    ctx.line_to(x + width - radius, y)
    ctx.close_path()

def create_channels_chart(channels_data, width=400, height=150):
    """Create a horizontal bar chart for top channels using Seaborn"""
    if not channels_data or len(channels_data) == 0:
        return create_fallback_chart("No channel data", width, height)
    
    try:
        # Extract data
        channels = []
        counts = []
        
        # Limit to top 5 channels
        for channel, count in channels_data[:5]:
            # Truncate long channel names
            if len(channel) > 15:
                channel = channel[:12] + "..."
            channels.append(channel)
            counts.append(count)
        
        # Reverse the order for bottom-to-top plotting
        channels.reverse()
        counts.reverse()
        
        # Create figure
        plt.figure(figsize=(width/100, height/100), dpi=100)
        
        # Set the style for dark theme
        sns.set(style="darkgrid")
        
        # Create the horizontal bar chart
        ax = sns.barplot(x=counts, y=channels, palette="viridis")
        
        # Set dark background
        fig = plt.gcf()
        fig.patch.set_facecolor(HEX_COLORS['card_bg'])
        ax.set_facecolor(HEX_COLORS['card_bg'])
        
        # Format y-axis labels
        ax.set_ylabel('')
        for label in ax.get_yticklabels():
            label.set_color(HEX_COLORS['text'])
        
        # Format x-axis labels
        ax.set_xlabel('Messages')
        ax.xaxis.label.set_color(HEX_COLORS['text'])
        for label in ax.get_xticklabels():
            label.set_color(HEX_COLORS['text'])
        
        # Add count labels to the bars
        for i, count in enumerate(counts):
            ax.text(count + max(counts) * 0.02, i, str(count), 
                    va='center', color=HEX_COLORS['text'], fontweight='bold')
        
        # Adjust layout
        plt.tight_layout()
        
        # Save to buffer
        buf = BytesIO()
        plt.savefig(buf, format='png', facecolor=fig.get_facecolor(), transparent=False)
        buf.seek(0)
        plt.close(fig)  # Close the figure to free memory
        
        return buf
        
    except Exception as e:
        print(f"Error generating channels chart: {e}")
        return create_fallback_chart("Chart generation failed", width, height)

def create_activity_chart(message_data, voice_data, width=600, height=250):
    """Create a beautiful activity chart using Seaborn with advanced styling"""
    import threading
    from functools import partial
    
    # Check if we have enough data
    if len(message_data) < 2 or len(voice_data) < 2:
        return create_fallback_chart("Insufficient data for chart", width, height)
    
    # Extract data
    try:
        dates = [datetime.strptime(d, '%Y-%m-%d') for d in message_data.keys()]
        message_values = list(message_data.values())
        voice_values = list(voice_data.values())
        
        # Ensure all lists are the same length
        min_len = min(len(dates), len(message_values), len(voice_values))
        dates = dates[:min_len]
        message_values = message_values[:min_len]
        voice_values = voice_values[:min_len]
        
        # Check if we have enough activity data
        if sum(message_values) < 2 and sum(voice_values) < 0.1:
            return create_fallback_chart("Not enough activity data to chart", width, height)
    
    except Exception as e:
        print(f"Error processing chart data: {e}")
        return create_fallback_chart(f"Data processing error", width, height)
    
    try:
        # Set the Seaborn style
        sns.set(style="darkgrid")
        
        # Create figure with two y-axes
        fig, ax1 = plt.subplots(figsize=(width/100, height/100), dpi=100)
        
        # Set dark background
        fig.patch.set_facecolor(HEX_COLORS['card_bg'])
        ax1.set_facecolor(HEX_COLORS['card_bg'])
        
        # Add light grid in background
        ax1.grid(color=HEX_COLORS['grid'], linestyle='-', linewidth=0.5, alpha=0.7)
        
        # Create dates array for smoothing
        dates_array = np.array([(d - min(dates)).days for d in dates])
        
        # Smooth the message data if we have enough points
        if len(dates) > 5 and sum(message_values) > 0:
            try:
                # Use spline interpolation for smoother curves
                x_smooth = np.linspace(dates_array.min(), dates_array.max(), 200)
                message_smooth = make_interp_spline(dates_array, message_values)(x_smooth)
                dates_smooth = min(dates) + pd.to_timedelta(x_smooth, unit='D')
                
                # Plot the smoothed message line
                ax1.plot(dates_smooth, message_smooth, color=HEX_COLORS['green'], 
                        linewidth=2.5, alpha=0.9)
                
                # Add light fill below the line
                ax1.fill_between(dates_smooth, 0, message_smooth, 
                                color=HEX_COLORS['green'], alpha=0.15)
            except Exception as e:
                print(f"Error smoothing message data: {e}")
                # Fallback to regular line if smoothing fails
                ax1.plot(dates, message_values, color=HEX_COLORS['green'], 
                        linewidth=2.5, alpha=0.9)
        else:
            # Regular line for few data points
            ax1.plot(dates, message_values, color=HEX_COLORS['green'], 
                    linewidth=2.5, alpha=0.9, marker='o', markersize=4)
        
        # Configure y-axis for messages
        ax1.set_ylabel('Messages', color=HEX_COLORS['green'], fontweight='bold')
        ax1.tick_params(axis='y', labelcolor=HEX_COLORS['green'])
        
        # Create secondary y-axis for voice data
        ax2 = ax1.twinx()
        
        # Smooth the voice data if we have enough points
        if len(dates) > 5 and sum(voice_values) > 0:
            try:
                # Use spline interpolation for voice data
                x_smooth = np.linspace(dates_array.min(), dates_array.max(), 200)
                voice_smooth = make_interp_spline(dates_array, voice_values)(x_smooth)
                dates_smooth = min(dates) + pd.to_timedelta(x_smooth, unit='D')
                
                # Plot the smoothed voice line
                ax2.plot(dates_smooth, voice_smooth, color=HEX_COLORS['voice'], 
                        linewidth=2.5, alpha=0.9)
                
                # Add light fill below the line
                ax2.fill_between(dates_smooth, 0, voice_smooth, 
                                color=HEX_COLORS['voice'], alpha=0.15)
            except Exception as e:
                print(f"Error smoothing voice data: {e}")
                # Fallback to regular line
                ax2.plot(dates, voice_values, color=HEX_COLORS['voice'], 
                        linewidth=2.5, alpha=0.9)
        else:
            # Regular line for few data points
            ax2.plot(dates, voice_values, color=HEX_COLORS['voice'], 
                    linewidth=2.5, alpha=0.9, marker='o', markersize=4)
                    
        # Configure y-axis for voice hours
        ax2.set_ylabel('Voice Hours', color=HEX_COLORS['voice'], fontweight='bold')
        ax2.tick_params(axis='y', labelcolor=HEX_COLORS['voice'])
        
        # Determine date formatting based on date range
        date_range = (max(dates) - min(dates)).days if dates else 0
        
        # Format x-axis based on date range
        if date_range > 180:  # > 6 months
            ax1.xaxis.set_major_locator(plt.matplotlib.dates.MonthLocator())
            date_format = '%b'  # Month abbreviated name
        elif date_range > 60:  # 2-6 months
            ax1.xaxis.set_major_locator(plt.matplotlib.dates.WeekdayLocator(interval=2))
            date_format = '%b %d'  # Month and day
        elif date_range > 30:  # 1-2 months
            ax1.xaxis.set_major_locator(plt.matplotlib.dates.WeekdayLocator())
            date_format = '%b %d'  # Month and day
        else:  # < 1 month
            ax1.xaxis.set_major_locator(plt.matplotlib.dates.DayLocator(interval=max(1, date_range//10 or 1)))
            date_format = '%d'  # Day of month
        
        # Format dates
        date_formatter = plt.matplotlib.dates.DateFormatter(date_format)
        ax1.xaxis.set_major_formatter(date_formatter)
        plt.xticks(rotation=30)
        
        # Set text colors for a dark theme
        for label in ax1.get_xticklabels():
            label.set_color(HEX_COLORS['text'])
        
        # Add legend with custom handles
        legend = fig.legend(
            ['Messages', 'Voice Hours'], 
            loc='upper center', 
            bbox_to_anchor=(0.5, 1.05), 
            ncol=2, 
            fancybox=True, 
            shadow=True,
            framealpha=0.8
        )
        
        # Set legend text color
        for text in legend.get_texts():
            text.set_color(HEX_COLORS['text'])
        
        # Adjust layout and margins
        plt.tight_layout()
        
        # Convert to image
        buf = BytesIO()
        plt.savefig(buf, format='png', facecolor=fig.get_facecolor(), transparent=False, bbox_inches='tight')
        buf.seek(0)
        plt.close(fig)  # Close the figure to free memory
        
        return buf
        
    except Exception as e:
        print(f"Error generating Seaborn chart: {e}")
        return create_fallback_chart("Chart generation failed", width, height)
    
async def generate_cairo_stats(user, guild, stats_data, width=1200, height=600):
    """Generate a beautiful stats image using Cairo with Pygal charts"""
    # Create image surface
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    ctx = cairo.Context(surface)
    
    # Fill background
    ctx.set_source_rgba(*COLORS['background'])
    ctx.rectangle(0, 0, width, height)
    ctx.fill()
    
    # Extract data
    message_day_count = stats_data.get('message_day', 0)
    message_week_count = stats_data.get('message_week', 0)
    message_month_count = stats_data.get('message_month', 0)
    
    voice_day_hours = stats_data.get('voice_day', 0)
    voice_week_hours = stats_data.get('voice_week', 0)
    voice_month_hours = stats_data.get('voice_month', 0)
    
    message_rank = stats_data.get('message_rank', '#0')
    voice_rank = stats_data.get('voice_rank', 'No Data')
    
    top_channels = stats_data.get('top_channels', [])
    message_history = stats_data.get('message_history', {})
    voice_history = stats_data.get('voice_history', {})
    
    start_date = stats_data.get('start_date')
    end_date = stats_data.get('end_date')
    lookback_days = stats_data.get('lookback_days', 30)
    
    # Download and place avatar
    avatar_size = 80
    avatar_bytes = await download_avatar(str(user.display_avatar.url), avatar_size)
    if avatar_bytes:
        avatar_img = cairo.ImageSurface.create_from_png(avatar_bytes)
        # Create circular clip path for avatar
        ctx.save()
        ctx.arc(30 + avatar_size/2, 30 + avatar_size/2, avatar_size/2, 0, 2*math.pi)
        ctx.clip()
        ctx.set_source_surface(avatar_img, 30, 30)
        ctx.paint()
        ctx.restore()
    
    # User name and display name
    ctx.select_font_face("Arial", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(28)
    ctx.set_source_rgba(*COLORS['text'])
    ctx.move_to(30 + avatar_size + PADDING, 30 + 30)
    ctx.show_text(user.name)
    
    ctx.select_font_face("Arial", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(18)
    ctx.set_source_rgba(*COLORS['subtext'])
    ctx.move_to(30 + avatar_size + PADDING, 30 + 60)
    ctx.show_text(user.display_name)
    
    # Created/Joined Date boxes
    created_box_width = 250
    created_box_height = 60
    created_text = "Created On"
    created_date = user.created_at.strftime("%B %d, %Y") if user.created_at else "Unknown"
    joined_text = "Joined On"
    joined_date = user.joined_at.strftime("%B %d, %Y") if user.joined_at else "Unknown"
    
    # Joined Date Box
    joined_x = width - created_box_width - PADDING - created_box_width - PADDING
    draw_rounded_rect_with_shadow(ctx, joined_x, 30, created_box_width, created_box_height)
    
    # Joined label
    ctx.select_font_face("Arial", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(16)
    ctx.set_source_rgba(*COLORS['subtext'])
    ctx.move_to(joined_x + CARD_PADDING, 30 + 25)
    ctx.show_text(joined_text)
    
    # Joined value
    ctx.select_font_face("Arial", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(18)
    ctx.set_source_rgba(*COLORS['text'])
    ctx.move_to(joined_x + CARD_PADDING, 30 + 50)
    ctx.show_text(joined_date)
    
    # Created Date Box
    created_x = width - created_box_width - PADDING
    draw_rounded_rect_with_shadow(ctx, created_x, 30, created_box_width, created_box_height)
    
    # Created label
    ctx.set_font_size(16)
    ctx.set_source_rgba(*COLORS['subtext'])
    ctx.move_to(created_x + CARD_PADDING, 30 + 25)
    ctx.show_text(created_text)
    
    # Created value
    ctx.set_font_size(18)
    ctx.set_source_rgba(*COLORS['text'])
    ctx.move_to(created_x + CARD_PADDING, 30 + 50)
    ctx.show_text(created_date)
    
    # Calculate main layout
    stats_y = 30 + avatar_size + PADDING * 2
    col_width = (width - PADDING * 4) / 3
    card_height = 180
    
    # Server Ranks Section
    draw_rounded_rect_with_shadow(ctx, PADDING, stats_y, col_width, card_height)
    
    # Title
    ctx.select_font_face("Arial", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(22)
    ctx.set_source_rgba(*COLORS['text'])
    ctx.move_to(PADDING + CARD_PADDING + 20, stats_y + 30)
    ctx.show_text("Server Ranks")
    
    # Icon
    ctx.select_font_face("Arial", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(24)
    ctx.move_to(PADDING + CARD_PADDING, stats_y + 30)
    ctx.show_text("🏆")
    
    # Message rank
    draw_rounded_rect_with_shadow(ctx, 
                             PADDING + CARD_PADDING, 
                             stats_y + 50, 
                             col_width - CARD_PADDING * 2, 
                             40, 
                             radius=SMALL_RADIUS, 
                             fill=COLORS['card_bg_alt'])
    
    ctx.set_font_size(18)
    ctx.set_source_rgba(*COLORS['text'])
    ctx.move_to(PADDING + CARD_PADDING * 2, stats_y + 50 + 26)
    ctx.show_text("Message")
    
    ctx.set_font_size(18)
    ctx.set_source_rgba(*COLORS['text'])
    rank_text = message_rank
    # Get text width
    x_bearing, y_bearing, rank_width, rank_height = ctx.text_extents(rank_text)[:4]
    ctx.move_to(PADDING + col_width - CARD_PADDING * 2 - rank_width, stats_y + 50 + 26)
    ctx.show_text(rank_text)
    
    # Voice rank
    draw_rounded_rect_with_shadow(ctx, 
                             PADDING + CARD_PADDING, 
                             stats_y + 100, 
                             col_width - CARD_PADDING * 2, 
                             40, 
                             radius=SMALL_RADIUS, 
                             fill=COLORS['card_bg_alt'])
                           
    ctx.set_font_size(18)
    ctx.set_source_rgba(*COLORS['text'])
    ctx.move_to(PADDING + CARD_PADDING * 2, stats_y + 100 + 26)
    ctx.show_text("Voice")
    
    voice_rank_text = voice_rank
    x_bearing, y_bearing, rank_width, rank_height = ctx.text_extents(voice_rank_text)[:4]
    ctx.move_to(PADDING + col_width - CARD_PADDING * 2 - rank_width, stats_y + 100 + 26)
    ctx.show_text(voice_rank_text)
    
    # Messages Section
    msg_x = PADDING * 2 + col_width
    draw_rounded_rect_with_shadow(ctx, msg_x, stats_y, col_width, card_height)
    
    # Title
    ctx.select_font_face("Arial", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(22)
    ctx.set_source_rgba(*COLORS['text'])
    ctx.move_to(msg_x + CARD_PADDING + 20, stats_y + 30)
    ctx.show_text("Messages")
    
    # Icon
    ctx.select_font_face("Arial", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(24)
    ctx.move_to(msg_x + CARD_PADDING, stats_y + 30)
    ctx.show_text("#")
    
    # Message stats
    periods = ["1d", "7d", "30d"]
    counts = [message_day_count, message_week_count, message_month_count]
    
    for i, (period, count) in enumerate(zip(periods, counts)):
        y_pos = stats_y + 60 + (i * 35)
        
        ctx.set_font_size(18)
        ctx.set_source_rgba(*COLORS['text'])
        ctx.move_to(msg_x + CARD_PADDING, y_pos)
        ctx.show_text(period)
        
        ctx.set_font_size(18)
        ctx.set_source_rgba(*COLORS['subtext'])
        count_text = f"{count} messages"
        ctx.move_to(msg_x + CARD_PADDING + 60, y_pos)
        ctx.show_text(count_text)
    
    # Voice Section
    voice_x = PADDING * 3 + col_width * 2
    draw_rounded_rect_with_shadow(ctx, voice_x, stats_y, col_width, card_height)
    
    # Title
    ctx.select_font_face("Arial", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(22)
    ctx.set_source_rgba(*COLORS['text'])
    ctx.move_to(voice_x + CARD_PADDING + 20, stats_y + 30)
    ctx.show_text("Voice Activity")
    
    # Icon
    ctx.select_font_face("Arial", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(24)
    ctx.move_to(voice_x + CARD_PADDING, stats_y + 30)
    ctx.show_text("🔊")
    
    # Voice stats
    voice_hours = [voice_day_hours, voice_week_hours, voice_month_hours]
    
    for i, (period, hours) in enumerate(zip(periods, voice_hours)):
        y_pos = stats_y + 60 + (i * 35)
        
        ctx.set_font_size(18)
        ctx.set_source_rgba(*COLORS['text'])
        ctx.move_to(voice_x + CARD_PADDING, y_pos)
        ctx.show_text(period)
        
        ctx.set_font_size(18)
        ctx.set_source_rgba(*COLORS['subtext'])
        hours_text = f"{hours:.1f} hours"
        ctx.move_to(voice_x + CARD_PADDING + 60, y_pos)
        ctx.show_text(hours_text)
    
    # Bottom row
    bottom_y = stats_y + card_height + PADDING
    bottom_card_height = 200
    
    # Channels Section
    channels_width = col_width * 1.5
    draw_rounded_rect_with_shadow(ctx, PADDING, bottom_y, channels_width, bottom_card_height)
    
    # Title
    ctx.select_font_face("Arial", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(22)
    ctx.set_source_rgba(*COLORS['text'])
    ctx.move_to(PADDING + CARD_PADDING + 20, bottom_y + 30)
    ctx.show_text("Top Channels & Applications")
    
    # Generate channels chart
    channels_chart_buf = create_channels_chart(
        top_channels,
        width=int(channels_width - CARD_PADDING * 2),
        height=140
    )
    
    # Load channels chart as image
    try:
        channels_chart_img = cairo.ImageSurface.create_from_png(channels_chart_buf)
        ctx.set_source_surface(channels_chart_img, PADDING + CARD_PADDING, bottom_y + 50)
        ctx.paint()
    except Exception as e:
        print(f"Error loading channels chart: {e}")
        
        # Fallback to text-based channel list if chart fails
        for i, (channel_name, count) in enumerate(top_channels[:3]):
            y_pos = bottom_y + 60 + (i * 40)
            
            # Channel row background
            draw_rounded_rect_with_shadow(ctx,
                                    PADDING + CARD_PADDING,
                                    y_pos,
                                    channels_width - CARD_PADDING * 2,
                                    30,
                                    radius=SMALL_RADIUS,
                                    fill=COLORS['card_bg_alt'])
            
            # Icon based on index
            icon = "#" if i == 0 else "🔊" if i == 1 else "🎮"
            ctx.set_font_size(18)
            ctx.set_source_rgba(*COLORS['text'])
            ctx.move_to(PADDING + CARD_PADDING + 10, y_pos + 22)
            ctx.show_text(icon)
            
            # Channel name
            ctx.move_to(PADDING + CARD_PADDING + 40, y_pos + 22)
            ctx.show_text(f"#{channel_name}")
            
            # Message count
            ctx.set_source_rgba(*COLORS['subtext'])
            count_text = f"{count} messages"
            x_bearing, y_bearing, count_width, count_height = ctx.text_extents(count_text)[:4]
            ctx.move_to(PADDING + channels_width - CARD_PADDING - 10 - count_width, y_pos + 22)
            ctx.show_text(count_text)
    
    # Chart Section
    chart_x = PADDING * 2 + channels_width
    chart_width = width - chart_x - PADDING
    
    draw_rounded_rect_with_shadow(ctx, chart_x, bottom_y, chart_width, bottom_card_height)
    
    # Title
    ctx.select_font_face("Arial", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(22)
    ctx.set_source_rgba(*COLORS['text'])
    ctx.move_to(chart_x + CARD_PADDING + 20, bottom_y + 30)
    ctx.show_text("Activity Over Time")
    
    # Generate activity chart with Pygal
    chart_buf = create_activity_chart(
        message_history, 
        voice_history, 
        width=int(chart_width - CARD_PADDING * 2),
        height=130
    )
    
    # Load chart as image
    try:
        chart_img = cairo.ImageSurface.create_from_png(chart_buf)
        ctx.set_source_surface(chart_img, chart_x + CARD_PADDING, bottom_y + 45)
        ctx.paint()
    except Exception as e:
        print(f"Error loading activity chart: {e}")
        # Fallback - draw a placeholder
        ctx.set_source_rgba(*COLORS['text'])
        ctx.select_font_face("Arial", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(18)
        
        text = "Chart rendering error"
        x_bearing, y_bearing, text_width, text_height = ctx.text_extents(text)[:4]
        text_x = chart_x + CARD_PADDING + (chart_width - CARD_PADDING * 2 - text_width) / 2
        text_y = bottom_y + 45 + 130/2
        ctx.move_to(text_x, text_y)
        ctx.show_text(text)
    
    # Footer
    footer_y = height - 30
    if start_date and end_date:
        date_range_text = f"Server Lookback: {start_date.strftime('%b %d, %Y')} to {end_date.strftime('%b %d, %Y')}"
    else:
        date_range_text = f"Server Lookback: Last {lookback_days} days"
        
    timezone = stats_data.get('timezone', 'UTC')
    
    ctx.set_font_size(14)
    ctx.set_source_rgba(*COLORS['subtext'])
    ctx.move_to(PADDING, footer_y)
    ctx.show_text(f"{date_range_text} — Timezone: {timezone}")
    
    # Powered by text
    powered_text = "Powered by Badgey with Pygal"
    x_bearing, y_bearing, text_width, text_height = ctx.text_extents(powered_text)[:4]
    ctx.move_to(width - PADDING - text_width, footer_y)
    ctx.show_text(powered_text)
    
    # Convert to bytes for discord
    buf = BytesIO()
    surface.write_to_png(buf)
    buf.seek(0)
    
    return buf

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