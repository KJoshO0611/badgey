import threading
import http.server
import socketserver
import logging
import json
import time
import os
import psutil
from typing import Dict, Any

logger = logging.getLogger('badgey.health')

# Global metrics
start_time = time.time()
bot_ready = False

class HealthCheckHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler for health check requests"""
    
    def _send_response(self, status_code: int, content_type: str, content: str):
        """Send HTTP response with specified status code and content"""
        self.send_response(status_code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content.encode('utf-8'))
    
    def get_health_data(self) -> Dict[str, Any]:
        """Get health check data"""
        process = psutil.Process(os.getpid())
        
        uptime = time.time() - start_time
        days, remainder = divmod(uptime, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        return {
            'status': 'healthy' if bot_ready else 'starting',
            'uptime': f"{int(days)}d {int(hours)}h {int(minutes)}m {int(seconds)}s",
            'uptime_seconds': uptime,
            'memory_usage_mb': process.memory_info().rss / 1024 / 1024,
            'cpu_percent': process.cpu_percent(interval=0.1),
            'thread_count': len(threading.enumerate()),
            'ready': bot_ready
        }
    
    def do_GET(self):
        """Handle GET requests"""
        if self.path == '/health':
            # Get health data
            health_data = self.get_health_data()
            
            # Return appropriate status code based on health
            status_code = 200 if health_data['ready'] else 503
            response = json.dumps(health_data, indent=2)
            
            self._send_response(status_code, 'application/json', response)
        else:
            # Return 404 for other paths
            self._send_response(404, 'text/plain', 'Not Found')
    
    def log_message(self, format, *args):
        """Override to use our logger instead of printing to stderr"""
        if 'health' in args[0]:  # Only log health check requests at debug level
            logger.debug("%s - %s", self.client_address[0], format % args)
        else:
            logger.info("%s - %s", self.client_address[0], format % args)

def set_bot_ready(ready: bool = True):
    """Set the bot ready status"""
    global bot_ready
    bot_ready = ready
    logger.info(f"Bot ready status set to: {ready}")

def start_health_server(port: int = 8080, host: str = '0.0.0.0'):
    """Start the health check HTTP server in a background thread"""
    def run_server():
        with socketserver.TCPServer((host, port), HealthCheckHandler) as httpd:
            logger.info(f"Health check server started at http://{host}:{port}")
            httpd.serve_forever()
    
    # Start server in a daemon thread so it doesn't block program exit
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    logger.info("Health check server thread started") 