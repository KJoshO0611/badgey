import os
import logging
from dotenv import load_dotenv

logger = logging.getLogger('badgey.config')

class ConfigManager:
    """
    Configuration manager with validation and hot-reloading support
    """
    def __init__(self):
        self.config = {}
        self.load_config()
    
    def load_config(self):
        """
        Load configuration from environment variables with validation
        """
        # Load environment variables
        load_dotenv()
        
        # Validate required environment variables
        required_env_vars = ['TOKEN', 'GUILDID', 'DBHOST', 'DBPORT', 'DBUSER', 'DBPASSWORD', 'DBNAME']
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]
        
        if missing_vars:
            error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Parse guild IDs
        try:
            guild_ids = os.getenv('GUILDID').split(',')
            # Validate that they're all integers
            for guild_id in guild_ids:
                int(guild_id.strip())
        except (ValueError, AttributeError) as e:
            error_msg = f"Invalid GUILDID format. Must be comma-separated integers. Error: {e}"
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        # Parse database port
        try:
            db_port = int(os.getenv('DBPORT'))
        except ValueError:
            error_msg = "DBPORT must be an integer"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Build configuration
        self.config = {
            'TOKEN': os.getenv('TOKEN'),
            'GUILD_ID': guild_ids,
            'PREFIX': os.getenv('PREFIX', '-'),
            'REQUIRED_ROLES': ["Secret", "Community Managers", "Admin"],
            'DB': {
                'HOST': os.getenv('DBHOST'),
                'PORT': db_port,
                'USER': os.getenv('DBUSER'),
                'PASSWORD': os.getenv('DBPASSWORD'),
                'DATABASE': os.getenv('DBNAME'),
            }
        }
        
        logger.info("Configuration loaded successfully")
    
    def reload(self):
        """
        Reload configuration from environment variables
        """
        logger.info("Reloading configuration...")
        try:
            self.load_config()
            logger.info("Configuration reloaded successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to reload configuration: {e}")
            return False
    
    def get_config(self):
        """
        Get the current configuration
        
        Returns:
            dict: Current configuration
        """
        return self.config
        
# Create singleton instance
config_manager = ConfigManager()
CONFIG = config_manager.get_config()

def reload_config():
    """
    Reload configuration and return new config
    
    Returns:
        dict: New configuration or None if reload failed
    """
    if config_manager.reload():
        global CONFIG
        CONFIG = config_manager.get_config()
        return CONFIG
    return None