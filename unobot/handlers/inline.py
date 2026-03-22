#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultsButton, Update
from telegram.ext import CallbackContext

from unobot.core import card as c
from unobot.services.actions import do_call_bluff, do_draw, do_play_card, start_player_countdown
from unobot.infra.config import WAITING_TIME
from unobot.i18n.internationalization import _, __, game_locales, user_locale
from unobot.ui.results import (
    add_call_bluff,
    add_card,
    add_choose_color,
    add_draw,
    add_gameinfo,
    add_mode_classic,
    add_mode_fast,
    add_mode_text,
    add_mode_wild,
    add_no_game,
    add_not_started,
    add_other_cards,
    add_pass,
    decode_result_id,
)
from unobot.infra.shared_vars import gm
from unobot.common.utils import display_name, game_is_running, send_async, user_is_creator


@game_locales
@user_locale
async def reply_to_query(update: Update, context: CallbackContext):
    """Build and answer the inline menu for the current player."""
    query = update.inline_query
    if query is None:
        return

    results = []
    switch = None

    try:
        user = query.from_user
        user_id = user.id
        players = gm.userid_players[user_id]
        player = gm.userid_current[user_id]
        game = player.game
    except KeyError:
        add_no_game(results)
    else:
        anti_cheat = player.anti_cheat

        if not game.started:
            if user_is_creator(user, game):
                add_mode_classic(results, anti_cheat=anti_cheat)
                add_mode_fast(results, anti_cheat=anti_cheat)
                add_mode_wild(results, anti_cheat=anti_cheat)
                add_mode_text(results, anti_cheat=anti_cheat)
            else:
                add_not_started(results)
        elif user_id == game.current_player.user.id:
            if game.choosing_color:
                add_choose_color(results, game, anti_cheat=anti_cheat)
                add_other_cards(player, results, game)
            else:
                if not player.drew:
                    add_draw(player, results, anti_cheat=anti_cheat)
                else:
                    add_pass(results, game, anti_cheat=anti_cheat)

                if game.last_card.special == c.DRAW_FOUR and game.draw_counter:
                    add_call_bluff(results, game, anti_cheat=anti_cheat)

                playable = player.playable_cards()
                added_ids = []
                for card in sorted(player.cards):
                    add_card(
                        game,
                        card,
                        results,
                        can_play=(card in playable and str(card) not in added_ids),
                        anti_cheat=anti_cheat,
                    )
                    added_ids.append(str(card))

                add_gameinfo(game, results)
        elif user_id != game.current_player.user.id or not game.started:
            for card in sorted(player.cards):
                add_card(game, card, results, can_play=False)
        else:
            add_gameinfo(game, results)

        if players and game and len(players) > 1:
            switch = _('Current game: {game}').format(game=game.chat.title)

    button = None
    if switch:
        button = InlineQueryResultsButton(switch, start_parameter='select')

    await query.answer(results, cache_time=0, is_personal=True, button=button)


@game_locales
@user_locale
async def process_result(update: Update, context: CallbackContext):
    """Handle a chosen inline result and apply the selected UNO action."""
    try:
        user = update.chosen_inline_result.from_user
        player = gm.userid_current[user.id]
        game = player.game
        raw_result_id = update.chosen_inline_result.result_id
        chat = game.chat
    except (KeyError, AttributeError):
        return

    result_id, anti_cheat = decode_result_id(raw_result_id, player.anti_cheat)
    last_anti_cheat = player.anti_cheat
    player.anti_cheat += 1

    if result_id in ('hand', 'gameinfo', 'nogame'):
        return
    if result_id.startswith('mode_'):
        mode = result_id[5:]
        game.set_mode(mode)
        send_async(context.bot, chat.id, text=__("Gamemode changed to {mode}".format(mode=mode)))
        return
    if len(result_id) == 36:
        return
    if anti_cheat != last_anti_cheat:
        send_async(
            context.bot,
            chat.id,
            text=__("Cheat attempt by {name}", multi=game.translate).format(
                name=display_name(player.user)
            ),
        )
        return
    if result_id == 'call_bluff':
        reset_waiting_time(context.bot, player)
        do_call_bluff(context.bot, player)
    elif result_id == 'draw':
        reset_waiting_time(context.bot, player)
        do_draw(context.bot, player)
    elif result_id == 'pass':
        game.turn()
    elif result_id in c.COLORS:
        game.choose_color(result_id)
    else:
        reset_waiting_time(context.bot, player)
        do_play_card(context.bot, player, result_id)

    if game_is_running(game):
        nextplayer_message = __("Next player: {name}", multi=game.translate).format(
            name=display_name(game.current_player.user)
        )
        choice = [[InlineKeyboardButton(text=_("Make your choice!"), switch_inline_query_current_chat='')]]
        send_async(
            context.bot,
            chat.id,
            text=nextplayer_message,
            reply_markup=InlineKeyboardMarkup(choice),
        )
        start_player_countdown(context.bot, game, context.job_queue)


def reset_waiting_time(bot, player):
    """Reset waiting time for a player and notify the group."""
    chat = player.game.chat
    if player.waiting_time < WAITING_TIME:
        player.waiting_time = WAITING_TIME
        send_async(
            bot,
            chat.id,
            text=__("Waiting time for {name} has been reset to {time} seconds", multi=player.game.translate).format(
                name=display_name(player.user),
                time=WAITING_TIME,
            ),
        )

