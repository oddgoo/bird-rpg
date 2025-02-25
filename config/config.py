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

# Create necessary directories
os.makedirs(DATA_PATH, exist_ok=True)
