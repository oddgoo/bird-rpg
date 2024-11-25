from flask import Flask
from threading import Thread
from config.config import PORT
from web.home import get_home_page

app = Flask('')

@app.route('/')
def home():
    return get_home_page()

def run_server():
    app.run(host='0.0.0.0', port=PORT)

def start_server():
    server_thread = Thread(target=run_server)
    server_thread.start()
    return server_thread