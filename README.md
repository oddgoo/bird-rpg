# bird-rpg
 Bird RPG discord BOT

# run
activate venv: 'venv\Scripts\activate'
pip install -r requirements.txt
python bot.py

# debug
set DEBUG = True in your .env file to enable the Debug commands

# Run tests
pytest ./tests

# bot configuration

bot permissions integer: Oauth2 permissions:

*"Scopes":*
- bot
- applications.commands

*"Bot Permissions":*
- Read Messages/View Channels
- Send Messages
- Read Message History

