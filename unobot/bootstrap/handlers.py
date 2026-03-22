#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from telegram.ext import CallbackQueryHandler, ChosenInlineResultHandler, CommandHandler, InlineQueryHandler, MessageHandler, filters

from unobot.ui import settings
from unobot.ui import simple_commands
from unobot.handlers.game_admin import (
    add_bot,
    close_game,
    disable_translations,
    enable_translations,
    kill_game,
    kick_player,
    open_game,
)
from unobot.handlers.game_lobby import join_game, leave_game, new_game, notify_me
from unobot.handlers.game_runtime import select_game, skip_player, start_game, status_update
from unobot.handlers.inline import process_result, reply_to_query
from unobot.infra.shared_vars import dispatcher
from unobot.common.utils import error


def register_handlers():
    """Register all Telegram handlers for the bot application."""
    dispatcher.add_handler(InlineQueryHandler(reply_to_query))
    dispatcher.add_handler(ChosenInlineResultHandler(process_result))
    dispatcher.add_handler(CallbackQueryHandler(select_game))
    dispatcher.add_handler(CommandHandler('start', start_game))
    dispatcher.add_handler(CommandHandler('new', new_game))
    dispatcher.add_handler(CommandHandler(['addbot', 'add_bot'], add_bot))
    dispatcher.add_handler(CommandHandler('kill', kill_game))
    dispatcher.add_handler(CommandHandler('join', join_game))
    dispatcher.add_handler(CommandHandler('leave', leave_game))
    dispatcher.add_handler(CommandHandler('kick', kick_player))
    dispatcher.add_handler(CommandHandler('open', open_game))
    dispatcher.add_handler(CommandHandler('close', close_game))
    dispatcher.add_handler(CommandHandler('enable_translations', enable_translations))
    dispatcher.add_handler(CommandHandler('disable_translations', disable_translations))
    dispatcher.add_handler(CommandHandler('skip', skip_player))
    dispatcher.add_handler(CommandHandler('notify_me', notify_me))
    simple_commands.register()
    settings.register()
    dispatcher.add_handler(MessageHandler(filters.StatusUpdate.ALL, status_update))
    dispatcher.add_error_handler(error)

