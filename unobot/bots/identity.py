from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BotIdentity:
    id: int
    first_name: str
    username: str | None = None
    strategy_name: str = 'random'
    is_bot: bool = True


def is_bot_user(user) -> bool:
    return isinstance(user, BotIdentity)
