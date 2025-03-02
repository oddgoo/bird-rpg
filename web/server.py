from flask import Flask, render_template, send_from_directory, request, redirect, url_for, session, flash
from threading import Thread
from config.config import PORT, DEBUG, ADMIN_PASSWORD, NESTS_FILE, LORE_FILE, REALM_LORE_FILE, SPECIES_IMAGES_DIR
from web.home import get_home_page
from web.admin import admin_routes
from data.storage import load_data, load_lore, load_realm_lore, save_data
from data.models import get_personal_nest, get_total_chicks, get_total_bird_species, load_bird_species, get_discovered_species, get_discovered_plants
from utils.time_utils import get_time_until_reset, get_current_date, get_australian_time
from datetime import timedelta
import json
import os
import secrets

app = Flask('', static_url_path='/static', static_folder='static')
# Set a secret key for session management
app.secret_key = secrets.token_hex(16)

# Register admin routes
admin_routes(app)

@app.route('/')
def home():
    return get_home_page()

@app.route('/help')
def help_page():
    return render_template('help.html')

@app.route('/wings-of-time')
def wings_of_time():
    lore_data = load_lore()
    realm_lore = load_realm_lore()
    
    # Combine memoirs and realm messages
    all_entries = []
    
    # Add memoirs with type
    for memoir in lore_data["memoirs"]:
        all_entries.append({
            **memoir,
            "type": "memoir"
        })
    
    # Add realm messages with type and sort order
    for message in realm_lore["messages"]:
        all_entries.append({
            "date": message["date"],
            "message": message["message"],
            "type": "realm",
            "sort_order": 0  # Realm messages appear first
        })
    
    # Add sort order to memoirs (after realm messages)
    for entry in all_entries:
        if "sort_order" not in entry:
            entry["sort_order"] = 1
    
    # Sort entries by date (descending) and sort_order
    sorted_entries = sorted(all_entries, key=lambda x: (x["date"], x["sort_order"]))
    
    return render_template('wings-of-time.html', entries=sorted_entries)

@app.route('/user/<user_id>')
def user_page(user_id):
    data = load_data()
    nest = get_personal_nest(data, user_id)
    bird_species_data = {species["scientificName"]: species for species in load_bird_species()}

    # Enrich chicks data with species info
    enriched_chicks = []
    for chick in nest.get("chicks", []):
        species_info = bird_species_data.get(chick["scientificName"], {})
        enriched_chicks.append({
            **chick,
            "rarity": species_info.get("rarity", "common"),
            "effect": species_info.get("effect", "")
        })

    today = get_current_date()

    
    
    # Count songs given
    songs_given = 0
    for date_songs in data.get("daily_songs", {}).values():
        for target_songs in date_songs.values():
            if str(user_id) in target_songs:
                songs_given += 1
    
    # Get today's songs given to
    songs_given_to = []
    if today in data.get("daily_songs", {}):
        for target_id, singers in data["daily_songs"][today].items():
            if str(user_id) in singers:
                target_nest = get_personal_nest(data, target_id)
                songs_given_to.append({
                    "user_id": target_id,
                    "name": target_nest.get("name", "Some Bird's Nest")
                })
    
    # Get today's brooded nests
    brooded_nests = []
    if today in data.get("daily_brooding", {}):
        for target_id, brooders in data["daily_brooding"][today].items():
            if str(user_id) in brooders:
                target_nest = get_personal_nest(data, target_id)
                brooded_nests.append({
                    "user_id": target_id,
                    "name": target_nest.get("name", "Some Bird's Nest")
                })
    
    # Load plant species data (including manifested plants)
    plant_species_data = {}
    try:
        from data.models import load_plant_species
        plants = load_plant_species()
        plant_species_data = {plant["scientificName"]: plant for plant in plants}
    except Exception as e:
        print(f"Error loading plant species data: {e}")
    
    # Enrich plants data with species info
    enriched_plants = []
    for plant in nest.get("plants", []):
        species_info = plant_species_data.get(plant["scientificName"], {})
        enriched_plants.append({
            **plant,
            "rarity": species_info.get("rarity", "common"),
            "effect": species_info.get("effect", "")
        })
    
    # Add all data to nest_data
    nest_data = {
        "name": nest.get("name", "Some Bird's Nest"),
        "twigs": nest["twigs"],
        "seeds": nest["seeds"],
        "chicks": enriched_chicks,
        "plants": enriched_plants,
        "songs_given": songs_given,
        "egg": nest.get("egg", None),
        "songs_given_to": songs_given_to,
        "brooded_nests": brooded_nests,
        "garden_size": nest.get("garden_size", 0),
        "garden_life": nest.get("garden_life", 0),
        "inspiration": nest.get("inspiration", 0)
    }
    
    return render_template('user.html', nest=nest_data)

@app.route('/species_images/<path:filename>')
def species_images(filename):
    # Check if the directory exists
    if not os.path.exists(SPECIES_IMAGES_DIR):
        return "Directory not found", 404
    
    try:
        # Try with the encoded name (replacing spaces with %20)
        encoded_filename = filename.replace(' ', '%20')
        
        # Check if the file exists with the encoded name
        if encoded_filename in os.listdir(SPECIES_IMAGES_DIR):
            return send_from_directory(SPECIES_IMAGES_DIR, encoded_filename)
        
        # Check if the file exists with the decoded name
        if filename in os.listdir(SPECIES_IMAGES_DIR):
            return send_from_directory(SPECIES_IMAGES_DIR, filename)
        
        # If neither exists, return 404
        return "File not found", 404
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/codex')
def codex():
    # Load bird species data (including manifested birds)
    birds = load_bird_species()
    
    # Load plant species data (including manifested plants)
    from data.models import load_plant_species
    plants = load_plant_species()
    
    # Load game data and get discovered species
    data = load_data()
    discovered_birds = {scientific_name for _, scientific_name in get_discovered_species(data)}
    discovered_plants = {scientific_name for _, scientific_name in get_discovered_plants(data)}
    
    # Load realm lore data
    realm_lore = load_realm_lore()
    
    return render_template('codex.html', 
                         birds=birds,
                         plants=plants,
                         discovered_birds=discovered_birds,
                         discovered_plants=discovered_plants,
                         realm_messages=realm_lore["messages"])


def run_server():
    app.jinja_env.auto_reload = DEBUG  # Enable template auto-reload
    app.config['TEMPLATES_AUTO_RELOAD'] = DEBUG  # Set template auto-reload config
    app.run(host='0.0.0.0', port=PORT)

def start_server():
    server_thread = Thread(target=run_server)
    server_thread.start()
    return server_thread
