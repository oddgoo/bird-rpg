"""
Tests for gardening resource-check logic.

The planting / composting commands now live entirely inside async command
callbacks that talk to the DB via data.storage.  These tests exercise the
pure-logic parts (resource sufficiency, refund calculation) without needing
a real database or the old get_personal_nest helper.
"""

import pytest

from data.models import can_afford_plant, has_garden_space, calc_compost_refund


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPlantResourceChecks:
    def test_insufficient_seeds(self):
        """Player cannot plant if they lack seeds."""
        player = {"seeds": 20, "inspiration": 10}
        plant = {"seedCost": 30, "inspirationCost": 1, "sizeCost": 1, "commonName": "X"}
        ok, err = can_afford_plant(player, plant)
        assert ok is False
        assert "seeds" in err

    def test_insufficient_inspiration(self):
        """Player cannot plant if they lack inspiration."""
        player = {"seeds": 100, "inspiration": 1}
        plant = {"seedCost": 10, "inspirationCost": 3, "sizeCost": 1, "commonName": "X"}
        ok, err = can_afford_plant(player, plant)
        assert ok is False
        assert "inspiration" in err

    def test_sufficient_resources(self):
        """Player can plant when they have enough of everything."""
        player = {"seeds": 100, "inspiration": 10}
        plant = {"seedCost": 30, "inspirationCost": 3, "sizeCost": 1, "commonName": "X"}
        ok, err = can_afford_plant(player, plant)
        assert ok is True
        assert err is None


class TestGardenSpaceChecks:
    def test_no_space(self):
        """Cannot plant when garden is full."""
        existing = [{"common_name": "Existing Plant"}]
        species_list = [{"commonName": "Existing Plant", "sizeCost": 1}]
        new_plant = {"sizeCost": 1, "commonName": "New"}
        ok, err = has_garden_space(1, existing, species_list, new_plant)
        assert ok is False
        assert "space" in err

    def test_has_space(self):
        """Can plant when space is available."""
        existing = [{"common_name": "Existing Plant"}]
        species_list = [{"commonName": "Existing Plant", "sizeCost": 1}]
        new_plant = {"sizeCost": 1, "commonName": "New"}
        ok, err = has_garden_space(3, existing, species_list, new_plant)
        assert ok is True

    def test_large_plant_needs_more_space(self):
        """A size-2 plant needs 2 free spaces."""
        existing = []
        species_list = []
        new_plant = {"sizeCost": 2, "commonName": "Big Plant"}
        ok, _ = has_garden_space(1, existing, species_list, new_plant)
        assert ok is False
        ok2, _ = has_garden_space(2, existing, species_list, new_plant)
        assert ok2 is True


class TestCompostRefund:
    def test_refund_80_percent(self):
        """Composting refunds 80% of seed and inspiration cost."""
        plant_data = {"seedCost": 30, "inspirationCost": 3}
        seed_refund, insp_refund = calc_compost_refund(plant_data)
        assert seed_refund == 24  # int(30 * 0.8)
        assert insp_refund == 2   # int(3 * 0.8)

    def test_refund_rounds_down(self):
        """Refund uses int() which truncates toward zero."""
        plant_data = {"seedCost": 10, "inspirationCost": 1}
        seed_refund, insp_refund = calc_compost_refund(plant_data)
        assert seed_refund == 8   # int(10 * 0.8)
        assert insp_refund == 0   # int(1 * 0.8) = int(0.8) = 0

    def test_refund_expensive_plant(self):
        """Check refund on a more expensive plant."""
        plant_data = {"seedCost": 100, "inspirationCost": 5}
        seed_refund, insp_refund = calc_compost_refund(plant_data)
        assert seed_refund == 80
        assert insp_refund == 4


class TestPlantNotFound:
    def test_plant_name_lookup(self):
        """Searching for a non-existent plant in a species list fails."""
        species_list = [
            {"commonName": "Kangaroo Paw", "scientificName": "Anigozanthos flavidus"},
        ]
        search_name = "Nonexistent Plant"
        found = None
        for p in species_list:
            if p["commonName"].lower() == search_name.lower() or p["scientificName"].lower() == search_name.lower():
                found = p
                break
        assert found is None

    def test_plant_name_lookup_success(self):
        """Searching by common name (case-insensitive) finds the plant."""
        species_list = [
            {"commonName": "Kangaroo Paw", "scientificName": "Anigozanthos flavidus"},
        ]
        search_name = "kangaroo paw"
        found = None
        for p in species_list:
            if p["commonName"].lower() == search_name.lower():
                found = p
                break
        assert found is not None
        assert found["commonName"] == "Kangaroo Paw"
