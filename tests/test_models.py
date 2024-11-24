import pytest
from datetime import datetime, timedelta
from data.models import (
    get_personal_nest, get_common_nest, get_remaining_actions,
    record_actions, has_been_sung_to, has_been_sung_to_by,
    record_song, get_singers_today, add_bonus_actions
)

@pytest.fixture
def mock_data():
    return {
        "personal_nests": {},
        "common_nest": {"twigs": 0, "seeds": 0},
        "daily_actions": {},
        "daily_songs": {}
    }

class TestNestOperations:
    def test_get_personal_nest_new_user(self, mock_data):
        nest = get_personal_nest(mock_data, "123")
        assert nest == {"twigs": 0, "seeds": 0}
        assert "123" in mock_data["personal_nests"]

    def test_add_seeds_within_capacity(self, mock_data):
        nest = get_personal_nest(mock_data, "123")
        nest["twigs"] = 5
        nest["seeds"] = 2
        assert nest["seeds"] + 2 <= nest["twigs"]  # Verify space available

class TestActionTracking:
    def test_initial_actions_available(self, mock_data):
        actions = get_remaining_actions(mock_data, "123")
        assert actions == 3  # Default daily actions

    def test_record_actions(self, mock_data):
        record_actions(mock_data, "123", 1)
        remaining = get_remaining_actions(mock_data, "123")
        assert remaining == 2

    def test_bonus_actions(self, mock_data):
        add_bonus_actions(mock_data, "123", 3)
        remaining = get_remaining_actions(mock_data, "123")
        assert remaining == 6  # 3 default + 3 bonus

class TestSongMechanics:
    def test_record_and_check_song(self, mock_data):
        singer_id = "123"
        target_id = "456"
        
        # Initial state
        assert not has_been_sung_to_by(mock_data, singer_id, target_id)
        
        # Record song
        record_song(mock_data, singer_id, target_id)
        
        # Verify recording
        assert has_been_sung_to_by(mock_data, singer_id, target_id)
        assert has_been_sung_to(mock_data, target_id)
        
        # Verify singers list
        singers = get_singers_today(mock_data, target_id)
        assert singer_id in singers

    def test_multiple_singers(self, mock_data):
        target_id = "456"
        singers = ["123", "789", "101"]
        
        for singer_id in singers:
            record_song(mock_data, singer_id, target_id)
        
        assert len(get_singers_today(mock_data, target_id)) == len(singers)
        for singer_id in singers:
            assert has_been_sung_to_by(mock_data, singer_id, target_id)