import os
import json
from config.config import NESTS_FILE, LORE_FILE, REALM_LORE_FILE, DATA_PATH
from utils.logging import log_debug

def load_data():
    try:
        if os.path.exists(NESTS_FILE):
            with open(NESTS_FILE, 'r') as f:
                data = json.load(f)
                log_debug("Data loaded successfully")
                return data
        log_debug("No existing data, creating new")
        default_data = {
            "personal_nests": {},
            "common_nest": {"twigs": 0, "seeds": 0},
            "daily_actions": {},
            "daily_songs": {}
        }
        save_data(default_data)
        return default_data
    except Exception as e:
        log_debug(f"Error loading data: {e}")
        raise

def save_data(data):
    try:
        with open(NESTS_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        log_debug("Data saved successfully")
    except Exception as e:
        log_debug(f"Error saving data: {e}")
        raise

def load_lore():
    try:
        if os.path.exists(LORE_FILE):
            with open(LORE_FILE, 'r') as f:
                data = json.load(f)
                log_debug("Lore data loaded successfully")
                return data
        log_debug("No existing lore data, creating new")
        default_data = {
            "memoirs": []
        }
        save_lore(default_data)
        return default_data
    except Exception as e:
        log_debug(f"Error loading lore data: {e}")
        raise

def save_lore(data):
    try:
        with open(LORE_FILE, 'w') as f:
            json.dump(data, f, indent=4)
        log_debug("Lore data saved successfully")
    except Exception as e:
        log_debug(f"Error saving lore data: {e}")
        raise

def load_realm_lore():
    try:
        if os.path.exists(REALM_LORE_FILE):
            with open(REALM_LORE_FILE, 'r') as f:
                data = json.load(f)
                log_debug("Realm lore data loaded successfully")
                return data
        log_debug("No existing realm lore data, creating new")
        default_data = {
            "messages": []
        }
        save_realm_lore(default_data)
        return default_data
    except Exception as e:
        log_debug(f"Error loading realm lore data: {e}")
        raise

def save_realm_lore(data):
    try:
        with open(REALM_LORE_FILE, 'w') as f:
            json.dump(data, f, indent=4)
        log_debug("Realm lore data saved successfully")
    except Exception as e:
        log_debug(f"Error saving realm lore data: {e}")
        raise

def load_manifested_birds():
    """Load manifested birds data from JSON file"""
    manifested_birds_file = os.path.join(DATA_PATH, 'manifested_birds.json')
    try:
        if os.path.exists(manifested_birds_file):
            with open(manifested_birds_file, 'r') as f:
                data = json.load(f)
                log_debug("Manifested birds data loaded successfully")
                return data
        log_debug("No existing manifested birds data, creating new")
        default_data = []
        save_manifested_birds(default_data)
        return default_data
    except Exception as e:
        log_debug(f"Error loading manifested birds data: {e}")
        raise

def save_manifested_birds(data):
    """Save manifested birds data to JSON file"""
    manifested_birds_file = os.path.join(DATA_PATH, 'manifested_birds.json')
    try:
        with open(manifested_birds_file, 'w') as f:
            json.dump(data, f, indent=4)
        log_debug("Manifested birds data saved successfully")
    except Exception as e:
        log_debug(f"Error saving manifested birds data: {e}")
        raise

def load_manifested_plants():
    """Load manifested plants data from JSON file"""
    manifested_plants_file = os.path.join(DATA_PATH, 'manifested_plants.json')
    try:
        if os.path.exists(manifested_plants_file):
            with open(manifested_plants_file, 'r') as f:
                data = json.load(f)
                log_debug("Manifested plants data loaded successfully")
                return data
        log_debug("No existing manifested plants data, creating new")
        default_data = []
        save_manifested_plants(default_data)
        return default_data
    except Exception as e:
        log_debug(f"Error loading manifested plants data: {e}")
        raise

def save_manifested_plants(data):
    """Save manifested plants data to JSON file"""
    manifested_plants_file = os.path.join(DATA_PATH, 'manifested_plants.json')
    try:
        with open(manifested_plants_file, 'w') as f:
            json.dump(data, f, indent=4)
        log_debug("Manifested plants data saved successfully")
    except Exception as e:
        log_debug(f"Error saving manifested plants data: {e}")
        raise

def load_research_progress():
    """Load research progress data from JSON file"""
    research_progress_file = os.path.join(DATA_PATH, 'research_progress.json')
    try:
        if os.path.exists(research_progress_file):
            with open(research_progress_file, 'r') as f:
                data = json.load(f)
                log_debug("Research progress data loaded successfully")
                return data
        log_debug("No existing research progress data, creating new")
        default_data = {}
        save_research_progress(default_data)
        return default_data
    except Exception as e:
        log_debug(f"Error loading research progress data: {e}")
        raise

def save_research_progress(data):
    """Save research progress data to JSON file"""
    research_progress_file = os.path.join(DATA_PATH, 'research_progress.json')
    try:
        with open(research_progress_file, 'w') as f:
            json.dump(data, f, indent=4)
        log_debug("Research progress data saved successfully")
    except Exception as e:
        log_debug(f"Error saving research progress data: {e}")
        raise
