from flask import render_template
from datetime import datetime, timedelta
import data.storage as db
from data.models import (
    load_bird_species_sync,
    get_discovered_species_sync,
    get_discovered_plant_species_count_sync,
    load_treasures,
    get_extra_bird_space_sync,
)
from config.config import MAX_BIRDS_PER_NEST
from utils.time_utils import get_time_until_reset, get_australian_time
from utils.human_spawner import HumanSpawner

def get_home_page():
    # Load treasures data (cached)
    treasures_data = load_treasures()

    all_treasures = {}
    for category in treasures_data.values():
        for treasure in category:
            all_treasures[treasure['id']] = treasure

    # Get common nest data
    common_nest = db.load_common_nest_sync()

    # Get time until reset
    time_until_reset = get_time_until_reset()

    # Load bird species data for reference (one call, reused everywhere)
    bird_species_list = load_bird_species_sync()
    bird_species_data = {bird["scientificName"]: bird for bird in bird_species_list}

    # ---- BULK FETCH (one query each) ----
    all_players = db.load_all_players_sync()
    now = get_australian_time()
    songs_cutoff = (now - timedelta(days=30)).strftime('%Y-%m-%d')
    all_songs = db.get_all_songs_sync(since_date=songs_cutoff)
    all_eggs = db.get_all_eggs_sync()
    all_birds_by_user = db.get_all_player_birds_sync()
    all_plants_by_user = db.get_all_player_plants_sync()
    all_nest_treasures = db.get_all_nest_treasures_sync()

    # Pre-compute songs_given per user (last 30 days)
    songs_count = {}
    for s in all_songs:
        uid = s["singer_user_id"]
        songs_count[uid] = songs_count.get(uid, 0) + 1

    # Get all personal nests with singing data
    personal_nests = []

    for player in all_players:
        user_id = str(player["user_id"])

        songs_given = songs_count.get(user_id, 0)

        # Get egg data from bulk fetch
        egg_progress = all_eggs.get(user_id)

        # Get birds and plants from bulk fetch
        birds = all_birds_by_user.get(user_id, [])
        plants = all_plants_by_user.get(user_id, [])

        # Skip players with no birds
        if not birds:
            continue

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
            # Use first bird if no featured bird set (from pre-fetched data)
            if birds:
                first = birds[0]
                bird_data = bird_species_data.get(first["scientific_name"], {})
                featured_bird = {
                    "commonName": first["common_name"],
                    "scientificName": first["scientific_name"],
                    "rarity": bird_data.get("rarity", "common"),
                }

        # Get nest treasures from bulk fetch
        nest_treasures_rows = all_nest_treasures.get(user_id, [])
        nest_treasures = []
        for decoration in nest_treasures_rows:
            tid = decoration.get('treasure_id')
            if tid in all_treasures:
                treasure_info = all_treasures[tid].copy()
                treasure_info['x'] = decoration.get('x', 0)
                treasure_info['y'] = decoration.get('y', 0)
                treasure_info['rotation'] = decoration.get('rotation', 0)
                treasure_info['z_index'] = decoration.get('z_index', 0)
                if decoration.get('size') is not None:
                    treasure_info['size'] = decoration.get('size')
                nest_treasures.append(treasure_info)

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
    total_bird_species = len(bird_species_list)

    # get_discovered_species_sync does 2 DB queries (all_birds + released_birds)
    # Reuse the result for both count and species list
    discovered = get_discovered_species_sync()
    discovered_species_count = len(discovered)
    discovered_plant_species_count = get_discovered_plant_species_count_sync()

    # Build discovered species list using the bird_species_data dict (no extra queries)
    discovered_species = []
    for common_name, scientific_name in discovered:
        bird = bird_species_data.get(scientific_name)
        if bird:
            discovered_species.append({
                "commonName": common_name,
                "scientificName": scientific_name,
                "rarity": bird["rarity"],
                "effect": bird.get("effect", ""),
            })

    exploration = db.get_exploration_data_sync()

    # Get current human
    spawner = HumanSpawner()
    current_human = spawner.spawn_human()

    # Get defeated humans data
    defeated_humans = db.get_defeated_humans_sync(limit=5)

    # Bird capacity per nest
    max_birds = MAX_BIRDS_PER_NEST + get_extra_bird_space_sync()

    return render_template(
        'home.html',
        common_nest=common_nest,
        max_birds=max_birds,
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
