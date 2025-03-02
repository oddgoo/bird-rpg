import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json
import os

from commands.manifest import ManifestCommands
from data.storage import load_manifested_birds, save_manifested_birds, load_manifested_plants, save_manifested_plants
from data.models import get_personal_nest, get_remaining_actions, record_actions, select_random_bird_species

@pytest.fixture
def mock_interaction():
    interaction = AsyncMock()
    interaction.user = AsyncMock()
    interaction.user.id = 123  # Default user ID
    interaction.user.display_name = "Test User"
    interaction.response = AsyncMock()
    interaction.followup = AsyncMock()
    return interaction

@pytest.fixture
def mock_data():
    return {
        "personal_nests": {},
        "common_nest": {"twigs": 0, "seeds": 0},
        "daily_actions": {},
        "daily_songs": {},
        "daily_brooding": {}
    }

@pytest.fixture
def manifest_cog(mock_data):
    bot = AsyncMock()
    cog = ManifestCommands(bot)
    
    # Mock load_data and save_data to use mock_data
    def mock_load_data():
        return mock_data

    def mock_save_data(data):
        mock_data.update(data)
    
    # Mock get_remaining_actions to return a controlled value
    def mock_get_remaining_actions(data, user_id):
        # Get the nest for this user
        nest = get_personal_nest(data, user_id)
        # Return the bonus_actions value directly
        return nest.get("bonus_actions", 0)
    
    # Mock record_actions to directly update bonus_actions
    def mock_record_actions(data, user_id, count, action_type=None):
        nest = get_personal_nest(data, user_id)
        nest["bonus_actions"] -= count
        
    # Mock manifested birds and plants data
    manifested_birds = []
    manifested_plants = []
    
    def mock_load_manifested_birds():
        return manifested_birds
        
    def mock_save_manifested_birds(data):
        nonlocal manifested_birds
        manifested_birds = data
        
    def mock_load_manifested_plants():
        return manifested_plants
        
    def mock_save_manifested_plants(data):
        nonlocal manifested_plants
        manifested_plants = data

    with patch('commands.manifest.load_data', mock_load_data), \
         patch('commands.manifest.save_data', mock_save_data), \
         patch('commands.manifest.get_remaining_actions', mock_get_remaining_actions), \
         patch('commands.manifest.record_actions', mock_record_actions), \
         patch('commands.manifest.load_manifested_birds', mock_load_manifested_birds), \
         patch('commands.manifest.save_manifested_birds', mock_save_manifested_birds), \
         patch('commands.manifest.load_manifested_plants', mock_load_manifested_plants), \
         patch('commands.manifest.save_manifested_plants', mock_save_manifested_plants):
        yield cog, manifested_birds, manifested_plants

@pytest.fixture
def mock_inaturalist_bird_response():
    """Mock response from iNaturalist API for a bird species"""
    return {
        "name": "Casuarius casuarius",
        "preferred_common_name": "Southern Cassowary",
        "iconic_taxon_name": "Aves",
        "observations_count": 2188
    }

@pytest.fixture
def mock_inaturalist_plant_response():
    """Mock response from iNaturalist API for a plant species"""
    return {
        "name": "Swainsona formosa",
        "preferred_common_name": "Sturt's Desert Pea",
        "iconic_taxon_name": "Plantae",
        "observations_count": 1500
    }

@pytest.fixture
def mock_inaturalist_invalid_response():
    """Mock response from iNaturalist API for a non-existent species"""
    return None

@pytest.fixture
def mock_inaturalist_non_bird_response():
    """Mock response from iNaturalist API for a non-bird species"""
    return {
        "name": "Felis catus",
        "preferred_common_name": "Domestic Cat",
        "iconic_taxon_name": "Mammalia",
        "observations_count": 50000
    }

class TestManifestBirdCommand:
    @pytest.mark.asyncio
    async def test_manifest_bird_only_use_needed_actions(self, manifest_cog, mock_interaction, mock_data, mock_inaturalist_bird_response):
        """Test that only the necessary actions are used when manifesting a bird"""
        cog, manifested_birds, _ = manifest_cog
        
        # Add actions to the user
        nest = get_personal_nest(mock_data, mock_interaction.user.id)
        nest["bonus_actions"] = 50
        
        # Add a partially manifested bird that needs 10 more points to be fully manifested
        points_needed = 100  # uncommon bird needs 100 points
        manifested_birds.append({
            "commonName": "Southern Cassowary",
            "scientificName": "Casuarius casuarius",
            "rarityWeight": 4,
            "effect": "Your first nest-building action of the day gives +3 twigs.",
            "rarity": "uncommon",
            "manifested_points": 90,  # Only needs 10 more points
            "fully_manifested": False
        })
        
        # Mock fetch_species_data to return a bird
        cog.fetch_species_data = AsyncMock(return_value=mock_inaturalist_bird_response)
        
        # Mock download_species_image to do nothing
        cog.download_species_image = AsyncMock(return_value=True)
        
        # Call the command callback with more actions than needed (20 instead of 10)
        await cog.manifest_bird.callback(cog, mock_interaction, "Casuarius casuarius", 20)
        
        # Check that the bird was fully manifested
        assert len(manifested_birds) == 1
        assert manifested_birds[0]["manifested_points"] == 100  # Should be exactly 100, not 110
        assert manifested_birds[0]["fully_manifested"]  # Should be fully manifested
        
        # Check that only 10 actions were used, not 20
        assert nest["bonus_actions"] == 40  # Started with 50, used 10
        
        # Check that the response was sent
        assert mock_interaction.followup.send.call_count >= 1
    @pytest.mark.asyncio
    async def test_manifest_bird_success(self, manifest_cog, mock_interaction, mock_data, mock_inaturalist_bird_response):
        """Test successfully manifesting a bird"""
        cog, manifested_birds, _ = manifest_cog
        
        # Add actions to the user
        nest = get_personal_nest(mock_data, mock_interaction.user.id)
        nest["bonus_actions"] = 10
        
        # Mock fetch_species_data to return a bird
        cog.fetch_species_data = AsyncMock(return_value=mock_inaturalist_bird_response)
        
        # Mock find_similar_bird to return a fixed bird
        cog.find_similar_bird = MagicMock(return_value={
            "rarityWeight": 4,
            "effect": "Your first nest-building action of the day gives +3 twigs."
        })
        
        # Mock download_species_image to do nothing
        cog.download_species_image = AsyncMock(return_value=True)
        
        # Call the command callback
        await cog.manifest_bird.callback(cog, mock_interaction, "Casuarius casuarius", 5)
        
        # Check that the bird was added to manifested_birds
        assert len(manifested_birds) == 1
        assert manifested_birds[0]["scientificName"] == "Casuarius casuarius"
        assert manifested_birds[0]["commonName"] == "Southern Cassowary"
        assert manifested_birds[0]["manifested_points"] == 5
        assert manifested_birds[0]["rarity"] == "uncommon"  # Based on observations_count
        assert not manifested_birds[0]["fully_manifested"]  # Should not be fully manifested yet
        
        # Check that the response was sent
        mock_interaction.followup.send.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_manifest_bird_fully_manifested(self, manifest_cog, mock_interaction, mock_data, mock_inaturalist_bird_response):
        """Test fully manifesting a bird"""
        cog, manifested_birds, _ = manifest_cog
        
        # Add actions to the user
        nest = get_personal_nest(mock_data, mock_interaction.user.id)
        nest["bonus_actions"] = 200
        
        # Mock fetch_species_data to return a bird
        cog.fetch_species_data = AsyncMock(return_value=mock_inaturalist_bird_response)
        
        # Mock find_similar_bird to return a fixed bird
        cog.find_similar_bird = MagicMock(return_value={
            "rarityWeight": 4,
            "effect": "Your first nest-building action of the day gives +3 twigs."
        })
        
        # Mock download_species_image to do nothing
        cog.download_species_image = AsyncMock(return_value=True)
        
        # Call the command callback with enough actions to fully manifest
        await cog.manifest_bird.callback(cog, mock_interaction, "Casuarius casuarius", 100)
        
        # Check that the bird was fully manifested
        assert len(manifested_birds) == 1
        assert manifested_birds[0]["scientificName"] == "Casuarius casuarius"
        assert manifested_birds[0]["manifested_points"] == 100
        assert manifested_birds[0]["fully_manifested"]  # Should be fully manifested
        
        # Check that the response was sent
        mock_interaction.followup.send.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_manifest_bird_already_manifested(self, manifest_cog, mock_interaction, mock_data, mock_inaturalist_bird_response):
        """Test attempting to manifest an already fully manifested bird"""
        cog, manifested_birds, _ = manifest_cog
        
        # Add a fully manifested bird
        manifested_birds.append({
            "commonName": "Southern Cassowary",
            "scientificName": "Casuarius casuarius",
            "rarityWeight": 4,
            "effect": "Your first nest-building action of the day gives +3 twigs.",
            "rarity": "uncommon",
            "manifested_points": 100,
            "fully_manifested": True
        })
        
        # Add actions to the user
        nest = get_personal_nest(mock_data, mock_interaction.user.id)
        nest["bonus_actions"] = 10
        
        # Mock fetch_species_data to return a bird
        cog.fetch_species_data = AsyncMock(return_value=mock_inaturalist_bird_response)
        
        # Call the command callback
        await cog.manifest_bird.callback(cog, mock_interaction, "Casuarius casuarius", 5)
        
        # Check that the response was sent with an error
        mock_interaction.followup.send.assert_called_once()
        args = mock_interaction.followup.send.call_args[0][0]
        assert "already been fully manifested" in args
        
        
    @pytest.mark.asyncio
    async def test_manifest_bird_continue_manifestation(self, manifest_cog, mock_interaction, mock_data, mock_inaturalist_bird_response):
        """Test continuing manifestation of a partially manifested bird"""
        cog, manifested_birds, _ = manifest_cog
        
        # Add a partially manifested bird
        manifested_birds.append({
            "commonName": "Southern Cassowary",
            "scientificName": "Casuarius casuarius",
            "rarityWeight": 4,
            "effect": "Your first nest-building action of the day gives +3 twigs.",
            "rarity": "uncommon",
            "manifested_points": 50,
            "fully_manifested": False
        })
        
        # Add actions to the user
        nest = get_personal_nest(mock_data, mock_interaction.user.id)
        nest["bonus_actions"] = 100
        
        # Mock fetch_species_data to return a bird
        cog.fetch_species_data = AsyncMock(return_value=mock_inaturalist_bird_response)
        
        # Mock download_species_image to do nothing
        cog.download_species_image = AsyncMock(return_value=True)
        
        # Call the command callback to add more points
        await cog.manifest_bird.callback(cog, mock_interaction, "Casuarius casuarius", 50)
        
        # Check that the bird was updated and fully manifested
        assert len(manifested_birds) == 1
        assert manifested_birds[0]["manifested_points"] == 100
        assert manifested_birds[0]["fully_manifested"]  # Should now be fully manifested
        
    @pytest.mark.asyncio
    async def test_manifest_bird_invalid_species(self, manifest_cog, mock_interaction, mock_data, mock_inaturalist_invalid_response):
        """Test attempting to manifest a non-existent species"""
        cog, manifested_birds, _ = manifest_cog
        
        # Add actions to the user
        nest = get_personal_nest(mock_data, mock_interaction.user.id)
        nest["bonus_actions"] = 10
        
        # Mock fetch_species_data to return None (species not found)
        cog.fetch_species_data = AsyncMock(return_value=mock_inaturalist_invalid_response)
        
        # Call the command callback
        await cog.manifest_bird.callback(cog, mock_interaction, "NonexistentBird", 5)
        
        # Check that the response was sent with an error
        mock_interaction.followup.send.assert_called_once()
        args = mock_interaction.followup.send.call_args[0][0]
        assert "might not exist" in args
        
    @pytest.mark.asyncio
    async def test_manifest_bird_non_bird_species(self, manifest_cog, mock_interaction, mock_data, mock_inaturalist_non_bird_response):
        """Test attempting to manifest a non-bird species"""
        cog, manifested_birds, _ = manifest_cog
        
        # Add actions to the user
        nest = get_personal_nest(mock_data, mock_interaction.user.id)
        nest["bonus_actions"] = 10
        
        # Mock fetch_species_data to return a non-bird species
        cog.fetch_species_data = AsyncMock(return_value=mock_inaturalist_non_bird_response)
        
        # Call the command callback
        await cog.manifest_bird.callback(cog, mock_interaction, "Felis catus", 5)
        
        # Check that the response was sent with an error
        mock_interaction.followup.send.assert_called_once()
        args = mock_interaction.followup.send.call_args[0][0]
        assert "not a bird" in args
    
        
    @pytest.mark.asyncio
    async def test_manifest_bird_insufficient_actions(self, manifest_cog, mock_interaction, mock_data, mock_inaturalist_bird_response):
        """Test attempting to manifest a bird with insufficient actions"""
        cog, manifested_birds, _ = manifest_cog
        
        # Add limited actions to the user
        nest = get_personal_nest(mock_data, mock_interaction.user.id)
        nest["bonus_actions"] = 3
        
        # Mock fetch_species_data to return a bird
        cog.fetch_species_data = AsyncMock(return_value=mock_inaturalist_bird_response)
        
        # Call the command callback with more actions than available
        await cog.manifest_bird.callback(cog, mock_interaction, "Casuarius casuarius", 5)
        
        # Check that the response was sent with an error
        mock_interaction.followup.send.assert_called_once()
        args = mock_interaction.followup.send.call_args[0][0]
        assert "don't have enough actions" in args


class TestManifestPlantCommand:
    @pytest.mark.asyncio
    async def test_manifest_plant_only_use_needed_actions(self, manifest_cog, mock_interaction, mock_data, mock_inaturalist_plant_response):
        """Test that only the necessary actions are used when manifesting a plant"""
        cog, _, manifested_plants = manifest_cog
        
        # Add actions to the user
        nest = get_personal_nest(mock_data, mock_interaction.user.id)
        nest["bonus_actions"] = 50
        
        # Add a partially manifested plant that needs 5 more points to be fully manifested
        points_needed = 30  # common plant needs 30 points
        manifested_plants.append({
            "commonName": "Sturt's Desert Pea",
            "scientificName": "Swainsona formosa",
            "rarityWeight": 7,
            "effect": "+10% chance of your eggs needing one less brood (when laying an egg)",
            "rarity": "common",
            "seedCost": 30,
            "sizeCost": 1,
            "inspirationCost": 1,
            "manifested_points": 25,  # Only needs 5 more points
            "fully_manifested": False
        })
        
        # Mock fetch_species_data to return a plant
        cog.fetch_species_data = AsyncMock(return_value=mock_inaturalist_plant_response)
        
        # Mock download_species_image to do nothing
        cog.download_species_image = AsyncMock(return_value=True)
        
        # Call the command callback with more actions than needed (15 instead of 5)
        await cog.manifest_plant.callback(cog, mock_interaction, "Swainsona formosa", 15)
        
        # Check that the plant was fully manifested
        assert len(manifested_plants) == 1
        assert manifested_plants[0]["manifested_points"] == 30  # Should be exactly 30, not 40
        assert manifested_plants[0]["fully_manifested"]  # Should be fully manifested
        
        # Check that only 5 actions were used, not 15
        assert nest["bonus_actions"] == 45  # Started with 50, used 5
        
        # Check that the response was sent
        assert mock_interaction.followup.send.call_count >= 1
    @pytest.mark.asyncio
    async def test_manifest_plant_success(self, manifest_cog, mock_interaction, mock_data, mock_inaturalist_plant_response):
        """Test successfully manifesting a plant"""
        cog, _, manifested_plants = manifest_cog
        
        # Add actions to the user
        nest = get_personal_nest(mock_data, mock_interaction.user.id)
        nest["bonus_actions"] = 10
        
        # Mock fetch_species_data to return a plant
        cog.fetch_species_data = AsyncMock(return_value=mock_inaturalist_plant_response)
        
        # Mock find_similar_plant to return a fixed plant
        cog.find_similar_plant = MagicMock(return_value={
            "rarityWeight": 4,
            "effect": "+25% chance of your eggs needing one less brood",
            "seedCost": 100,
            "sizeCost": 2,
            "inspirationCost": 3
        })
        
        # Mock download_species_image to do nothing
        cog.download_species_image = AsyncMock(return_value=True)
        
        # Call the command callback
        await cog.manifest_plant.callback(cog, mock_interaction, "Swainsona formosa", 5)
        
        # Check that the plant was added to manifested_plants
        assert len(manifested_plants) == 1
        assert manifested_plants[0]["scientificName"] == "Swainsona formosa"
        assert manifested_plants[0]["commonName"] == "Sturt's Desert Pea"
        assert manifested_plants[0]["manifested_points"] == 5
        assert manifested_plants[0]["rarity"] == "uncommon"  # Based on observations_count
        assert not manifested_plants[0]["fully_manifested"]  # Should not be fully manifested yet
        
        # Check that the response was sent
        mock_interaction.followup.send.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_manifest_plant_fully_manifested(self, manifest_cog, mock_interaction, mock_data, mock_inaturalist_plant_response):
        """Test fully manifesting a plant"""
        cog, _, manifested_plants = manifest_cog
        
        # Add actions to the user
        nest = get_personal_nest(mock_data, mock_interaction.user.id)
        nest["bonus_actions"] = 200
        
        # Mock fetch_species_data to return a plant
        cog.fetch_species_data = AsyncMock(return_value=mock_inaturalist_plant_response)
        
        # Mock find_similar_plant to return a fixed plant
        cog.find_similar_plant = MagicMock(return_value={
            "rarityWeight": 4,
            "effect": "+25% chance of your eggs needing one less brood",
            "seedCost": 100,
            "sizeCost": 2,
            "inspirationCost": 3
        })
        
        # Mock download_species_image to do nothing
        cog.download_species_image = AsyncMock(return_value=True)
        
        # Call the command callback with enough actions to fully manifest
        await cog.manifest_plant.callback(cog, mock_interaction, "Swainsona formosa", 100)
        
        # Check that the plant was fully manifested
        assert len(manifested_plants) == 1
        assert manifested_plants[0]["scientificName"] == "Swainsona formosa"
        assert manifested_plants[0]["manifested_points"] == 100
        assert manifested_plants[0]["fully_manifested"]  # Should be fully manifested
        
        # Check that the response was sent
        mock_interaction.followup.send.assert_called_once()

class TestManifestHelperFunctions:
    def test_get_points_needed(self, manifest_cog):
        """Test the get_points_needed function"""
        cog, _, _ = manifest_cog
        
        assert cog.get_points_needed("common") == 30
        assert cog.get_points_needed("uncommon") == 100
        assert cog.get_points_needed("rare") == 150
        assert cog.get_points_needed("mythical") == 200
        assert cog.get_points_needed("unknown") == 100  # Default
        
    def test_generate_progress_bar(self, manifest_cog):
        """Test the generate_progress_bar function"""
        cog, _, _ = manifest_cog
        
        assert cog.generate_progress_bar(0) == "░░░░░░░░░░"
        assert cog.generate_progress_bar(50) == "█████░░░░░"
        assert cog.generate_progress_bar(100) == "██████████"
        assert cog.generate_progress_bar(25, length=4) == "█░░░"
        
    def test_find_similar_bird(self, manifest_cog):
        """Test the find_similar_bird function"""
        cog, _, _ = manifest_cog
        
        # Mock bird species data
        test_birds = {
            "bird_species": [
                {
                    "commonName": "Common Bird",
                    "scientificName": "Commonus birdus",
                    "rarityWeight": 8,
                    "effect": "Common effect",
                    "rarity": "common"
                },
                {
                    "commonName": "Uncommon Bird",
                    "scientificName": "Uncommonus birdus",
                    "rarityWeight": 4,
                    "effect": "Uncommon effect",
                    "rarity": "uncommon"
                },
                {
                    "commonName": "Rare Bird",
                    "scientificName": "Rarus birdus",
                    "rarityWeight": 1,
                    "effect": "Rare effect",
                    "rarity": "rare"
                }
            ]
        }
        
        # Mock open to return test data
        mock_open = MagicMock()
        mock_file = MagicMock()
        mock_file.__enter__.return_value.read.return_value = json.dumps(test_birds)
        mock_open.return_value = mock_file
        
        with patch('builtins.open', mock_open):
            # Test finding a common bird
            common_bird = cog.find_similar_bird("common")
            assert common_bird["rarity"] == "common"
            
            # Test finding an uncommon bird
            uncommon_bird = cog.find_similar_bird("uncommon")
            assert uncommon_bird["rarity"] == "uncommon"
            
            # Test finding a rare bird
            rare_bird = cog.find_similar_bird("rare")
            assert rare_bird["rarity"] == "rare"
            
            # Test finding a non-existent rarity (should return any bird)
            any_bird = cog.find_similar_bird("nonexistent")
            assert any_bird["rarity"] in ["common", "uncommon", "rare"]
            
    def test_find_similar_plant(self, manifest_cog):
        """Test the find_similar_plant function"""
        cog, _, _ = manifest_cog
        
        # Mock plant species data
        test_plants = [
            {
                "commonName": "Common Plant",
                "scientificName": "Commonus plantus",
                "rarityWeight": 8,
                "effect": "Common effect",
                "rarity": "common",
                "seedCost": 30,
                "sizeCost": 1,
                "inspirationCost": 1
            },
            {
                "commonName": "Uncommon Plant",
                "scientificName": "Uncommonus plantus",
                "rarityWeight": 4,
                "effect": "Uncommon effect",
                "rarity": "uncommon",
                "seedCost": 100,
                "sizeCost": 2,
                "inspirationCost": 3
            },
            {
                "commonName": "Rare Plant",
                "scientificName": "Rarus plantus",
                "rarityWeight": 1,
                "effect": "Rare effect",
                "rarity": "rare",
                "seedCost": 300,
                "sizeCost": 5,
                "inspirationCost": 5
            }
        ]
        
        # Mock open to return test data
        mock_open = MagicMock()
        mock_file = MagicMock()
        mock_file.__enter__.return_value.read.return_value = json.dumps(test_plants)
        mock_open.return_value = mock_file
        
        with patch('builtins.open', mock_open):
            # Test finding a common plant
            common_plant = cog.find_similar_plant("common")
            assert common_plant["rarity"] == "common"
            assert "seedCost" in common_plant
            assert "sizeCost" in common_plant
            assert "inspirationCost" in common_plant
            
            # Test finding an uncommon plant
            uncommon_plant = cog.find_similar_plant("uncommon")
            assert uncommon_plant["rarity"] == "uncommon"
            
            # Test finding a rare plant
            rare_plant = cog.find_similar_plant("rare")
            assert rare_plant["rarity"] == "rare"
            
            # Test finding a non-existent rarity (should return any plant)
            any_plant = cog.find_similar_plant("nonexistent")
            assert any_plant["rarity"] in ["common", "uncommon", "rare"]
