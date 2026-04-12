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


import asyncio
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from html import escape

from telegram import Update
from telegram.error import BadRequest, Forbidden, RetryAfter, TelegramError
from telegram.ext import CallbackContext

from unobot.infra.config import TOKEN
from unobot.i18n.internationalization import _, __
from unobot.common.mwt import MWT
from unobot.infra.shared_vars import gm

logger = logging.getLogger(__name__)

TIMEOUT = 2.5


def list_subtract(list1, list2):
    """ Helper function to subtract two lists and return the sorted result """
    list1 = list1.copy()

    for x in list2:
        list1.remove(x)

    return list(sorted(list1))


def display_name(user) -> str:
    """Return first name; if username exists, return first name linked to profile."""
    first = escape(user.first_name or '')
    if user.username:
        username = escape(user.username)
        return f'<a href="https://t.me/{username}">{first}</a>'
    return first


def display_color(color):
    """ Convert a color code to actual color name """
    if color == "r":
        return _("{emoji} Red").format(emoji='❤️')
    if color == "b":
        return _("{emoji} Blue").format(emoji='💙')
    if color == "g":
        return _("{emoji} Green").format(emoji='💚')
    if color == "y":
        return _("{emoji} Yellow").format(emoji='💛')
    return None


def display_color_group(color, game):
    """ Convert a color code to actual color name """
    if color == "r":
        return __("{emoji} Red", game.translate).format(
            emoji='❤️')
    if color == "b":
        return __("{emoji} Blue", game.translate).format(
            emoji='💙')
    if color == "g":
        return __("{emoji} Green", game.translate).format(
            emoji='💚')
    if color == "y":
        return __("{emoji} Yellow", game.translate).format(
            emoji='💛')
    return None


def log_error(err: Exception):
    """Log an exception if present."""
    if err is not None:
        if err.__traceback__ is not None:
            logger.error(
                "%s",
                err,
                exc_info=(type(err), err, err.__traceback__),
            )
        else:
            logger.error("%s", err)


async def error(update: Update = None, context: CallbackContext = None):
    """Application error handler compatible with PTB 22."""
    log_error(context.error if context is not None else None)


def run_async(coro):
    """Schedule a coroutine from sync handler code."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(coro)
        return

    loop.create_task(coro)


async def _safe_telegram_call(coro_factory, max_retry_after_retries=1):
    attempts = 0

    while True:
        try:
            return await coro_factory()
        except RetryAfter as exc:
            retry_after = max(1, int(getattr(exc, 'retry_after', 1)))
            if attempts >= max_retry_after_retries:
                logger.error("Flood control exceeded. Retry in %s seconds", retry_after)
                return None

            attempts += 1
            logger.warning(
                "Flood control exceeded. Retrying in %s seconds (%s/%s)",
                retry_after,
                attempts,
                max_retry_after_retries,
            )
            await asyncio.sleep(retry_after)
        except (Forbidden, BadRequest) as exc:
            logger.warning("Telegram request was rejected: %s", exc)
            return None
        except TelegramError as exc:
            logger.error("Telegram error: %s", exc)
            return None


async def send_message_with_retry(bot, *args, **kwargs):
    """Send a message and retry once when Telegram asks for flood-control backoff."""
    kwargs.pop('timeout', None)
    return await _safe_telegram_call(lambda: bot.send_message(*args, **kwargs))


async def send_sticker_with_retry(bot, *args, **kwargs):
    """Send a sticker and retry once when Telegram asks for flood-control backoff."""
    kwargs.pop('timeout', None)
    return await _safe_telegram_call(lambda: bot.send_sticker(*args, **kwargs))


def send_async(bot, *args, **kwargs):
    """Send a message asynchronously"""
    kwargs.pop('timeout', None)

    try:
        run_async(_safe_telegram_call(lambda: bot.send_message(*args, **kwargs)))
    except Exception as e:
        log_error(e)

def answer_async(bot, *args, **kwargs):
    """Answer an inline query asynchronously"""
    kwargs.pop('timeout', None)

    try:
        run_async(_safe_telegram_call(lambda: bot.answer_inline_query(*args, **kwargs)))
    except Exception as e:
        log_error(e)


def game_is_running(game):
    return game in gm.chatid_games.get(game.chat.id, list())


def user_is_creator(user, game):
    return user.id in game.owner


def user_is_admin(user, bot, chat):
    return user.id in get_admin_ids(bot, chat.id)


def user_is_creator_or_admin(user, game, bot, chat):
    return user_is_creator(user, game) or user_is_admin(user, bot, chat)


@MWT(timeout=60*60)
def get_admin_ids(bot, chat_id):
    """Returns a list of admin IDs for a given chat. Results are cached for 1 hour."""
    url = (
        f"https://api.telegram.org/bot{TOKEN}/getChatAdministrators?"
        + urllib.parse.urlencode({'chat_id': chat_id})
    )

    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except (urllib.error.URLError, json.JSONDecodeError):
        logger.warning("Could not refresh admin list for chat_id=%s", chat_id)
        return []

    if not payload.get('ok'):
        return []

    return [admin['user']['id'] for admin in payload.get('result', [])]
