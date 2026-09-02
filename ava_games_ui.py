# AVA PET - Games UI helpers
# Keeps game-page construction independent from main.py logic.

from kivy.metrics import dp
from kivy.uix.button import Button
from kivy.uix.label import Label


def build_game_button(game_id, title, subtitle, font_name, callback):
    button = Button(
        text=f"{title}\n{subtitle}",
        font_name=font_name,
        font_size=dp(15),
        size_hint=(None, None),
        size=(dp(250), dp(62)),
        background_normal="",
        background_down="",
        background_color=(0.45, 0.12, 0.75, 0.9),
        color=(1, 1, 1, 1),
    )
    button.bind(on_press=lambda *_: callback(game_id))
    return button
