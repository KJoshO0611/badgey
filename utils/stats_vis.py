import discord
import asyncio
import io
import os
import cairo
import math
from datetime import datetime, timedelta
import aiohttp
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

# Import Plotly for beautiful charts
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from kaleido.scopes.plotly import PlotlyScope

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

# Plotly-friendly hex colors
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

# Initialize Plotly renderer
scope = PlotlyScope()

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

def create_plotly_chart(message_data, voice_data, width=600, height=250):
    """Create a beautiful activity chart using Plotly with timeout protection"""
    import signal
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
    except Exception as e:
        print(f"Error processing chart data: {e}")
        return create_fallback_chart(f"Data processing error", width, height)
    
    # Create figure with secondary y-axis
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Add message line trace
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=message_values,
            name="Messages",
            line=dict(color=HEX_COLORS['green'], width=2.5),
            hovertemplate="%{y} messages<extra></extra>"
        ),
        secondary_y=False
    )
    
    # Add voice line trace
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=voice_values,
            name="Voice Hours",
            line=dict(color=HEX_COLORS['magenta'], width=2.5),
            hovertemplate="%{y} hours<extra></extra>"
        ),
        secondary_y=True
    )
    
    # Determine date formatting based on date range
    date_range = (max(dates) - min(dates)).days if dates else 0
    
    if date_range > 180:  # > 6 months
        dtick = "M1"  # Monthly ticks
        tickformat = "%b"  # Month abbreviated name
    elif date_range > 60:  # 2-6 months
        dtick = "M0.5"  # Bi-weekly ticks
        tickformat = "%b %d"
    elif date_range > 30:  # 1-2 months
        dtick = 7 * 24 * 60 * 60 * 1000  # Weekly ticks (in milliseconds)
        tickformat = "%b %d"
    else:  # < 1 month
        dtick = 3 * 24 * 60 * 60 * 1000  # Every 3 days (in milliseconds)
        tickformat = "%d"  # Day of month
    
    # Update layout for dark theme and proper formatting
    fig.update_layout(
        xaxis=dict(
            showgrid=True,
            gridcolor=HEX_COLORS['grid'],
            dtick=dtick,
            tickformat=tickformat,
            tickangle=30,
            tickfont=dict(color=HEX_COLORS['text'])
        ),
        yaxis=dict(
            title=dict(text="Messages", font=dict(color=HEX_COLORS['green'])),
            tickfont=dict(color=HEX_COLORS['green']),
            showgrid=True,
            gridcolor=HEX_COLORS['grid'],
            zeroline=False
        ),
        yaxis2=dict(
            title=dict(text="Voice Hours", font=dict(color=HEX_COLORS['magenta'])),
            tickfont=dict(color=HEX_COLORS['magenta']),
            showgrid=False,
            zeroline=False
        ),
        plot_bgcolor=HEX_COLORS['card_bg'],
        paper_bgcolor=HEX_COLORS['card_bg'],
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
            font=dict(color=HEX_COLORS['text'])
        ),
        hovermode="x unified",
        height=height,
        width=width
    )
    
    # Convert to image with a timeout protection
    result_container = {"img_bytes": None, "error": None}
    
    def render_with_timeout():
        try:
            result_container["img_bytes"] = scope.transform(
                fig, 
                format="png", 
                width=width, 
                height=height
            )
        except Exception as e:
            result_container["error"] = str(e)
    
    # Create and start thread for rendering
    render_thread = threading.Thread(target=render_with_timeout)
    render_thread.daemon = True
    render_thread.start()
    
    # Wait for thread with timeout
    render_thread.join(timeout=5.0)  # 5 second timeout
    
    if render_thread.is_alive() or result_container["error"] is not None:
        # If thread is still running after timeout or error occurred
        error_msg = result_container["error"] if result_container["error"] else "Chart rendering timed out"
        print(f"Plotly rendering error: {error_msg}")
        return create_fallback_chart("Chart rendering failed", width, height)
    
    return BytesIO(result_container["img_bytes"])


def create_fallback_chart(message, width, height):
    """Create a simple fallback chart using Cairo when Plotly fails"""
    from io import BytesIO
    import cairo
    
    # Create surface
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    ctx = cairo.Context(surface)
    
    # Fill background with card background color
    ctx.set_source_rgba(*COLORS['card_bg'])
    ctx.rectangle(0, 0, width, height)
    ctx.fill()
    
    # Add message
    ctx.select_font_face("Arial", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(16)
    ctx.set_source_rgba(*COLORS['text'])
    
    # Calculate text position
    x_bearing, y_bearing, text_width, text_height = ctx.text_extents(message)[:4]
    x = (width - text_width) / 2
    y = (height + text_height) / 2
    
    # Draw text
    ctx.move_to(x, y)
    ctx.show_text(message)
    
    # Draw placeholder chart elements
    ctx.set_source_rgba(*COLORS['grid'])
    
    # X-axis
    ctx.move_to(width * 0.1, height * 0.8)
    ctx.line_to(width * 0.9, height * 0.8)
    ctx.stroke()
    
    # Y-axis
    ctx.move_to(width * 0.1, height * 0.2)
    ctx.line_to(width * 0.1, height * 0.8)
    ctx.stroke()
    
    # Convert to bytes
    buf = BytesIO()
    surface.write_to_png(buf)
    buf.seek(0)
    
    return buf

async def generate_cairo_stats(user, guild, stats_data, width=1200, height=600):
    """Generate a beautiful stats image using Cairo with Plotly chart"""
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
    
    # Channel rows
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
    ctx.show_text("Charts")
    
    # Generate chart - this is NOT awaitable, so don't use await here
    chart_buf = create_plotly_chart(
        message_history, 
        voice_history, 
        width=int(chart_width - CARD_PADDING * 2),
        height=130
    )
    
    # Load chart as image - may need to use PIL as intermediary if there are compatibility issues
    try:
        chart_img = cairo.ImageSurface.create_from_png(chart_buf)
        ctx.set_source_surface(chart_img, chart_x + CARD_PADDING, bottom_y + 45)
        ctx.paint()
    except Exception as e:
        print(f"Error loading Plotly chart: {e}")
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
    powered_text = "Powered by Badgey"
    x_bearing, y_bearing, text_width, text_height = ctx.text_extents(powered_text)[:4]
    ctx.move_to(width - PADDING - text_width, footer_y)
    ctx.show_text(powered_text)
    
    # Convert to bytes for discord
    buf = BytesIO()
    surface.write_to_png(buf)
    buf.seek(0)
    
    return buf