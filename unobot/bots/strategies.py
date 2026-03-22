from dataclasses import dataclass
from random import choice
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


_STRATEGIES = {
    RandomStrategy.name: RandomStrategy(),
}


def get_strategy(name: str = 'random'):
    try:
        return _STRATEGIES[name]
    except KeyError as exc:
        raise ValueError(f'Unknown bot strategy: {name}') from exc

