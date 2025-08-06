from flask import render_template
import json
from datetime import datetime
from data.storage import load_data
from data.models import (
    get_common_nest, 
    get_total_bird_species, 
    load_bird_species,
    get_discovered_species_count, get_discovered_species,
    get_discovered_plant_species_count
)
from utils.time_utils import get_time_until_reset
from commands.swooping import Swooping
from utils.human_spawner import HumanSpawner

def get_home_page():
    data = load_data()
    
    # Load treasures data
    with open('data/treasures.json', 'r') as f:
        treasures_data = json.load(f)
    
    all_treasures = {}
    for category in treasures_data.values():
        for treasure in category:
            all_treasures[treasure['id']] = treasure

    # Get common nest data
    common_nest = get_common_nest(data)
    
    # Get time until reset
    time_until_reset = get_time_until_reset()
    
    # Load bird species data for reference
    bird_species_data = {bird["scientificName"]: bird for bird in load_bird_species()}
    
    # Get all personal nests with singing data
    personal_nests = []
    
    for user_id in data["personal_nests"]:
        nest = data["personal_nests"][user_id]
        # Count how many times this user has sung to others across all dates
        songs_given = 0
        for date_songs in data.get("daily_songs", {}).values():
            for target_songs in date_songs.values():
                if str(user_id) in target_songs:
                    songs_given += 1
        
        # Get egg progress if present
        egg_data = nest.get("egg")
        egg_progress = egg_data["brooding_progress"] if egg_data else None
        
        # Get featured bird data with rarity from bird_species.json
        featured_bird = nest.get("featured_bird")
        if featured_bird:
            bird_data = bird_species_data.get(featured_bird["scientificName"], {})
            featured_bird = {
                **featured_bird,
                "rarity": bird_data.get("rarity", "common")
            }
        # If no featured bird but there are chicks, use the first chick as featured bird
        elif nest.get("chicks") and len(nest.get("chicks", [])) > 0:
            first_chick = nest["chicks"][0]
            bird_data = bird_species_data.get(first_chick["scientificName"], {})
            featured_bird = {
                **first_chick,
                "rarity": bird_data.get("rarity", "common")
            }
        
        # Get treasure details for the nest
        nest_treasures = []
        if 'treasures_applied_on_nest' in nest:
            for decoration in nest['treasures_applied_on_nest']:
                treasure_id = decoration.get('id')
                if treasure_id in all_treasures:
                    treasure_info = all_treasures[treasure_id].copy()
                    if 'x' in decoration:
                        treasure_info['x'] = decoration['x']
                    if 'y' in decoration:
                        treasure_info['y'] = decoration['y']
                    nest_treasures.append(treasure_info)

        personal_nests.append({
            "user_id": user_id,
            "name": nest.get("name", "Some Bird's Nest"),
            "twigs": nest["twigs"],
            "seeds": nest["seeds"],
            "songs_given": songs_given,
            "space": nest["twigs"] - nest["seeds"],
            "chicks": len(nest.get("chicks", [])),
            "has_egg": egg_data is not None,
            "egg_progress": egg_progress,
            "garden_size": nest.get("garden_size", 0),
            "garden_life": nest.get("garden_life", 0),
            "inspiration": nest.get("inspiration", 0),
            "discord_username": nest.get("discord_username", "Unknown User"), # Add discord username
            "featured_bird": featured_bird,
            "treasures": nest_treasures
        })
    
    # Sort nests by songs given, descending
    personal_nests.sort(key=lambda x: x["songs_given"], reverse=True)
    
    # Get discovered species tally
    total_bird_species = get_total_bird_species(data)
    discovered_species_count = get_discovered_species_count(data)
    discovered_plant_species_count = get_discovered_plant_species_count(data)
    
    discovered_species = []
    for species in get_discovered_species(data):
        common_name, scientific_name = species
        # Find the full bird data from bird_species.json
        for bird in load_bird_species():
            if bird["scientificName"] == scientific_name:
                discovered_species.append({
                    "commonName": common_name,
                    "scientificName": scientific_name,
                    "rarity": bird["rarity"],
                    "effect": bird.get("effect", "")
                })
                break

    print(discovered_species)
    exploration = data.get("exploration", {})
    
    # Get current human
    spawner = HumanSpawner()
    current_human = spawner.spawn_human()

    # Get defeated humans data
    defeated_humans = data.get("defeated_humans", [])
    # Sort by date, most recent first
    defeated_humans.sort(key=lambda x: x["date"], reverse=True)
    # Keep only the last 5 defeated humans
    defeated_humans = defeated_humans[:5]

    return render_template(
        'home.html',
        common_nest=common_nest,
        personal_nests=personal_nests,
        time_until_reset=time_until_reset,
        total_bird_species=total_bird_species,
        discovered_species_count=discovered_species_count,
        discovered_plant_species_count=discovered_plant_species_count,
        discovered_species=discovered_species,
        exploration=exploration,
        current_human=current_human,
        defeated_humans=defeated_humans,
    )
