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


"""Defines helper functions to build the inline result list"""

from uuid import uuid4

from telegram import InlineQueryResultArticle, InlineQueryResultCachedSticker, InputTextMessageContent

from unobot.core import card as c
from unobot.common.utils import display_color, display_color_group, display_name
from unobot.i18n.internationalization import _, __


def encode_result_id(result_id, anti_cheat=None):
    """Create a stable inline result id without mutating PTB objects later."""
    if anti_cheat is None:
        return result_id
    return f"{result_id}:{anti_cheat}"


def decode_result_id(result_id, fallback_anti_cheat):
    """Decode an inline result id and return (base_id, anti_cheat)."""
    if ':' not in result_id:
        return result_id, fallback_anti_cheat

    base_id, anti_cheat = result_id.split(':', 1)
    return base_id, int(anti_cheat)


def _card_text(card):
    return repr(card).replace('Draw Four', '+4').replace('Draw', '+2') \
        .replace('Colorchooser', 'Color Chooser')


def add_choose_color(results, game, anti_cheat=None):
    """Add choose color options"""
    for color in c.COLORS:
        results.append(
            InlineQueryResultArticle(
                id=encode_result_id(color, anti_cheat),
                title=_("Choose Color"),
                description=display_color(color),
                input_message_content=
                InputTextMessageContent(display_color_group(color, game))
            )
        )


def add_other_cards(player, results, game):
    """Add hand cards when choosing colors"""

    results.append(
        InlineQueryResultArticle(
            "hand",
            title=_("Card (tap for game state):",
                    "Cards (tap for game state):",
                    len(player.cards)),
            description=', '.join([repr(card) for card in player.cards]),
            input_message_content=game_info(game)
        )
    )


def player_list(game):
    """Generate list of player strings"""
    return [_("{name} ({number} card)",
              "{name} ({number} cards)",
              len(player.cards))
            .format(name=player.user.first_name, number=len(player.cards))
            for player in game.players]


def add_no_game(results):
    """Add text result if user is not playing"""
    results.append(
        InlineQueryResultArticle(
            "nogame",
            title=_("You are not playing"),
            input_message_content=
            InputTextMessageContent(_('Not playing right now. Use /new to '
                                      'start a game or /join to join the '
                                      'current game in this group'))
        )
    )


def add_not_started(results):
    """Add text result if the game has not yet started"""
    results.append(
        InlineQueryResultArticle(
            "nogame",
            title=_("The game wasn't started yet"),
            input_message_content=
            InputTextMessageContent(_('Start the game with /start'))
        )
    )


def add_mode_classic(results, anti_cheat=None):
    """Change mode to classic"""
    results.append(
        InlineQueryResultArticle(
            encode_result_id("mode_classic", anti_cheat),
            title=_("🎻 Classic mode"),
            input_message_content=
            InputTextMessageContent(_('Classic 🎻'))
        )
    )


def add_mode_fast(results, anti_cheat=None):
    """Change mode to fast"""
    results.append(
        InlineQueryResultArticle(
            encode_result_id("mode_fast", anti_cheat),
            title=_("🚀 Sonic mode"),
            input_message_content=
            InputTextMessageContent(_('Gotta go fast! 🚀'))
        )
    )


def add_mode_wild(results, anti_cheat=None):
    """Change mode to wild"""
    results.append(
        InlineQueryResultArticle(
            encode_result_id("mode_wild", anti_cheat),
            title=_("🐉 Wild mode"),
            input_message_content=
            InputTextMessageContent(_('Into the Wild~ 🐉'))
        )
    )


def add_mode_text(results, anti_cheat=None):
    """Change mode to text"""
    results.append(
        InlineQueryResultArticle(
            encode_result_id("mode_text", anti_cheat),
            title=_("✍️ Text mode"),
            input_message_content=
            InputTextMessageContent(_('Text ✍️'))
        )
    )
    
    
def add_draw(player, results, anti_cheat=None):
    """Add option to draw"""
    n = player.game.draw_counter or 1

    result_id = encode_result_id("draw", anti_cheat)
    message = __("Drawing {number} card",
                 'Drawing {number} cards', n,
                 multi=player.game.translate).format(number=n)

    results.append(
        InlineQueryResultCachedSticker(
            id=result_id,
            sticker_file_id=c.STICKERS['option_draw'],
            input_message_content=InputTextMessageContent(message),
        )
    )


def add_gameinfo(game, results):
    """Add option to show game info"""

    results.append(
        InlineQueryResultCachedSticker(
            id="gameinfo",
            sticker_file_id=c.STICKERS['option_info'],
            input_message_content=game_info(game)
        )
    )


def add_pass(results, game, anti_cheat=None):
    """Add option to pass"""
    results.append(
        InlineQueryResultCachedSticker(
            id=encode_result_id("pass", anti_cheat),
            sticker_file_id=c.STICKERS['option_pass'],
            input_message_content=InputTextMessageContent(
                __('Pass', multi=game.translate)
            )
        )
    )


def add_call_bluff(results, game, anti_cheat=None):
    """Add option to call a bluff"""
    results.append(
        InlineQueryResultCachedSticker(
            id=encode_result_id("call_bluff", anti_cheat),
            sticker_file_id=c.STICKERS['option_bluff'],
            input_message_content=InputTextMessageContent(
                __("I'm calling your bluff!",
                   multi=game.translate)
            )
        )
    )


def add_card(game, card, results, can_play, anti_cheat=None):
    """Add an option that represents a card"""

    display = _card_text(card)

    if can_play:
        if game.mode == 'text':
            results.append(
                InlineQueryResultArticle(
                    id=encode_result_id(str(card), anti_cheat),
                    title=display,
                    description=_("Tap to play this card"),
                    input_message_content=InputTextMessageContent(
                        "Card Played: {card}".format(card=display)
                    )
                )
            )
        else:
            results.append(
                InlineQueryResultCachedSticker(
                    id=encode_result_id(str(card), anti_cheat),
                    sticker_file_id=c.STICKERS[str(card)],
                )
            )
    else:
        if game.mode == 'text':
            results.append(
                InlineQueryResultArticle(
                    id=str(uuid4()),
                    title=display,
                    description=_("You can't play this card right now"),
                    input_message_content=game_info(game)
                )
            )
        else:
            results.append(
                InlineQueryResultCachedSticker(
                    id=str(uuid4()),
                    sticker_file_id=c.STICKERS_GREY[str(card)],
                    input_message_content=game_info(game),
                )
            )


def game_info(game):
    players = player_list(game)
    return InputTextMessageContent(
        _("Current player: {name}")
        .format(name=display_name(game.current_player.user)) +
        "\n" +
        _("Last card: {card}").format(card=repr(game.last_card)) +
        "\n" +
        _("Player: {player_list}",
          "Players: {player_list}",
          len(players))
        .format(player_list=" -> ".join(players))
    )
