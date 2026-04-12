#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from telegram import Update, Message, User, Chat
from telegram.ext import CallbackContext

from unobot.infra.config import DEFAULT_GAME_MODE
from unobot.common.errors import AlreadyJoinedError, DeckEmptyError, LobbyClosedError, NoGameInChatError, NotEnoughPlayersError
from unobot.i18n.internationalization import _, __, user_locale
from unobot.infra.shared_vars import gm
from unobot.services.actions import continue_game
from unobot.ui.simple_commands import help_handler
from unobot.common.utils import display_name, send_async


@user_locale
def notify_me(update: Update, context: CallbackContext):
    """Handler for /notify_me command, pm people for next game."""
    chat_id = update.message.chat_id
    if update.message.chat.type == 'private':
        send_async(
            context.bot,
            chat_id,
            text=_("Send this command in a group to be notified when a new game is started there."),
        )
    else:
        gm.remind_dict.setdefault(chat_id, set()).add(update.message.from_user.id)


@user_locale
def new_game(update: Update, context: CallbackContext):
    """Handler for the /new command."""

    message: Message = update.message
    chat: Chat = message.chat

    if chat.type == 'private':
        help_handler(update, context)
        return

    if message.chat_id in gm.remind_dict:
        for user in gm.remind_dict[message.chat_id]:
            send_async(
                context.bot,
                user,
                text=_("A new game has been started in {title}").format(
                    title=chat.title
                ),
            )
        del gm.remind_dict[message.chat_id]

    game = gm.new_game(chat)
    game.starter = message.from_user
    game.owner.append(message.from_user.id)
    game.mode = DEFAULT_GAME_MODE
    send_async(
        context.bot,
        message.chat_id,
        text=_("Created a new game! Join the game with /join and start the game with /start"),
    )


@user_locale
def join_game(update: Update, context: CallbackContext):
    """Handler for the /join command."""
    chat = update.message.chat

    if update.message.chat.type == 'private':
        help_handler(update, context)
        return

    try:
        gm.join_game(update.message.from_user, chat)
    except LobbyClosedError:
        send_async(context.bot, chat.id, text=_("The lobby is closed"))
    except NoGameInChatError:
        send_async(
            context.bot,
            chat.id,
            text=_("No game is running at the moment. Create a new game with /new"),
            reply_to_message_id=update.message.message_id,
        )
    except AlreadyJoinedError:
        send_async(
            context.bot,
            chat.id,
            text=_("You already joined the game. Start the game with /start"),
            reply_to_message_id=update.message.message_id,
        )
    except DeckEmptyError:
        send_async(
            context.bot,
            chat.id,
            text=_("There are not enough cards left in the deck for new players to join."),
            reply_to_message_id=update.message.message_id,
        )
    else:
        send_async(
            context.bot,
            chat.id,
            text=_("Joined the game"),
            reply_to_message_id=update.message.message_id,
        )


@user_locale
def leave_game(update: Update, context: CallbackContext):
    """Handler for the /leave command."""
    chat = update.message.chat
    user = update.message.from_user

    player = gm.player_for_user_in_chat(user, chat)
    if player is None:
        send_async(
            context.bot,
            chat.id,
            text=_("You are not playing in a game in this group."),
            reply_to_message_id=update.message.message_id,
        )
        return

    game = player.game
    was_current_player = player is game.current_player

    try:
        gm.leave_game(user, chat)
    except NoGameInChatError:
        send_async(
            context.bot,
            chat.id,
            text=_("You are not playing in a game in this group."),
            reply_to_message_id=update.message.message_id,
        )
    except NotEnoughPlayersError:
        gm.end_game(chat, user)
        send_async(context.bot, chat.id, text=__("Game ended!", multi=game.translate))
    else:
        if game.started:
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
        else:
            send_async(
                context.bot,
                chat.id,
                text=__("{name} left the game before it started.", multi=game.translate).format(
                    name=display_name(user)
                ),
                reply_to_message_id=update.message.message_id,
            )

