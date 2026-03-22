"""
Promote other UNO bots
"""
import random
import sys


# Promotion messages and their weights
PROMOTIONS = {
    """
For a more modern UNO experience, <a href="https://t.me/uno9bot/uno">try out</a> the new <a href="https://t.me/uno9bot?start=ref-unobot">@uno9bot</a>.
""": 2.0,
    """
Also check out @UnoDemoBot, a newer version of this bot with exclusive modes and features!
""": 1.0,
}

def get_promotion():
    """ Get a random promotion message """
    return random.choices(list(PROMOTIONS.keys()), weights=list(PROMOTIONS.values()))[0]

def send_promotion(bot, chat_id, chance=1.0):
    """ (Maybe) send a promotion message """
    if random.random() <= chance:
        from unobot.common.utils import send_async
        send_async(bot, chat_id, text=get_promotion(), parse_mode='HTML')


def send_promotion_async(chat, chance=1.0):
    """ Send a promotion message asynchronously """
    shared_vars = sys.modules.get('shared_vars')
    if shared_vars is None:
        return

    application = getattr(shared_vars, 'application', None)
    if application is None:
        return

    send_promotion(application.bot, chat.id, chance=chance)
