#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from datetime import datetime

from unobot.core import card as c
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import CallbackContext

from unobot.services.actions import continue_game, do_skip
from unobot.infra.config import MIN_PLAYERS
from unobot.common.errors import NotEnoughPlayersError
from unobot.i18n.internationalization import _, __, game_locales, user_locale
from unobot.infra.shared_vars import gm
from unobot.ui.simple_commands import help_handler
from unobot.common.utils import display_name, run_async, send_async


async def select_game(update: Update, context: CallbackContext):
    """Handler for callback queries to select the current game."""
    message = update.callback_query.message
    if message is None:
        return

    chat_id = int(update.callback_query.data)
    user_id = update.callback_query.from_user.id
    players = gm.userid_players[user_id]
    for player in players:
        if player.game.chat.id == chat_id:
            gm.userid_current[user_id] = player
            break
    else:
        send_async(context.bot, message.chat.id, text=_("Game not found."))
        return

    back = [[InlineKeyboardButton(text=_("Back to last group"), switch_inline_query='')]]
    await context.bot.answer_callback_query(
        update.callback_query.id,
        text=_("Please switch to the group you selected!"),
        show_alert=False,
    )
    await context.bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=message.message_id,
        text=_("Selected group: {group}\n"
               "<b>Make sure that you switch to the correct group!</b>").format(
            group=gm.userid_current[user_id].game.chat.title
        ),
        reply_markup=InlineKeyboardMarkup(back),
        parse_mode=ParseMode.HTML,
    )


@game_locales
def status_update(update: Update, context: CallbackContext):
    """Remove a player from the game if they leave the group."""
    chat = update.message.chat
    game = None

    if update.message.left_chat_member:
        user = update.message.left_chat_member
        player = gm.player_for_user_in_chat(user, chat)
        if player is None:
            return

        game = player.game
        was_current_player = player is game.current_player

        try:
            gm.leave_game(user, chat)
        except NotEnoughPlayersError:
            gm.end_game(chat, user)
            send_async(context.bot, chat.id, text=__("Game ended!", multi=game.translate if game else False))
        else:
            send_async(
                context.bot,
                chat.id,
                text=__("Removing {name} from the game", multi=game.translate).format(
                    name=display_name(user)
                ),
            )
            if game.started and was_current_player:
                continue_game(context.bot, game, context.job_queue)


@game_locales
@user_locale
def start_game(update: Update, context: CallbackContext):
    """Handler for the /start command."""
    if update.message.chat.type != 'private':
        chat = update.message.chat
        try:
            game = gm.chatid_games[chat.id][-1]
        except (KeyError, IndexError):
            send_async(
                context.bot,
                chat.id,
                text=_("There is no game running in this chat. Create a new one with /new"),
            )
            return

        if game.started:
            send_async(context.bot, chat.id, text=_("The game has already started"))
        elif len(game.players) < MIN_PLAYERS:
            send_async(
                context.bot,
                chat.id,
                text=__("At least {minplayers} players must /join the game before you can start it").format(
                    minplayers=MIN_PLAYERS
                ),
            )
        else:
            game.start()
            for player in game.players:
                player.draw_first_hand()

            choice = [[InlineKeyboardButton(text=_("Make your choice!"), switch_inline_query_current_chat='')]]
            first_message = __(
                "First player: {name}\n"
                "Use /close to stop people from joining the game.\n"
                "Enable multi-translations with /enable_translations",
                multi=game.translate,
            ).format(name=display_name(game.current_player.user))

            run_async(context.bot.send_sticker(chat.id, sticker=c.STICKERS[str(game.last_card)]))
            send_async(
                context.bot,
                chat.id,
                text=first_message,
                reply_markup=InlineKeyboardMarkup(choice),
            )
            continue_game(context.bot, game, context.job_queue, announce_next_player=False)
    elif len(context.args) and context.args[0] == 'select':
        players = gm.userid_players[update.message.from_user.id]
        groups = []
        for player in players:
            title = player.game.chat.title
            if player == gm.userid_current[update.message.from_user.id]:
                title = '- %s -' % player.game.chat.title
            groups.append([InlineKeyboardButton(text=title, callback_data=str(player.game.chat.id))])

        send_async(
            context.bot,
            update.message.chat_id,
            text=_('Please select the group you want to play in.'),
            reply_markup=InlineKeyboardMarkup(groups),
        )
    else:
        help_handler(update, context)


@game_locales
@user_locale
def skip_player(update: Update, context: CallbackContext):
    """Handler for the /skip command."""
    chat = update.message.chat
    user = update.message.from_user

    player = gm.player_for_user_in_chat(user, chat)
    if not player:
        send_async(context.bot, chat.id, text=_("You are not playing in a game in this chat."))
        return

    game = player.game
    skipped_player = game.current_player
    delta = (datetime.now() - skipped_player.turn_started).seconds

    if delta < skipped_player.waiting_time and player != skipped_player:
        n = skipped_player.waiting_time - delta
        send_async(
            context.bot,
            chat.id,
            text=_("Please wait {time} second", "Please wait {time} seconds", n).format(time=n),
            reply_to_message_id=update.message.message_id,
        )
    else:
        do_skip(context.bot, player, context.job_queue)

