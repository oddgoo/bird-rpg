import os
import json
from config.config import NESTS_FILE, LORE_FILE, REALM_LORE_FILE
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
