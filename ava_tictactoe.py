from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout


GAME_ID = "TIC_TAC_TOE"


def _hide(page):
    if page is not None:
        page.opacity = 0
        page.disabled = True


def install_tictactoe(AvaPetApp, font_name="Roboto"):
    """Install the Tic-Tac-Toe UI/controller on the existing app.

    The ESP32 remains the sole game brain. This module only renders
    board state and sends ALI moves/rematch commands over BLE.
    """

    original_build = AvaPetApp.build
    original_select_game = AvaPetApp.select_game
    original_handle_game_data = AvaPetApp.handle_game_data
    original_back_to_games = AvaPetApp.back_to_games
    original_show_my_games = AvaPetApp.show_my_games
    original_show_settings = AvaPetApp.show_settings
    original_show_ava_home = AvaPetApp.show_ava_home
    original_start_automatic_scan = AvaPetApp.start_automatic_scan

    def build(self):
        self.ttt_font_name = font_name
        root = original_build(self)
        self._ttt_build_page()
        return root

    def _ttt_build_page(self):
        self.ttt_page = FloatLayout(size_hint=(1, 1))

        self.ttt_title = Label(
            text="TIC TAC TOE",
            font_name=self.ttt_font_name,
            font_size=dp(24),
            color=(1, 1, 1, 1),
            size_hint=(1, None),
            height=dp(55),
            pos_hint={"center_x": 0.5, "top": 0.95},
        )
        self.ttt_page.add_widget(self.ttt_title)

        self.ttt_score = Label(
            text="ALI: 0     AVA: 0",
            font_name=self.ttt_font_name,
            font_size=dp(14),
            color=(1, 1, 1, 1),
            size_hint=(1, None),
            height=dp(35),
            pos_hint={"center_x": 0.5, "top": 0.84},
        )
        self.ttt_page.add_widget(self.ttt_score)

        self.ttt_status = Label(
            text="WAITING...",
            font_name=self.ttt_font_name,
            font_size=dp(14),
            color=(1, 1, 1, 1),
            size_hint=(0.94, None),
            height=dp(48),
            pos_hint={"center_x": 0.5, "top": 0.78},
            halign="center",
            valign="middle",
        )
        self.ttt_status.bind(
            size=lambda inst, val: setattr(inst, "text_size", val)
        )
        self.ttt_page.add_widget(self.ttt_status)

        self.ttt_board = GridLayout(
            cols=3,
            rows=3,
            spacing=dp(8),
            padding=[dp(4), dp(4)],
            size_hint=(0.78, None),
            height=dp(270),
            pos_hint={"center_x": 0.5, "center_y": 0.47},
        )

        self.ttt_buttons = []
        for index in range(9):
            button = Button(
                text="",
                font_name=self.ttt_font_name,
                font_size=dp(30),
                background_normal="",
                background_down="",
                background_color=(0.45, 0.12, 0.75, 0.9),
                color=(1, 1, 1, 1),
            )
            button.bind(
                on_release=lambda _, idx=index: self.ttt_select_cell(idx)
            )
            self.ttt_buttons.append(button)
            self.ttt_board.add_widget(button)

        self.ttt_page.add_widget(self.ttt_board)

        self.ttt_rematch_button = Button(
            text="REMATCH",
            font_name=self.ttt_font_name,
            font_size=dp(13),
            size_hint=(None, None),
            size=(dp(145), dp(42)),
            pos_hint={"center_x": 0.30, "y": 0.10},
            background_normal="",
            background_down="",
            background_color=(0.45, 0.12, 0.75, 0.9),
            color=(1, 1, 1, 1),
        )
        self.ttt_rematch_button.bind(on_release=self.ttt_rematch)
        self.ttt_page.add_widget(self.ttt_rematch_button)

        self.ttt_back_button = Button(
            text="BACK TO GAMES",
            font_name=self.ttt_font_name,
            font_size=dp(12),
            size_hint=(None, None),
            size=(dp(145), dp(42)),
            pos_hint={"center_x": 0.70, "y": 0.10},
            background_normal="",
            background_down="",
            background_color=(0.25, 0.08, 0.42, 0.9),
            color=(1, 1, 1, 1),
        )
        self.ttt_back_button.bind(on_release=self.back_to_games)
        self.ttt_page.add_widget(self.ttt_back_button)

        self.ttt_rematch_button.disabled = True
        self.ttt_page.opacity = 0
        self.ttt_page.disabled = True
        self.root_layout.add_widget(self.ttt_page)

        self.ttt_board_state = "---------"
        self.ttt_turn = "ALI"
        self.ttt_finished = False
        self.ttt_selected_pending = False
        self.ttt_ali_score = 0
        self.ttt_ava_score = 0

    def _ttt_hide(self):
        _hide(getattr(self, "ttt_page", None))

    def _ttt_show(self):
        for name in (
            "finding_page",
            "home_page",
            "games_page",
            "math_page",
            "logic_page",
            "settings_page",
        ):
            _hide(getattr(self, name, None))

        self.connect_button.opacity = 0
        self.connect_button.disabled = True
        self.ttt_page.opacity = 1
        self.ttt_page.disabled = False
        self.root_layout.remove_widget(self.ttt_page)
        self.root_layout.add_widget(self.ttt_page)

    def _ttt_reset_visuals(self):
        self.ttt_board_state = "---------"
        self.ttt_turn = "ALI"
        self.ttt_finished = False
        self.ttt_selected_pending = False
        self.ttt_ali_score = 0
        self.ttt_ava_score = 0
        self.ttt_status.text = "STARTING GAME..."
        self.ttt_rematch_button.disabled = True
        self._ttt_render_board()

    def _ttt_render_board(self):
        board = self.ttt_board_state
        for index, button in enumerate(self.ttt_buttons):
            value = board[index] if index < len(board) else "-"
            button.text = "" if value == "-" else value
            button.disabled = (
                self.ttt_finished
                or self.ttt_selected_pending
                or self.ttt_turn != "ALI"
                or value != "-"
            )

        self.ttt_score.text = (
            f"ALI: {self.ttt_ali_score}     "
            f"AVA: {self.ttt_ava_score}"
        )

    def ttt_select_cell(self, index):
        if self.ttt_finished:
            return
        if self.ttt_turn != "ALI":
            return
        if self.ttt_selected_pending:
            return
        if index < 0 or index >= 9:
            return
        if self.ttt_board_state[index] != "-":
            return

        self.ttt_selected_pending = True
        self.ttt_status.text = "AVA THINKING..."
        self._ttt_render_board()

        command = f"TTT_MOVE|ALI|{index}"
        self.add_log(f"TIC TAC TOE MOVE -> {command}")

        if not self.ble.write_data(command):
            self.ttt_selected_pending = False
            self.ttt_status.text = "MOVE SEND FAILED"
            self._ttt_render_board()

    def ttt_rematch(self, *_):
        if not self.ttt_finished:
            return

        self.ttt_finished = False
        self.ttt_selected_pending = False
        self.ttt_rematch_button.disabled = True
        self.ttt_status.text = "REMATCH STARTING..."
        self._ttt_render_board()

        if self.ble.write_data("TTT_REMATCH"):
            self.add_log("TIC TAC TOE REMATCH -> TTT_REMATCH")
        else:
            self.ttt_status.text = "REMATCH SEND FAILED"
            self.ttt_finished = True
            self.ttt_rematch_button.disabled = False
            self._ttt_render_board()

    def _ttt_handle_data(self, text):
        parts = str(text).strip().split("|")
        message = parts[0].strip().upper() if parts else ""

        if message == "TTT_STATE":
            if len(parts) < 3:
                return
            board = parts[1].strip().upper()
            turn = parts[2].strip().upper()
            if len(board) != 9 or any(c not in "XO-" for c in board):
                self.add_log(f"TTT INVALID BOARD <- {text}")
                return

            self.ttt_board_state = board
            self.ttt_turn = turn if turn in ("ALI", "AVA") else "ALI"
            self.ttt_selected_pending = False
            self.ttt_finished = False
            self.ttt_rematch_button.disabled = True
            self.ttt_status.text = (
                "YOUR TURN" if self.ttt_turn == "ALI" else "AVA THINKING..."
            )
            self._ttt_render_board()
            return

        if message == "TTT_MOVE":
            if len(parts) < 3:
                return
            player = parts[1].strip().upper()
            try:
                cell = int(parts[2])
            except Exception:
                return
            self.add_log(f"TIC TAC TOE MOVE <- {player}|{cell}")
            return

        if message == "TTT_MOVE_ACCEPTED":
            self.ttt_selected_pending = False
            self.add_log(f"TIC TAC TOE MOVE ACCEPTED <- {text}")
            return

        if message == "TTT_MOVE_REJECTED":
            self.ttt_selected_pending = False
            self.ttt_status.text = "MOVE REJECTED"
            self._ttt_render_board()
            self.add_log(f"TIC TAC TOE MOVE REJECTED <- {text}")
            return

        if message == "TTT_RESULT":
            winner = parts[1].strip().upper() if len(parts) > 1 else "DRAW"
            if winner == "ALI":
                self.ttt_status.text = "ALI WINS!"
            elif winner == "AVA":
                self.ttt_status.text = "AVA WINS!"
            else:
                self.ttt_status.text = "DRAW!"
            self.add_log(f"TIC TAC TOE RESULT <- {winner}")
            return

        if message == "TTT_FINISHED":
            winner = parts[1].strip().upper() if len(parts) > 1 else "DRAW"
            self.ttt_finished = True
            self.ttt_selected_pending = False
            self.ttt_rematch_button.disabled = False
            if winner == "ALI":
                self.ttt_status.text = "ALI WINS!"
            elif winner == "AVA":
                self.ttt_status.text = "AVA WINS!"
            else:
                self.ttt_status.text = "DRAW!"
            self._ttt_render_board()
            self.add_log(f"TIC TAC TOE FINISHED <- {winner}")
            return

        if message == "TTT_SCORE":
            if len(parts) >= 3:
                try:
                    self.ttt_ali_score = int(parts[1])
                    self.ttt_ava_score = int(parts[2])
                    self._ttt_render_board()
                except Exception:
                    pass
            return

    def select_game(self, game_id, _button_event=False):
        normalized = str(game_id).strip().upper()
        if normalized != GAME_ID:
            return original_select_game(self, game_id, _button_event)

        self.game_id = GAME_ID
        self.games_status.text = "TIC TAC TOE STARTING"
        self._ttt_reset_visuals()
        self._ttt_show()

        if not self.ble.write_command("GAME_LOAD|TIC_TAC_TOE"):
            self.ttt_status.text = "GAME LOAD FAILED"
            self.add_log("TIC TAC TOE GAME_LOAD FAILED")
            return

        self.add_log("GAME LOAD -> TIC_TAC_TOE")

        # GAME_LOAD identifies the game on ESP32. The existing BLE game
        # command flow has no separate TTT start state, so use the TTT
        # rematch command to initialize the first round in the ESP32 engine.
        if not self.ble.write_data("TTT_REMATCH"):
            self.ttt_status.text = "GAME START FAILED"
            self.add_log("TIC TAC TOE INITIALIZATION FAILED")
            return

        self.add_log("TTT INIT -> TTT_REMATCH")

    def handle_game_data(self, text):
        if self.game_id == GAME_ID and str(text).strip().upper().startswith("TTT_"):
            self._ttt_handle_data(text)
            return
        return original_handle_game_data(self, text)

    def back_to_games(self, *_):
        if getattr(self, "game_id", "") == GAME_ID and getattr(self, "ttt_page", None) is not None:
            self.ble.write_command("GAME_END")
            self._ttt_hide()
            self.game_id = None
        return original_back_to_games(self)

    def show_my_games(self, *args):
        self._ttt_hide()
        return original_show_my_games(self, *args)

    def show_settings(self, *args):
        self._ttt_hide()
        return original_show_settings(self, *args)

    def show_ava_home(self, *args):
        self._ttt_hide()
        return original_show_ava_home(self, *args)

    def start_automatic_scan(self, *args):
        self._ttt_hide()
        return original_start_automatic_scan(self, *args)

    # Install every helper used through self.*. The previous version only
    # installed the public wrappers, leaving _ttt_build_page and the other
    # helpers as local functions inside install_tictactoe(). That caused the
    # startup crash: AttributeError: 'AvaPetApp' object has no attribute
    # '_ttt_build_page'.
    AvaPetApp._ttt_build_page = _ttt_build_page
    AvaPetApp._ttt_hide = _ttt_hide
    AvaPetApp._ttt_show = _ttt_show
    AvaPetApp._ttt_reset_visuals = _ttt_reset_visuals
    AvaPetApp._ttt_render_board = _ttt_render_board
    AvaPetApp.ttt_select_cell = ttt_select_cell
    AvaPetApp.ttt_rematch = ttt_rematch
    AvaPetApp._ttt_handle_data = _ttt_handle_data

    AvaPetApp.build = build
    AvaPetApp.select_game = select_game
    AvaPetApp.handle_game_data = handle_game_data
    AvaPetApp.back_to_games = back_to_games
    AvaPetApp.show_my_games = show_my_games
    AvaPetApp.show_settings = show_settings
    AvaPetApp.show_ava_home = show_ava_home
    AvaPetApp.start_automatic_scan = start_automatic_scan

# End of AVA Tic-Tac-Toe controller module.
