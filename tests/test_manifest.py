"""
Tests for the ManifestCommands cog.

All DB operations (data.storage, data.models) are mocked via AsyncMock so
no real Supabase connection is needed.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch

from commands.manifest import ManifestCommands
from data.manifest_constants import get_points_needed


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_interaction():
    interaction = AsyncMock()
    interaction.user = AsyncMock()
    interaction.user.id = 123
    interaction.user.display_name = "Test User"
    interaction.response = AsyncMock()
    interaction.followup = AsyncMock()
    return interaction


@pytest.fixture
def mock_inaturalist_bird_response():
    return {
        "name": "Casuarius casuarius",
        "preferred_common_name": "Southern Cassowary",
        "iconic_taxon_name": "Aves",
        "observations_count": 2188,
    }


@pytest.fixture
def mock_inaturalist_plant_response():
    return {
        "name": "Swainsona formosa",
        "preferred_common_name": "Sturt's Desert Pea",
        "iconic_taxon_name": "Plantae",
        "observations_count": 1500,
    }


@pytest.fixture
def mock_inaturalist_invalid_response():
    return None


@pytest.fixture
def mock_inaturalist_non_bird_response():
    return {
        "name": "Felis catus",
        "preferred_common_name": "Domestic Cat",
        "iconic_taxon_name": "Mammalia",
        "observations_count": 50000,
    }


@pytest.fixture
def manifest_cog():
    """Create a ManifestCommands cog with mocked DB layer."""
    bot = AsyncMock()
    cog = ManifestCommands(bot)

    # Mutable containers the tests can inspect / populate
    manifested_birds = []
    manifested_plants = []

    # Track how many actions were consumed
    actions_state = {"remaining": 0, "used": 0}

    # --- async mocks for data.models ---
    async def mock_get_remaining_actions(user_id):
        return actions_state["remaining"]

    async def mock_record_actions(user_id, count, action_type=None):
        actions_state["remaining"] -= count
        actions_state["used"] += count

    # --- async mocks for data.storage (db) ---
    async def mock_load_manifested_birds():
        return list(manifested_birds)

    async def mock_upsert_manifested_bird(bird_data):
        # Replace existing entry or append
        for i, b in enumerate(manifested_birds):
            if b["scientificName"] == bird_data["scientificName"]:
                manifested_birds[i] = bird_data
                return
        manifested_birds.append(bird_data)

    async def mock_load_manifested_plants():
        return list(manifested_plants)

    async def mock_upsert_manifested_plant(plant_data):
        for i, p in enumerate(manifested_plants):
            if p["scientificName"] == plant_data["scientificName"]:
                manifested_plants[i] = plant_data
                return
        manifested_plants.append(plant_data)

    patches = {
        "commands.manifest.get_remaining_actions": mock_get_remaining_actions,
        "commands.manifest.record_actions": mock_record_actions,
        "commands.manifest.db.load_manifested_birds": mock_load_manifested_birds,
        "commands.manifest.db.upsert_manifested_bird": mock_upsert_manifested_bird,
        "commands.manifest.db.load_manifested_plants": mock_load_manifested_plants,
        "commands.manifest.db.upsert_manifested_plant": mock_upsert_manifested_plant,
    }

    ctx_managers = [patch(k, v) for k, v in patches.items()]
    for cm in ctx_managers:
        cm.start()

    yield cog, manifested_birds, manifested_plants, actions_state

    for cm in ctx_managers:
        cm.stop()


# ---------------------------------------------------------------------------
# Bird manifestation tests
# ---------------------------------------------------------------------------

class TestManifestBirdCommand:
    @pytest.mark.asyncio
    async def test_manifest_bird_success(self, manifest_cog, mock_interaction, mock_inaturalist_bird_response):
        cog, manifested_birds, _, actions_state = manifest_cog
        actions_state["remaining"] = 10

        cog.fetch_species_data = AsyncMock(return_value=mock_inaturalist_bird_response)
        cog.find_similar_bird = MagicMock(return_value={
            "rarityWeight": 4,
            "effect": "Your first nest-building action of the day gives +3 twigs.",
        })
        cog.download_species_image = AsyncMock(return_value=True)

        await cog.manifest_bird.callback(cog, mock_interaction, "Casuarius casuarius", 5)

        assert len(manifested_birds) == 1
        assert manifested_birds[0]["scientificName"] == "Casuarius casuarius"
        assert manifested_birds[0]["commonName"] == "Southern Cassowary"
        assert manifested_birds[0]["manifested_points"] == 5
        assert manifested_birds[0]["rarity"] == "uncommon"
        assert not manifested_birds[0]["fully_manifested"]
        mock_interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_manifest_bird_fully_manifested(self, manifest_cog, mock_interaction, mock_inaturalist_bird_response):
        cog, manifested_birds, _, actions_state = manifest_cog
        actions_state["remaining"] = 200

        cog.fetch_species_data = AsyncMock(return_value=mock_inaturalist_bird_response)
        cog.find_similar_bird = MagicMock(return_value={
            "rarityWeight": 4,
            "effect": "Your first nest-building action of the day gives +3 twigs.",
        })
        cog.download_species_image = AsyncMock(return_value=True)

        await cog.manifest_bird.callback(cog, mock_interaction, "Casuarius casuarius", 100)

        assert len(manifested_birds) == 1
        assert manifested_birds[0]["manifested_points"] == 70  # uncommon needs 70
        assert manifested_birds[0]["fully_manifested"]
        # Only 70 actions should be consumed, not 100
        assert actions_state["used"] == 70

    @pytest.mark.asyncio
    async def test_manifest_bird_only_use_needed_actions(self, manifest_cog, mock_interaction, mock_inaturalist_bird_response):
        """Only the necessary actions are consumed when continuing manifestation."""
        cog, manifested_birds, _, actions_state = manifest_cog
        actions_state["remaining"] = 50

        manifested_birds.append({
            "commonName": "Southern Cassowary",
            "scientificName": "Casuarius casuarius",
            "rarityWeight": 4,
            "effect": "Your first nest-building action of the day gives +3 twigs.",
            "rarity": "uncommon",
            "manifested_points": 60,
            "fully_manifested": False,
        })

        cog.fetch_species_data = AsyncMock(return_value=mock_inaturalist_bird_response)
        cog.download_species_image = AsyncMock(return_value=True)

        await cog.manifest_bird.callback(cog, mock_interaction, "Casuarius casuarius", 20)

        assert manifested_birds[0]["manifested_points"] == 70
        assert manifested_birds[0]["fully_manifested"]
        # Only 10 actions needed (70 - 60), not 20
        assert actions_state["used"] == 10

    @pytest.mark.asyncio
    async def test_manifest_bird_already_manifested(self, manifest_cog, mock_interaction, mock_inaturalist_bird_response):
        cog, manifested_birds, _, actions_state = manifest_cog
        actions_state["remaining"] = 10

        manifested_birds.append({
            "commonName": "Southern Cassowary",
            "scientificName": "Casuarius casuarius",
            "rarityWeight": 4,
            "effect": "Your first nest-building action of the day gives +3 twigs.",
            "rarity": "uncommon",
            "manifested_points": 100,
            "fully_manifested": True,
        })

        cog.fetch_species_data = AsyncMock(return_value=mock_inaturalist_bird_response)

        await cog.manifest_bird.callback(cog, mock_interaction, "Casuarius casuarius", 5)

        mock_interaction.followup.send.assert_called_once()
        args = mock_interaction.followup.send.call_args[0][0]
        assert "already been fully manifested" in args

    @pytest.mark.asyncio
    async def test_manifest_bird_continue_manifestation(self, manifest_cog, mock_interaction, mock_inaturalist_bird_response):
        cog, manifested_birds, _, actions_state = manifest_cog
        actions_state["remaining"] = 100

        manifested_birds.append({
            "commonName": "Southern Cassowary",
            "scientificName": "Casuarius casuarius",
            "rarityWeight": 4,
            "effect": "Your first nest-building action of the day gives +3 twigs.",
            "rarity": "uncommon",
            "manifested_points": 50,
            "fully_manifested": False,
        })

        cog.fetch_species_data = AsyncMock(return_value=mock_inaturalist_bird_response)
        cog.download_species_image = AsyncMock(return_value=True)

        await cog.manifest_bird.callback(cog, mock_interaction, "Casuarius casuarius", 50)

        assert manifested_birds[0]["manifested_points"] == 70
        assert manifested_birds[0]["fully_manifested"]

    @pytest.mark.asyncio
    async def test_manifest_bird_invalid_species(self, manifest_cog, mock_interaction, mock_inaturalist_invalid_response):
        cog, manifested_birds, _, actions_state = manifest_cog
        actions_state["remaining"] = 10

        cog.fetch_species_data = AsyncMock(return_value=mock_inaturalist_invalid_response)

        await cog.manifest_bird.callback(cog, mock_interaction, "NonexistentBird", 5)

        mock_interaction.followup.send.assert_called_once()
        args = mock_interaction.followup.send.call_args[0][0]
        assert "might not exist" in args

    @pytest.mark.asyncio
    async def test_manifest_bird_non_bird_species(self, manifest_cog, mock_interaction, mock_inaturalist_non_bird_response):
        cog, manifested_birds, _, actions_state = manifest_cog
        actions_state["remaining"] = 10

        cog.fetch_species_data = AsyncMock(return_value=mock_inaturalist_non_bird_response)

        await cog.manifest_bird.callback(cog, mock_interaction, "Felis catus", 5)

        mock_interaction.followup.send.assert_called_once()
        args = mock_interaction.followup.send.call_args[0][0]
        assert "not a bird" in args

    @pytest.mark.asyncio
    async def test_manifest_bird_insufficient_actions(self, manifest_cog, mock_interaction, mock_inaturalist_bird_response):
        cog, manifested_birds, _, actions_state = manifest_cog
        actions_state["remaining"] = 3

        cog.fetch_species_data = AsyncMock(return_value=mock_inaturalist_bird_response)

        await cog.manifest_bird.callback(cog, mock_interaction, "Casuarius casuarius", 5)

        mock_interaction.followup.send.assert_called_once()
        args = mock_interaction.followup.send.call_args[0][0]
        assert "don't have enough actions" in args


# ---------------------------------------------------------------------------
# Plant manifestation tests
# ---------------------------------------------------------------------------

class TestManifestPlantCommand:
    @pytest.mark.asyncio
    async def test_manifest_plant_success(self, manifest_cog, mock_interaction, mock_inaturalist_plant_response):
        cog, _, manifested_plants, actions_state = manifest_cog
        actions_state["remaining"] = 10

        cog.fetch_species_data = AsyncMock(return_value=mock_inaturalist_plant_response)
        cog.find_similar_plant = MagicMock(return_value={
            "rarityWeight": 4,
            "effect": "+25% chance of your eggs needing one less brood",
            "seedCost": 100,
            "sizeCost": 2,
            "inspirationCost": 3,
        })
        cog.download_species_image = AsyncMock(return_value=True)

        await cog.manifest_plant.callback(cog, mock_interaction, "Swainsona formosa", 5)

        assert len(manifested_plants) == 1
        assert manifested_plants[0]["scientificName"] == "Swainsona formosa"
        assert manifested_plants[0]["commonName"] == "Sturt's Desert Pea"
        assert manifested_plants[0]["manifested_points"] == 5
        assert manifested_plants[0]["rarity"] == "uncommon"
        assert not manifested_plants[0]["fully_manifested"]
        mock_interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_manifest_plant_fully_manifested(self, manifest_cog, mock_interaction, mock_inaturalist_plant_response):
        cog, _, manifested_plants, actions_state = manifest_cog
        actions_state["remaining"] = 200

        cog.fetch_species_data = AsyncMock(return_value=mock_inaturalist_plant_response)
        cog.find_similar_plant = MagicMock(return_value={
            "rarityWeight": 4,
            "effect": "+25% chance of your eggs needing one less brood",
            "seedCost": 100,
            "sizeCost": 2,
            "inspirationCost": 3,
        })
        cog.download_species_image = AsyncMock(return_value=True)

        await cog.manifest_plant.callback(cog, mock_interaction, "Swainsona formosa", 100)

        assert len(manifested_plants) == 1
        assert manifested_plants[0]["manifested_points"] == 70
        assert manifested_plants[0]["fully_manifested"]

    @pytest.mark.asyncio
    async def test_manifest_plant_only_use_needed_actions(self, manifest_cog, mock_interaction, mock_inaturalist_plant_response):
        cog, _, manifested_plants, actions_state = manifest_cog
        actions_state["remaining"] = 50

        manifested_plants.append({
            "commonName": "Sturt's Desert Pea",
            "scientificName": "Swainsona formosa",
            "rarityWeight": 7,
            "effect": "+10% chance of your eggs needing one less brood (when laying an egg)",
            "rarity": "common",
            "seedCost": 30,
            "sizeCost": 1,
            "inspirationCost": 1,
            "manifested_points": 35,
            "fully_manifested": False,
        })

        cog.fetch_species_data = AsyncMock(return_value=mock_inaturalist_plant_response)
        cog.download_species_image = AsyncMock(return_value=True)

        await cog.manifest_plant.callback(cog, mock_interaction, "Swainsona formosa", 15)

        assert manifested_plants[0]["manifested_points"] == 40
        assert manifested_plants[0]["fully_manifested"]
        # Only 5 actions needed (40 - 35)
        assert actions_state["used"] == 5


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------

class TestManifestHelperFunctions:
    def test_get_points_needed(self):
        assert get_points_needed("common") == 40
        assert get_points_needed("uncommon") == 70
        assert get_points_needed("rare") == 110
        assert get_points_needed("mythical") == 160
        assert get_points_needed("unknown") == 100  # default

    def test_generate_progress_bar(self, manifest_cog):
        cog, _, _, _ = manifest_cog
        assert cog.generate_progress_bar(0) == "░░░░░░░░░░"
        assert cog.generate_progress_bar(50) == "█████░░░░░"
        assert cog.generate_progress_bar(100) == "██████████"
        assert cog.generate_progress_bar(25, length=4) == "█░░░"

    def test_find_similar_bird(self, manifest_cog):
        cog, _, _, _ = manifest_cog
        test_birds = {
            "bird_species": [
                {"commonName": "Common Bird", "scientificName": "Commonus birdus",
                 "rarityWeight": 8, "effect": "Common effect", "rarity": "common"},
                {"commonName": "Uncommon Bird", "scientificName": "Uncommonus birdus",
                 "rarityWeight": 4, "effect": "Uncommon effect", "rarity": "uncommon"},
                {"commonName": "Rare Bird", "scientificName": "Rarus birdus",
                 "rarityWeight": 1, "effect": "Rare effect", "rarity": "rare"},
            ]
        }

        mock_open = MagicMock()
        mock_file = MagicMock()
        mock_file.__enter__.return_value.read.return_value = json.dumps(test_birds)
        mock_open.return_value = mock_file

        with patch('builtins.open', mock_open):
            assert cog.find_similar_bird("common")["rarity"] == "common"
            assert cog.find_similar_bird("uncommon")["rarity"] == "uncommon"
            assert cog.find_similar_bird("rare")["rarity"] == "rare"
            any_bird = cog.find_similar_bird("nonexistent")
            assert any_bird["rarity"] in ["common", "uncommon", "rare"]

    def test_find_similar_plant(self, manifest_cog):
        cog, _, _, _ = manifest_cog
        test_plants = [
            {"commonName": "Common Plant", "scientificName": "Commonus plantus",
             "rarityWeight": 8, "effect": "Common effect", "rarity": "common",
             "seedCost": 30, "sizeCost": 1, "inspirationCost": 1},
            {"commonName": "Uncommon Plant", "scientificName": "Uncommonus plantus",
             "rarityWeight": 4, "effect": "Uncommon effect", "rarity": "uncommon",
             "seedCost": 100, "sizeCost": 2, "inspirationCost": 3},
            {"commonName": "Rare Plant", "scientificName": "Rarus plantus",
             "rarityWeight": 1, "effect": "Rare effect", "rarity": "rare",
             "seedCost": 300, "sizeCost": 5, "inspirationCost": 5},
        ]

        mock_open = MagicMock()
        mock_file = MagicMock()
        mock_file.__enter__.return_value.read.return_value = json.dumps(test_plants)
        mock_open.return_value = mock_file

        with patch('builtins.open', mock_open):
            common = cog.find_similar_plant("common")
            assert common["rarity"] == "common"
            assert "seedCost" in common
            assert cog.find_similar_plant("uncommon")["rarity"] == "uncommon"
            assert cog.find_similar_plant("rare")["rarity"] == "rare"
            any_plant = cog.find_similar_plant("nonexistent")
            assert any_plant["rarity"] in ["common", "uncommon", "rare"]
