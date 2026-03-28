#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from telegram import Update
from telegram.ext import CallbackContext

from unobot.common.errors import DeckEmptyError, NoGameInChatError, NotEnoughPlayersError
from unobot.i18n.internationalization import _, __, user_locale
from unobot.infra.shared_vars import gm
from unobot.services.actions import continue_game
from unobot.ui.simple_commands import help_handler
from unobot.common.utils import display_name, send_async, user_is_creator_or_admin


@user_locale
def add_bot(update: Update, context: CallbackContext):
    """Handler for the /add_bot command."""
    if update.message.chat.type == 'private':
        help_handler(update, context)
        return

    chat = update.message.chat
    user = update.message.from_user

    try:
        game = gm.chatid_games[chat.id][-1]
    except (KeyError, IndexError):
        send_async(
            context.bot,
            chat.id,
            text=_("There is no running game in this chat."),
            reply_to_message_id=update.message.message_id,
        )
        return

    if not user_is_creator_or_admin(user, game, context.bot, chat):
        send_async(
            context.bot,
            chat.id,
            text=_("Only the game creator ({name}) and admin can do that.").format(
                name=game.starter.first_name
            ),
            reply_to_message_id=update.message.message_id,
        )
        return

    name = ""
    if context.args:
        for arg in context.args:
            name += (arg + ' ')

    player = None
    deck_exhausted = False

    try:
        player = gm.add_bot(chat, name)
    except DeckEmptyError:
        deck_exhausted = True

    if not player:
        send_async(
            context.bot,
            chat.id,
            text=_('There are not enough cards left in the deck for new player to join.'),
            reply_to_message_id=update.message.message_id,
        )
        return

    message = _('Added bot player {name} with {strategy} strategy.').format(name=display_name(player.user), strategy=player.user.strategy_name)
    if deck_exhausted:
        message += '\n' + _('Stopped early because there are not enough cards left in the deck.')

    send_async(
        context.bot,
        chat.id,
        text=message,
        reply_to_message_id=update.message.message_id,
    )

    if game.started:
        continue_game(context.bot, game, context.job_queue, announce_next_player=False)


@user_locale
def kill_game(update: Update, context: CallbackContext):
    """Handler for the /kill command."""
    chat = update.message.chat
    user = update.message.from_user
    games = gm.chatid_games.get(chat.id)

    if update.message.chat.type == 'private':
        help_handler(update, context)
        return

    if not games:
        send_async(context.bot, chat.id, text=_("There is no running game in this chat."))
        return

    game = games[-1]
    if user_is_creator_or_admin(user, game, context.bot, chat):
        try:
            gm.end_game(chat, user)
            send_async(context.bot, chat.id, text=__("Game ended!", multi=game.translate))
        except NoGameInChatError:
            send_async(
                context.bot,
                chat.id,
                text=_("The game is not started yet. Join the game with /join and start the game with /start"),
                reply_to_message_id=update.message.message_id,
            )
    else:
        send_async(
            context.bot,
            chat.id,
            text=_("Only the game creator ({name}) and admin can do that.").format(
                name=game.starter.first_name
            ),
            reply_to_message_id=update.message.message_id,
        )


@user_locale
def kick_player(update: Update, context: CallbackContext):
    """Handler for the /kick command."""
    if update.message.chat.type == 'private':
        help_handler(update, context)
        return

    chat = update.message.chat
    user = update.message.from_user

    try:
        game = gm.chatid_games[chat.id][-1]
    except (KeyError, IndexError):
        send_async(
            context.bot,
            chat.id,
            text=_("No game is running at the moment. Create a new game with /new"),
            reply_to_message_id=update.message.message_id,
        )
        return

    if not game.started:
        send_async(
            context.bot,
            chat.id,
            text=_("The game is not started yet. Join the game with /join and start the game with /start"),
            reply_to_message_id=update.message.message_id,
        )
        return

    if not user_is_creator_or_admin(user, game, context.bot, chat):
        send_async(
            context.bot,
            chat.id,
            text=_("Only the game creator ({name}) and admin can do that.").format(
                name=game.starter.first_name
            ),
            reply_to_message_id=update.message.message_id,
        )
        return

    if not update.message.reply_to_message:
        send_async(
            context.bot,
            chat.id,
            text=_("Please reply to the person you want to kick and type /kick again."),
            reply_to_message_id=update.message.message_id,
        )
        return

    kicked = update.message.reply_to_message.from_user
    was_current_player = kicked.id == game.current_player.user.id
    try:
        gm.leave_game(kicked, chat)
    except NoGameInChatError:
        send_async(
            context.bot,
            chat.id,
            text=_("Player {name} is not found in the current game.").format(
                name=display_name(kicked)
            ),
            reply_to_message_id=update.message.message_id,
        )
        return
    except NotEnoughPlayersError:
        gm.end_game(chat, user)
        send_async(context.bot, chat.id, text=_("{0} was kicked by {1}".format(display_name(kicked), display_name(user))))
        send_async(context.bot, chat.id, text=__("Game ended!", multi=game.translate))
        return

    send_async(context.bot, chat.id, text=_("{0} was kicked by {1}".format(display_name(kicked), display_name(user))))
    if not was_current_player or not getattr(game.current_player.user, 'is_bot', False):
        send_async(
            context.bot,
            chat.id,
            text=__("Okay. Next Player: {name}", multi=game.translate).format(
                name=display_name(game.current_player.user)
            ),
            reply_to_message_id=update.message.message_id,
        )
    if was_current_player:
        continue_game(context.bot, game, context.job_queue, announce_next_player=False)


@user_locale
def close_game(update: Update, context: CallbackContext):
    """Handler for the /close command."""
    _set_lobby_state(update, context, is_open=False)


@user_locale
def open_game(update: Update, context: CallbackContext):
    """Handler for the /open command."""
    _set_lobby_state(update, context, is_open=True)


@user_locale
def enable_translations(update: Update, context: CallbackContext):
    """Handler for the /enable_translations command."""
    _set_translation_state(update, context, enabled=True)


@user_locale
def disable_translations(update: Update, context: CallbackContext):
    """Handler for the /disable_translations command."""
    _set_translation_state(update, context, enabled=False)


def _set_lobby_state(update: Update, context: CallbackContext, is_open: bool):
    chat = update.message.chat
    user = update.message.from_user
    games = gm.chatid_games.get(chat.id)

    if not games:
        send_async(context.bot, chat.id, text=_("There is no running game in this chat."))
        return

    game = games[-1]
    if user.id in game.owner:
        game.open = is_open
        send_async(
            context.bot,
            chat.id,
            text=_("Opened the lobby. New players may /join the game.") if is_open else _("Closed the lobby. No more players can join this game."),
        )
        return

    send_async(
        context.bot,
        chat.id,
        text=_("Only the game creator ({name}) and admin can do that.").format(
            name=game.starter.first_name
        ),
        reply_to_message_id=update.message.message_id,
    )


def _set_translation_state(update: Update, context: CallbackContext, enabled: bool):
    chat = update.message.chat
    user = update.message.from_user
    games = gm.chatid_games.get(chat.id)

    if not games:
        send_async(context.bot, chat.id, text=_("There is no running game in this chat."))
        return

    game = games[-1]
    if user.id in game.owner:
        game.translate = enabled
        send_async(
            context.bot,
            chat.id,
            text=_("Enabled multi-translations. Disable with /disable_translations") if enabled else _("Disabled multi-translations. Enable them again with /enable_translations"),
        )
        return

    send_async(
        context.bot,
        chat.id,
        text=_("Only the game creator ({name}) and admin can do that.").format(
            name=game.starter.first_name
        ),
        reply_to_message_id=update.message.message_id,
    )

