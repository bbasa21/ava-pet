from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget

GAME_ID = "TIC_TAC_TOE"


def install_tictactoe(app_class, font_name="Orbitron"):
    original_build = app_class.build
    original_start_automatic_scan = app_class.start_automatic_scan
    original_handle_game_data = app_class.handle_game_data
    original_select_game = app_class.select_game
    original_back_to_games = app_class.back_to_games
    original_show_my_games = app_class.show_my_games
    original_show_settings = app_class.show_settings
    original_show_ava_home = app_class.show_ava_home

    def build(self):
        root = original_build(self)

        self.ttt_page = FloatLayout(size_hint=(1, 1))
        self.ttt_title = Label(text="TIC TAC TOE", font_name=font_name, font_size=dp(24), size_hint=(1, None), height=dp(45), pos_hint={"center_x": .5, "top": .99})
        self.ttt_subtitle = Label(text="ALI X  •  AVA O", font_name=font_name, font_size=dp(12), size_hint=(1, None), height=dp(30), pos_hint={"center_x": .5, "top": .90})
        self.ttt_score = Label(text="ALI  0     —     0  AVA", font_name=font_name, font_size=dp(13), size_hint=(None, None), size=(dp(190), dp(35)), pos_hint={"center_x": .76, "top": .90})
        self.ttt_status = Label(text="YOUR TURN", font_name=font_name, font_size=dp(13), size_hint=(1, None), height=dp(35), pos_hint={"center_x": .5, "y": .15})

        self.ttt_board = GridLayout(cols=3, rows=3, spacing=dp(5), padding=dp(4), size_hint=(None, None), size=(dp(300), dp(300)), pos_hint={"center_x": .5, "center_y": .45})
        self.ttt_buttons = []
        for index in range(9):
            button = Button(text="", font_name=font_name, font_size=dp(48), background_normal="", background_down="", background_color=(.17, .055, .29, 1), color=(1, 1, 1, 1))
            button.bind(on_release=lambda _button, idx=index: self.ttt_select_cell(idx))
            self.ttt_buttons.append(button)
            self.ttt_board.add_widget(button)

        self.ttt_touch_layer = Widget(size=self.ttt_board.size, size_hint=(None, None), pos=self.ttt_board.pos)

        def sync_ttt_touch_layer(_instance, _value):
            self.ttt_touch_layer.size = self.ttt_board.size
            self.ttt_touch_layer.pos = self.ttt_board.pos

        self.ttt_board.bind(pos=sync_ttt_touch_layer, size=sync_ttt_touch_layer)

        def ttt_touch_layer_down(_layer, touch):
            if self.ttt_page.opacity <= 0 or self.ttt_page.disabled:
                return False
            if not self.ttt_touch_layer.collide_point(*touch.pos):
                return False
            for index, button in enumerate(self.ttt_buttons):
                if button.collide_point(*touch.pos):
                    self.add_log(f"TTT TOUCH LAYER -> cell={index}")
                    self.ttt_select_cell(index)
                    return True
            return True

        self.ttt_touch_layer.bind(on_touch_down=ttt_touch_layer_down)

        self.ttt_rematch = Button(text="REMATCH", font_name=font_name, font_size=dp(12), size_hint=(None, None), size=(dp(135), dp(42)), pos_hint={"center_x": .37, "y": .055}, background_normal="", background_down="", background_color=(.25, .08, .42, 1))
        self.ttt_back = Button(text="BACK TO GAMES", font_name=font_name, font_size=dp(11), size_hint=(None, None), size=(dp(155), dp(42)), pos_hint={"center_x": .67, "y": .055}, background_normal="", background_down="", background_color=(.25, .08, .42, 1))
        self.ttt_rematch.bind(on_release=self.ttt_request_rematch)
        self.ttt_back.bind(on_release=self.back_to_games)

        for widget in (self.ttt_title, self.ttt_subtitle, self.ttt_score, self.ttt_board, self.ttt_touch_layer, self.ttt_status, self.ttt_rematch, self.ttt_back):
            self.ttt_page.add_widget(widget)

        root.add_widget(self.ttt_page)
        self.ttt_page.opacity = 0
        self.ttt_page.disabled = True

        self.ttt_board_state = ["-"] * 9
        self.ttt_turn = "ALI"
        self.ttt_finished = False
        self.ttt_selected_pending = False
        self.ttt_ali_score = 0
        self.ttt_ava_score = 0
        self._ttt_auto_connecting = False
        return root

    def _ttt_hide(self):
        if not hasattr(self, "ttt_page"):
            return
        self.ttt_page.opacity = 0
        self.ttt_page.disabled = True

    def _ttt_hide_other_pages(self):
        pages = ("finding_page", "home_page", "games_page", "settings_page", "math_page", "logic_page")
        for name in pages:
            page = getattr(self, name, None)
            if page is not None:
                page.opacity = 0
                page.disabled = True
        self.connect_button.opacity = 0
        self.connect_button.disabled = True

    def _ttt_show(self):
        self._ttt_hide_other_pages()
        # TTT must be the topmost sibling so its board receives Android touches.
        if self.ttt_page.parent is self.root_layout:
            self.root_layout.remove_widget(self.ttt_page)
        self.root_layout.add_widget(self.ttt_page)
        self.ttt_page.opacity = 1
        self.ttt_page.disabled = False

    def _ttt_render_board(self):
        for index, button in enumerate(self.ttt_buttons):
            value = self.ttt_board_state[index]
            button.text = "" if value == "-" else value
            button.disabled = False
            button.background_color = (.17, .055, .29, 1) if value == "-" else (.50, .16, .78, 1)
            button.color = (1, 1, 1, 1)
        self.ttt_score.text = f"ALI  {self.ttt_ali_score}     —     {self.ttt_ava_score}  AVA"

    def _ttt_reset_visuals(self):
        self.ttt_board_state = ["-"] * 9
        self.ttt_turn = "ALI"
        self.ttt_finished = False
        self.ttt_selected_pending = False
        self.ttt_status.text = "YOUR TURN"
        self.ttt_rematch.disabled = True
        self._ttt_render_board()

    def select_game(self, game_id, _button_event=False):
        normalized = str(game_id).strip().upper()
        if normalized != GAME_ID:
            self._ttt_hide()
            return original_select_game(self, game_id, _button_event)

        self.game_id = GAME_ID
        self._ttt_reset_visuals()
        self._ttt_show()
        self.games_status.text = "TIC TAC TOE STARTING"

        try:
            sent = self.ble.write_command("GAME_LOAD|TIC_TAC_TOE")
        except Exception as exc:
            sent = False
            self.add_log(f"TIC TAC TOE GAME LOAD ERROR -> {exc}")

        if not sent:
            self.ttt_status.text = "GAME LOAD FAILED"
            self.add_log("TIC TAC TOE GAME_LOAD FAILED")
            return

        self.add_log("GAME LOAD -> TIC_TAC_TOE")

    def ttt_select_cell(self, index):
        self.add_log(
            f"TTT TOUCH -> cell={index} | "
            f"turn={self.ttt_turn} | "
            f"finished={self.ttt_finished} | "
            f"pending={self.ttt_selected_pending}"
        )
        if self.ttt_finished or self.ttt_turn != "ALI" or self.ttt_selected_pending:
            return
        if index < 0 or index >= 9 or self.ttt_board_state[index] != "-":
            return

        self.ttt_selected_pending = True
        self.ttt_status.text = "AVA THINKING..."
        self._ttt_render_board()
        command = f"TTT_MOVE|ALI|{index}"
        self.add_log(f"TIC TAC TOE MOVE -> {command}")

        try:
            sent = self.ble.write_data(command)
        except Exception as exc:
            sent = False
            self.add_log(f"TIC TAC TOE WRITE ERROR -> {exc}")

        if not sent:
            self.ttt_selected_pending = False
            self.ttt_status.text = "MOVE SEND FAILED"
            self._ttt_render_board()

    def _ttt_end_glee(self, *_):
        try:
            sent = self.ble.write_data("TTT_GLEE_END")
            self.add_log(f"TIC TAC TOE GLEE END | sent={sent}")
        except Exception as exc:
            self.add_log(f"TIC TAC TOE GLEE END ERROR -> {exc}")

    def ttt_request_rematch(self, *_):
        if not self.ttt_finished:
            return
        self.ttt_selected_pending = True
        self.ttt_status.text = "STARTING..."
        try:
            # Keep rematch control commands on the COMMAND queue so
            # debug eyes is sent before TTT_REMATCH.
            debug_eyes_sent = self.ble.write_command("debug eyes")
            self.add_log(f"TIC TAC TOE REMATCH -> debug eyes | sent={debug_eyes_sent}")
            sent = self.ble.write_command("TTT_REMATCH")
        except Exception as exc:
            sent = False
            self.add_log(f"TIC TAC TOE REMATCH ERROR: {exc}")
        if not sent:
            self.ttt_selected_pending = False
            self.ttt_status.text = "REMATCH FAILED"

    def _ttt_handle_data(self, text):
        value = str(text).strip()
        parts = value.split("|")
        kind = parts[0].strip().upper() if parts else ""

        if kind == "TTT_STATE" and len(parts) >= 3:
            board = parts[1].strip().upper()
            turn = parts[2].strip().upper()
            if len(board) != 9 or any(char not in "XO-" for char in board):
                self.add_log(f"TIC TAC TOE INVALID STATE -> {value}")
                return

            self.ttt_board_state = list(board)
            if turn in ("X", "ALI"):
                self.ttt_turn = "ALI"
            elif turn in ("O", "AVA"):
                self.ttt_turn = "AVA"
            else:
                self.add_log(f"TIC TAC TOE INVALID TURN -> {value}")
                return

            self.ttt_finished = False
            self.ttt_selected_pending = False
            self.ttt_rematch.disabled = True
            self.ttt_status.text = "YOUR TURN" if self.ttt_turn == "ALI" else "AVA THINKING..."
            self._ttt_render_board()
            return

        if kind == "TTT_MOVE_ACCEPTED":
            self.add_log(f"TIC TAC TOE ACCEPTED -> {value}")
            return

        if kind == "TTT_MOVE_REJECTED":
            self.ttt_selected_pending = False
            reason = parts[1].strip() if len(parts) > 1 else "UNKNOWN"
            self.ttt_status.text = f"MOVE REJECTED: {reason}"
            self._ttt_render_board()
            return

        if kind == "TTT_MOVE":
            self.add_log(f"TIC TAC TOE AVA MOVE -> {value}")
            return

        if kind == "TTT_RESULT":
            winner = parts[1].strip().upper() if len(parts) > 1 else "DRAW"
            self.ttt_status.text = "YOU WIN!" if winner == "ALI" else ("AVA WINS!" if winner == "AVA" else "DRAW!")
            return

        if kind == "TTT_FINISHED":
            winner = parts[1].strip().upper() if len(parts) > 1 else "DRAW"

            # When ALI wins the round, AVA reacts with SAD.
            if winner == "ALI":
                try:
                    sent = self.ble.write_data("SAD")
                    self.add_log(f"TIC TAC TOE WIN REACTION -> SAD | sent={sent}")
                except Exception as exc:
                    self.add_log(f"TIC TAC TOE SAD ERROR -> {exc}")

            # When ALI loses the round, AVA briefly celebrates with GLEE.
            if winner == "AVA":
                try:
                    sent = self.ble.write_data("TTT_GLEE")
                    self.add_log(f"TIC TAC TOE LOSS REACTION -> GLEE | sent={sent}")
                    Clock.schedule_once(self._ttt_end_glee, 0.9)
                except Exception as exc:
                    self.add_log(f"TIC TAC TOE GLEE ERROR -> {exc}")

            self.ttt_finished = True
            self.ttt_selected_pending = False
            self.ttt_rematch.disabled = False
            self.ttt_status.text = "YOU WIN!" if winner == "ALI" else ("AVA WINS!" if winner == "AVA" else "DRAW!")
            self._ttt_render_board()
            return

        if kind == "TTT_SCORE" and len(parts) >= 3:
            try:
                self.ttt_ali_score = int(parts[1])
                self.ttt_ava_score = int(parts[2])
            except ValueError:
                self.add_log(f"TIC TAC TOE INVALID SCORE -> {value}")
                return
            self._ttt_render_board()

    def handle_game_data(self, text):
        if self.game_id == GAME_ID and str(text).strip().upper().startswith("TTT_"):
            self._ttt_handle_data(text)
            return
        return original_handle_game_data(self, text)

    def start_automatic_scan(self, *args):
        self._ttt_hide()
        result = original_start_automatic_scan(self, *args)
        self._ttt_auto_connecting = False

        def watch_for_ava(_dt):
            if self._ttt_auto_connecting:
                return False
            try:
                if self.ble.has_ava():
                    self._ttt_auto_connecting = True
                    self.add_log("AVA FOUND -> AUTO CONNECT")
                    if self.ble.connect():
                        self.add_log("AUTO CONNECT REQUEST SENT")
                    else:
                        self.add_log("AUTO CONNECT REQUEST FAILED")
                        self._ttt_auto_connecting = False
                        return True
            except Exception as exc:
                self.add_log(f"AUTO CONNECT WATCH ERROR: {exc}")
                self._ttt_auto_connecting = False
                return True
            return True

        Clock.schedule_interval(watch_for_ava, 0.5)
        return result

    def back_to_games(self, *_):
        self._ttt_hide()
        return original_back_to_games(self)

    def show_my_games(self, *_):
        self._ttt_hide()
        return original_show_my_games(self)

    def show_settings(self, *_):
        self._ttt_hide()
        return original_show_settings(self)

    def show_ava_home(self, *_):
        self._ttt_hide()
        return original_show_ava_home(self)

    app_class.build = build
    app_class.select_game = select_game
    app_class.handle_game_data = handle_game_data
    app_class.start_automatic_scan = start_automatic_scan
    app_class.back_to_games = back_to_games
    app_class.show_my_games = show_my_games
    app_class.show_settings = show_settings
    app_class.show_ava_home = show_ava_home
    app_class._ttt_show = _ttt_show
    app_class._ttt_hide = _ttt_hide
    app_class._ttt_hide_other_pages = _ttt_hide_other_pages
    app_class._ttt_render_board = _ttt_render_board
    app_class._ttt_reset_visuals = _ttt_reset_visuals
    app_class.ttt_select_cell = ttt_select_cell
    app_class.ttt_request_rematch = ttt_request_rematch
    app_class._ttt_handle_data = _ttt_handle_data
