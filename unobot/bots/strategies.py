from dataclasses import dataclass
from random import choice
from collections import Counter
from typing import Literal

from unobot.core import card as c


@dataclass(frozen=True, slots=True)
class BotTurnDecision:
    action: Literal['play', 'draw', 'pass', 'choose_color']
    card: object | None = None
    color: str | None = None


class RandomStrategy:
    name = 'random'

    def decide(self, player) -> BotTurnDecision:
        game = player.game
        if game.choosing_color:
            return BotTurnDecision('choose_color', color=self._pick_color(player))

        playable = player.playable_cards()
        if playable:
            return BotTurnDecision('play', card=choice(playable))

        if player.drew:
            return BotTurnDecision('pass')

        return BotTurnDecision('draw')

    def _pick_color(self, player) -> str:
        hand_colors = [card.color for card in player.cards if card.color in c.COLORS]
        return choice(hand_colors or list(c.COLORS))


class GreedyStrategy:
    name = 'greedy'

    def decide(self, player) -> BotTurnDecision:
        game = player.game
        if game.choosing_color:
            return BotTurnDecision('choose_color', color=self._pick_color(player))

        playable = player.playable_cards()
        if playable:
            return BotTurnDecision('play', card=self._pick_card(player, playable))

        if player.drew:
            return BotTurnDecision('pass')

        return BotTurnDecision('draw')

    def _pick_color(self, player) -> str:
        color_counts = self._color_counts(player.cards)
        if not color_counts:
            return choice(c.COLORS)

        best = max(color_counts.values())
        best_colors = [color for color in c.COLORS if color_counts.get(color, 0) == best]
        return choice(best_colors)

    def _pick_card(self, player, playable):
        game = player.game
        same_color_playable = [card for card in playable if card.color == game.last_card.color]
        candidates = same_color_playable or playable
        color_counts = self._color_counts(player.cards)
        value_counts = Counter(card.value for card in player.cards if card.value is not None)
        next_player_low = len(player.next.cards) <= 2

        scored = []
        for card in candidates:
            stay_same_color = 1 if card.color and card.color == game.last_card.color else 0
            color_exhaustion = color_counts.get(card.color, 0)
            has_duplicate_value = 1 if value_counts.get(card.value, 0) > 1 else 0
            disruption = self._disruption_score(card, next_player_low, len(same_color_playable))
            scored.append(((stay_same_color, color_exhaustion, has_duplicate_value, disruption), card))

        best_score = max(score for score, _ in scored)
        best_cards = [card for score, card in scored if score == best_score]
        return choice(best_cards)

    def _color_counts(self, cards):
        return Counter(card.color for card in cards if card.color in c.COLORS)

    def _disruption_score(self, card, next_player_low: bool, same_color_playable_count: int) -> int:
        if not next_player_low:
            return 0

        if card.value == c.DRAW_TWO:
            return 3
        if card.value == c.SKIP:
            return 2
        if card.value == c.REVERSE:
            return 1
        # +4 is only a bluff risk when a same-color option exists.
        if card.special == c.DRAW_FOUR:
            return 4 if same_color_playable_count <= 1 else 0
        return 0


_STRATEGIES = {
    GreedyStrategy.name: GreedyStrategy(),
    RandomStrategy.name: RandomStrategy(),
}


def get_strategy(name: str = 'random'):
    try:
        return _STRATEGIES[name]
    except KeyError as exc:
        raise ValueError(f'Unknown bot strategy: {name}') from exc

