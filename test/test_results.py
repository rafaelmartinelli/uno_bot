import unittest
from types import SimpleNamespace

from telegram import InlineQueryResultArticle, InlineQueryResultCachedSticker

from unobot.core import card as c
from unobot.ui.results import add_card, add_draw, add_gameinfo, add_mode_classic, decode_result_id, encode_result_id


class TestResults(unittest.TestCase):
    def _build_game(self, mode='classic'):
        user = SimpleNamespace(first_name='Alice', username='alice')
        player = SimpleNamespace(user=user, cards=[])
        game = SimpleNamespace(
            translate=False,
            draw_counter=0,
            mode=mode,
            current_player=player,
            players=[player],
            last_card=c.Card(c.RED, '5'),
        )
        player.game = game
        return game, player

    def test_encode_decode_result_id(self):
        encoded = encode_result_id('r_5', 7)
        self.assertEqual(encoded, 'r_5:7')
        self.assertEqual(decode_result_id(encoded, 0), ('r_5', 7))
        self.assertEqual(decode_result_id('gameinfo', 3), ('gameinfo', 3))

    def test_classic_cards_use_stickers(self):
        game, _ = self._build_game(mode='classic')
        results = []

        add_card(game, c.Card(c.RED, '5'), results, can_play=True, anti_cheat=4)
        add_gameinfo(game, results)

        self.assertIsInstance(results[0], InlineQueryResultCachedSticker)
        self.assertEqual(results[0].id, 'r_5:4')
        self.assertIsInstance(results[1], InlineQueryResultCachedSticker)

    def test_text_mode_cards_use_articles(self):
        game, player = self._build_game(mode='text')
        results = []

        add_card(game, c.Card(c.RED, '5'), results, can_play=True, anti_cheat=2)
        add_draw(player, results, anti_cheat=2)
        add_mode_classic(results, anti_cheat=2)

        self.assertIsInstance(results[0], InlineQueryResultArticle)
        self.assertEqual(results[0].id, 'r_5:2')
        self.assertIsInstance(results[1], InlineQueryResultCachedSticker)
        self.assertEqual(results[2].id, 'mode_classic:2')


if __name__ == '__main__':
    unittest.main()

