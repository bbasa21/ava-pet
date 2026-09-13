# AVA PET - Snake & Ladder
# Native Kivy implementation for the AVA PET app.
#
# This file is intentionally independent from BLE and from the existing
# Math Battle / Logic Battle code. It provides the graphical board,
# classic snakes/ladders rules, dice animation, and token movement.

import random

from kivy.clock import Clock
from kivy.graphics import Color, Ellipse, Line, Rectangle, RoundedRectangle
from kivy.metrics import dp
from kivy.properties import NumericProperty
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.widget import Widget


SNAKES = {
    99: 54,
    95: 75,
    92: 88,
    89: 68,
    74: 53,
    64: 36,
    62: 19,
    49: 11,
    47: 26,
    16: 6,
}

LADDERS = {
    2: 38,
    7: 14,
    8: 31,
    15: 26,
    21: 42,
    28: 84,
    36: 44,
    51: 67,
    71: 91,
    78: 98,
}


class SnakeLadderBoard(Widget):
    player_ali = NumericProperty(0)
    player_ava = NumericProperty(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self._redraw, size=self._redraw)
        Clock.schedule_once(lambda *_: self._redraw(), 0)

    def square_center(self, square):
        if square <= 0:
            return self.x + self.width * 0.05, self.y + self.height * 0.05

        square = max(1, min(100, int(square)))
        index = square - 1
        row = index // 10
        column = index % 10

        if row % 2:
            column = 9 - column

        cell_w = self.width / 10.0
        cell_h = self.height / 10.0
        return (
            self.x + (column + 0.5) * cell_w,
            self.y + (row + 0.5) * cell_h,
        )

    def _redraw(self, *_):
        self.canvas.clear()

        with self.canvas:
            Color(0.055, 0.035, 0.09, 1)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(14)])

            cell_w = self.width / 10.0
            cell_h = self.height / 10.0

            for square in range(1, 101):
                index = square - 1
                row = index // 10
                column = index % 10
                if row % 2:
                    column = 9 - column

                px = self.x + column * cell_w
                py = self.y + row * cell_h

                Color(
                    0.12 if (square + row) % 2 else 0.18,
                    0.06 if square % 2 else 0.10,
                    0.20 if (square + row) % 3 else 0.27,
                    1,
                )
                Rectangle(
                    pos=(px + dp(1), py + dp(1)),
                    size=(max(0, cell_w - dp(2)), max(0, cell_h - dp(2))),
                )

                Color(1, 1, 1, 0.32)
                Line(rectangle=(px, py, cell_w, cell_h), width=0.55)

            for start, end in LADDERS.items():
                self._draw_ladder(start, end)

            for start, end in SNAKES.items():
                self._draw_snake(start, end)

            self._draw_token(self.player_ali, 0.25, 0.75, 1.0)
            self._draw_token(self.player_ava, 0.95, 0.30, 0.75)

    def _draw_ladder(self, start, end):
        x1, y1 = self.square_center(start)
        x2, y2 = self.square_center(end)

        dx = x2 - x1
        dy = y2 - y1
        length = max(1.0, (dx * dx + dy * dy) ** 0.5)
        nx = -dy / length
        ny = dx / length
        offset = dp(5)

        Color(0.90, 0.75, 0.18, 1)
        Line(
            points=[x1 + nx * offset, y1 + ny * offset,
                    x2 + nx * offset, y2 + ny * offset],
            width=dp(2.2),
        )
        Line(
            points=[x1 - nx * offset, y1 - ny * offset,
                    x2 - nx * offset, y2 - ny * offset],
            width=dp(2.2),
        )

        steps = 7
        for i in range(1, steps):
            t = i / float(steps)
            cx = x1 + dx * t
            cy = y1 + dy * t
            Color(0.96, 0.83, 0.28, 1)
            Line(
                points=[cx + nx * offset, cy + ny * offset,
                        cx - nx * offset, cy - ny * offset],
                width=dp(1.4),
            )

    def _draw_snake(self, start, end):
        x1, y1 = self.square_center(start)
        x2, y2 = self.square_center(end)

        dx = x2 - x1
        dy = y2 - y1
        length = max(1.0, (dx * dx + dy * dy) ** 0.5)
        nx = -dy / length
        ny = dx / length

        points = []
        segments = 18
        amplitude = dp(6)
        for i in range(segments + 1):
            t = i / float(segments)
            base_x = x1 + dx * t
            base_y = y1 + dy * t
            wave = (1 if i % 2 else -1) * amplitude
            points.extend([base_x + nx * wave, base_y + ny * wave])

        Color(0.80, 0.16, 0.52, 1)
        # Kivy accepts only: none, miter, bevel, round.
        # 'curve' here caused the Android runtime crash.
        Line(points=points, width=dp(3.2), joint='round')

        Color(0.95, 0.24, 0.55, 1)
        Ellipse(pos=(x1 - dp(5), y1 - dp(5)), size=(dp(10), dp(10)))

    def _draw_token(self, square, r, g, b):
        if not square:
            return
        cx, cy = self.square_center(square)
        radius = min(self.width, self.height) / 42.0
        Color(r, g, b, 1)
        Ellipse(pos=(cx - radius, cy - radius), size=(radius * 2, radius * 2))
        Color(1, 1, 1, 0.85)
        Line(circle=(cx, cy, radius), width=dp(1.1))

    def set_positions(self, ali, ava):
        self.player_ali = int(ali)
        self.player_ava = int(ava)


class SnakeLadderGame:
    def __init__(self, board, status_label=None, dice_label=None, turn_label=None):
        self.board = board
        self.status_label = status_label
        self.dice_label = dice_label
        self.turn_label = turn_label
        self.ali = 0
        self.ava = 0
        self.turn = 'ALI'
        self.finished = False
        self.rolling = False
        self.roll_token = None
        self.on_position_change = None
        self.on_dice_result = None
        self.on_turn_change = None
        self.reset()

    def reset(self):
        self.ali = 0
        self.ava = 0
        self.turn = 'ALI'
        self.finished = False
        self.rolling = False
        self.roll_token = None
        self.board.set_positions(0, 0)
        self._update_labels()

    def _update_labels(self):
        if self.turn_label is not None:
            self.turn_label.text = f"{self.turn}'S TURN"
        if self.dice_label is not None:
            self.dice_label.text = '🎲'
        if self.status_label is not None:
            self.status_label.text = 'ROLL THE DICE'
        if self.on_turn_change:
            self.on_turn_change(self.turn)

    def roll(self):
        if self.finished or self.rolling:
            return

        self.rolling = True
        self.roll_token = object()
        token = self.roll_token
        frames = [random.randint(1, 6) for _ in range(8)]

        if self.status_label is not None:
            self.status_label.text = 'ROLLING...'

        def frame(index):
            if token is not self.roll_token:
                return
            if self.dice_label is not None:
                self.dice_label.text = str(frames[index])
            if index + 1 < len(frames):
                Clock.schedule_once(lambda *_: frame(index + 1), 0.08)
            else:
                self._finish_roll(frames[-1])

        frame(0)

    def _finish_roll(self, result):
        if self.finished:
            self.rolling = False
            return

        if self.dice_label is not None:
            self.dice_label.text = str(result)

        if self.on_dice_result:
            self.on_dice_result(self.turn, result)

        current = self.ali if self.turn == 'ALI' else self.ava
        target = current + result
        if target > 100:
            target = current
        else:
            target = self._resolve_jump(target)

        self._move_current_player(target)

    def _resolve_jump(self, square):
        if square in LADDERS:
            return LADDERS[square]
        if square in SNAKES:
            return SNAKES[square]
        return square

    def _move_current_player(self, target):
        if self.turn == 'ALI':
            self.ali = target
        else:
            self.ava = target

        self.board.set_positions(self.ali, self.ava)
        if self.on_position_change:
            self.on_position_change(self.turn, target, self.ali, self.ava)

        if target == 100:
            self.finished = True
            self.rolling = False
            if self.status_label is not None:
                self.status_label.text = f'{self.turn} WINS!'
            return

        self.turn = 'AVA' if self.turn == 'ALI' else 'ALI'
        self.rolling = False
        self._update_labels()


def build_snake_ladder_page(font_name, back_callback, roll_callback, reset_callback):
    from kivy.uix.floatlayout import FloatLayout

    page = FloatLayout(size_hint=(1, 1))

    title = Label(
        text='SNAKE & LADDER',
        font_name=font_name,
        font_size=dp(23),
        color=(1, 1, 1, 1),
        size_hint=(1, None),
        height=dp(45),
        pos_hint={'center_x': 0.5, 'top': 0.97},
    )
    page.add_widget(title)

    turn_label = Label(
        text="ALI'S TURN",
        font_name=font_name,
        font_size=dp(12),
        color=(1, 1, 1, 1),
        size_hint=(1, None),
        height=dp(30),
        pos_hint={'center_x': 0.5, 'top': 0.90},
    )
    page.add_widget(turn_label)

    board = SnakeLadderBoard(
        size_hint=(0.88, None),
        height=dp(330),
        pos_hint={'center_x': 0.5, 'top': 0.85},
    )
    page.add_widget(board)

    status = Label(
        text='ROLL THE DICE',
        font_name=font_name,
        font_size=dp(11),
        color=(1, 1, 1, 1),
        size_hint=(0.70, None),
        height=dp(35),
        pos_hint={'center_x': 0.37, 'y': 0.08},
    )
    page.add_widget(status)

    dice = Label(
        text='🎲',
        font_name=font_name,
        font_size=dp(25),
        color=(1, 1, 1, 1),
        size_hint=(0.18, None),
        height=dp(45),
        pos_hint={'center_x': 0.78, 'y': 0.075},
    )
    page.add_widget(dice)

    roll_button = Button(
        text='ROLL',
        font_name=font_name,
        font_size=dp(13),
        size_hint=(None, None),
        size=(dp(110), dp(42)),
        pos_hint={'center_x': 0.30, 'y': 0.015},
        background_normal='',
        background_down='',
        background_color=(0.45, 0.12, 0.75, 0.9),
        color=(1, 1, 1, 1),
    )
    roll_button.bind(on_release=lambda *_: roll_callback())
    page.add_widget(roll_button)

    reset_button = Button(
        text='RESET',
        font_name=font_name,
        font_size=dp(11),
        size_hint=(None, None),
        size=(dp(95), dp(38)),
        pos_hint={'center_x': 0.52, 'y': 0.018},
        background_normal='',
        background_down='',
        background_color=(0.25, 0.08, 0.42, 0.9),
        color=(1, 1, 1, 1),
    )
    reset_button.bind(on_release=lambda *_: reset_callback())
    page.add_widget(reset_button)

    back_button = Button(
        text='BACK',
        font_name=font_name,
        font_size=dp(11),
        size_hint=(None, None),
        size=(dp(80), dp(38)),
        pos_hint={'center_x': 0.75, 'y': 0.018},
        background_normal='',
        background_down='',
        background_color=(0.15, 0.15, 0.18, 0.9),
        color=(1, 1, 1, 1),
    )
    back_button.bind(on_release=lambda *_: back_callback())
    page.add_widget(back_button)

    return page, board, status, dice, turn_label, roll_button
