from flask import render_template
from datetime import datetime
from data.storage import load_data
from data.models import (
    get_common_nest, 
    get_total_bird_species, 
    load_bird_species,
    get_discovered_species_count, get_discovered_species
)
from utils.time_utils import get_time_until_reset

def get_home_page():
    data = load_data()
    
    # Get common nest data
    common_nest = get_common_nest(data)
    
    # Get time until reset
    time_until_reset = get_time_until_reset()
    
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
            "inspiration": nest.get("inspiration", 0)
        })
    
    # Sort nests by songs given, descending
    personal_nests.sort(key=lambda x: x["songs_given"], reverse=True)
    
    # Get discovered species tally
    total_bird_species = get_total_bird_species(data)
    discovered_species_count = get_discovered_species_count(data)
    
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
    
    return render_template(
        'home.html',
        common_nest=common_nest,
        personal_nests=personal_nests,
        time_until_reset=time_until_reset,
        total_bird_species=total_bird_species,
        discovered_species_count=discovered_species_count,
        discovered_species=discovered_species,
        exploration=exploration
    )
