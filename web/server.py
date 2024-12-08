from flask import Flask, render_template, send_from_directory
from threading import Thread
from config.config import PORT, DEBUG
from web.home import get_home_page
from data.storage import load_data
from data.models import get_personal_nest, get_total_chicks, get_total_bird_species, load_bird_species
from utils.time_utils import get_time_until_reset, get_current_date

app = Flask('', static_url_path='/static', static_folder='static')

@app.route('/')
def home():
    return get_home_page()

@app.route('/help')
def help_page():
    return render_template('help.html')

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
    
    # Add all data to nest_data
    nest_data = {
        "name": nest.get("name", "Some Bird's Nest"),
        "twigs": nest["twigs"],
        "seeds": nest["seeds"],
        "chicks": enriched_chicks,
        "songs_given": songs_given,
        "egg": nest.get("egg", None),
        "songs_given_to": songs_given_to,
        "brooded_nests": brooded_nests
    }
    
    return render_template('user.html', nest=nest_data)

def run_server():
    app.jinja_env.auto_reload = DEBUG  # Enable template auto-reload
    app.config['TEMPLATES_AUTO_RELOAD'] = DEBUG  # Set template auto-reload config
    app.run(host='0.0.0.0', port=PORT)

def start_server():
    server_thread = Thread(target=run_server)
    server_thread.start()
    return server_thread