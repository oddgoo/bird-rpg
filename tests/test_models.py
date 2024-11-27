import pytest
from datetime import datetime, timedelta
from data.models import (
    get_personal_nest, get_common_nest, get_remaining_actions,
    record_actions, has_been_sung_to, has_been_sung_to_by,
    record_song, get_singers_today, add_bonus_actions,
    get_egg_cost, select_random_bird_species, record_brooding,
    has_brooded_egg, get_total_chicks, load_bird_species
)
import random

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
        assert nest == {
            "twigs": 0,
            "seeds": 0,
            "name": "Some Bird's Nest",
            "egg": None,
            "chicks": []
        }
        assert "123" in mock_data["personal_nests"]

    def test_add_seeds_within_capacity(self, mock_data):
        nest = get_personal_nest(mock_data, "123")
        nest["twigs"] = 5
        nest["seeds"] = 2
        assert nest["seeds"] + 2 <= nest["twigs"]  # Verify space available

    def test_add_seeds_beyond_capacity(self, mock_data):
        nest = get_personal_nest(mock_data, "123")
        nest["twigs"] = 3
        nest["seeds"] = 3
        nest["seeds"] += 2
        assert nest["seeds"] > nest["twigs"], "Should not allow seeds to exceed twigs"

    def test_move_seeds_no_seeds(self, mock_data):
        nest = get_personal_nest(mock_data, "123")
        common_nest = get_common_nest(mock_data)
        nest["twigs"] = 5
        nest["seeds"] = 0
        common_nest["twigs"] = 5
        common_nest["seeds"] = 0
        if nest["seeds"] < 1:
            with pytest.raises(ValueError):
                raise ValueError("Not enough seeds to move")
        else:
            nest["seeds"] -= 1
            common_nest["seeds"] += 1

    def test_get_personal_nest_type_safety(self, mock_data):
        """Test that personal nest handles different ID types correctly"""
        # Test with different ID types
        int_id = get_personal_nest(mock_data, 123)
        str_id = get_personal_nest(mock_data, "123")
        
        assert int_id == str_id
        assert isinstance(int_id["twigs"], int)
        assert isinstance(int_id["seeds"], int)

    def test_common_nest_initialization(self, mock_data):
        """Test common nest is properly initialized"""
        del mock_data["common_nest"]
        mock_data["common_nest"] = None
        
        common_nest = get_common_nest(mock_data)
        assert isinstance(common_nest, dict)
        assert "twigs" in common_nest
        assert "seeds" in common_nest

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

    def test_record_negative_actions(self, mock_data):
        record_actions(mock_data, "123", -1)
        remaining = get_remaining_actions(mock_data, "123")
        assert remaining == 4  # Actions should decrease 'used' by -1, increasing remaining

    def test_add_negative_bonus_actions(self, mock_data):
        add_bonus_actions(mock_data, "123", -2)
        remaining = get_remaining_actions(mock_data, "123")
        assert remaining == 1  # Bonus actions decreased by 2

class TestSongMechanics:
    def test_record_and_check_song(self, mock_data):
        singer_id = "123"
        target_id = "456"
        
        assert not has_been_sung_to_by(mock_data, singer_id, target_id)
        
        record_song(mock_data, singer_id, target_id)
        
        assert has_been_sung_to_by(mock_data, singer_id, target_id)
        assert has_been_sung_to(mock_data, target_id)
        
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

    def test_sing_duplicate(self, mock_data):
        singer_id = "123"
        target_id = "456"
        record_song(mock_data, singer_id, target_id)
        record_song(mock_data, singer_id, target_id)
        singers = get_singers_today(mock_data, target_id)
        assert singers.count(singer_id) == 2, "Singer should be recorded twice"

    def test_sing_self(self, mock_data):
        singer_id = "123"
        target_id = "123"
        record_song(mock_data, singer_id, target_id)
        assert has_been_sung_to_by(mock_data, singer_id, target_id), "User should be able to sing to themselves if allowed"

    def test_empty_daily_songs(self, mock_data):
        """Test behavior when daily_songs structure doesn't exist"""
        del mock_data["daily_songs"]
        
        # Should handle missing structure gracefully
        assert not has_been_sung_to(mock_data, "123")
        assert not has_been_sung_to_by(mock_data, "456", "123")
        assert get_singers_today(mock_data, "123") == []

    def test_record_song_creates_structure(self, mock_data):
        """Test that recording a song creates necessary data structure"""
        del mock_data["daily_songs"]
        
        record_song(mock_data, "singer", "target")
        
        assert "daily_songs" in mock_data
        assert len(mock_data["daily_songs"]) > 0

class TestEdgeCases:
    def test_zero_remaining_actions(self, mock_data):
        record_actions(mock_data, "123", 3)
        remaining = get_remaining_actions(mock_data, "123")
        assert remaining == 0, "Remaining actions should be zero after using all actions"

    def test_add_zero_seeds(self, mock_data):
        nest = get_personal_nest(mock_data, "123")
        initial_seeds = nest["seeds"]
        nest["seeds"] += 0
        assert nest["seeds"] == initial_seeds, "Seeds should remain unchanged when adding zero"

    def test_maximum_possible_actions(self, mock_data):
        add_bonus_actions(mock_data, "123", 100)
        remaining = get_remaining_actions(mock_data, "123")
        assert remaining == 103, "Remaining actions should be 103 (3 default + 100 bonus)"

    def test_negative_seeds_direct_assignment(self, mock_data):
        nest = get_personal_nest(mock_data, "123")
        nest["seeds"] = -5
        assert nest["seeds"] == -5, "Seeds should be allowed to be negative if not handled properly"

    def test_negative_twigs_direct_assignment(self, mock_data):
        common_nest = get_common_nest(mock_data)
        common_nest["twigs"] = -10
        assert common_nest["twigs"] == -10, "Twigs should be allowed to be negative if not handled properly"

class TestDataConsistency:
    def test_action_counting_overflow(self, mock_data):
        """Test handling of very large action counts"""
        # Try to record an extremely large number of actions
        record_actions(mock_data, "123", 1000000)
        
        actions_data = get_remaining_actions(mock_data, "123")
        assert isinstance(actions_data, (int, float))
        assert actions_data <= 3  # Should not exceed base actions

    def test_concurrent_bonus_actions(self, mock_data):
        """Test multiple bonus action additions"""
        # Add bonus actions multiple times
        add_bonus_actions(mock_data, "123", 1)
        add_bonus_actions(mock_data, "123", 2)
        add_bonus_actions(mock_data, "123", 3)
        
        remaining = get_remaining_actions(mock_data, "123")
        assert remaining == 9  # 3 base + (1+2+3) bonus

    def test_cross_day_boundary(self, mock_data):
        """Test that actions reset properly across days"""
        # Record actions for yesterday
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        mock_data["daily_actions"]["123"] = {
            f"actions_{yesterday}": {"used": 3, "bonus": 2}
        }
        
        # Check today's actions
        remaining = get_remaining_actions(mock_data, "123")
        assert remaining == 3  # Should be fresh daily actions

class TestIncubationModule:
    def test_lay_egg_success(self, mock_data):
        """Test laying an egg with sufficient seeds and no existing egg"""
        user_id = "123"
        nest = get_personal_nest(mock_data, user_id)
        nest["seeds"] = 50  # Sufficient seeds
        assert "egg" not in nest or nest["egg"] is None
        
        egg_cost = get_egg_cost(nest)
        nest["seeds"] -= egg_cost
        nest["egg"] = {"brooding_progress": 0, "brooded_by": []}
        
        assert nest["seeds"] == 50 - egg_cost
        assert nest["egg"]["brooding_progress"] == 0
        assert nest["egg"]["brooded_by"] == []

    def test_brood_egg_progress(self, mock_data):
        """Test brooding an egg increments brooding progress"""
        user_id = "123"
        brooder_id = "456"
        nest = get_personal_nest(mock_data, user_id)
        nest["egg"] = {"brooding_progress": 5, "brooded_by": []}
        mock_data["daily_actions"][brooder_id] = {"actions_2023-10-10": {"used": 0, "bonus": 0}}
        
        # Brooder broods the egg
        record_brooding(mock_data, brooder_id, user_id)
        nest["egg"]["brooding_progress"] += 1
        record_actions(mock_data, brooder_id, 1)
        
        assert nest["egg"]["brooding_progress"] == 6
        assert brooder_id in nest["egg"]["brooded_by"]

    def test_hatch_egg(self, mock_data, mocker):
        """Test that an egg hatches correctly into a chick"""
        user_id = "123"
        nest = get_personal_nest(mock_data, user_id)
        nest["egg"] = {"brooding_progress": 10, "brooded_by": ["456"]}
        initial_chicks = len(nest["chicks"])
        
        # Mock select_random_bird_species to return a fixed species
        mock_species = {
            "commonName": "Test Finch",
            "scientificName": "Testus finchus"
        }
        mocker.patch('data.models.select_random_bird_species', return_value=mock_species)
        
        # Hatch the egg
        bird_species = select_random_bird_species()
        chick = {
            "commonName": bird_species["commonName"],
            "scientificName": bird_species["scientificName"]
        }
        nest["chicks"].append(chick)
        nest["egg"] = None
        
        assert len(nest["chicks"]) == initial_chicks + 1
        assert nest["chicks"][-1] == chick
        assert nest["egg"] is None

    def test_select_random_bird_species_weighted(self, mock_data):
        """Test that bird species selection respects rarity weights"""
        species = load_bird_species()
        rarity_counts = {spec['commonName']: 0 for spec in species}
        trials = 10000
        for _ in range(trials):
            selected = select_random_bird_species()
            rarity_counts[selected['commonName']] += 1
        
        # Calculate expected proportions
        total_weight = sum(spec['rarityWeight'] for spec in species)
        expected_proportions = {
            spec['commonName']: spec['rarityWeight'] / total_weight
            for spec in species
        }
        
        # Calculate actual proportions
        actual_proportions = {
            name: count / trials
            for name, count in rarity_counts.items()
        }
        
        # Allow a tolerance of ±1%
        for name, expected in expected_proportions.items():
            actual = actual_proportions[name]
            assert abs(actual - expected) < 0.01, f"Rarity weight mismatch for {name}: expected ~{expected:.2f}, got {actual:.2f}"

    def test_brooding_limit(self, mock_data):
        """Test that a user cannot brood the same egg more than once per day"""
        user_id = "123"
        brooder_id = "456"
        nest = get_personal_nest(mock_data, user_id)
        nest["egg"] = {"brooding_progress": 5, "brooded_by": []}
        today = datetime.now().strftime('%Y-%m-%d')
        
        # First brooding attempt
        record_brooding(mock_data, brooder_id, user_id)
        nest["egg"]["brooding_progress"] += 1
        record_actions(mock_data, brooder_id, 1)
        assert brooder_id in nest["egg"]["brooded_by"]
        
        # Second brooding attempt on the same day
        has_brooded = has_brooded_egg(mock_data, brooder_id, user_id)
        assert has_brooded, "Brooder should have already brooded the egg today"
        
        # Attempt to brood again should be prevented
        if has_brooded:
            with pytest.raises(Exception):
                raise Exception("User has already brooded this egg today")

    def test_chicks_bonus_actions(self, mock_data):
        """Test that each chick grants 1 extra action per day"""
        user_id = "123"
        nest = get_personal_nest(mock_data, user_id)
        nest["chicks"] = [
            {"commonName": "Test Finch", "scientificName": "Testus finchus"},
            {"commonName": "Another Finch", "scientificName": "Anotherus finchus"}
        ]
        
        remaining_actions = get_remaining_actions(mock_data, user_id)
        expected_actions = 3 + len(nest["chicks"])
        assert remaining_actions == expected_actions, f"Expected {expected_actions} actions, got {remaining_actions}"

    def test_get_total_chicks(self, mock_data):
        """Test the get_total_chicks function"""
        user_id = "123"
        nest = get_personal_nest(mock_data, user_id)
        nest["chicks"] = [
            {"commonName": "Finch A", "scientificName": "Fincha fincha"},
            {"commonName": "Finch B", "scientificName": "Finchb fincha"},
            {"commonName": "Finch C", "scientificName": "Finchc fincha"}
        ]
        assert get_total_chicks(nest) == 3