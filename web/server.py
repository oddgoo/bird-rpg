from flask import Flask, render_template, send_from_directory, request, redirect, url_for, send_file, session, flash
from threading import Thread
from config.config import PORT, DEBUG, ADMIN_PASSWORD, NESTS_FILE, LORE_FILE, REALM_LORE_FILE
from web.home import get_home_page
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
    
    # Load plant species data
    plant_species_data = {}
    try:
        with open('data/plant_species.json') as f:
            plant_species_data = {plant["scientificName"]: plant for plant in json.load(f)}
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

@app.route('/codex')
def codex():
    # Load bird species data
    birds = load_bird_species()
    
    # Load plant species data
    with open('data/plant_species.json') as f:
        plants = json.load(f)
    
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

@app.route('/admin/', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            # Store authentication in session
            session['admin_authenticated'] = True
            return redirect(url_for('admin'))
        else:
            return render_template('admin.html', authenticated=False, error="Invalid password")
    
    # Check if authenticated in session
    if session.get('admin_authenticated'):
        return render_template('admin.html', authenticated=True)
    
    return render_template('admin.html', authenticated=False)

@app.route('/admin/logout')
def admin_logout():
    # Clear admin authentication from session
    session.pop('admin_authenticated', None)
    return redirect(url_for('admin'))

@app.route('/admin/download/<file_type>')
def download_data(file_type):
    # Check if authenticated in session
    if not session.get('admin_authenticated'):
        return redirect(url_for('admin'))
    
    try:
        if file_type == 'nests':
            return send_file(NESTS_FILE, as_attachment=True, download_name='nests.json')
        elif file_type == 'lore':
            return send_file(LORE_FILE, as_attachment=True, download_name='lore.json')
        elif file_type == 'realm_lore':
            return send_file(REALM_LORE_FILE, as_attachment=True, download_name='realm_lore.json')
        else:
            return redirect(url_for('admin'))
    except Exception as e:
        print(f"Error downloading file: {e}")
        return redirect(url_for('admin'))

@app.route('/admin/purge-old-actions')
@app.route('/admin/purge_old_actions')
def purge_old_actions():
    # Check if authenticated in session
    if not session.get('admin_authenticated'):
        return redirect(url_for('admin'))
    
    try:
        # Calculate date 4 days ago
        current_time = get_australian_time()
        four_days_ago = (current_time - timedelta(days=4)).strftime('%Y-%m-%d')
        
        # Load data
        data = load_data()
        
        # Track counts for reporting
        purged_counts = {
            'daily_actions': 0,
            'daily_songs': 0,
            'daily_brooding': 0
        }
        
        # Purge old actions from daily_actions
        # Structure: data['daily_actions'][user_id]['actions_YYYY-MM-DD']
        if 'daily_actions' in data:
            for user_id in data['daily_actions']:
                # Find action keys that are older than 4 days
                old_action_keys = []
                for action_key in data['daily_actions'][user_id]:
                    # Extract date from action_key (format: actions_YYYY-MM-DD)
                    if action_key.startswith('actions_'):
                        date_str = action_key[8:]  # Remove 'actions_' prefix
                        if date_str < four_days_ago:
                            old_action_keys.append(action_key)
                
                # Remove old actions
                for action_key in old_action_keys:
                    purged_counts['daily_actions'] += 1
                    del data['daily_actions'][user_id][action_key]
        
        # Purge old actions from daily_songs
        # Structure: data['daily_songs'][date][user_id] = [singer_ids]
        if 'daily_songs' in data:
            old_dates = [date for date in data['daily_songs'] if date < four_days_ago]
            for date in old_dates:
                for user_id, singers in data['daily_songs'][date].items():
                    purged_counts['daily_songs'] += len(singers)
                del data['daily_songs'][date]
        
        # Purge old actions from daily_brooding
        # Structure: data['daily_brooding'][date][user_id] = [brooder_ids]
        if 'daily_brooding' in data:
            old_dates = [date for date in data['daily_brooding'] if date < four_days_ago]
            for date in old_dates:
                for user_id, brooders in data['daily_brooding'][date].items():
                    purged_counts['daily_brooding'] += len(brooders)
                del data['daily_brooding'][date]
        
        # Save updated data
        save_data(data)
        
        # Prepare success message
        total_purged = sum(purged_counts.values())
        message = f"Successfully purged old actions older than {four_days_ago}: "
        message += f"{purged_counts['daily_actions']} daily actions, "
        message += f"{purged_counts['daily_songs']} songs, "
        message += f"{purged_counts['daily_brooding']} brooding actions."
        
        # Flash message will be displayed on the admin page
        flash(message, 'success')
        
        return redirect(url_for('admin'))
    except Exception as e:
        print(f"Error purging old actions: {e}")
        flash(f"Error purging old actions: {str(e)}", 'error')
        return redirect(url_for('admin'))

def run_server():
    app.jinja_env.auto_reload = DEBUG  # Enable template auto-reload
    app.config['TEMPLATES_AUTO_RELOAD'] = DEBUG  # Set template auto-reload config
    app.run(host='0.0.0.0', port=PORT)

def start_server():
    server_thread = Thread(target=run_server)
    server_thread.start()
    return server_thread
