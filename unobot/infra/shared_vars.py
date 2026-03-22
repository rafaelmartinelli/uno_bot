#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Telegram bot to play UNO in group chats
# Copyright (c) 2016 Jannes Höke <uno@jhoeke.de>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.


from pathlib import Path

from unobot.infra.config import TOKEN
import os
from telegram.ext import Application

from unobot.services.game_manager import GameManager
from unobot.infra.database import db

project_root_db = Path(__file__).resolve().parents[2] / 'uno.sqlite3'
db.bind('sqlite', os.getenv('UNO_DB', str(project_root_db)), create_db=True)
db.generate_mapping(create_tables=True)

gm = GameManager()
application = Application.builder().token(TOKEN).build()

# Backward-compatible aliases used by existing modules.
updater = application
dispatcher = application
