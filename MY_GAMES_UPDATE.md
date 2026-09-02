# MY GAMES update

The AVA PET game-definition layer is ready. `ava_games.py` defines the available ALI VS AVA games and `GAME_LOAD|MATH_BATTLE` as the first game-load command.

Main UI integration is intentionally kept as a separate step so the existing BLE, clock, weather, and connection flow is not overwritten by a partial `main.py` replacement.
