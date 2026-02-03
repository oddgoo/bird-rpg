"""
Tests for data.models after the Supabase migration.

All model functions that touch the DB are now async and call data.storage (db).
Tests mock the storage layer and verify business logic.
"""

import pytest
import random
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from constants import BASE_DAILY_ACTIONS
from utils.time_utils import get_current_date

from data.models import (
    get_remaining_actions,
    record_actions,
    add_bonus_actions,
    is_first_action_of_type,
    get_egg_cost,
    can_bless_egg,
    bless_egg,
    handle_blessed_egg_hatching,
    select_random_bird_species,
    load_bird_species,
    clear_bird_species_cache,
    get_nest_building_bonus,
    get_singing_bonus,
    get_seed_gathering_bonus,
    get_singing_inspiration_chance,
    get_less_brood_chance,
    get_extra_bird_chance,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_player(**overrides):
    """Return a minimal player dict with sensible defaults."""
    base = {
        "user_id": "123",
        "twigs": 0,
        "seeds": 0,
        "name": "Some Bird's Nest",
        "garden_size": 0,
        "inspiration": 0,
        "bonus_actions": 0,
    }
    base.update(overrides)
    return base


def _make_daily_actions(used=0, action_history=None):
    return {"used": used, "action_history": action_history or []}


@pytest.fixture
def mock_db():
    """Patch data.storage (imported as db in models) with AsyncMocks."""
    clear_bird_species_cache()
    with patch("data.models.db") as db:
        db.load_player = AsyncMock(return_value=_make_player())
        db.get_player_birds = AsyncMock(return_value=[])
        db.get_daily_actions = AsyncMock(return_value=None)
        db.upsert_daily_actions = AsyncMock()
        db.increment_player_field = AsyncMock()
        db.get_egg = AsyncMock(return_value=None)
        db.update_egg = AsyncMock()
        db.load_manifested_birds = AsyncMock(return_value=[])
        db.load_manifested_plants = AsyncMock(return_value=[])
        yield db
    clear_bird_species_cache()


# ===================================================================
# get_remaining_actions
# ===================================================================

class TestGetRemainingActions:
    @pytest.mark.asyncio
    async def test_initial_actions_no_birds_no_bonus(self, mock_db):
        """Brand-new player with no birds, no bonus, no actions used."""
        remaining = await get_remaining_actions("123")
        assert remaining == BASE_DAILY_ACTIONS

    @pytest.mark.asyncio
    async def test_with_birds(self, mock_db):
        """Each bird gives +1 action."""
        mock_db.get_player_birds.return_value = [
            {"common_name": "A", "scientific_name": "A a"},
            {"common_name": "B", "scientific_name": "B b"},
        ]
        remaining = await get_remaining_actions("123")
        assert remaining == BASE_DAILY_ACTIONS + 2

    @pytest.mark.asyncio
    async def test_with_bonus_actions(self, mock_db):
        mock_db.load_player.return_value = _make_player(bonus_actions=3)
        remaining = await get_remaining_actions("123")
        assert remaining == BASE_DAILY_ACTIONS + 3

    @pytest.mark.asyncio
    async def test_after_some_used(self, mock_db):
        mock_db.get_daily_actions.return_value = _make_daily_actions(used=2)
        remaining = await get_remaining_actions("123")
        assert remaining == BASE_DAILY_ACTIONS - 2

    @pytest.mark.asyncio
    async def test_combination_birds_bonus_used(self, mock_db):
        mock_db.load_player.return_value = _make_player(bonus_actions=2)
        mock_db.get_player_birds.return_value = [{"common_name": "A", "scientific_name": "A a"}]
        mock_db.get_daily_actions.return_value = _make_daily_actions(used=3)
        remaining = await get_remaining_actions("123")
        # BASE + 2 bonus + 1 bird - 3 used
        assert remaining == BASE_DAILY_ACTIONS + 2 + 1 - 3

    @pytest.mark.asyncio
    async def test_negative_bonus_clamped_to_zero(self, mock_db):
        """Negative bonus_actions should be treated as 0."""
        mock_db.load_player.return_value = _make_player(bonus_actions=-5)
        remaining = await get_remaining_actions("123")
        assert remaining == BASE_DAILY_ACTIONS

    @pytest.mark.asyncio
    async def test_zero_remaining(self, mock_db):
        mock_db.get_daily_actions.return_value = _make_daily_actions(used=BASE_DAILY_ACTIONS)
        remaining = await get_remaining_actions("123")
        assert remaining == 0


# ===================================================================
# record_actions
# ===================================================================

class TestRecordActions:
    @pytest.mark.asyncio
    async def test_record_simple(self, mock_db):
        """Recording actions when no bonus_actions exist."""
        await record_actions("123", 2)
        mock_db.upsert_daily_actions.assert_awaited_once()
        args = mock_db.upsert_daily_actions.call_args
        # user_id, today, new_used, history
        assert args[0][2] == 2  # new_used

    @pytest.mark.asyncio
    async def test_record_with_action_type(self, mock_db):
        """Action type should be appended to the history."""
        await record_actions("123", 1, "build")
        args = mock_db.upsert_daily_actions.call_args
        history = args[0][3]
        assert history == ["build"]

    @pytest.mark.asyncio
    async def test_bonus_actions_consumed_first(self, mock_db):
        """Bonus actions should be consumed before regular actions."""
        mock_db.load_player.return_value = _make_player(bonus_actions=2)
        await record_actions("123", 3, "build")

        # Should decrement bonus_actions by 2
        mock_db.increment_player_field.assert_awaited_once_with("123", "bonus_actions", -2)

        # Only 1 regular action used (3 total - 2 bonus)
        args = mock_db.upsert_daily_actions.call_args
        assert args[0][2] == 1  # new_used = 0 + 1
        # History should still have 3 entries (all count toward history)
        assert args[0][3] == ["build", "build", "build"]

    @pytest.mark.asyncio
    async def test_all_covered_by_bonus(self, mock_db):
        """When bonus covers everything, no regular actions are consumed."""
        mock_db.load_player.return_value = _make_player(bonus_actions=5)
        await record_actions("123", 3)

        mock_db.increment_player_field.assert_awaited_once_with("123", "bonus_actions", -3)
        args = mock_db.upsert_daily_actions.call_args
        assert args[0][2] == 0  # no regular actions used

    @pytest.mark.asyncio
    async def test_record_appends_to_existing(self, mock_db):
        """Recording should add to existing daily action state."""
        mock_db.get_daily_actions.return_value = _make_daily_actions(used=1, action_history=["seed"])
        await record_actions("123", 1, "build")

        args = mock_db.upsert_daily_actions.call_args
        assert args[0][2] == 2  # 1 existing + 1 new
        assert args[0][3] == ["seed", "build"]


# ===================================================================
# add_bonus_actions
# ===================================================================

class TestAddBonusActions:
    @pytest.mark.asyncio
    async def test_add_positive(self, mock_db):
        await add_bonus_actions("123", 5)
        mock_db.increment_player_field.assert_awaited_once_with("123", "bonus_actions", 5)

    @pytest.mark.asyncio
    async def test_add_negative(self, mock_db):
        await add_bonus_actions("123", -2)
        mock_db.increment_player_field.assert_awaited_once_with("123", "bonus_actions", -2)


# ===================================================================
# is_first_action_of_type
# ===================================================================

class TestIsFirstActionOfType:
    @pytest.mark.asyncio
    async def test_no_actions_yet(self, mock_db):
        mock_db.get_daily_actions.return_value = None
        assert await is_first_action_of_type("123", "build") is True

    @pytest.mark.asyncio
    async def test_empty_history(self, mock_db):
        mock_db.get_daily_actions.return_value = _make_daily_actions(used=0, action_history=[])
        assert await is_first_action_of_type("123", "build") is True

    @pytest.mark.asyncio
    async def test_type_already_recorded(self, mock_db):
        mock_db.get_daily_actions.return_value = _make_daily_actions(used=2, action_history=["build", "seed"])
        assert await is_first_action_of_type("123", "build") is False
        assert await is_first_action_of_type("123", "seed") is False

    @pytest.mark.asyncio
    async def test_different_type_not_recorded(self, mock_db):
        mock_db.get_daily_actions.return_value = _make_daily_actions(used=1, action_history=["build"])
        assert await is_first_action_of_type("123", "sing") is True


# ===================================================================
# get_egg_cost  (sync, unchanged)
# ===================================================================

class TestGetEggCost:
    def test_returns_fixed_cost(self):
        assert get_egg_cost({}) == 20
        assert get_egg_cost({"seeds": 100}) == 20
        assert get_egg_cost(_make_player()) == 20


# ===================================================================
# handle_blessed_egg_hatching  (sync)
# ===================================================================

class TestHandleBlessedEggHatching:
    def test_unblessed_egg_returns_none(self):
        egg = {"multipliers": {"Bird1": 2, "Bird2": 1}}
        assert handle_blessed_egg_hatching(egg, "Bird1") is None

    def test_blessed_egg_hatched_most_prayed_returns_none(self):
        egg = {
            "protected_prayers": True,
            "multipliers": {"Bird1": 2, "Bird2": 1},
        }
        assert handle_blessed_egg_hatching(egg, "Bird1") is None

    def test_blessed_egg_hatched_different_bird_returns_multipliers(self):
        egg = {
            "protected_prayers": True,
            "multipliers": {"Bird1": 2, "Bird2": 1},
        }
        saved = handle_blessed_egg_hatching(egg, "Bird2")
        assert saved == {"Bird1": 2, "Bird2": 1}

    def test_blessed_egg_no_multipliers_returns_none(self):
        egg = {"protected_prayers": True}
        # No multipliers key at all -> empty dict -> falsy -> returns None
        assert handle_blessed_egg_hatching(egg, "Bird1") is None

    def test_blessed_egg_empty_multipliers_returns_none(self):
        egg = {"protected_prayers": True, "multipliers": {}}
        assert handle_blessed_egg_hatching(egg, "Bird1") is None

    def test_tied_most_prayed_birds(self):
        """When two birds are tied for most prayers, hatching either returns None."""
        egg = {
            "protected_prayers": True,
            "multipliers": {"Bird1": 3, "Bird2": 3, "Bird3": 1},
        }
        assert handle_blessed_egg_hatching(egg, "Bird1") is None
        assert handle_blessed_egg_hatching(egg, "Bird2") is None
        # Hatching Bird3 should save multipliers
        saved = handle_blessed_egg_hatching(egg, "Bird3")
        assert saved == {"Bird1": 3, "Bird2": 3, "Bird3": 1}


# ===================================================================
# can_bless_egg  (async, calls db)
# ===================================================================

class TestCanBlessEgg:
    @pytest.mark.asyncio
    async def test_no_egg(self, mock_db):
        mock_db.get_egg.return_value = None
        can, error = await can_bless_egg("123")
        assert can is False
        assert "don't have an egg" in error

    @pytest.mark.asyncio
    async def test_not_enough_resources(self, mock_db):
        mock_db.load_player.return_value = _make_player(inspiration=0, seeds=5)
        mock_db.get_egg.return_value = {}
        can, error = await can_bless_egg("123")
        assert can is False
        assert "need 1 inspiration" in error

    @pytest.mark.asyncio
    async def test_not_enough_seeds(self, mock_db):
        mock_db.load_player.return_value = _make_player(inspiration=5, seeds=10)
        mock_db.get_egg.return_value = {}
        can, error = await can_bless_egg("123")
        assert can is False
        assert "need 1 inspiration and 30 seeds" in error

    @pytest.mark.asyncio
    async def test_already_blessed(self, mock_db):
        mock_db.load_player.return_value = _make_player(inspiration=5, seeds=50)
        mock_db.get_egg.return_value = {"protected_prayers": True}
        can, error = await can_bless_egg("123")
        assert can is False
        assert "already blessed" in error

    @pytest.mark.asyncio
    async def test_can_bless_success(self, mock_db):
        mock_db.load_player.return_value = _make_player(inspiration=1, seeds=30)
        mock_db.get_egg.return_value = {}
        can, error = await can_bless_egg("123")
        assert can is True
        assert error is None


# ===================================================================
# bless_egg  (async)
# ===================================================================

class TestBlessEgg:
    @pytest.mark.asyncio
    async def test_successful_bless(self, mock_db):
        mock_db.load_player.return_value = _make_player(inspiration=5, seeds=40)
        mock_db.get_egg.return_value = {}
        success, message = await bless_egg("123")

        assert success
        assert "has been blessed" in message
        mock_db.increment_player_field.assert_any_await("123", "inspiration", -1)
        mock_db.increment_player_field.assert_any_await("123", "seeds", -30)
        mock_db.update_egg.assert_awaited_once_with("123", protected_prayers=True)

    @pytest.mark.asyncio
    async def test_failed_bless_insufficient_resources(self, mock_db):
        mock_db.load_player.return_value = _make_player(inspiration=0, seeds=5)
        mock_db.get_egg.return_value = {}
        success, message = await bless_egg("123")

        assert not success
        assert "need 1 inspiration" in message
        # Should not have modified anything
        mock_db.update_egg.assert_not_awaited()


# ===================================================================
# select_random_bird_species  (async)
# ===================================================================

class TestSelectRandomBirdSpecies:
    @pytest.mark.asyncio
    async def test_returns_a_species(self, mock_db):
        test_birds = [
            {"commonName": "Bird A", "scientificName": "A a", "rarityWeight": 10},
            {"commonName": "Bird B", "scientificName": "B b", "rarityWeight": 10},
        ]
        with patch("data.models._load_bird_species_json", return_value=test_birds):
            result = await select_random_bird_species()
            assert result in test_birds

    @pytest.mark.asyncio
    async def test_respects_multipliers(self, mock_db):
        test_birds = [
            {"commonName": "Bird A", "scientificName": "A a", "rarityWeight": 10},
            {"commonName": "Bird B", "scientificName": "B b", "rarityWeight": 10},
            {"commonName": "Bird C", "scientificName": "C c", "rarityWeight": 10},
        ]
        multipliers = {"A a": 100}  # Bird A massively boosted

        with patch("data.models._load_bird_species_json", return_value=test_birds):
            results = []
            for _ in range(200):
                r = await select_random_bird_species(multipliers)
                results.append(r["scientificName"])

            a_count = results.count("A a")
            # Bird A should dominate with 100x weight
            assert a_count > 150, f"Bird A should appear most often, got {a_count}/200"

    @pytest.mark.asyncio
    async def test_includes_manifested_birds(self, mock_db):
        standard = [
            {"commonName": "Bird A", "scientificName": "A a", "rarityWeight": 10},
        ]
        manifested = [
            {
                "common_name": "Manifested Bird",
                "scientific_name": "M m",
                "rarity_weight": 10,
                "fully_manifested": True,
            }
        ]
        mock_db.load_manifested_birds.return_value = manifested
        with patch("data.models._load_bird_species_json", return_value=standard):
            species = await load_bird_species(include_manifested=True)
            assert len(species) == 2
            names = [s["commonName"] for s in species]
            assert "Manifested Bird" in names


# ===================================================================
# Bird effect bonuses (async)
# ===================================================================

class TestNestBuildingBonus:
    @pytest.mark.asyncio
    async def test_first_build_with_bonus_birds(self, mock_db):
        mock_db.get_daily_actions.return_value = None  # no actions yet

        birds = [
            {"common_name": "Plains-wanderer", "scientific_name": "Pedionomus torquatus"},
        ]

        with patch("data.models.get_bird_effect", new_callable=AsyncMock) as mock_effect:
            mock_effect.return_value = "Your first nest-building action of the day gives +5 bonus twigs"
            bonus = await get_nest_building_bonus("123", birds)
            assert bonus == 5

    @pytest.mark.asyncio
    async def test_second_build_no_bonus(self, mock_db):
        mock_db.get_daily_actions.return_value = _make_daily_actions(used=1, action_history=["build"])

        birds = [
            {"common_name": "Plains-wanderer", "scientific_name": "Pedionomus torquatus"},
        ]

        with patch("data.models.get_bird_effect", new_callable=AsyncMock) as mock_effect:
            mock_effect.return_value = "Your first nest-building action of the day gives +5 bonus twigs"
            bonus = await get_nest_building_bonus("123", birds)
            assert bonus == 0

    @pytest.mark.asyncio
    async def test_stacking_multiple_bonus_birds(self, mock_db):
        mock_db.get_daily_actions.return_value = None

        birds = [
            {"common_name": "Plains-wanderer", "scientific_name": "Pedionomus torquatus"},
            {"common_name": "Southern Cassowary", "scientific_name": "Casuarius casuarius"},
            {"common_name": "Plains-wanderer", "scientific_name": "Pedionomus torquatus"},
        ]

        effects = {
            "Pedionomus torquatus": "Your first nest-building action of the day gives +5 bonus twigs",
            "Casuarius casuarius": "Your first nest-building action of the day gives +3 bonus twigs",
        }

        with patch("data.models.get_bird_effect", new_callable=AsyncMock) as mock_effect:
            mock_effect.side_effect = lambda sn: effects.get(sn, "")
            bonus = await get_nest_building_bonus("123", birds)
            assert bonus == 13  # 5 + 3 + 5

    @pytest.mark.asyncio
    async def test_no_effect_birds(self, mock_db):
        mock_db.get_daily_actions.return_value = None
        birds = [
            {"common_name": "Australian White Ibis", "scientific_name": "Threskiornis molucca"},
        ]
        with patch("data.models.get_bird_effect", new_callable=AsyncMock, return_value=""):
            bonus = await get_nest_building_bonus("123", birds)
            assert bonus == 0


class TestSingingBonus:
    @pytest.mark.asyncio
    async def test_singing_bonus_stacking(self, mock_db):
        birds = [
            {"common_name": "Orange-bellied Parrot", "scientific_name": "Neophema chrysogaster"},
            {"common_name": "Night Parrot", "scientific_name": "Pezoporus occidentalis"},
        ]

        effects = {
            "Neophema chrysogaster": "All your songs give +3 bonus actions to the target",
            "Pezoporus occidentalis": "All your songs give +10 bonus actions to the target",
        }

        with patch("data.models.get_bird_effect", new_callable=AsyncMock) as mock_effect:
            mock_effect.side_effect = lambda sn: effects.get(sn, "")
            bonus = await get_singing_bonus(birds)
            assert bonus == 13

    @pytest.mark.asyncio
    async def test_multiple_same_bird_stacks(self, mock_db):
        birds = [
            {"common_name": "Orange-bellied Parrot", "scientific_name": "Neophema chrysogaster"},
            {"common_name": "Orange-bellied Parrot", "scientific_name": "Neophema chrysogaster"},
        ]

        with patch("data.models.get_bird_effect", new_callable=AsyncMock) as mock_effect:
            mock_effect.return_value = "All your songs give +3 bonus actions to the target"
            bonus = await get_singing_bonus(birds)
            assert bonus == 6

    @pytest.mark.asyncio
    async def test_no_singing_birds(self, mock_db):
        birds = [
            {"common_name": "Australian White Ibis", "scientific_name": "Threskiornis molucca"},
        ]
        with patch("data.models.get_bird_effect", new_callable=AsyncMock, return_value=""):
            bonus = await get_singing_bonus(birds)
            assert bonus == 0


class TestSeedGatheringBonus:
    @pytest.mark.asyncio
    async def test_first_seed_action_with_bonus_birds(self, mock_db):
        mock_db.get_daily_actions.return_value = None

        birds = [
            {"common_name": "Gang-gang Cockatoo", "scientific_name": "Callocephalon fimbriatum"},
            {"common_name": "Major Mitchell's Cockatoo", "scientific_name": "Lophochroa leadbeateri"},
        ]

        with patch("data.models.get_bird_effect", new_callable=AsyncMock) as mock_effect:
            mock_effect.return_value = "Your first seed gathering action of the day also gives +1 garden size"
            bonus = await get_seed_gathering_bonus("123", birds)
            assert bonus == 2

    @pytest.mark.asyncio
    async def test_subsequent_seed_action_no_bonus(self, mock_db):
        mock_db.get_daily_actions.return_value = _make_daily_actions(used=1, action_history=["seed"])

        birds = [
            {"common_name": "Gang-gang Cockatoo", "scientific_name": "Callocephalon fimbriatum"},
        ]

        with patch("data.models.get_bird_effect", new_callable=AsyncMock) as mock_effect:
            mock_effect.return_value = "Your first seed gathering action of the day also gives +1 garden size"
            bonus = await get_seed_gathering_bonus("123", birds)
            assert bonus == 0


class TestSingingInspirationChance:
    @pytest.mark.asyncio
    async def test_first_sing_with_inspiration_birds(self, mock_db):
        mock_db.get_daily_actions.return_value = None

        birds = [
            {"common_name": "Black-throated Finch", "scientific_name": "Poephila cincta"},
            {"common_name": "Gouldian Finch", "scientific_name": "Erythrura gouldiae"},
        ]

        with patch("data.models.get_bird_effect", new_callable=AsyncMock) as mock_effect:
            mock_effect.return_value = "has a 50% chance to give you +1 inspiration"
            # Force random to always succeed
            with patch("data.models.random.random", return_value=0.1):
                bonus = await get_singing_inspiration_chance("123", birds)
                assert bonus == 2

    @pytest.mark.asyncio
    async def test_subsequent_sing_no_inspiration(self, mock_db):
        mock_db.get_daily_actions.return_value = _make_daily_actions(used=1, action_history=["sing"])

        birds = [
            {"common_name": "Black-throated Finch", "scientific_name": "Poephila cincta"},
        ]

        with patch("data.models.get_bird_effect", new_callable=AsyncMock) as mock_effect:
            mock_effect.return_value = "has a 50% chance to give you +1 inspiration"
            bonus = await get_singing_inspiration_chance("123", birds)
            assert bonus == 0

    @pytest.mark.asyncio
    async def test_inspiration_chance_fails(self, mock_db):
        mock_db.get_daily_actions.return_value = None

        birds = [
            {"common_name": "Black-throated Finch", "scientific_name": "Poephila cincta"},
        ]

        with patch("data.models.get_bird_effect", new_callable=AsyncMock) as mock_effect:
            mock_effect.return_value = "has a 50% chance to give you +1 inspiration"
            # Force random to fail
            with patch("data.models.random.random", return_value=0.9):
                bonus = await get_singing_inspiration_chance("123", birds)
                assert bonus == 0


# ===================================================================
# Plant effect bonuses (async - they load plant species from DB)
# ===================================================================

class TestLessBroodChance:
    @pytest.mark.asyncio
    async def test_no_plants(self, mock_db):
        with patch("data.models._load_plant_species_json", return_value=[]):
            chance = await get_less_brood_chance([])
            assert chance == 0

    @pytest.mark.asyncio
    async def test_single_plant(self, mock_db):
        plant_species = [
            {
                "commonName": "Sturt's Desert Pea",
                "scientificName": "Swainsona formosa",
                "effect": "+25% chance of your eggs needing one less brood",
            }
        ]
        plants = [{"common_name": "Sturt's Desert Pea"}]

        with patch("data.models._load_plant_species_json", return_value=plant_species):
            chance = await get_less_brood_chance(plants)
            assert chance == 25

    @pytest.mark.asyncio
    async def test_multiple_plants_stack(self, mock_db):
        plant_species = [
            {
                "commonName": "Sturt's Desert Pea",
                "scientificName": "Swainsona formosa",
                "effect": "+25% chance of your eggs needing one less brood",
            },
            {
                "commonName": "Kangaroo Paw",
                "scientificName": "Anigozanthos manglesii",
                "effect": "+10% chance of your eggs needing one less brood",
            },
        ]
        plants = [
            {"common_name": "Sturt's Desert Pea"},
            {"common_name": "Kangaroo Paw"},
        ]

        with patch("data.models._load_plant_species_json", return_value=plant_species):
            chance = await get_less_brood_chance(plants)
            assert chance == 35

    @pytest.mark.asyncio
    async def test_ignores_other_effects(self, mock_db):
        plant_species = [
            {
                "commonName": "Sturt's Desert Pea",
                "scientificName": "Swainsona formosa",
                "effect": "+25% chance of your eggs needing one less brood",
            },
            {
                "commonName": "Waratah",
                "scientificName": "Telopea speciosissima",
                "effect": "+7% chance of your eggs hatching an extra bird",
            },
        ]
        plants = [
            {"common_name": "Sturt's Desert Pea"},
            {"common_name": "Waratah"},
        ]

        with patch("data.models._load_plant_species_json", return_value=plant_species):
            chance = await get_less_brood_chance(plants)
            assert chance == 25


class TestExtraBirdChance:
    @pytest.mark.asyncio
    async def test_no_plants(self, mock_db):
        with patch("data.models._load_plant_species_json", return_value=[]):
            chance = await get_extra_bird_chance([])
            assert chance == 0

    @pytest.mark.asyncio
    async def test_single_plant(self, mock_db):
        plant_species = [
            {
                "commonName": "Waratah",
                "scientificName": "Telopea speciosissima",
                "effect": "+7% chance of your eggs hatching an extra bird",
            }
        ]
        plants = [{"common_name": "Waratah"}]

        with patch("data.models._load_plant_species_json", return_value=plant_species):
            chance = await get_extra_bird_chance(plants)
            assert chance == 7

    @pytest.mark.asyncio
    async def test_multiple_plants_stack(self, mock_db):
        plant_species = [
            {
                "commonName": "Waratah",
                "scientificName": "Telopea speciosissima",
                "effect": "+7% chance of your eggs hatching an extra bird",
            },
            {
                "commonName": "Wattle",
                "scientificName": "Acacia pycnantha",
                "effect": "+2% chance of your eggs hatching an extra bird",
            },
            {
                "commonName": "Wollemi Pine",
                "scientificName": "Wollemia nobilis",
                "effect": "+25% chance of your eggs hatching an extra bird",
            },
        ]
        plants = [
            {"common_name": "Waratah"},
            {"common_name": "Wattle"},
            {"common_name": "Wollemi Pine"},
        ]

        with patch("data.models._load_plant_species_json", return_value=plant_species):
            chance = await get_extra_bird_chance(plants)
            assert chance == 34

    @pytest.mark.asyncio
    async def test_ignores_other_effects(self, mock_db):
        plant_species = [
            {
                "commonName": "Waratah",
                "scientificName": "Telopea speciosissima",
                "effect": "+7% chance of your eggs hatching an extra bird",
            },
            {
                "commonName": "Sturt's Desert Pea",
                "scientificName": "Swainsona formosa",
                "effect": "+25% chance of your eggs needing one less brood",
            },
        ]
        plants = [
            {"common_name": "Waratah"},
            {"common_name": "Sturt's Desert Pea"},
        ]

        with patch("data.models._load_plant_species_json", return_value=plant_species):
            chance = await get_extra_bird_chance(plants)
            assert chance == 7
