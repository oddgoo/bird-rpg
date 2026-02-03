from flask import Flask, render_template, send_from_directory, request, redirect, url_for, session, flash, jsonify
from threading import Thread
from config.config import PORT, DEBUG, ADMIN_PASSWORD, SPECIES_IMAGES_DIR
from web.home import get_home_page
from web.admin import admin_routes
from web.research import get_research_page
from data.models import load_bird_species_sync, load_plant_species_sync, get_discovered_species_sync, get_discovered_plants_sync
from data.db import get_sync_client
from utils.time_utils import get_time_until_reset, get_current_date, get_australian_time
from datetime import timedelta
import json
import os
import secrets
import time

import data.storage as db

app = Flask('', static_url_path='/static', static_folder='static')
# Set a secret key for session management
app.secret_key = secrets.token_hex(16)

# Register admin routes
admin_routes(app)

@app.route('/')
def home():
    start = time.time()
    result = get_home_page()
    print(f"Homepage rendered in {time.time()-start:.1f}s")
    return result

@app.route('/help')
def help_page():
    return render_template('help.html')

@app.route('/wings-of-time')
def wings_of_time():
    memoirs = db.load_memoirs_sync()
    realm_messages = db.load_realm_messages_sync()

    # Combine memoirs and realm messages
    all_entries = []

    # Add memoirs with type
    for memoir in memoirs:
        all_entries.append({
            "date": memoir["memoir_date"],
            "nest_name": memoir.get("nest_name", "Unknown"),
            "text": memoir["text"],
            "user_id": memoir["user_id"],
            "type": "memoir",
            "sort_order": 1,
        })

    # Add realm messages with type
    for message in realm_messages:
        all_entries.append({
            "date": message["message_date"],
            "message": message["message"],
            "type": "realm",
            "sort_order": 0,
        })

    # Sort entries by date (descending) and sort_order
    sorted_entries = sorted(all_entries, key=lambda x: (x["date"], x["sort_order"]))

    return render_template('wings-of-time.html', entries=sorted_entries)

@app.route('/user/<user_id>')
def user_page(user_id):
    player = db.load_player_sync(user_id)
    birds = db.get_player_birds_sync(user_id)
    plants = db.get_player_plants_sync(user_id)
    nest_treasures = db.get_nest_treasures_sync(user_id)

    bird_species_data = {species["scientificName"]: species for species in load_bird_species_sync()}

    # Load treasures data
    with open('data/treasures.json', 'r') as f:
        treasures_data = json.load(f)

    all_treasures = {}
    for category in treasures_data.values():
        for treasure in category:
            all_treasures[treasure['id']] = treasure

    # Enrich chicks data with species info
    enriched_chicks = []
    for bird in birds:
        species_info = bird_species_data.get(bird["scientific_name"], {})

        # Get treasure details for this bird
        bird_treasures_rows = get_sync_client().table("bird_treasures").select("*").eq("bird_id", bird["id"]).execute().data or []
        chick_treasures = []
        for decoration in bird_treasures_rows:
            tid = decoration.get('treasure_id')
            if tid in all_treasures:
                treasure_info = all_treasures[tid].copy()
                treasure_info['x'] = decoration.get('x', 0)
                treasure_info['y'] = decoration.get('y', 0)
                chick_treasures.append(treasure_info)

        enriched_chicks.append({
            "commonName": bird["common_name"],
            "scientificName": bird["scientific_name"],
            "rarity": species_info.get("rarity", "common"),
            "effect": species_info.get("effect", ""),
            "treasures": chick_treasures,
        })

    today = get_current_date()

    # Count songs given (all time)
    all_songs = db.get_all_songs_sync()
    songs_given = sum(1 for s in all_songs if s["singer_user_id"] == str(user_id))

    # Get today's songs given to
    songs_given_to = []
    today_songs = [s for s in all_songs if s["song_date"] == today and s["singer_user_id"] == str(user_id)]
    for song in today_songs:
        target = db.load_player_sync(song["target_user_id"])
        songs_given_to.append({
            "user_id": song["target_user_id"],
            "name": target.get("nest_name", "Some Bird's Nest"),
        })

    # Get today's brooded nests
    brooded_nests = []
    sb = get_sync_client()
    brooding_today = sb.table("daily_brooding").select("target_user_id").eq("brooding_date", today).eq("brooder_user_id", str(user_id)).execute().data or []
    for row in brooding_today:
        target = db.load_player_sync(row["target_user_id"])
        brooded_nests.append({
            "user_id": row["target_user_id"],
            "name": target.get("nest_name", "Some Bird's Nest"),
        })

    # Load plant species data
    plant_species_data = {}
    try:
        all_plant_species = load_plant_species_sync()
        plant_species_data = {plant["scientificName"]: plant for plant in all_plant_species}
    except Exception as e:
        print(f"Error loading plant species data: {e}")

    # Enrich plants data with species info
    enriched_plants = []
    for plant in plants:
        species_info = plant_species_data.get(plant["scientific_name"], {})
        enriched_plants.append({
            "commonName": plant["common_name"],
            "scientificName": plant["scientific_name"],
            "rarity": species_info.get("rarity", "common"),
            "effect": species_info.get("effect", ""),
            "treasures": [],
        })

    # Enrich inventory treasures
    enriched_treasures = []
    player_inv = sb.table("player_treasures").select("treasure_id").eq("user_id", str(user_id)).execute().data or []
    for row in player_inv:
        tid = row["treasure_id"]
        if tid in all_treasures:
            enriched_treasures.append(all_treasures[tid])

    # Get egg data
    egg_data = sb.table("eggs").select("*").eq("user_id", str(user_id)).execute().data
    egg = egg_data[0] if egg_data else None

    nest_data = {
        "name": player.get("nest_name", "Some Bird's Nest"),
        "twigs": player["twigs"],
        "seeds": player["seeds"],
        "chicks": enriched_chicks,
        "plants": enriched_plants,
        "treasures": enriched_treasures,
        "songs_given": songs_given,
        "egg": egg,
        "songs_given_to": songs_given_to,
        "brooded_nests": brooded_nests,
        "garden_size": player.get("garden_size", 0),
        "garden_life": len(plants),
        "inspiration": player.get("inspiration", 0),
    }

    return render_template('user.html', nest=nest_data)

@app.route('/species_images/<path:filename>')
def species_images(filename):
    if not os.path.exists(SPECIES_IMAGES_DIR):
        return "Directory not found", 404

    try:
        encoded_filename = filename.replace(' ', '%20')
        if encoded_filename in os.listdir(SPECIES_IMAGES_DIR):
            return send_from_directory(SPECIES_IMAGES_DIR, encoded_filename)
        if filename in os.listdir(SPECIES_IMAGES_DIR):
            return send_from_directory(SPECIES_IMAGES_DIR, filename)
        return "File not found", 404
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/codex')
def codex():
    birds = load_bird_species_sync()
    plants = load_plant_species_sync()

    discovered_birds = {scientific_name for _, scientific_name in get_discovered_species_sync()}
    discovered_plants = {scientific_name for _, scientific_name in get_discovered_plants_sync()}

    realm_messages = db.load_realm_messages_sync()

    return render_template('codex.html',
                         birds=birds,
                         plants=plants,
                         discovered_birds=discovered_birds,
                         discovered_plants=discovered_plants,
                         realm_messages=realm_messages)

@app.route('/research')
def research():
    return get_research_page()


@app.route('/health')
def health():
    """Health check endpoint that tests the sync Supabase connection."""
    try:
        start = time.time()
        sb = get_sync_client()
        sb.table("common_nest").select("id").limit(1).execute()
        elapsed = time.time() - start
        return jsonify({"status": "ok", "supabase_latency_ms": round(elapsed * 1000, 1)})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

def run_server():
    # Startup diagnostic: test sync Supabase client
    try:
        start = time.time()
        sb = get_sync_client()
        sb.table("common_nest").select("id").limit(1).execute()
        elapsed = time.time() - start
        print(f"Sync Supabase connection verified ({elapsed*1000:.0f}ms)")
    except Exception as e:
        print(f"Sync Supabase connection FAILED: {e}")

    app.jinja_env.auto_reload = DEBUG
    app.config['TEMPLATES_AUTO_RELOAD'] = DEBUG
    app.run(host='0.0.0.0', port=PORT)

def start_server():
    server_thread = Thread(target=run_server)
    server_thread.start()
    return server_thread
