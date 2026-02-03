from flask import render_template
import json
from datetime import datetime
import data.storage as db
from data.models import (
    get_total_bird_species_sync,
    load_bird_species_sync,
    get_discovered_species_count_sync, get_discovered_species_sync,
    get_discovered_plant_species_count_sync
)
from utils.time_utils import get_time_until_reset
from utils.human_spawner import HumanSpawner

def get_home_page():
    # Load treasures data
    with open('data/treasures.json', 'r') as f:
        treasures_data = json.load(f)

    all_treasures = {}
    for category in treasures_data.values():
        for treasure in category:
            all_treasures[treasure['id']] = treasure

    # Get common nest data
    common_nest = db.load_common_nest_sync()

    # Get time until reset
    time_until_reset = get_time_until_reset()

    # Load bird species data for reference
    bird_species_data = {bird["scientificName"]: bird for bird in load_bird_species_sync()}

    # Load all players and their data
    all_players = db.load_all_players_sync()
    all_songs = db.get_all_songs_sync()

    # Get all personal nests with singing data
    personal_nests = []

    for player in all_players:
        user_id = player["user_id"]

        # Count how many times this user has sung to others
        songs_given = sum(1 for s in all_songs if s["singer_user_id"] == str(user_id))

        # Get egg data via storage layer
        egg_res = db._sync_client().table("eggs").select("brooding_progress").eq("user_id", str(user_id)).execute()
        egg_progress = egg_res.data[0]["brooding_progress"] if egg_res.data else None

        # Get featured bird
        featured_bird = None
        if player.get("featured_bird_scientific_name"):
            bird_data = bird_species_data.get(player["featured_bird_scientific_name"], {})
            featured_bird = {
                "commonName": player.get("featured_bird_common_name", ""),
                "scientificName": player["featured_bird_scientific_name"],
                "rarity": bird_data.get("rarity", "common"),
            }
        else:
            # Use first bird if no featured bird set
            birds = db.get_player_birds_sync(user_id)
            if birds:
                first = birds[0]
                bird_data = bird_species_data.get(first["scientific_name"], {})
                featured_bird = {
                    "commonName": first["common_name"],
                    "scientificName": first["scientific_name"],
                    "rarity": bird_data.get("rarity", "common"),
                }

        # Get nest treasures
        nest_treasures_rows = db.get_nest_treasures_sync(user_id)
        nest_treasures = []
        for decoration in nest_treasures_rows:
            tid = decoration.get('treasure_id')
            if tid in all_treasures:
                treasure_info = all_treasures[tid].copy()
                treasure_info['x'] = decoration.get('x', 0)
                treasure_info['y'] = decoration.get('y', 0)
                nest_treasures.append(treasure_info)

        birds = db.get_player_birds_sync(user_id)
        plants = db.get_player_plants_sync(user_id)

        personal_nests.append({
            "user_id": user_id,
            "name": player.get("nest_name", "Some Bird's Nest"),
            "twigs": player["twigs"],
            "seeds": player["seeds"],
            "songs_given": songs_given,
            "space": player["twigs"] - player["seeds"],
            "chicks": len(birds),
            "has_egg": egg_progress is not None,
            "egg_progress": egg_progress,
            "garden_size": player.get("garden_size", 0),
            "garden_life": len(plants),
            "inspiration": player.get("inspiration", 0),
            "discord_username": player.get("discord_username", "Unknown User"),
            "featured_bird": featured_bird,
            "treasures": nest_treasures,
        })

    # Sort nests by songs given, descending
    personal_nests.sort(key=lambda x: x["songs_given"], reverse=True)

    # Get discovered species tally
    total_bird_species = get_total_bird_species_sync()
    discovered_species_count = get_discovered_species_count_sync()
    discovered_plant_species_count = get_discovered_plant_species_count_sync()

    discovered_species = []
    for common_name, scientific_name in get_discovered_species_sync():
        for bird in load_bird_species_sync():
            if bird["scientificName"] == scientific_name:
                discovered_species.append({
                    "commonName": common_name,
                    "scientificName": scientific_name,
                    "rarity": bird["rarity"],
                    "effect": bird.get("effect", ""),
                })
                break

    exploration = db.get_exploration_data_sync()

    # Get current human
    spawner = HumanSpawner()
    current_human = spawner.spawn_human()

    # Get defeated humans data
    defeated_humans = db.get_defeated_humans_sync(limit=5)

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
