# UNO Bot

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](./LICENSE)

Telegram Bot that allows you to play the popular card game UNO via inline queries. The bot currently runs as [@unobot](http://telegram.me/unobot).

To run the bot yourself, you will need: 
- Python 3.11+
- The [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) module (v22.x)
- [Pony ORM](https://ponyorm.com/)
- [APScheduler](https://apscheduler.readthedocs.io/)

## Setup
- Get a bot token from [@BotFather](http://telegram.me/BotFather) and change configurations in `config.json`.
- Convert all language files from `.po` files to `.mo` by executing the bash script `compile.sh` located in the `locales` folder.
  Another option is: `find . -maxdepth 2 -type d -name 'LC_MESSAGES' -exec bash -c 'msgfmt {}/unobot.po -o {}/unobot.mo' \;`.
- Refresh the translation template with `locales/genpot.sh`.
- Use `/setinline` and `/setinlinefeedback` with BotFather for your bot.
- Use `/setcommands` and submit the list of commands in commandlist.txt
- Install requirements (using a `virtualenv` is recommended): `pip install -r requirements.txt`
- Run tests with `python -m pytest -q`
- The Python source code now lives under the `unobot/` package (`core`, `ui`, `handlers`, `services`, `infra`, `common`, `persistence`, `i18n`).
- By default, the SQLite database path is the project-root `uno.sqlite3` (override with `UNO_DB`).

You can change some gameplay parameters like turn times, minimum amount of players and default gamemode in `config.json`.
Current gamemodes available: classic, fast and wild. Check the details with the `/modes` command.

You can also add synthetic players with `/addbot` (optionally `/addbot 3` to add several). The first built-in bot uses a random strategy: it plays a random valid card, chooses a valid color at random, or draws/passes when needed.

Then run the bot with `python -m unobot`.

Code documentation is minimal but there.
