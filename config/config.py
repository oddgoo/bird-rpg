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
SPECIES_IMAGES_DIR = os.path.join(DATA_PATH, 'species_images')

# Web server configuration
PORT = int(os.getenv('PORT', 10000))
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'godbird')  # Default password if not set

# Create necessary directories
os.makedirs(DATA_PATH, exist_ok=True)
os.makedirs(SPECIES_IMAGES_DIR, exist_ok=True)

# Supabase configuration
SUPABASE_URL = os.getenv('SUPABASE_URL', '')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', '')

# Game limits
MAX_BIRDS_PER_NEST = 45  # Maximum number of birds a user can have
MAX_GARDEN_SIZE = 45     # Maximum garden size a user can have

# Birdwatch image settings
MAX_BIRDWATCH_IMAGE_SIZE = 25 * 1024 * 1024  # 25MB (Discord default limit)
BIRDWATCH_MAX_DIMENSION = 1920  # Max px on longest side after resize
BIRDWATCH_JPEG_QUALITY = 85
ALLOWED_IMAGE_TYPES = {'image/png', 'image/jpeg', 'image/gif', 'image/webp'}
ALLOWED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
