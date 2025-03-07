from flask import render_template
from data.storage import load_research_progress, load_data, load_manifested_birds, load_manifested_plants
from data.manifest_constants import get_points_needed
import json
import os

# Import milestone thresholds from commands.research
MILESTONE_THRESHOLDS = [30, 75, 150, 300, 600, 1200, 2400, 4800, 6700, 10000]

def load_research_entities():
    """Load research entities from JSON file"""
    file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'research_entities.json')
    with open(file_path, 'r', encoding='utf-8') as file:
        return json.load(file)

def get_research_page():
    """Render the research page"""
    # Load research entities
    research_entities = load_research_entities()
    
    # Load research progress
    research_progress = load_research_progress()
    
    # Load manifested birds and plants
    manifested_birds = load_manifested_birds()
    manifested_plants = load_manifested_plants()
    
    # Prepare author data for the template
    authors = []
    for entity in research_entities:
        # Get the current progress for this author (defaulting to 0 if not found)
        current_points = research_progress.get(entity["author"], 0)
        
        # Determine current milestone and next threshold
        milestone_index = 0
        for i, threshold in enumerate(MILESTONE_THRESHOLDS):
            if current_points < threshold:
                milestone_index = i
                break
            elif i == len(MILESTONE_THRESHOLDS) - 1:
                milestone_index = i
        
        # Calculate progress percentage towards next milestone
        if milestone_index == 0:
            # First milestone
            progress_percent = (current_points / MILESTONE_THRESHOLDS[0]) * 100
            next_threshold = MILESTONE_THRESHOLDS[0]
        elif milestone_index >= len(MILESTONE_THRESHOLDS) - 1 and current_points >= MILESTONE_THRESHOLDS[-1]:
            # Already at max milestone
            progress_percent = 100
            next_threshold = MILESTONE_THRESHOLDS[-1]
        else:
            # Between milestones
            prev_threshold = MILESTONE_THRESHOLDS[milestone_index - 1] if milestone_index > 0 else 0
            next_threshold = MILESTONE_THRESHOLDS[milestone_index]
            points_in_current_tier = current_points - prev_threshold
            tier_size = next_threshold - prev_threshold
            progress_percent = (points_in_current_tier / tier_size) * 100
        
        # Get the milestones
        milestones = entity["milestones"][:10]
        while len(milestones) < 10:
            milestones.append("To be discovered")
        
        # Calculate how many milestones are unlocked
        milestones_unlocked = 0
        for i, threshold in enumerate(MILESTONE_THRESHOLDS):
            if current_points >= threshold:
                milestones_unlocked += 1
            else:
                break
        
        # Build the author object for the template
        authors.append({
            "name": entity["author"],
            "current_points": current_points,
            "next_threshold": next_threshold,
            "progress_percent": min(100, progress_percent),  # Ensure it doesn't exceed 100%
            "milestones": milestones,
            "milestones_unlocked": milestones_unlocked
        })
    
    # Process manifested birds
    birds_in_progress = []
    for bird in manifested_birds:
        # Skip fully manifested birds
        if bird.get("fully_manifested", False):
            continue
            
        # Calculate the threshold for this bird's rarity
        threshold = get_points_needed(bird["rarity"])
        
        # Calculate progress percentage
        progress_percent = min(100, (bird["manifested_points"] / threshold) * 100)
        
        birds_in_progress.append({
            "name": bird["commonName"],
            "scientific_name": bird["scientificName"],
            "rarity": bird["rarity"].capitalize(),
            "current_points": bird["manifested_points"],
            "threshold": threshold,
            "progress_percent": progress_percent
        })
    
    # Process manifested plants
    plants_in_progress = []
    for plant in manifested_plants:
        # Skip fully manifested plants
        if plant.get("fully_manifested", False):
            continue
            
        # Calculate the threshold for this plant's rarity
        threshold = get_points_needed(plant["rarity"])
        
        # Calculate progress percentage
        progress_percent = min(100, (plant["manifested_points"] / threshold) * 100)
        
        plants_in_progress.append({
            "name": plant["commonName"],
            "scientific_name": plant["scientificName"],
            "rarity": plant["rarity"].capitalize(),
            "current_points": plant["manifested_points"],
            "threshold": threshold,
            "progress_percent": progress_percent
        })
    
    # Return the rendered template
    return render_template('research.html', 
                          authors=authors, 
                          birds_in_progress=birds_in_progress,
                          plants_in_progress=plants_in_progress)
