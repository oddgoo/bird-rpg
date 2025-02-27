from flask import render_template, request, redirect, url_for, send_file, session, flash
from config.config import ADMIN_PASSWORD, NESTS_FILE, LORE_FILE, REALM_LORE_FILE, SPECIES_IMAGES_DIR
import requests
from threading import Thread
import os
import json
import shutil
import urllib.parse
from datetime import timedelta
from utils.time_utils import get_australian_time
from utils.logging import log_debug

def admin_routes(app):
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
            from data.storage import load_data, save_data
            
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

    @app.route('/admin/download_species_images')
    def download_species_images():
        # Check if authenticated in session
        if not session.get('admin_authenticated'):
            return redirect(url_for('admin'))
        
        try:
            # Create species_images directory if it doesn't exist
            os.makedirs(SPECIES_IMAGES_DIR, exist_ok=True)
            
            # Start the download process in a background thread
            thread = Thread(target=download_species_images_thread)
            thread.daemon = True
            thread.start()
            
            # Flash message
            flash("Species image download started in the background. This may take a few minutes. Check the server logs for progress.", 'success')
            
            return redirect(url_for('admin'))
        except Exception as e:
            log_debug(f"Error starting species images download: {e}")
            flash(f"Error starting species images download: {str(e)}", 'error')
            return redirect(url_for('admin'))

def download_species_images_thread():
    """Background thread to download species images"""
    try:
        # Load bird and plant species data
        bird_species = []
        plant_species = []
        
        # Load bird species
        try:
            with open('data/bird_species.json', 'r') as f:
                bird_data = json.load(f)
                bird_species = bird_data.get('bird_species', [])
        except Exception as e:
            log_debug(f"Error loading bird species: {e}")
            return
        
        # Load plant species
        try:
            with open('data/plant_species.json', 'r') as f:
                plant_species = json.load(f)
        except Exception as e:
            log_debug(f"Error loading plant species: {e}")
            return
        
        # Download images
        success_count = 0
        error_count = 0
        special_count = 0
        
        # Process birds
        for bird in bird_species:
            scientific_name = bird.get('scientificName')
            if not scientific_name:
                continue
            
            # Skip special birds as they already have local images
            if bird.get('rarity') == 'Special':
                special_count += 1
                continue
            
            # Download image
            image_url = fetch_image_url(scientific_name)
            if image_url:
                filename = f"{urllib.parse.quote(scientific_name)}.jpg"
                filepath = os.path.join(SPECIES_IMAGES_DIR, filename)
                
                # Download the image
                try:
                    response = requests.get(image_url, stream=True)
                    if response.status_code == 200:
                        with open(filepath, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                f.write(chunk)
                        success_count += 1
                        log_debug(f"Downloaded image for {scientific_name}")
                    else:
                        error_count += 1
                        log_debug(f"Error downloading image for {scientific_name}: HTTP {response.status_code}")
                except Exception as e:
                    log_debug(f"Error downloading image for {scientific_name}: {e}")
                    error_count += 1
            else:
                error_count += 1
                log_debug(f"No image URL found for {scientific_name}")
        
        # Process plants
        for plant in plant_species:
            scientific_name = plant.get('scientificName')
            if not scientific_name:
                continue
            
            # Download image
            image_url = fetch_image_url(scientific_name)
            if image_url:
                filename = f"{urllib.parse.quote(scientific_name)}.jpg"
                filepath = os.path.join(SPECIES_IMAGES_DIR, filename)
                
                # Download the image
                try:
                    response = requests.get(image_url, stream=True)
                    if response.status_code == 200:
                        with open(filepath, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                f.write(chunk)
                        success_count += 1
                        log_debug(f"Downloaded image for {scientific_name}")
                    else:
                        error_count += 1
                        log_debug(f"Error downloading image for {scientific_name}: HTTP {response.status_code}")
                except Exception as e:
                    log_debug(f"Error downloading image for {scientific_name}: {e}")
                    error_count += 1
            else:
                error_count += 1
                log_debug(f"No image URL found for {scientific_name}")
        
        log_debug(f"Species image download complete: {success_count} successful, {error_count} errors, {special_count} special birds skipped")
    except Exception as e:
        log_debug(f"Error in download thread: {e}")

def fetch_image_url(scientific_name):
    """Fetches the image URL from iNaturalist."""
    api_url = f"https://api.inaturalist.org/v1/taxa?q={scientific_name}&limit=1"
    try:
        response = requests.get(api_url)
        if response.status_code == 200:
            data = response.json()
            if data['results']:
                taxon = data['results'][0]
                image_url = taxon.get('default_photo', {}).get('medium_url')
                return image_url
    except Exception as e:
        log_debug(f"Error fetching image from iNaturalist: {e}")
    return None
