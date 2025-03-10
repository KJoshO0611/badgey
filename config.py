import os
#from dotenv import load_dotenv

# Load environment variables
#load_dotenv()

# Bot configuration
CONFIG = {
    'TOKEN': os.getenv('TOKEN'),
    'GUILD_ID': os.getenv('GUILDID').split(','),
    'PREFIX': '-',
    'REQUIRED_ROLES': ["Secret", "Community Managers", "Admin"],
    'DB': {
        'HOST': os.getenv('DBHOST'),
        'PORT': int(os.getenv('DBPORT')),
        'USER': os.getenv('DBUSER'),
        'PASSWORD': os.getenv('DBPASSWORD'),
        'DATABASE': os.getenv('DBNAME'),
    }
}