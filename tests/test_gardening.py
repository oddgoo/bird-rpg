import pytest
from datetime import date, timedelta

from data.models import get_personal_nest
from commands.gardening import GardeningCommands

def test_plant_resource_checks():
    """Test that planting checks for required resources"""
    # Setup test nest with limited resources
    nest = {
        "twigs": 100,
        "seeds": 20,
        "inspiration": 1,
        "garden_size": 1,
        "plants": []
    }
    
    # Create a mock plant that requires more resources than available
    expensive_plant = {
        "commonName": "Expensive Plant",
        "scientificName": "Expensivus plantus",
        "seedCost": 30,
        "inspirationCost": 3,
        "sizeCost": 2,
        "rarity": "rare",
        "effect": "Test effect"
    }
    
    # Create a mock plant that the nest can afford
    affordable_plant = {
        "commonName": "Affordable Plant",
        "scientificName": "Affordabilis plantus",
        "seedCost": 10,
        "inspirationCost": 1,
        "sizeCost": 1,
        "rarity": "common",
        "effect": "Test effect"
    }
    
    # Mock the GardeningCommands class
    gardening = GardeningCommands(None)
    
    # Test insufficient seeds
    gardening.load_plant_species = lambda: [expensive_plant]
    result, error = gardening.process_planting_logic("Expensive Plant", nest)
    assert result is None
    assert "seeds" in error
    assert nest["seeds"] == 20  # Seeds should not be consumed
    
    # Test insufficient inspiration
    expensive_plant["seedCost"] = 10  # Make seeds affordable
    result, error = gardening.process_planting_logic("Expensive Plant", nest)
    assert result is None
    assert "inspiration" in error
    assert nest["inspiration"] == 1  # Inspiration should not be consumed
    
    # Test insufficient garden size
    expensive_plant["inspirationCost"] = 1  # Make inspiration affordable
    expensive_plant["sizeCost"] = 2  # But garden size is still too expensive
    result, error = gardening.process_planting_logic("Expensive Plant", nest)
    assert result is None
    assert "garden space" in error
    assert nest["garden_size"] == 1  # Garden size should not be consumed
    
    # Test successful planting
    gardening.load_plant_species = lambda: [affordable_plant]
    result, error = gardening.process_planting_logic("Affordable Plant", nest)
    assert error is None
    assert result is not None
    assert nest["seeds"] == 10  # Seeds should be consumed
    assert nest["inspiration"] == 0  # Inspiration should be consumed
    assert nest["garden_size"] == 1  # Garden size should NOT be consumed
    assert len(nest["plants"]) == 1
    assert nest["plants"][0]["commonName"] == "Affordable Plant"

def test_plant_not_found():
    """Test that planting checks if the plant exists"""
    # Setup test nest
    nest = {
        "twigs": 100,
        "seeds": 100,
        "inspiration": 10,
        "garden_size": 10,
        "plants": []
    }
    
    # Mock the GardeningCommands class
    gardening = GardeningCommands(None)
    gardening.load_plant_species = lambda: []
    
    # Test plant not found
    result, error = gardening.process_planting_logic("Nonexistent Plant", nest)
    assert result is None
    assert "not found" in error
    assert len(nest["plants"]) == 0

def test_process_planting_logic():
    """Test the process_planting_logic method"""
    # This is a helper method to test the actual planting logic
    # without the Discord interaction
    
    # Setup test nest
    nest = {
        "twigs": 100,
        "seeds": 100,
        "inspiration": 10,
        "garden_size": 10,
        "plants": []
    }
    
    # Create a test plant
    test_plant = {
        "commonName": "Test Plant",
        "scientificName": "Testus plantus",
        "seedCost": 30,
        "inspirationCost": 3,
        "sizeCost": 2,
        "rarity": "uncommon",
        "effect": "Test effect"
    }
    
    # Mock the GardeningCommands class
    gardening = GardeningCommands(None)
    gardening.load_plant_species = lambda: [test_plant]
    
    # Test successful planting
    result, error = gardening.process_planting_logic("Test Plant", nest)
    assert error is None
    assert result is not None
    
    # Check that resources were consumed
    assert nest["seeds"] == 70
    assert nest["inspiration"] == 7
    assert nest["garden_size"] == 10  # Garden size should NOT be consumed
    
    # Check that the plant was added to the nest
    assert len(nest["plants"]) == 1
    assert nest["plants"][0]["commonName"] == "Test Plant"
    assert "planted_date" in nest["plants"][0]
    # Note: scientificName, rarity, and effect are no longer stored in the nest

def test_plant_compost():
    """Test the plant_compost functionality"""
    # Setup test nest with a plant
    nest = {
        "twigs": 100,
        "seeds": 50,
        "inspiration": 5,
        "garden_size": 10,
        "plants": [
            {
                "commonName": "Test Plant",
                "scientificName": "Testus plantus",
                "planted_date": "2025-02-25"
            }
        ]
    }
    
    # Create a test plant species data
    test_plant = {
        "commonName": "Test Plant",
        "scientificName": "Testus plantus",
        "seedCost": 30,
        "inspirationCost": 3,
        "sizeCost": 2,
        "rarity": "uncommon",
        "effect": "Test effect"
    }
    
    # Mock the GardeningCommands class
    gardening = GardeningCommands(None)
    gardening.load_plant_species = lambda: [test_plant]
    
    # Test successful composting
    result, error = gardening.process_composting_logic("Test Plant", nest)
    assert error is None
    assert result is not None
    
    # Unpack the result
    removed_plant, plant_data, seed_refund, inspiration_refund, updated_nest, remaining_space = result
    
    # Check that the plant was removed
    assert len(nest["plants"]) == 0
    
    # Check that the refund was calculated correctly (80% of original cost)
    assert seed_refund == 24  # 80% of 30
    assert inspiration_refund == 2  # 80% of 3
    
    # Check that resources were refunded
    assert nest["seeds"] == 74  # 50 + 24
    assert nest["inspiration"] == 7  # 5 + 2
    
    # Test composting with scientific name
    # Reset the nest
    nest = {
        "twigs": 100,
        "seeds": 50,
        "inspiration": 5,
        "garden_size": 10,
        "plants": [
            {
                "commonName": "Test Plant",
                "scientificName": "Testus plantus",
                "planted_date": "2025-02-25"
            }
        ]
    }
    
    # Test composting using scientific name
    result, error = gardening.process_composting_logic("Testus plantus", nest)
    assert error is None
    assert result is not None
    
    # Check that the plant was removed
    assert len(nest["plants"]) == 0
    
    # Test plant not found
    # Reset the nest
    nest = {
        "twigs": 100,
        "seeds": 50,
        "inspiration": 5,
        "garden_size": 10,
        "plants": []
    }
    
    # Test composting a non-existent plant
    result, error = gardening.process_composting_logic("Nonexistent Plant", nest)
    assert result is None
    assert "don't have a plant" in error
