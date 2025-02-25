import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Bot configuration
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
STORAGE_PATH = '/var/data' if os.path.exists('/var/data') else '.'
DATA_PATH = os.path.join(STORAGE_PATH, 'bird-rpg')
NESTS_FILE = os.path.join(DATA_PATH, 'nests.json')
LORE_FILE = os.path.join(DATA_PATH, "lore.json")
REALM_LORE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'realm_lore.json')

# Web server configuration
PORT = int(os.getenv('PORT', 10000))
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'godbird')  # Default password if not set

# Create necessary directories
os.makedirs(DATA_PATH, exist_ok=True)

# Game limits
MAX_BIRDS_PER_NEST = 30  # Maximum number of birds a user can have
MAX_GARDEN_SIZE = 30     # Maximum garden size a user can have
