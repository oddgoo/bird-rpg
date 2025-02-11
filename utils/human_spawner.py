import json
import random
import os
from datetime import date
from config.config import DATA_PATH

class HumanSpawner:
    def __init__(self, test_mode=False):
        self.test_mode = test_mode
        self._load_human_data()
        self._load_current_human()

    def _load_human_data(self):
        """Load human data from the JSON file"""
        if self.test_mode:
            self.human_data = {
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
                self.human_data = json.load(f)

    def _get_state_file_path(self):
        """Get the path to the current human state file"""
        return os.path.join(DATA_PATH, 'current_human.json')

    def _load_current_human(self):
        """Load the current human state from file"""
        try:
            with open(self._get_state_file_path(), 'r') as f:
                state = json.load(f)
                self.current_human = state.get('current_human')
                self.last_spawn_date = date.fromisoformat(state.get('last_spawn_date')) if state.get('last_spawn_date') else None
        except (FileNotFoundError, json.JSONDecodeError):
            self.current_human = None
            self.last_spawn_date = None

    def _save_current_human(self):
        """Save the current human state to file"""
        state = {
            'current_human': self.current_human,
            'last_spawn_date': str(self.last_spawn_date) if self.last_spawn_date else None
        }
        with open(self._get_state_file_path(), 'w') as f:
            json.dump(state, f)

    def spawn_human(self):
        """Spawn a new human if one hasn't been spawned today"""
        today = date.today()
        if self.current_human is None or (
            self.last_spawn_date != today and self.current_human.get("resilience", 0) <= 0
        ):
            # In test mode, always use the first human for predictability
            human_type = self.human_data["human_types"][0] if self.test_mode else random.choice(self.human_data["human_types"])
            self.current_human = {
                "name": human_type["name"],
                "resilience": human_type["resilience"],
                "max_resilience": human_type["resilience"],
                "description": human_type["description"]
            }
            self.last_spawn_date = today
            self._save_current_human()
        return self.current_human

    def damage_human(self, amount):
        """Apply damage to the current human and return if they were defeated"""
        if self.current_human:
            self.current_human["resilience"] = max(0, self.current_human["resilience"] - amount)
            self._save_current_human()
            return self.current_human["resilience"] <= 0
        return False 