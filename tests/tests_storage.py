import pytest
import os
from data.storage import load_data, save_data

def test_save_and_load_data(tmp_path):
    test_data = {
        "personal_nests": {"123": {"twigs": 5, "seeds": 3}},
        "common_nest": {"twigs": 10, "seeds": 8},
        "daily_actions": {}
    }
    
    file_path = tmp_path / "test_nests.json"
    os.environ['NESTS_FILE'] = str(file_path)
    
    save_data(test_data)
    loaded_data = load_data()
    assert loaded_data == test_data
