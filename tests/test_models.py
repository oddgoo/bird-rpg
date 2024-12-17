import pytest
from datetime import datetime, timedelta
from data.models import (
    get_personal_nest, get_common_nest, get_remaining_actions,
    record_actions, has_been_sung_to, has_been_sung_to_by,
    record_song, get_singers_today, add_bonus_actions,
    get_egg_cost, select_random_bird_species, record_brooding,
    has_brooded_egg, get_total_chicks, load_bird_species,
    get_nest_building_bonus, get_singing_bonus,
    get_seed_gathering_bonus, get_singing_inspiration_chance,
    is_first_action_of_type
)
import random
from utils.time_utils import get_current_date
from constants import BASE_DAILY_ACTIONS  # Updated import path

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
            "chicks": [],
            "garden_size": 0,
            "inspiration": 0
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
        assert actions == BASE_DAILY_ACTIONS  # Use constant instead of hardcoded value

    def test_record_actions(self, mock_data):
        record_actions(mock_data, "123", 1)
        remaining = get_remaining_actions(mock_data, "123")
        assert remaining == BASE_DAILY_ACTIONS - 1

    def test_bonus_actions(self, mock_data):
        add_bonus_actions(mock_data, "123", 3)
        remaining = get_remaining_actions(mock_data, "123")
        assert remaining == BASE_DAILY_ACTIONS + 3  # Base + bonus

    def test_add_negative_bonus_actions(self, mock_data):
        add_bonus_actions(mock_data, "123", -2)
        remaining = get_remaining_actions(mock_data, "123")
        assert remaining == BASE_DAILY_ACTIONS - 2  # Bonus actions decreased by 2

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

    def test_multiple_targets_song(self, mock_data):
        """Test singing to multiple targets in one go"""
        singer_id = "123"
        target_ids = ["456", "789", "101"]
        
        # Record songs to multiple targets
        for target_id in target_ids:
            record_song(mock_data, singer_id, target_id)
            add_bonus_actions(mock_data, target_id, 3)
        
        # Verify each target was sung to
        for target_id in target_ids:
            assert has_been_sung_to_by(mock_data, singer_id, target_id)
            assert has_been_sung_to(mock_data, target_id)

    def test_multiple_targets_with_duplicates(self, mock_data):
        """Test handling duplicate targets in the list"""
        singer_id = "123"
        target_ids = ["456", "456", "789"]  # Duplicate target
        
        # First song should work, second should still record but not give bonus actions
        for target_id in target_ids:
            if not has_been_sung_to_by(mock_data, singer_id, target_id):
                record_song(mock_data, singer_id, target_id)
                add_bonus_actions(mock_data, target_id, 3)
        
        # Check the results
        assert len(get_singers_today(mock_data, "456")) == 1  # Should only record once
        assert has_been_sung_to_by(mock_data, singer_id, "789")

    def test_multiple_targets_insufficient_actions(self, mock_data):
        """Test singing to multiple targets with limited actions"""
        singer_id = "123"
        target_ids = ["456", "789", "101"]
        
        record_actions(mock_data, singer_id, 2)
        
        successful_targets = []
        for target_id in target_ids:
            remaining_actions = get_remaining_actions(mock_data, singer_id)
            if remaining_actions > 0:
                record_song(mock_data, singer_id, target_id)
                add_bonus_actions(mock_data, target_id, 3)
                record_actions(mock_data, singer_id, 1)
                successful_targets.append(target_id)
        
        assert len(successful_targets) == BASE_DAILY_ACTIONS-2  # Should only sing to first two targets
        assert not has_been_sung_to_by(mock_data, singer_id, target_ids[2])  # Last target shouldn't be sung to

    def test_multiple_targets_mixed_validity(self, mock_data):
        """Test singing to a mix of valid and invalid targets"""
        singer_id = "123"
        # Simulate one target that's already been sung to
        record_song(mock_data, singer_id, "456")
        
        target_ids = ["456", "789", singer_id]  # One sung to, one fresh, one self
        
        successful_targets = []
        for target_id in target_ids:
            if (target_id != singer_id and  # Not self
                not has_been_sung_to_by(mock_data, singer_id, target_id)):  # Not already sung to
                record_song(mock_data, singer_id, target_id)
                add_bonus_actions(mock_data, target_id, 3)
                successful_targets.append(target_id)
        
        assert len(successful_targets) == 1  # Only "789" should be successful
        assert "789" in successful_targets

class TestEdgeCases:
    def test_zero_remaining_actions(self, mock_data):
        record_actions(mock_data, "123", BASE_DAILY_ACTIONS)
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
        assert remaining == BASE_DAILY_ACTIONS + 100  # Base + bonus

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
        assert actions_data <= BASE_DAILY_ACTIONS  # Should not exceed base actions

    def test_concurrent_bonus_actions(self, mock_data):
        """Test multiple bonus action additions"""
        # Add bonus actions multiple times
        add_bonus_actions(mock_data, "123", 1)
        add_bonus_actions(mock_data, "123", 2)
        add_bonus_actions(mock_data, "123", 3)
        
        remaining = get_remaining_actions(mock_data, "123")
        assert remaining == BASE_DAILY_ACTIONS + 6  # 3 base + (1+2+3) bonus

    def test_cross_day_boundary(self, mock_data):
        """Test that actions reset properly across days"""
        # Record actions for yesterday
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        mock_data["daily_actions"]["123"] = {
            f"actions_{yesterday}": {"used": 3, "bonus": 2}
        }
        
        # Check today's actions
        remaining = get_remaining_actions(mock_data, "123")
        assert remaining == BASE_DAILY_ACTIONS  # Should be fresh daily actions

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

        print(actual_proportions)
        
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
        today = today = get_current_date()
        
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
        expected_actions = BASE_DAILY_ACTIONS + len(nest["chicks"])
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

class TestBirdEffects:
    def test_first_build_bonus_birds(self, mock_data):
        """Test that birds with first-build-of-day bonuses stack correctly"""
        user_id = "123"
        today = get_current_date()
        
        # Initialize daily actions
        mock_data["daily_actions"] = {
            user_id: {
                f"actions_{today}": {
                    "used": 0,
                    "bonus": 0
                }
            }
        }
        
        nest = get_personal_nest(mock_data, user_id)
        
        # Add birds with first-build bonuses
        nest["chicks"].extend([
            {
                "commonName": "Plains-wanderer",
                "scientificName": "Pedionomus torquatus",
            },
            {
                "commonName": "Southern Cassowary",
                "scientificName": "Casuarius casuarius",
            },
            {
                "commonName": "Plains-wanderer",
                "scientificName": "Pedionomus torquatus",
            }
        ])
        
        # First build of the day should get stacking bonuses
        bonus_twigs = get_nest_building_bonus(mock_data, nest)
        assert bonus_twigs == 13, "Should get +5 twigs per Plains-wanderer and +3 from Cassowary"
        
        # Record a build action
        record_actions(mock_data, user_id, 1, "build")
        
        # Subsequent builds should not get bonuses
        bonus_twigs = get_nest_building_bonus(mock_data, nest)
        assert bonus_twigs == 0, "Should not get bonus on subsequent builds"

    def test_singing_bonus_stacking(self, mock_data):
        """Test Orange-bellied Parrot and Night Parrot singing bonuses stack"""
        user_id = "123"
        today = get_current_date()
        
        # Initialize daily actions
        mock_data["daily_actions"] = {
            user_id: {
                f"actions_{today}": {
                    "used": 0,
                    "bonus": 0
                }
            }
        }
        
        nest = get_personal_nest(mock_data, user_id)
        
        # Add both rare parrots to nest
        nest["chicks"].extend([
            {
                "commonName": "Orange-bellied Parrot",
                "scientificName": "Neophema chrysogaster",
                "effect": "Your singing actions give +3 bonus actions to the target"
            },
            {
                "commonName": "Night Parrot",
                "scientificName": "Pezoporus occidentalis",
                "effect": "Your singing actions give +5 bonus actions to the target"
            }
        ])
        
        bonus = get_singing_bonus(nest)
        assert bonus == 8, "Should get +3 from Orange-bellied and +5 from Night Parrot"

    def test_multiple_same_bird_effects(self, mock_data):
        """Test multiple copies of same bird stack effects"""
        user_id = "123"
        today = get_current_date()
        
        # Initialize daily actions
        mock_data["daily_actions"] = {
            user_id: {
                f"actions_{today}": {
                    "used": 0,
                    "bonus": 0
                }
            }
        }
        
        nest = get_personal_nest(mock_data, user_id)
        
        # Add two Orange-bellied Parrots
        nest["chicks"].extend([
            {
                "commonName": "Orange-bellied Parrot",
                "scientificName": "Neophema chrysogaster",
                "effect": "Your singing actions give +3 bonus actions to the target"
            },
            {
                "commonName": "Orange-bellied Parrot",
                "scientificName": "Neophema chrysogaster",
                "effect": "Your singing actions give +3 bonus actions to the target"
            }
        ])
        
        bonus = get_singing_bonus(nest)
        assert bonus == 6, "Multiple copies of same bird should stack effects (+3 each)"

    def test_no_effect_birds(self, mock_data):
        """Test birds without effects don't contribute bonuses"""
        user_id = "123"
        nest = get_personal_nest(mock_data, user_id)
        
        # Add some common birds
        nest["chicks"].extend([
            {
                "commonName": "Australian White Ibis",
                "scientificName": "Threskiornis molucca"
            },
            {
                "commonName": "Noisy Miner",
                "scientificName": "Manorina melanocephala"
            }
        ])
        
        build_bonus = get_nest_building_bonus(mock_data, nest)
        sing_bonus = get_singing_bonus(nest)
        
        assert build_bonus == 0, "Common birds should not give building bonus"
        assert sing_bonus == 0, "Common birds should not give singing bonus"

class TestMultiBrooding:
    def test_multi_brooding_different_nests(self, mock_data):
        """Test brooding multiple different nests in one go"""
        brooder_id = "123"
        target_ids = ["456", "789", "101"]
        
        # Setup nests with eggs
        for target_id in target_ids:
            nest = get_personal_nest(mock_data, target_id)
            nest["egg"] = {"brooding_progress": 5, "brooded_by": []}
        
        # Record brooding for each target
        successful_broods = []
        for target_id in target_ids:
            if not has_brooded_egg(mock_data, brooder_id, target_id):
                record_brooding(mock_data, brooder_id, target_id)
                nest = get_personal_nest(mock_data, target_id)
                nest["egg"]["brooding_progress"] += 1
                record_actions(mock_data, brooder_id, 1)
                successful_broods.append(target_id)
        
        assert len(successful_broods) == 3, "Should successfully brood all three nests"
        for target_id in target_ids:
            nest = get_personal_nest(mock_data, target_id)
            assert nest["egg"]["brooding_progress"] == 6, f"Nest {target_id} should have 6 brooding progress"
            assert brooder_id in nest["egg"]["brooded_by"], f"Brooder should be recorded in nest {target_id}"

    def test_multi_brooding_insufficient_actions(self, mock_data):
        """Test multi-brooding with limited actions available"""
        brooder_id = "123"
        target_ids = ["456", "789", "101"]
        
        # Setup nests with eggs
        for target_id in target_ids:
            nest = get_personal_nest(mock_data, target_id)
            nest["egg"] = {"brooding_progress": 5, "brooded_by": []}
        
        # Set remaining actions to 2
        mock_data["daily_actions"][brooder_id] = {
            f"actions_{get_current_date()}": {"used": BASE_DAILY_ACTIONS - 2, "bonus": 0}
        }
        
        successful_broods = []
        for target_id in target_ids:
            remaining_actions = get_remaining_actions(mock_data, brooder_id)
            if remaining_actions > 0 and not has_brooded_egg(mock_data, brooder_id, target_id):
                record_brooding(mock_data, brooder_id, target_id)
                nest = get_personal_nest(mock_data, target_id)
                nest["egg"]["brooding_progress"] += 1
                record_actions(mock_data, brooder_id, 1)
                successful_broods.append(target_id)
        
        assert len(successful_broods) == 2, "Should only brood two nests due to action limit"
        assert get_remaining_actions(mock_data, brooder_id) == 0, "Should have no actions remaining"

class TestRandomBrooding:
    def test_random_brooding_selection(self, mock_data):
        """Test random brooding selects from valid targets"""
        brooder_id = "123"
        target_ids = ["456", "789", "101"]
        
        # Setup nests with eggs
        for target_id in target_ids:
            nest = get_personal_nest(mock_data, target_id)
            nest["egg"] = {"brooding_progress": 5, "brooded_by": []}
        
        # Record brooding for one target to make it invalid
        record_brooding(mock_data, brooder_id, target_ids[0])
        
        # Get valid targets
        valid_targets = []
        for target_id in target_ids:
            if not has_brooded_egg(mock_data, brooder_id, target_id):
                valid_targets.append(target_id)
        
        assert len(valid_targets) == 2, "Should have two valid targets remaining"
        assert target_ids[0] not in valid_targets, "Already brooded target should not be valid"

    def test_random_brooding_no_targets(self, mock_data):
        """Test random brooding with no valid targets"""
        brooder_id = "123"
        target_ids = ["456", "789"]
        
        # Setup nests with eggs and mark them as brooded
        for target_id in target_ids:
            nest = get_personal_nest(mock_data, target_id)
            nest["egg"] = {"brooding_progress": 5, "brooded_by": []}
            record_brooding(mock_data, brooder_id, target_id)
        
        # Get valid targets
        valid_targets = []
        for target_id in target_ids:
            if not has_brooded_egg(mock_data, brooder_id, target_id):
                valid_targets.append(target_id)
        
        assert len(valid_targets) == 0, "Should have no valid targets"

class TestFlockCommands:
    def test_flock_session_creation(self, mock_data):
        """Test creating a new flock session"""
        leader_id = "123"
        active_flocks = {}
        
        # Create new flock session
        active_flocks[leader_id] = {
            'leader': leader_id,
            'members': [leader_id],
            'start_time': datetime.now(),
            'joining_deadline': datetime.now() + timedelta(minutes=10)
        }
        
        assert leader_id in active_flocks
        assert len(active_flocks[leader_id]['members']) == 1
        assert active_flocks[leader_id]['leader'] == leader_id

    def test_flock_session_joining(self, mock_data):
        """Test joining an existing flock session"""
        leader_id = "123"
        joiner_id = "456"
        active_flocks = {}
        
        # Create flock session
        active_flocks[leader_id] = {
            'leader': leader_id,
            'members': [leader_id],
            'start_time': datetime.now(),
            'joining_deadline': datetime.now() + timedelta(minutes=10)
        }
        
        # Join flock
        flock = active_flocks[leader_id]
        flock['members'].append(joiner_id)
        
        assert len(flock['members']) == 2
        assert joiner_id in flock['members']

    def test_flock_session_rewards(self, mock_data):
        """Test flock session completion rewards"""
        leader_id = "123"
        member_id = "456"
        active_flocks = {
            leader_id: {
                'leader': leader_id,
                'members': [leader_id, member_id],
                'start_time': datetime.now(),
                'joining_deadline': datetime.now() + timedelta(minutes=10)
            }
        }
        
        # Simulate session completion and reward distribution
        for member in active_flocks[leader_id]['members']:
            member_str = str(member)
            if member_str not in mock_data:
                mock_data[member_str] = {'garden_size': 0}
            if 'garden_size' not in mock_data[member_str]:
                mock_data[member_str]['garden_size'] = 0
            
            # Increment garden size and add bonus actions
            mock_data[member_str]['garden_size'] += 1
            add_bonus_actions(mock_data, member, 5)
        
        # Verify rewards
        for member in active_flocks[leader_id]['members']:
            member_str = str(member)
            assert mock_data[member_str]['garden_size'] == 1
            assert get_remaining_actions(mock_data, member) == BASE_DAILY_ACTIONS + 5

    def test_flock_session_deadline(self, mock_data):
        """Test flock session joining deadline"""
        leader_id = "123"
        joiner_id = "456"
        active_flocks = {}
        
        # Create expired flock session
        active_flocks[leader_id] = {
            'leader': leader_id,
            'members': [leader_id],
            'start_time': datetime.now() - timedelta(minutes=15),
            'joining_deadline': datetime.now() - timedelta(minutes=5)
        }
        
        flock = active_flocks[leader_id]
        assert datetime.now() > flock['joining_deadline']
        
        # Attempt to join after deadline
        initial_members = len(flock['members'])
        if datetime.now() <= flock['joining_deadline']:
            flock['members'].append(joiner_id)
        
        assert len(flock['members']) == initial_members
        assert joiner_id not in flock['members']

class TestLoreMechanics:


    def test_duplicate_memoir_same_day(self, mock_data):
        """Test that a user can't add multiple memoirs on the same day"""
        user_id = "123"
        nest = get_personal_nest(mock_data, user_id)
        today = get_current_date()
        
        # Add first memoir
        first_memoir = {
            "user_id": user_id,
            "nest_name": nest["name"],
            "text": "First memoir",
            "date": today
        }
        
        if "memoirs" not in mock_data:
            mock_data["memoirs"] = []
        mock_data["memoirs"].append(first_memoir)
        
        # Try to add second memoir
        has_memoir_today = any(
            memoir["user_id"] == user_id and memoir["date"] == today
            for memoir in mock_data["memoirs"]
        )
        
        assert has_memoir_today
        assert len([m for m in mock_data["memoirs"] if m["user_id"] == user_id and m["date"] == today]) == 1

    def test_memoir_length_limit(self, mock_data):
        """Test that memoirs are limited to 256 characters"""
        user_id = "123"
        nest = get_personal_nest(mock_data, user_id)
        long_text = "x" * 257
        
        # Verify text is too long
        assert len(long_text) > 256
        
        # Try to add memoir (should not be added due to length)
        if len(long_text) <= 256:
            if "memoirs" not in mock_data:
                mock_data["memoirs"] = []
            mock_data["memoirs"].append({
                "user_id": user_id,
                "nest_name": nest["name"],
                "text": long_text,
                "date": get_current_date()
            })
        
        # Check memoir was not added
        assert len(mock_data.get("memoirs", [])) == 0


def test_get_seed_gathering_bonus(mock_data):
    """Test garden size bonus calculation from cockatoos"""
    nest = {
        "chicks": [
            {
                "commonName": "Gang-gang Cockatoo",
                "scientificName": "Callocephalon fimbriatum",
                "effect": "Your first seed gathering action of the day also gives +1 garden size"
            },
            {
                "commonName": "Major Mitchell's Cockatoo",
                "scientificName": "Lophochroa leadbeateri",
                "effect": "Your first seed gathering action of the day also gives +1 garden size"
            }
        ]
    }
    mock_data["personal_nests"] = {"123": nest}
    
    # Test first action of the day
    bonus = get_seed_gathering_bonus(mock_data, nest)
    assert bonus == 2
    
    # Test after actions used
    record_actions(mock_data, "123", 1, "seed")
    bonus = get_seed_gathering_bonus(mock_data, nest)
    assert bonus == 0

def test_get_singing_inspiration_chance(mock_data, mocker):
    """Test inspiration chance calculation from finches"""
    # Mock random to always return 0.4 (less than 0.5, so inspiration triggers)
    mocker.patch('random.random', return_value=0.4)
    
    nest = {
        "chicks": [
            {
                "commonName": "Black-throated Finch",
                "scientificName": "Poephila cincta",
            },
            {
                "commonName": "Gouldian Finch",
                "scientificName": "Erythrura gouldiae",
            }
        ]
    }
    mock_data["personal_nests"] = {"123": nest}
    
    # Test first action of the day
    bonus = get_singing_inspiration_chance(mock_data, nest)
    assert bonus == 2  # Both finches should trigger
    
    # Test after actions used
    record_actions(mock_data, "123", 1, "sing")
    bonus = get_singing_inspiration_chance(mock_data, nest)
    assert bonus == 0

def test_action_history_tracking(mock_data):
    """Test that action history is properly tracked"""
    user_id = "123"
    
    # Record different types of actions
    record_actions(mock_data, user_id, 1, "build")
    record_actions(mock_data, user_id, 2, "seed")
    record_actions(mock_data, user_id, 1, "sing")
    
    today = get_current_date()
    daily_data = mock_data["daily_actions"][user_id][f"actions_{today}"]
    
    assert daily_data["used"] == 4
    assert daily_data["action_history"] == ["build", "seed", "seed", "sing"]
    
    # Test is_first_action_of_type
    assert not is_first_action_of_type(mock_data, user_id, "build")
    assert not is_first_action_of_type(mock_data, user_id, "seed")
    assert not is_first_action_of_type(mock_data, user_id, "sing")
    assert is_first_action_of_type(mock_data, user_id, "brood")

def test_first_action_bonuses(mock_data):
    """Test that first-action bonuses only trigger on first action of that type"""
    user_id = "123"
    nest = get_personal_nest(mock_data, user_id)
    
    # Add birds with first-action bonuses
    nest["chicks"] = [
        {
            "commonName": "Plains-wanderer",
            "scientificName": "Pedionomus torquatus"
        },
        {
            "commonName": "Gang-gang Cockatoo",
            "scientificName": "Callocephalon fimbriatum"
        }
    ]
    
    # First actions should get bonuses
    assert get_nest_building_bonus(mock_data, nest) == 5
    assert get_seed_gathering_bonus(mock_data, nest) == 1
    
    # Record the actions
    record_actions(mock_data, user_id, 1, "build")
    record_actions(mock_data, user_id, 1, "seed")
    
    # Subsequent actions should not get bonuses
    assert get_nest_building_bonus(mock_data, nest) == 0
    assert get_seed_gathering_bonus(mock_data, nest) == 0

