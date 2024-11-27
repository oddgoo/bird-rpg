from flask import Flask, render_template
from threading import Thread
from config.config import PORT
from web.home import get_home_page
from data.storage import load_data
from data.models import get_personal_nest, get_total_chicks, get_total_bird_species

app = Flask('')

@app.route('/')
def home():
    return get_home_page()

@app.route('/user/<user_id>')
def user_page(user_id):
    data = load_data()
    nest = get_personal_nest(data, user_id)
    
    # Count songs given
    songs_given = 0
    for date_songs in data.get("daily_songs", {}).values():
        for target_songs in date_songs.values():
            if str(user_id) in target_songs:
                songs_given += 1
    
    # Add songs_given to nest data
    nest_data = {
        "name": nest.get("name", "Some Bird's Nest"),
        "twigs": nest["twigs"],
        "seeds": nest["seeds"],
        "chicks": nest.get("chicks", []),
        "songs_given": songs_given
    }
    
    return render_template('user.html', nest=nest_data)

def run_server():
    app.run(host='0.0.0.0', port=PORT)

def start_server():
    server_thread = Thread(target=run_server)
    server_thread.start()
    return server_thread