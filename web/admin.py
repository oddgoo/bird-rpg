from flask import render_template, request, redirect, url_for, send_file, session, flash
from config.config import ADMIN_PASSWORD, SPECIES_IMAGES_DIR, MAX_GARDEN_SIZE
import requests
from threading import Thread
import os
import json
import urllib.parse
from datetime import timedelta
from utils.time_utils import get_australian_time
from utils.logging import log_debug
import data.storage as db

def admin_routes(app):
    @app.route('/admin/', methods=['GET', 'POST'])
    def admin():
        if request.method == 'POST':
            password = request.form.get('password')
            if password == ADMIN_PASSWORD:
                session['admin_authenticated'] = True
                return redirect(url_for('admin'))
            else:
                return render_template('admin.html', authenticated=False, error="Invalid password")

        if session.get('admin_authenticated'):
            return render_template('admin.html', authenticated=True)

        return render_template('admin.html', authenticated=False)

    @app.route('/admin/logout')
    def admin_logout():
        session.pop('admin_authenticated', None)
        return redirect(url_for('admin'))

    @app.route('/admin/download/<file_type>')
    def download_data(file_type):
        if not session.get('admin_authenticated'):
            return redirect(url_for('admin'))

        # Downloads are no longer available since data is in Supabase
        flash("Data is now stored in Supabase. Use the Supabase dashboard to export data.", 'info')
        return redirect(url_for('admin'))

    @app.route('/admin/purge-old-actions')
    @app.route('/admin/purge_old_actions')
    def purge_old_actions():
        if not session.get('admin_authenticated'):
            return redirect(url_for('admin'))

        try:
            current_time = get_australian_time()
            four_days_ago = (current_time - timedelta(days=4)).strftime('%Y-%m-%d')

            db.delete_old_daily_actions_sync(four_days_ago)
            db.delete_old_songs_sync(four_days_ago)
            db.delete_old_brooding_sync(four_days_ago)

            message = f"Successfully purged old actions older than {four_days_ago}."
            flash(message, 'success')

            return redirect(url_for('admin'))
        except Exception as e:
            print(f"Error purging old actions: {e}")
            flash(f"Error purging old actions: {str(e)}", 'error')
            return redirect(url_for('admin'))

    @app.route('/admin/download_species_images')
    def download_species_images():
        if not session.get('admin_authenticated'):
            return redirect(url_for('admin'))

        try:
            os.makedirs(SPECIES_IMAGES_DIR, exist_ok=True)

            thread = Thread(target=download_species_images_thread)
            thread.daemon = True
            thread.start()

            flash("Species image download started in the background. This may take a few minutes. Check the server logs for progress.", 'success')

            return redirect(url_for('admin'))
        except Exception as e:
            log_debug(f"Error starting species images download: {e}")
            flash(f"Error starting species images download: {str(e)}", 'error')
            return redirect(url_for('admin'))

    @app.route('/admin/grant_boon', methods=['POST'])
    def grant_boon():
        if not session.get('admin_authenticated'):
            return redirect(url_for('admin'))

        try:
            user_id = request.form.get('user_id', '').strip()
            boon_type = request.form.get('boon_type')
            amount = int(request.form.get('amount', 0))
            apply_to_all = request.form.get('apply_to_all') == 'on'

            if amount <= 0:
                flash("Amount must be greater than 0", 'error')
                return redirect(url_for('admin'))

            if not apply_to_all and not user_id:
                flash("Please provide a user ID or select 'Apply to all players'", 'error')
                return redirect(url_for('admin'))

            if apply_to_all:
                all_players = db.load_all_players_sync()
                players_by_id = {p["user_id"]: p for p in all_players}
                user_ids = list(players_by_id.keys())
            else:
                player = db.load_player_sync(user_id)
                players_by_id = {user_id: player}
                user_ids = [user_id]

            for uid in user_ids:
                if boon_type == "bonus_actions":
                    db.increment_player_field_sync(uid, "bonus_actions", amount)
                elif boon_type == "seeds":
                    p = players_by_id[uid]
                    space_left = p["twigs"] - p.get("seeds", 0)
                    actual = min(amount, space_left)
                    if actual > 0:
                        db.increment_player_field_sync(uid, "seeds", actual)
                elif boon_type == "twigs":
                    db.increment_player_field_sync(uid, "twigs", amount)
                elif boon_type == "inspiration":
                    db.increment_player_field_sync(uid, "inspiration", amount)
                elif boon_type == "garden_size":
                    p = players_by_id[uid]
                    current_size = p.get("garden_size", 0)
                    new_size = min(current_size + amount, MAX_GARDEN_SIZE)
                    increase = new_size - current_size
                    if increase > 0:
                        db.increment_player_field_sync(uid, "garden_size", increase)

            boon_names = {
                "bonus_actions": "Bonus Actions",
                "seeds": "Seeds",
                "twigs": "Twigs (Nest Capacity)",
                "inspiration": "Inspiration",
                "garden_size": "Garden Size"
            }

            if apply_to_all:
                flash(f"Granted {amount} {boon_names.get(boon_type, boon_type)} to all {len(user_ids)} players!", 'success')
            else:
                flash(f"Granted {amount} {boon_names.get(boon_type, boon_type)} to user {user_id}!", 'success')

            return redirect(url_for('admin'))
        except ValueError:
            flash("Invalid amount - please enter a number", 'error')
            return redirect(url_for('admin'))
        except Exception as e:
            log_debug(f"Error granting boon: {e}")
            flash(f"Error granting boon: {str(e)}", 'error')
            return redirect(url_for('admin'))

def download_species_images_thread():
    """Background thread to download species images"""
    try:
        bird_species = []
        plant_species = []

        try:
            with open('data/bird_species.json', 'r') as f:
                bird_data = json.load(f)
                bird_species = bird_data.get('bird_species', [])
        except Exception as e:
            log_debug(f"Error loading bird species: {e}")
            return

        try:
            with open('data/plant_species.json', 'r') as f:
                plant_species = json.load(f)
        except Exception as e:
            log_debug(f"Error loading plant species: {e}")
            return

        success_count = 0
        error_count = 0
        special_count = 0

        for bird in bird_species:
            scientific_name = bird.get('scientificName')
            if not scientific_name:
                continue
            if bird.get('rarity') == 'Special':
                special_count += 1
                continue

            image_url = fetch_image_url(scientific_name)
            if image_url:
                filename = f"{urllib.parse.quote(scientific_name)}.jpg"
                filepath = os.path.join(SPECIES_IMAGES_DIR, filename)
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
                except Exception as e:
                    log_debug(f"Error downloading image for {scientific_name}: {e}")
                    error_count += 1
            else:
                error_count += 1

        for plant in plant_species:
            scientific_name = plant.get('scientificName')
            if not scientific_name:
                continue

            image_url = fetch_image_url(scientific_name)
            if image_url:
                filename = f"{urllib.parse.quote(scientific_name)}.jpg"
                filepath = os.path.join(SPECIES_IMAGES_DIR, filename)
                try:
                    response = requests.get(image_url, stream=True)
                    if response.status_code == 200:
                        with open(filepath, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                f.write(chunk)
                        success_count += 1
                    else:
                        error_count += 1
                except Exception as e:
                    log_debug(f"Error downloading image for {scientific_name}: {e}")
                    error_count += 1
            else:
                error_count += 1

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
