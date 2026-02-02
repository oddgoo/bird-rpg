from flask import render_template
from data.storage import load_research_progress_sync, load_manifested_birds_sync, load_manifested_plants_sync, load_research_entities
from data.manifest_constants import get_points_needed
import json
import os

from commands.research import MILESTONE_THRESHOLDS

def get_research_page():
    """Render the research page"""
    research_entities = load_research_entities()
    research_progress = load_research_progress_sync()
    manifested_birds = load_manifested_birds_sync()
    manifested_plants = load_manifested_plants_sync()

    # Prepare author data for the template
    authors = []
    for entity in research_entities:
        current_points = research_progress.get(entity["author"], 0)

        milestone_index = 0
        for i, threshold in enumerate(MILESTONE_THRESHOLDS):
            if current_points < threshold:
                milestone_index = i
                break
            elif i == len(MILESTONE_THRESHOLDS) - 1:
                milestone_index = i

        if milestone_index == 0:
            progress_percent = (current_points / MILESTONE_THRESHOLDS[0]) * 100
            next_threshold = MILESTONE_THRESHOLDS[0]
        elif milestone_index >= len(MILESTONE_THRESHOLDS) - 1 and current_points >= MILESTONE_THRESHOLDS[-1]:
            progress_percent = 100
            next_threshold = MILESTONE_THRESHOLDS[-1]
        else:
            prev_threshold = MILESTONE_THRESHOLDS[milestone_index - 1] if milestone_index > 0 else 0
            next_threshold = MILESTONE_THRESHOLDS[milestone_index]
            points_in_current_tier = current_points - prev_threshold
            tier_size = next_threshold - prev_threshold
            progress_percent = (points_in_current_tier / tier_size) * 100

        milestones = entity["milestones"]
        while len(milestones) < len(MILESTONE_THRESHOLDS):
            milestones.append("To be discovered")

        milestones_unlocked = 0
        for i, threshold in enumerate(MILESTONE_THRESHOLDS):
            if current_points >= threshold:
                milestones_unlocked += 1
            else:
                break

        authors.append({
            "name": entity["author"],
            "current_points": current_points,
            "next_threshold": next_threshold,
            "progress_percent": min(100, progress_percent),
            "milestones": milestones,
            "milestones_unlocked": milestones_unlocked
        })

    # Process manifested birds
    birds_in_progress = []
    for bird in manifested_birds:
        if bird.get("fully_manifested", False):
            continue

        threshold = get_points_needed(bird.get("rarity", "common"))
        current_pts = bird.get("manifested_points", 0)
        progress_percent = min(100, (current_pts / threshold) * 100)

        birds_in_progress.append({
            "name": bird.get("common_name", bird.get("commonName", "")),
            "scientific_name": bird.get("scientific_name", bird.get("scientificName", "")),
            "rarity": bird.get("rarity", "common").capitalize(),
            "current_points": current_pts,
            "threshold": threshold,
            "progress_percent": progress_percent
        })

    # Process manifested plants
    plants_in_progress = []
    for plant in manifested_plants:
        if plant.get("fully_manifested", False):
            continue

        threshold = get_points_needed(plant.get("rarity", "common"))
        current_pts = plant.get("manifested_points", 0)
        progress_percent = min(100, (current_pts / threshold) * 100)

        plants_in_progress.append({
            "name": plant.get("common_name", plant.get("commonName", "")),
            "scientific_name": plant.get("scientific_name", plant.get("scientificName", "")),
            "rarity": plant.get("rarity", "common").capitalize(),
            "current_points": current_pts,
            "threshold": threshold,
            "progress_percent": progress_percent
        })

    authors.sort(key=lambda x: x["name"])

    return render_template('research.html',
                          authors=authors,
                          birds_in_progress=birds_in_progress,
                          plants_in_progress=plants_in_progress)
