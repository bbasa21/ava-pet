# AVA PET - Snake & Ladder
# Native Kivy implementation for the AVA PET app.
#
# Graphical board + classic two-player rules. BLE/OLED integration is
# intentionally kept outside this module so the existing Math/Logic games
# remain untouched.

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


class DiceWidget(Widget):
    value = NumericProperty(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self._draw, size=self._draw, value=self._draw)
        Clock.schedule_once(lambda *_: self._draw(), 0)

    def _draw(self, *_):
        self.canvas.clear()
        with self.canvas:
            Color(0.12, 0.07, 0.20, 1)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(12)])
            Color(1, 1, 1, 1)
            pad = min(self.width, self.height) * 0.14
            RoundedRectangle(
                pos=(self.x + pad, self.y + pad),
                size=(self.width - 2 * pad, self.height - 2 * pad),
                radius=[dp(7)],
            )
            if self.value in range(1, 7):
                self._dots(int(self.value))

    def _dots(self, value):
        left = self.x + self.width * 0.30
        right = self.x + self.width * 0.70
        mid_x = self.x + self.width * 0.50
        bottom = self.y + self.height * 0.30
        top = self.y + self.height * 0.70
        mid_y = self.y + self.height * 0.50
        radius = min(self.width, self.height) * 0.055

        patterns = {
            1: [(mid_x, mid_y)],
            2: [(left, top), (right, bottom)],
            3: [(left, top), (mid_x, mid_y), (right, bottom)],
            4: [(left, top), (right, top), (left, bottom), (right, bottom)],
            5: [(left, top), (right, top), (mid_x, mid_y), (left, bottom), (right, bottom)],
            6: [(left, top), (right, top), (left, mid_y), (right, mid_y), (left, bottom), (right, bottom)],
        }
        for x, y in patterns[value]:
            Color(0.12, 0.07, 0.20, 1)
            Ellipse(pos=(x - radius, y - radius), size=(radius * 2, radius * 2))

    def set_value(self, value):
        self.value = int(value)


class SnakeLadderBoard(Widget):
    player_ali = NumericProperty(0)
    player_ava = NumericProperty(0)

    def __init__(self, font_name='Roboto', **kwargs):
        self.font_name = font_name
        super().__init__(**kwargs)
        self.number_labels = []
        self.ali_label = Label(text='A', font_name=font_name, bold=True, color=(1, 1, 1, 1), size_hint=(None, None))
        self.ava_label = Label(text='V', font_name=font_name, bold=True, color=(1, 1, 1, 1), size_hint=(None, None))
        self.add_widget(self.ali_label)
        self.add_widget(self.ava_label)
        for square in range(1, 101):
            label = Label(
                text=str(square),
                font_name=font_name,
                font_size=dp(7.5),
                color=(1, 1, 1, 0.82),
                size_hint=(None, None),
                halign='center',
                valign='middle',
            )
            label.bind(size=lambda obj, *_: setattr(obj, 'text_size', obj.size))
            self.number_labels.append(label)
            self.add_widget(label)
        self.bind(pos=self._redraw, size=self._redraw)
        Clock.schedule_once(lambda *_: self._redraw(), 0)

    def square_center(self, square):
        square = max(1, min(100, int(square)))
        index = square - 1
        row = index // 10
        column = index % 10
        if row % 2:
            column = 9 - column
        cell_w = self.width / 10.0
        cell_h = self.height / 10.0
        return self.x + (column + 0.5) * cell_w, self.y + (row + 0.5) * cell_h

    def square_position(self, square):
        square = max(1, min(100, int(square)))
        index = square - 1
        row = index // 10
        column = index % 10
        if row % 2:
            column = 9 - column
        cell_w = self.width / 10.0
        cell_h = self.height / 10.0
        return self.x + column * cell_w, self.y + row * cell_h, cell_w, cell_h

    def _redraw(self, *_):
        self.canvas.clear()
        with self.canvas:
            Color(0.035, 0.025, 0.065, 1)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(14)])

            cell_w = self.width / 10.0
            cell_h = self.height / 10.0
            for square in range(1, 101):
                px, py, _, _ = self.square_position(square)
                even = (square + (square - 1) // 10) % 2 == 0
                if even:
                    Color(0.16, 0.09, 0.23, 1)
                else:
                    Color(0.09, 0.055, 0.15, 1)
                Rectangle(pos=(px + dp(0.8), py + dp(0.8)), size=(max(0, cell_w - dp(1.6)), max(0, cell_h - dp(1.6))))
                Color(1, 1, 1, 0.16)
                Line(rectangle=(px, py, cell_w, cell_h), width=0.6)

            for start, end in LADDERS.items():
                self._draw_ladder(start, end)
            for start, end in SNAKES.items():
                self._draw_snake(start, end)

            self._draw_token(self.player_ali, 0.20, 0.65, 1.0)
            self._draw_token(self.player_ava, 1.0, 0.25, 0.70)

        for square, label in enumerate(self.number_labels, 1):
            px, py, cw, ch = self.square_position(square)
            label.pos = (px + dp(2), py + dp(1))
            label.size = (cw - dp(4), ch - dp(2))

        self._position_token_label(self.ali_label, self.player_ali, -0.13)
        self._position_token_label(self.ava_label, self.player_ava, 0.13)

    def _position_token_label(self, label, square, x_offset):
        if not square:
            label.opacity = 0
            return
        cx, cy = self.square_center(square)
        size = max(dp(13), min(self.width, self.height) / 18.0)
        label.opacity = 1
        label.size = (size, size)
        label.center = (cx + self.width / 10.0 * x_offset, cy)
        label.font_size = max(dp(7), size * 0.48)

    def _draw_ladder(self, start, end):
        x1, y1 = self.square_center(start)
        x2, y2 = self.square_center(end)
        dx, dy = x2 - x1, y2 - y1
        length = max(1.0, (dx * dx + dy * dy) ** 0.5)
        nx, ny = -dy / length, dx / length
        offset = max(dp(3.5), min(self.width, self.height) * 0.018)
        Color(0.95, 0.76, 0.16, 1)
        Line(points=[x1 + nx * offset, y1 + ny * offset, x2 + nx * offset, y2 + ny * offset], width=dp(2.0))
        Line(points=[x1 - nx * offset, y1 - ny * offset, x2 - nx * offset, y2 - ny * offset], width=dp(2.0))
        for i in range(1, 7):
            t = i / 7.0
            cx, cy = x1 + dx * t, y1 + dy * t
            Line(points=[cx + nx * offset, cy + ny * offset, cx - nx * offset, cy - ny * offset], width=dp(1.25))

    def _draw_snake(self, start, end):
        x1, y1 = self.square_center(start)
        x2, y2 = self.square_center(end)
        dx, dy = x2 - x1, y2 - y1
        length = max(1.0, (dx * dx + dy * dy) ** 0.5)
        nx, ny = -dy / length, dx / length
        points = []
        segments = 20
        amplitude = max(dp(3.5), min(self.width, self.height) * 0.020)
        for i in range(segments + 1):
            t = i / float(segments)
            wave = amplitude * (1 if i % 2 else -1)
            points.extend([x1 + dx * t + nx * wave, y1 + dy * t + ny * wave])
        Color(0.92, 0.18, 0.52, 1)
        Line(points=points, width=dp(3.0), joint='round')
        Color(1, 0.35, 0.58, 1)
        Ellipse(pos=(x1 - dp(5), y1 - dp(5)), size=(dp(10), dp(10)))
        Color(0.03, 0.02, 0.05, 1)
        Ellipse(pos=(x1 - dp(2.7), y1 + dp(0.8)), size=(dp(1.8), dp(1.8)))
        Ellipse(pos=(x1 + dp(0.9), y1 + dp(0.8)), size=(dp(1.8), dp(1.8)))

    def _draw_token(self, square, r, g, b):
        if not square:
            return
        cx, cy = self.square_center(square)
        radius = max(dp(7), min(self.width, self.height) / 36.0)
        Color(0.02, 0.02, 0.03, 0.65)
        Ellipse(pos=(cx - radius - dp(1), cy - radius - dp(1)), size=(radius * 2 + dp(2), radius * 2 + dp(2)))
        Color(r, g, b, 1)
        Ellipse(pos=(cx - radius, cy - radius), size=(radius * 2, radius * 2))
        Color(1, 1, 1, 0.9)
        Line(circle=(cx, cy, radius), width=dp(1.0))

    def set_positions(self, ali, ava):
        self.player_ali = int(ali)
        self.player_ava = int(ava)


class SnakeLadderGame:
    def __init__(self, board, status_label=None, dice_widget=None, turn_label=None):
        self.board = board
        self.status_label = status_label
        self.dice_widget = dice_widget
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
        self.roll_token = object()
        self.board.set_positions(0, 0)
        self._update_labels()

    def _update_labels(self):
        if self.turn_label is not None:
            self.turn_label.text = f"{self.turn}'S TURN"
        if self.dice_widget is not None:
            self.dice_widget.set_value(0)
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
        frames = [random.randint(1, 6) for _ in range(10)]
        if self.status_label is not None:
            self.status_label.text = 'ROLLING...'

        def frame(index):
            if token is not self.roll_token:
                return
            if self.dice_widget is not None:
                self.dice_widget.set_value(frames[index])
            if index + 1 < len(frames):
                Clock.schedule_once(lambda *_: frame(index + 1), 0.07)
            else:
                self._finish_roll(frames[-1])

        frame(0)

    def _finish_roll(self, result):
        if self.finished:
            self.rolling = False
            return
        if self.dice_widget is not None:
            self.dice_widget.set_value(result)
        player = self.turn
        if self.on_dice_result:
            self.on_dice_result(player, result)
        current = self.ali if player == 'ALI' else self.ava
        rolled_target = current + result
        if rolled_target > 100:
            target = current
            message = f'{player}: NEED EXACT ROLL'
        else:
            target = self._resolve_jump(rolled_target)
            if target != rolled_target:
                if rolled_target in LADDERS:
                    message = f'{player} CLIMBS TO {target}'
                else:
                    message = f'{player} SLIDES TO {target}'
            else:
                message = f'{player} MOVES TO {target}'
        self._move_current_player(target, message)

    def _resolve_jump(self, square):
        if square in LADDERS:
            return LADDERS[square]
        if square in SNAKES:
            return SNAKES[square]
        return square

    def _move_current_player(self, target, message=''):
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
        if self.status_label is not None:
            self.status_label.text = message or 'ROLL THE DICE'
        self.turn = 'AVA' if self.turn == 'ALI' else 'ALI'
        self.rolling = False
        self._update_turn_only()

    def _update_turn_only(self):
        if self.turn_label is not None:
            self.turn_label.text = f"{self.turn}'S TURN"
        if self.on_turn_change:
            self.on_turn_change(self.turn)


def build_snake_ladder_page(font_name, back_callback, roll_callback, reset_callback):
    from kivy.uix.floatlayout import FloatLayout

    page = FloatLayout(size_hint=(1, 1))

    title = Label(text='SNAKE & LADDER', font_name=font_name, font_size=dp(22), color=(1, 1, 1, 1), size_hint=(1, None), height=dp(42), pos_hint={'center_x': 0.5, 'top': 0.98})
    page.add_widget(title)

    turn_label = Label(text="ALI'S TURN", font_name=font_name, font_size=dp(12), color=(1, 1, 1, 0.92), size_hint=(1, None), height=dp(28), pos_hint={'center_x': 0.5, 'top': 0.91})
    page.add_widget(turn_label)

    # Compact player HUD.
    ali_hud = Label(text='ALI  0', font_name=font_name, font_size=dp(9), color=(0.25, 0.75, 1, 1), size_hint=(0.30, None), height=dp(26), pos_hint={'x': 0.05, 'top': 0.91})
    ava_hud = Label(text='AVA  0', font_name=font_name, font_size=dp(9), color=(1, 0.35, 0.72, 1), size_hint=(0.30, None), height=dp(26), pos_hint={'right': 0.95, 'top': 0.91})
    page.add_widget(ali_hud)
    page.add_widget(ava_hud)

    board = SnakeLadderBoard(font_name=font_name, size_hint=(0.92, None), height=dp(360), pos_hint={'center_x': 0.5, 'top': 0.84})
    page.add_widget(board)

    dice = DiceWidget(size_hint=(None, None), size=(dp(64), dp(64)), pos_hint={'center_x': 0.82, 'y': 0.095})
    page.add_widget(dice)

    status = Label(text='ROLL THE DICE', font_name=font_name, font_size=dp(9.5), color=(1, 1, 1, 0.95), size_hint=(0.52, None), height=dp(46), pos_hint={'x': 0.05, 'y': 0.105}, halign='left', valign='middle')
    status.bind(size=lambda obj, *_: setattr(obj, 'text_size', obj.size))
    page.add_widget(status)

    def refresh_scores(*_):
        ali_hud.text = f'ALI  {board.player_ali}'
        ava_hud.text = f'AVA  {board.player_ava}'
    board.bind(player_ali=refresh_scores, player_ava=refresh_scores)

    roll_button = Button(text='ROLL DICE', font_name=font_name, font_size=dp(11), size_hint=(None, None), size=(dp(122), dp(42)), pos_hint={'center_x': 0.25, 'y': 0.025}, background_normal='', background_down='', background_color=(0.45, 0.12, 0.75, 0.95), color=(1, 1, 1, 1))
    roll_button.bind(on_release=lambda *_: roll_callback())
    page.add_widget(roll_button)

    reset_button = Button(text='RESET', font_name=font_name, font_size=dp(10), size_hint=(None, None), size=(dp(82), dp(38)), pos_hint={'center_x': 0.52, 'y': 0.027}, background_normal='', background_down='', background_color=(0.25, 0.08, 0.42, 0.95), color=(1, 1, 1, 1))
    reset_button.bind(on_release=lambda *_: reset_callback())
    page.add_widget(reset_button)

    back_button = Button(text='BACK', font_name=font_name, font_size=dp(10), size_hint=(None, None), size=(dp(76), dp(38)), pos_hint={'center_x': 0.78, 'y': 0.027}, background_normal='', background_down='', background_color=(0.13, 0.13, 0.17, 0.95), color=(1, 1, 1, 1))
    back_button.bind(on_release=lambda *_: back_callback())
    page.add_widget(back_button)

    return page, board, status, dice, turn_label, roll_button
