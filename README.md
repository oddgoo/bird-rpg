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

## TODO and Ideas
- study grows garden:
- Brood all (number) - random command
- aliases / clear confusion between add and build
- log book

```
    A: !host_study
    bird-rpg-bot: A has started a study session! Join in the next 10 minutes to be part of the group
    B: !join_study @A
    bird-rpg-bot: B has joined the study group!

    ...70 minutes pass..

    bird-rpg-bot: the study session has ended! Mahli-Ann and Cuauh have grown their gardens (and/or common garden) by x
```

- uncommon birds to get small bonuses
- Foraging for treasure
- "hehe okay, maybe you can encourage the cockatoos/parrots to come, and there is some benefit."
- Swooping: " special stones that can only be taken from defeated children"
- server-led notifications

parrot to give +2 extra inspiration, not just 1
