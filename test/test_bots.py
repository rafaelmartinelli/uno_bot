#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from telegram import Chat, User

from unobot.bots import BotIdentity, RandomStrategy
from unobot.core import card as c
from unobot.core.game import Game
from unobot.core.player import Player
from unobot.services.actions import BOT_ACTION_DELAY_SECONDS, _perform_bot_turn, continue_game, do_bot_turn, do_play_card
from unobot.services.game_manager import GameManager


class TestBotIntegration(unittest.TestCase):

    def setUp(self):
        self.chat = Chat(100, 'group')
        self.user0 = User(1, 'user0', False)
        self.user1 = User(2, 'user1', False)

    def test_add_bot_to_lobby(self):
        gm = GameManager()
        game = gm.new_game(self.chat)

        bot_player = gm.add_bot(self.chat)

        self.assertEqual(len(game.players), 1)
        self.assertLess(bot_player.user.id, 0)
        self.assertTrue(bot_player.user.is_bot)
        self.assertEqual(gm.userid_current[bot_player.user.id], bot_player)

    def test_add_bot_to_started_game_draws_first_hand(self):
        gm = GameManager()
        game = gm.new_game(self.chat)
        gm.join_game(self.user0, self.chat)
        gm.join_game(self.user1, self.chat)
        game.start()
        for player in game.players:
            player.draw_first_hand()

        deck_before = len(game.deck.cards)
        bot_player = gm.add_bot(self.chat)

        self.assertEqual(len(bot_player.cards), 7)
        self.assertEqual(deck_before - 7, len(game.deck.cards))
        self.assertIn(bot_player, game.players)


class TestRandomStrategy(unittest.TestCase):

    def test_decides_to_draw_or_pass(self):
        game = Game(Chat(101, 'group'))
        player = Player(game, BotIdentity(-1, 'Bot 1'))
        game.last_card = c.Card(c.RED, '5')
        player.cards = [c.Card(c.BLUE, '2')]

        decision = RandomStrategy().decide(player)
        self.assertEqual(decision.action, 'draw')

        player.drew = True
        decision = RandomStrategy().decide(player)
        self.assertEqual(decision.action, 'pass')

    def test_decides_color_from_hand_when_choosing(self):
        game = Game(Chat(102, 'group'))
        player = Player(game, BotIdentity(-1, 'Bot 1'))
        game.choosing_color = True
        player.cards = [c.Card(c.BLUE, '2'), c.Card(c.BLUE, '7'), c.Card(None, None, c.CHOOSE)]

        decision = RandomStrategy().decide(player)

        self.assertEqual(decision.action, 'choose_color')
        self.assertEqual(decision.color, c.BLUE)


class TestBotTurns(unittest.TestCase):

    @patch('unobot.services.actions.game_is_running', return_value=True)
    def test_continue_game_schedules_delayed_bot_turn(self, game_is_running_mock):
        chat = Chat(103, 'group')
        game = Game(chat)
        bot_player = Player(game, BotIdentity(-1, 'Bot 1'))
        Player(game, User(99, 'human', False))
        scheduled = {}

        class DummyJobQueue:
            def run_once(self, callback, delay, data):
                scheduled['callback'] = callback
                scheduled['delay'] = delay
                scheduled['data'] = data
                return object()

        continue_game(object(), game, DummyJobQueue())

        self.assertEqual(scheduled['delay'], BOT_ACTION_DELAY_SECONDS)
        self.assertIs(scheduled['data'].game, game)
        self.assertIsNotNone(game.bot_job)

    def test_bot_turn_plays_a_valid_card(self):
        chat = Chat(104, 'group')
        game = Game(chat)
        bot_player = Player(game, BotIdentity(-1, 'Bot 1'))
        next_player = Player(game, User(99, 'human', False))
        game.started = True
        game.last_card = c.Card(c.RED, '5')
        bot_player.cards = [c.Card(c.RED, '0'), c.Card(c.BLUE, '2'), c.Card(c.GREEN, '7')]
        bot = object()

        do_bot_turn(bot, bot_player)

        self.assertEqual(game.last_card, c.Card(c.RED, '0'))
        self.assertEqual(game.current_player, next_player)
        self.assertEqual(bot_player.cards, [c.Card(c.BLUE, '2'), c.Card(c.GREEN, '7')])

    @patch('unobot.services.actions.__', side_effect=lambda text, *args, **kwargs: text)
    @patch('unobot.services.actions.game_is_running', return_value=True)
    @patch('unobot.services.actions.start_player_countdown')
    def test_perform_bot_turn_orders_message_then_sticker_then_next_player(self, start_player_countdown_mock, game_is_running_mock, translate_mock):
        chat = Chat(105, 'group')
        game = Game(chat)
        bot_player = Player(game, BotIdentity(-1, 'Bot 1'))
        next_player = Player(game, User(99, 'human', False))
        game.started = True
        game.last_card = c.Card(c.RED, '5')
        bot_player.cards = [c.Card(c.RED, '0'), c.Card(c.BLUE, '2'), c.Card(c.GREEN, '7')]
        events = []

        async def send_message(chat_id, text, **kwargs):
            events.append(('message', text))

        async def send_sticker(chat_id, sticker, **kwargs):
            events.append(('sticker', sticker))

        bot = SimpleNamespace(
            send_message=send_message,
            send_sticker=send_sticker,
        )

        asyncio.run(_perform_bot_turn(bot, game, object()))

        self.assertEqual(events[0], ('message', 'Bot 1 plays:'))
        self.assertEqual(events[1], ('sticker', c.STICKERS['r_0']))
        self.assertEqual(events[2], ('message', 'Next player: human'))
        self.assertEqual(game.current_player, next_player)
        start_player_countdown_mock.assert_called_once()

    @patch(
        'unobot.services.actions.__',
        side_effect=lambda singular, plural=None, n=None, **kwargs: plural if (plural is not None and n is not None and n != 1) else singular,
    )
    @patch('unobot.services.actions.game_is_running', return_value=True)
    @patch('unobot.services.actions.start_player_countdown')
    def test_perform_bot_turn_draw_message_has_card_count(self, start_player_countdown_mock, game_is_running_mock, translate_mock):
        chat = Chat(107, 'group')
        game = Game(chat)
        bot_player = Player(game, BotIdentity(-1, 'Bot 1'))
        next_player = Player(game, User(99, 'human', False))
        game.started = True
        game.last_card = c.Card(c.RED, c.DRAW_TWO)
        game.draw_counter = 2
        bot_player.cards = [c.Card(c.BLUE, '2'), c.Card(c.GREEN, '7')]
        events = []

        async def send_message(chat_id, text, **kwargs):
            events.append(('message', text))

        async def send_sticker(chat_id, sticker, **kwargs):
            events.append(('sticker', sticker))

        bot = SimpleNamespace(
            send_message=send_message,
            send_sticker=send_sticker,
        )

        asyncio.run(_perform_bot_turn(bot, game, object()))

        self.assertEqual(events[0], ('message', 'Bot 1 draws 2 cards.'))
        self.assertEqual(events[1], ('message', 'Next player: human'))
        self.assertEqual(game.current_player, next_player)
        start_player_countdown_mock.assert_called_once()

    @patch('unobot.services.actions.gm.leave_game')
    @patch('unobot.services.actions.gm.end_game')
    @patch('unobot.services.actions.send_async')
    @patch('unobot.services.actions.__', side_effect=lambda text, *args, **kwargs: text)
    def test_first_winner_ends_game_immediately(self, translate_mock, send_async_mock, end_game_mock, leave_game_mock):
        chat = Chat(106, 'group')
        game = Game(chat)
        winner = Player(game, BotIdentity(-1, 'Bot 1'))
        Player(game, User(99, 'human', False))
        game.started = True
        game.last_card = c.Card(c.RED, '5')
        winner.cards = [c.Card(c.RED, '0')]

        do_play_card(object(), winner, 'r_0')

        end_game_mock.assert_called_once_with(chat, winner.user)
        leave_game_mock.assert_not_called()
        sent_texts = [call.kwargs.get('text') for call in send_async_mock.call_args_list]
        self.assertIn('Bot 1 won!', sent_texts)
        self.assertIn('Game ended!', sent_texts)


