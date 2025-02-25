import json
import random
import os
from datetime import date
from config.config import DATA_PATH
from utils.time_utils import get_current_date

class HumanSpawner:
    def __init__(self, test_mode=False):
        self.test_mode = test_mode

    def _get_human_data(self):
        """Load human data from the JSON file"""
        if self.test_mode:
            return {
                "human_types": [
                    {
                        "name": "test human",
                        "resilience": 25,
                        "description": "A test human"
                    }
                ]
            }
        else:
            file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'human_entities.json')
            with open(file_path, 'r') as f:
                return json.load(f)

    def _get_state_file_path(self):
        """Get the path to the current human state file"""
        return os.path.join(DATA_PATH, 'current_human.json')

    def _get_current_state(self):
        """Get the current state from file"""
        try:
            with open(self._get_state_file_path(), 'r') as f:
                state = json.load(f)
                return {
                    'current_human': state.get('current_human'),
                    'last_spawn_date': state.get('last_spawn_date')
                }
        except (FileNotFoundError, json.JSONDecodeError):
            return {'current_human': None, 'last_spawn_date': None}

    def _save_state(self, current_human, last_spawn_date):
        """Save the state to file"""
        state = {
            'current_human': current_human,
            'last_spawn_date': str(last_spawn_date) if last_spawn_date else None
        }
        with open(self._get_state_file_path(), 'w') as f:
            json.dump(state, f)

    def spawn_human(self):
        """Spawn a new human if one hasn't been spawned today"""
        state = self._get_current_state()
        today = get_current_date()
        current_human = state['current_human']
        last_spawn_date = state['last_spawn_date']

        # Only spawn if there's no current human or if the current human was defeated and it's a new day
        if current_human is None or (
            last_spawn_date != today and current_human.get("resilience", 0) <= 0
        ):
            human_data = self._get_human_data()
            # In test mode, always use the first human for predictability
            human_type = human_data["human_types"][0] if self.test_mode else random.choice(human_data["human_types"])
            current_human = {
                "name": human_type["name"],
                "resilience": human_type["resilience"],
                "max_resilience": human_type["resilience"],
                "description": human_type["description"]
            }
            self._save_state(current_human, today)
        return current_human

    def damage_human(self, amount):
        """Apply damage to the current human and return if they were defeated"""
        state = self._get_current_state()
        current_human = state['current_human']
        if current_human:
            current_human["resilience"] = max(0, current_human["resilience"] - amount)
            self._save_state(current_human, state['last_spawn_date'])
            return current_human["resilience"] <= 0
        return False
