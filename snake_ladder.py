"""Legacy compatibility module.

Snake & Ladder is no longer an available AVA PET game.
The game was removed from ava_games.py; this module remains temporarily
only because older main.py versions still import it.

Do not add game logic here. Remove this compatibility module after the
legacy import and unreachable handler are removed from main.py.
"""


class SnakeLadderGame:
    """Compatibility placeholder for the removed game."""

    def __init__(self, *args, **kwargs):
        raise RuntimeError(
            "Snake & Ladder has been removed from AVA PET."
        )


def build_snake_ladder_page(*args, **kwargs):
    """Compatibility placeholder for the removed game UI."""
    raise RuntimeError(
        "Snake & Ladder has been removed from AVA PET."
    )
