# AVA PET - Game Definitions
# First games: MATH_BATTLE + LOGIC_BATTLE (ALI VS AVA)
# This module is intentionally independent from the BLE/ESP32 core.

GAME_MATH_BATTLE = "MATH_BATTLE"
GAME_LOGIC_BATTLE = "LOGIC_BATTLE"

AVAILABLE_GAMES = [
    (GAME_MATH_BATTLE, "MATH BATTLE", "ALI VS AVA"),
    (GAME_LOGIC_BATTLE, "LOGIC BATTLE", "ALI VS AVA"),
    ("MEMORY_BATTLE", "MEMORY BATTLE", "ALI VS AVA"),
    ("NUMBER_GUESS", "NUMBER GUESS", "ALI VS AVA"),
    ("TRUE_FALSE", "TRUE OR FALSE", "ALI VS AVA"),
    ("EQUATION_DUEL", "EQUATION DUEL", "ALI VS AVA"),
    ("DICE_BATTLE", "DICE BATTLE", "ALI VS AVA"),
    ("GUESS_WHO", "GUESS WHO", "ALI VS AVA"),
    ("BLUFF_BATTLE", "BLUFF BATTLE", "ALI VS AVA"),
    ("FAST_ANSWER", "FAST ANSWER", "ALI VS AVA"),
]


def game_load_command(game_id):
    """Return the BLE command used to tell AVA which game to load."""
    return f"GAME_LOAD|{game_id}"
