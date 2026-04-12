import logging
import random
from dataclasses import dataclass

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

from unobot.core import card as c
from unobot.core.game import Game
from unobot.core.player import Player
from pony.orm import db_session

from telegram.ext import CallbackContext
from apscheduler.jobstores.base import JobLookupError

from unobot.bots import get_strategy, is_bot_user
from unobot.infra.config import BOT_ACTION_DELAY, TIME_REMOVAL_AFTER_SKIP, MIN_FAST_TURN_TIME, VOLCANO_PROBABILITY
from unobot.common.errors import DeckEmptyError, NotEnoughPlayersError
from unobot.i18n.internationalization import __
from unobot.infra.shared_vars import gm
from unobot.persistence.user_setting import UserSetting
from unobot.common.utils import (
    send_async,
    display_name,
    display_color_group,
    game_is_running,
    send_message_with_retry,
    send_sticker_with_retry, run_async,
)

logger = logging.getLogger(__name__)
BOT_ACTION_DELAY_SECONDS = max(0.0, BOT_ACTION_DELAY)

@dataclass(slots=True)
class Countdown:
    player: Player
    job_queue: object


@dataclass(slots=True)
class BotTurnContext:
    game: Game
    job_queue: object


def _clear_game_job(game):
    if not game.job:
        return

    try:
        game.job.schedule_removal()
    except JobLookupError:
        pass
    finally:
        game.job = None


def _clear_bot_job(game):
    if not getattr(game, 'bot_job', None):
        return

    try:
        game.bot_job.schedule_removal()
    except JobLookupError:
        pass
    finally:
        game.bot_job = None


def _announce_next_player(bot, game):
    choice = [[InlineKeyboardButton(text=__("Make your choice!", multi=game.translate), switch_inline_query_current_chat='')]]
    send_async(bot, game.chat.id, text=__("Next player: {name}", multi=game.translate)
        .format(name=display_name(game.current_player.user)), reply_markup=InlineKeyboardMarkup(choice), parse_mode=ParseMode.HTML,
        disable_web_page_preview=True)


def _schedule_bot_turn(game, job_queue):
    if getattr(game, 'bot_job', None):
        return

    game.bot_job = job_queue.run_once(
        bot_turn_job,
        BOT_ACTION_DELAY_SECONDS,
        data=BotTurnContext(game, job_queue),
    )


def continue_game(bot, game, job_queue=None, announce_next_player=True):
    if not game_is_running(game):
        return

    _clear_game_job(game)

    if is_bot_user(game.current_player.user):
        if job_queue:
            _schedule_bot_turn(game, job_queue)
            return

        do_bot_turn(bot, game.current_player)
        if game_is_running(game):
            continue_game(bot, game, job_queue)
        return

    _clear_bot_job(game)

    if announce_next_player:
        _announce_next_player(bot, game)

    if job_queue:
        start_player_countdown(bot, game, job_queue)


def do_bot_turn(bot, player):
    game = player.game
    strategy = get_strategy(getattr(player.user, 'strategy_name', 'greedy'))
    decision = strategy.decide(player)

    if decision.action == 'choose_color':
        game.choose_color(decision.color)
        return

    if decision.action == 'play':
        do_play_card(bot, player, str(decision.card))
        return

    if decision.action == 'draw':
        do_draw(bot, player)
        return

    if decision.action == 'pass':
        game.turn()
        return

    raise ValueError(f"Unsupported bot action: {decision.action}")


async def _announce_next_player_async(bot, game):
    choice = [[InlineKeyboardButton(text=__("Make your choice!", multi=game.translate), switch_inline_query_current_chat='')]]
    await send_message_with_retry(bot, game.chat.id, text=__("Next player: {name}", multi=game.translate)
        .format(name=display_name(game.current_player.user)), reply_markup=InlineKeyboardMarkup(choice), parse_mode=ParseMode.HTML,
        disable_web_page_preview=True)


async def _perform_bot_turn(bot, game, job_queue):
    if not game_is_running(game) or not is_bot_user(game.current_player.user):
        return

    player = game.current_player
    chat = game.chat
    strategy = get_strategy(getattr(player.user, 'strategy_name', 'greedy'))
    decision = strategy.decide(player)
    name = display_name(player.user)

    if decision.action == 'play':
        await send_message_with_retry(bot, chat.id, text=__("{name} plays:", multi=game.translate).format(name=name))
        if game.mode == 'text':
            await send_message_with_retry(bot, chat.id, text=repr(decision.card))
        else:
            await send_sticker_with_retry(bot, chat.id, sticker=c.STICKERS[str(decision.card)])
        do_play_card(bot, player, str(decision.card))

    elif decision.action == 'draw':
        draw_count = game.draw_counter or 1
        await send_message_with_retry(bot, chat.id, text=__("{name} draws {number} card.","{name} draws {number} cards.",
            draw_count, multi=game.translate).format(name=name, number=draw_count))
        do_draw(bot, player)

    elif decision.action == 'pass':
        await send_message_with_retry(
            bot,
            chat.id,
            text=__("{name} passes.", multi=game.translate).format(name=name),
        )
        game.turn()

    elif decision.action == 'choose_color':
        await send_message_with_retry(bot, chat.id, text=__("{name} chooses {color}.", multi=game.translate).format(name=name,
            color=display_color_group(decision.color, game)))
        game.choose_color(decision.color)

    else:
        raise ValueError(f"Unsupported bot action: {decision.action}")

    if not game_is_running(game):
        return

    if is_bot_user(game.current_player.user):
        _schedule_bot_turn(game, job_queue)
        return

    await _announce_next_player_async(bot, game)
    if job_queue:
        start_player_countdown(bot, game, job_queue)


# TODO do_skip() could get executed in another thread (it can be a job), so it looks like it can't use game.translate?
def do_skip(bot, player, job_queue=None):
    game = player.game
    chat = game.chat
    skipped_player = game.current_player
    next_player = game.current_player.next

    if skipped_player.waiting_time > 0:
        skipped_player.anti_cheat += 1
        skipped_player.waiting_time -= TIME_REMOVAL_AFTER_SKIP
        if skipped_player.waiting_time < 0:
            skipped_player.waiting_time = 0

        try:
            skipped_player.draw()
        except DeckEmptyError:
            pass

        n = skipped_player.waiting_time
        if getattr(next_player.user, 'is_bot', False):
            send_async(bot, chat.id,text=__("Waiting time to skip this player has "
                "been reduced to {time} seconds.", multi=game.translate).format(time=n))
        else:
            send_async(bot, chat.id, text=__("Waiting time to skip this player has "
                "been reduced to {time} seconds.\nNext player: {name}", multi=game.translate)
                .format(time=n, name=display_name(next_player.user)), parse_mode=ParseMode.HTML, disable_web_page_preview=True)
        logger.info("{player} was skipped! ".format(player=display_name(player.user)))

        game.turn()
        continue_game(bot, game, job_queue, announce_next_player=False)

    else:
        try:
            gm.leave_game(skipped_player.user, chat)
            if getattr(next_player.user, 'is_bot', False):
                send_async(bot, chat.id,
                           text=__("{name1} ran out of time "
                                "and has been removed from the game!", multi=game.translate)
                           .format(name1=display_name(skipped_player.user)), parse_mode=ParseMode.HTML, disable_web_page_preview=True)
            else:
                send_async(bot, chat.id, text=__("{name1} ran out of time and has been removed from the game!\nNext player: {name2}",
                    multi=game.translate).format(name1=display_name(skipped_player.user), name2=display_name(next_player.user)), parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True)

            logger.info("{player} was skipped! ".format(player=display_name(player.user)))
            continue_game(bot, game, job_queue, announce_next_player=False)

        except NotEnoughPlayersError:
            send_async(bot, chat.id, text=__("{name} ran out of time and has been removed from the game!\nThe game ended.",
                multi=game.translate).format(name=display_name(skipped_player.user)), parse_mode=ParseMode.HTML, disable_web_page_preview=True)

            gm.end_game(chat, skipped_player.user)


@db_session
def do_play_card(bot, player, result_id):
    """Plays the selected card and sends an update to the group if needed"""
    card = c.from_str(result_id)
    player.play(card)
    game = player.game
    chat = game.chat
    user = player.user

    us = None
    if not is_bot_user(user):
        us = UserSetting.get(id=user.id)
        if not us:
            us = UserSetting(id=user.id)

    if us and us.stats:
        us.cards_played += 1

    if game.choosing_color and not is_bot_user(user):
        send_async(bot, chat.id, text=__("Please choose a color", multi=game.translate))

    if len(player.cards) == 1:
        send_async(bot, chat.id, text="UNO!")

    if len(player.cards) == 0:
        send_async(bot, chat.id, text=__("{name} won!", multi=game.translate).format(name=user.first_name), parse_mode=ParseMode.HTML,
            disable_web_page_preview=True)

        if us and us.stats:
            us.first_places += 1

        send_async(bot, chat.id, text=__("Game ended!", multi=game.translate))
        gm.end_game(chat, user)


def do_draw(bot, player: Player):
    """Does the drawing"""
    game = player.game

    if game.mode == 'volcano' and game.draw_counter == 0:
        if random.random() < VOLCANO_PROBABILITY:
            counter = random.choices([1, 2, 3, 4, 5], weights=[5, 4, 3, 2, 1])[0]
            game.draw_counter = counter
            run_async(bot.send_sticker(game.chat.id, sticker=c.STICKERS['volcano_{}'.format(counter)]))

    draw_counter_before = game.draw_counter
    try:
        player.draw()
    except DeckEmptyError:
        send_async(bot, player.game.chat.id, text=__("There are no more cards in the deck.", multi=game.translate))

    if (game.last_card.value == c.DRAW_TWO or game.last_card.special == c.DRAW_FOUR) and draw_counter_before > 0:
        game.turn()


def do_call_bluff(bot, player):
    """Handles the bluff calling"""
    game = player.game
    chat = game.chat

    if player.prev.bluffing:
        send_async(bot, chat.id, text=__("Bluff called! Giving 4 cards to {name}", multi=game.translate)
            .format(name=player.prev.user.first_name), parse_mode=ParseMode.HTML, disable_web_page_preview=True)

        try:
            player.prev.draw()
        except DeckEmptyError:
            send_async(bot, player.game.chat.id, text=__("There are no more cards in the deck.", multi=game.translate))

    else:
        game.draw_counter += 2
        send_async(bot, chat.id, text=__("{name1} didn't bluff! Giving {num} cards to {name2}", multi=game.translate)
            .format(name1=player.prev.user.first_name, num=game.draw_counter, name2=player.user.first_name), parse_mode=ParseMode.HTML, disable_web_page_preview=True)
        try:
            player.draw()
        except DeckEmptyError:
            send_async(bot, player.game.chat.id,text=__("There are no more cards in the deck.", multi=game.translate))

    game.turn()


def start_player_countdown(bot, game, job_queue):
    player = game.current_player
    time = player.waiting_time

    if time < MIN_FAST_TURN_TIME:
        time = MIN_FAST_TURN_TIME

    if game.mode == 'fast':
        if game.job:
            try:
                game.job.schedule_removal()
            except JobLookupError:
                pass

        job = job_queue.run_once(
            #lambda x,y: do_skip(bot, player),
            skip_job,
            time,
            data=Countdown(player, job_queue)
        )

        logger.info("Started countdown for player: {player}. {time} seconds."
                    .format(player=display_name(player.user), time=time))
        player.game.job = job


async def bot_turn_job(context: CallbackContext):
    bot_turn = context.job.data
    if not isinstance(bot_turn, BotTurnContext):
        return

    game = bot_turn.game
    game.bot_job = None

    if game_is_running(game):
        await _perform_bot_turn(context.bot, game, bot_turn.job_queue)


def skip_job(context: CallbackContext):
    countdown = context.job.data
    if not isinstance(countdown, Countdown):
        return

    player = countdown.player
    game = player.game
    if game_is_running(game):
        job_queue = countdown.job_queue
        do_skip(context.bot, player, job_queue)
