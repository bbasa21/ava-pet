from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label

GAME_ID = "TIC_TAC_TOE"


def install_tictactoe(app_class):
    original_build = app_class.build
    original_start_automatic_scan = app_class.start_automatic_scan
    original_handle_game_data = app_class.handle_game_data
    original_select_game = app_class.select_game

    def build(self):
        root = original_build(self)

        self.ttt_page = FloatLayout(size_hint=(1, 1))
        self.ttt_title = Label(text="TIC TAC TOE", font_name="Orbitron", font_size=dp(24), size_hint=(1, None), height=dp(45), pos_hint={"center_x": .5, "top": .96})
        self.ttt_subtitle = Label(text="ALI X  •  AVA O", font_name="Orbitron", font_size=dp(12), size_hint=(1, None), height=dp(30), pos_hint={"center_x": .5, "top": .89})
        self.ttt_score = Label(text="ALI  0     —     0  AVA", font_name="Orbitron", font_size=dp(13), size_hint=(1, None), height=dp(35), pos_hint={"center_x": .5, "top": .82})
        self.ttt_status = Label(text="YOUR TURN", font_name="Orbitron", font_size=dp(13), size_hint=(1, None), height=dp(35), pos_hint={"center_x": .5, "y": .14})

        self.ttt_board = GridLayout(cols=3, rows=3, spacing=dp(5), padding=dp(4), size_hint=(None, None), size=(dp(300), dp(300)), pos_hint={"center_x": .5, "center_y": .49})
        self.ttt_buttons = []
        for index in range(9):
            button = Button(text="", font_name="Orbitron", font_size=dp(42), background_normal="", background_down="", background_color=(.17, .055, .29, 1), color=(1, 1, 1, 1), disabled=False)
            button.bind(on_release=lambda btn, idx=index: self.ttt_select_cell(idx))
            self.ttt_buttons.append(button)
            self.ttt_board.add_widget(button)

        self.ttt_rematch = Button(text="REMATCH", font_name="Orbitron", font_size=dp(12), size_hint=(None, None), size=(dp(135), dp(42)), pos_hint={"center_x": .37, "y": .055}, background_normal="", background_down="", background_color=(.25, .08, .42, 1))
        self.ttt_back = Button(text="BACK TO GAMES", font_name="Orbitron", font_size=dp(11), size_hint=(None, None), size=(dp(155), dp(42)), pos_hint={"center_x": .67, "y": .055}, background_normal="", background_down="", background_color=(.25, .08, .42, 1))
        self.ttt_rematch.bind(on_release=self.ttt_request_rematch)
        self.ttt_back.bind(on_release=self.back_to_games)

        self.ttt_page.add_widget(self.ttt_title)
        self.ttt_page.add_widget(self.ttt_subtitle)
        self.ttt_page.add_widget(self.ttt_score)
        self.ttt_page.add_widget(self.ttt_board)
        self.ttt_page.add_widget(self.ttt_status)
        self.ttt_page.add_widget(self.ttt_rematch)
        self.ttt_page.add_widget(self.ttt_back)
        root.add_widget(self.ttt_page)
        self.ttt_page.opacity = 0
        self.ttt_page.disabled = True

        self.ttt_board_state = ["-"] * 9
        self.ttt_turn = "ALI"
        self.ttt_finished = False
        self.ttt_selected_pending = False
        self.ttt_ali_score = 0
        self.ttt_ava_score = 0
        return root

    def _ttt_show(self):
        self.ttt_page.opacity = 1
        self.ttt_page.disabled = False

    def _ttt_hide(self):
        self.ttt_page.opacity = 0
        self.ttt_page.disabled = True

    def _ttt_render_board(self):
        for index, button in enumerate(self.ttt_buttons):
            value = self.ttt_board_state[index]
            button.text = "" if value == "-" else value
            button.disabled = self.ttt_finished or value != "-" or self.ttt_selected_pending or self.ttt_turn != "ALI"
            button.background_color = (.17, .055, .29, 1) if value == "-" else (.36, .09, .58, 1)
            button.color = (1, 1, 1, 1)
        self.ttt_score.text = f"ALI  {self.ttt_ali_score}     —     {self.ttt_ava_score}  AVA"

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

    def _ttt_reset_visuals(self):
        self.ttt_board_state = ["-"] * 9
        self.ttt_turn = "ALI"
        self.ttt_finished = False
        self.ttt_selected_pending = False
        self.ttt_status.text = "YOUR TURN"
        self.ttt_rematch.disabled = True
        self._ttt_render_board()

    def ttt_select_cell(self, index):
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

    def ttt_request_rematch(self, *_):
        if not self.ttt_finished:
            return
        self.ttt_selected_pending = True
        self.ttt_status.text = "STARTING..."
        try:
            sent = self.ble.write_data("TTT_REMATCH")
        except Exception as exc:
            sent = False
            self.add_log(f"TIC TAC TOE REMATCH ERROR: {exc}")
        if not sent:
            self.ttt_selected_pending = False
            self.ttt_status.text = "REMATCH FAILED"

    def _ttt_handle_data(self, text):
        value = str(text).strip()
        parts = value.split("|")
        kind = parts[0].upper() if parts else ""
        if kind == "TTT_STATE" and len(parts) >= 3:
            board = parts[1]
            turn = parts[2].upper()
            if len(board) == 9:
                self.ttt_board_state = list(board)
            self.ttt_turn = turn
            self.ttt_selected_pending = False
            if self.ttt_finished:
                self.ttt_status.text = "ROUND FINISHED"
            else:
                self.ttt_status.text = "YOUR TURN" if turn == "ALI" else "AVA THINKING..."
            self._ttt_render_board()
            return
        if kind == "TTT_MOVE_ACCEPTED":
            self.add_log(f"TIC TAC TOE ACCEPTED -> {value}")
            return
        if kind == "TTT_MOVE_REJECTED":
            self.ttt_selected_pending = False
            reason = parts[1] if len(parts) > 1 else "UNKNOWN"
            self.ttt_status.text = f"MOVE REJECTED: {reason}"
            self._ttt_render_board()
            return
        if kind == "TTT_MOVE":
            self.add_log(f"TIC TAC TOE AVA MOVE -> {value}")
            return
        if kind == "TTT_RESULT":
            winner = parts[1].upper() if len(parts) > 1 else "DRAW"
            self.ttt_status.text = "YOU WIN!" if winner == "ALI" else ("AVA WINS!" if winner == "AVA" else "DRAW!")
            return
        if kind == "TTT_FINISHED":
            self.ttt_finished = True
            self.ttt_selected_pending = False
            self.ttt_rematch.disabled = False
            self._ttt_render_board()
            return
        if kind == "TTT_SCORE" and len(parts) >= 3:
            try:
                self.ttt_ali_score = int(parts[1])
                self.ttt_ava_score = int(parts[2])
            except ValueError:
                pass
            self._ttt_render_board()

    def handle_game_data(self, text):
        if self.game_id == GAME_ID and str(text).strip().upper().startswith("TTT_"):
            self._ttt_handle_data(text)
            return
        return original_handle_game_data(self, text)

    def start_automatic_scan(self, *args):
        self._ttt_hide()
        return original_start_automatic_scan(self, *args)

    app_class.build = build
    app_class.select_game = select_game
    app_class.handle_game_data = handle_game_data
    app_class.start_automatic_scan = start_automatic_scan
    app_class._ttt_show = _ttt_show
    app_class._ttt_hide = _ttt_hide
    app_class._ttt_render_board = _ttt_render_board
    app_class._ttt_reset_visuals = _ttt_reset_visuals
    app_class.ttt_select_cell = ttt_select_cell
    app_class.ttt_request_rematch = ttt_request_rematch
    app_class._ttt_handle_data = _ttt_handle_data
