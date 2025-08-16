import socket
import json
import os
import time
import pygame
import threading
import pyautogui  # Used for reliable screen resolution detection

UDP_PORT = 12346
BROADCAST_MESSAGE = "POKER_SERVER_DISCOVERY"


def discover_server():
    """Listens for the server's UDP broadcast to find its IP and port."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('', UDP_PORT))
        print(f"Searching for server on local network...")
        while True:
            data, addr = sock.recvfrom(1024)
            message = data.decode('utf-8')
            if message.startswith(BROADCAST_MESSAGE):
                parts = message.split(':')
                tcp_port = int(parts[1])
                print(f"Found server at {addr[0]}:{tcp_port}")
                return addr[0], tcp_port


class ScrollableLogBox:
    """A scrollable text box component for Pygame."""

    def __init__(self, rect, font, text_color=(200, 255, 200), bg_color=(0, 0, 0, 150)):
        self.rect = pygame.Rect(rect)
        self.font = font
        self.text_color = text_color
        self.bg_color = bg_color
        self.all_logs = []
        self.scroll_y = 0
        self.line_height = font.get_linesize()

    def add_log(self, log_entry):
        self.all_logs.append(log_entry)
        self.scroll_y = max(0, len(self.all_logs) * self.line_height - self.rect.height)

    def handle_event(self, event):
        if event.type == pygame.MOUSEWHEEL:
            self.scroll_y -= event.y * self.line_height
            max_scroll = max(0, len(self.all_logs) * self.line_height - self.rect.height)
            self.scroll_y = max(0, min(self.scroll_y, max_scroll))

    def draw(self, surface):
        bg_surface = pygame.Surface(self.rect.size, pygame.SRCALPHA)
        bg_surface.fill(self.bg_color)
        surface.blit(bg_surface, self.rect.topleft)
        visible_lines_surface = pygame.Surface((self.rect.width, self.rect.height), pygame.SRCALPHA)
        for i, log_entry in enumerate(self.all_logs):
            text_surface = self.font.render(f"> {log_entry}", True, self.text_color)
            visible_lines_surface.blit(text_surface, (5, i * self.line_height - self.scroll_y))
        surface.blit(visible_lines_surface, self.rect.topleft)


class GameClient:
    """Manages the client-side connection, state display, and user input."""
    SUIT_EMOJIS = {"Hearts": '♥️', "Diamonds": '♦️', "Clubs": '♣️', "Spades": '♠️'}

    def __init__(self, host='127.0.0.1', port=12345):
        self.host, self.port = host, port
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.player_name, self.player_id = "", None
        self.state = {}
        self.lock = threading.Lock()
        self.is_running = True

        # --- Resolution Scaling Setup ---
        pygame.init()
        self.BASE_WIDTH, self.BASE_HEIGHT = 1280, 720

        # Use pyautogui to get the true screen resolution
        self.screen_width, self.screen_height = pyautogui.size()
        self.scale_w = self.screen_width / self.BASE_WIDTH
        self.scale_h = self.screen_height / self.BASE_HEIGHT

        self.screen, self.font, self.font_small, self.font_log = None, None, None, None
        self.card_images, self.buttons = {}, {}
        self.dealer_chip_img = None
        self.log_box = None
        self.last_log_count = 0
        self.last_game_stage = ""

        # Action UI State
        self.slider_track_rect = None
        self.slider_handle_rect = None
        self.slider_min_raise = 0
        self.slider_max_raise = 0
        self.slider_current_raise = 0
        self.slider_dragging = False
        self.just_started_turn = True  # FIX: Flag to reset slider only once per turn

    def network_thread(self):
        while self.is_running:
            try:
                data_buffer = self.client_socket.recv(8192)
                if not data_buffer: self.is_running = False; break
                with self.lock:
                    self.state = json.loads(data_buffer.decode('utf-8'))
                    if self.player_id is None:
                        me = next((p for p in self.state.get('players', []) if p['name'] == self.player_name), None)
                        if me: self.player_id = me['player_id']
            except (ConnectionAbortedError, ConnectionResetError, OSError, json.JSONDecodeError):
                print("Connection to server lost.")
                self.is_running = False

    def send_action(self, action_data):
        try:
            self.client_socket.sendall(json.dumps(action_data).encode('utf-8'))
        except socket.error:
            print("Failed to send action.");
            self.is_running = False

    def start(self):
        self.server_host, self.server_port = discover_server()
        if not self.server_host:
            print("Could not find server. Exiting.")
            return

        try:
            self.client_socket.connect((self.server_host, self.server_port))
            print("Connected to the game server.")
            self.player_name = input("Enter your name: ")
            self.send_action({"action": "join", "name": self.player_name})
            n_thread = threading.Thread(target=self.network_thread, daemon=True);
            n_thread.start()
            self.start_graphics_mode()
        except (ConnectionRefusedError, ConnectionResetError) as e:
            print(f"\nConnection error: {e}")
        finally:
            print("Closing connection.");
            self.is_running = False;
            self.client_socket.close()

    def init_pygame(self):
        # Use the detected resolution to create a fullscreen window
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height), pygame.FULLSCREEN)
        print(f"Fullscreen mode initialized at: {self.screen_width}x{self.screen_height}")

        pygame.display.set_caption(f"Poker Client - {self.player_name}")

        # Scale fonts
        self.font = pygame.font.SysFont("Arial", int(22 * self.scale_h))
        self.font_small = pygame.font.SysFont("Arial", int(18 * self.scale_h), bold=True)
        self.font_log = pygame.font.SysFont("Consolas", int(16 * self.scale_h))

        # Scale the log box rect
        log_rect = (
            int(10 * self.scale_w), int(580 * self.scale_h),
            int(500 * self.scale_w), int(130 * self.scale_h)
        )
        self.log_box = ScrollableLogBox(log_rect, self.font_log)

        # Scale the dealer chip
        chip_size = int(30 * self.scale_w)
        self.dealer_chip_img = pygame.Surface((chip_size, chip_size), pygame.SRCALPHA)
        pygame.draw.circle(self.dealer_chip_img, (255, 255, 255), (chip_size // 2, chip_size // 2), chip_size // 2)
        dealer_text = self.font_small.render("D", True, (0, 0, 0))
        self.dealer_chip_img.blit(dealer_text, dealer_text.get_rect(center=(chip_size // 2, chip_size // 2)))

        self.load_card_images()

    def load_card_images(self):
        RANK_TO_FILENAME = {"A": "ace", "K": "king", "Q": "queen", "J": "jack", "10": "10", "9": "9", "8": "8",
                            "7": "7", "6": "6", "5": "5", "4": "4", "3": "3", "2": "2"}
        server_ranks, server_suits = list(RANK_TO_FILENAME.keys()), ["Hearts", "Diamonds", "Clubs", "Spades"]

        # Scale card size
        card_size = (int(90 * self.scale_w), int(130 * self.scale_h))

        for suit in server_suits:
            for rank in server_ranks:
                filename = f"./cards/{RANK_TO_FILENAME[rank]}_of_{suit.lower()}.png"
                try:
                    img = pygame.image.load(filename).convert_alpha()
                    self.card_images[f"{rank}{suit}"] = pygame.transform.scale(img, card_size)
                except pygame.error:
                    placeholder = pygame.Surface(card_size)
                    placeholder.fill((200, 200, 200))
                    rank_text = self.font.render(f"{rank}{self.SUIT_EMOJIS[suit]}", True, (0, 0, 0))
                    placeholder.blit(rank_text, (10, 10))
                    self.card_images[f"{rank}{suit}"] = placeholder

    def draw_game(self):
        self.screen.fill((0, 80, 0))
        with self.lock:
            if not self.state or not self.state.get('players'): return
            self.draw_community_cards()
            self.draw_players()
            self.draw_pot()
            self.draw_action_ui()
            self.log_box.draw(self.screen)
        pygame.display.flip()

    def draw_community_cards(self):
        cards = self.state.get('community_cards', [])
        card_width = int(100 * self.scale_w)
        start_x = (self.screen_width - len(cards) * card_width) / 2
        y_pos = int(280 * self.scale_h)
        for i, card in enumerate(cards):
            card_img = self.card_images.get(f"{card['rank']}{card['suit']}")
            if card_img: self.screen.blit(card_img, (start_x + i * card_width, y_pos))

    def draw_pot(self):
        pot_text = self.font.render(f"Pot: ${self.state.get('pot', 0)}", True, (255, 255, 0))
        text_rect = pot_text.get_rect(center=(self.screen_width / 2, int(250 * self.scale_h)))
        self.screen.blit(pot_text, text_rect)

    def draw_players(self):
        players = self.state.get('players', [])
        me = next((p for p in players if p['player_id'] == self.player_id), None)
        if not me: return

        # Scale all seat positions
        base_positions = [(550, 580), (150, 420), (150, 180), (550, 80), (950, 180), (950, 420)]
        scaled_positions = [(int(x * self.scale_w), int(y * self.scale_h)) for x, y in base_positions]

        other_players = [p for p in players if p['player_id'] != self.player_id and not p.get('is_spectator')]
        self._draw_one_player(me, scaled_positions[0], is_me=True)
        for i, player in enumerate(other_players):
            self._draw_one_player(player, scaled_positions[i + 1], is_me=False)

    def _draw_one_player(self, player, pos, is_me):
        all_players = self.state.get('players', [])
        try:
            original_index = all_players.index(next(p for p in all_players if p['player_id'] == player['player_id']))
        except (ValueError, StopIteration):
            return

        is_dealer, is_sb, is_bb = (self.state.get(k) == original_index for k in
                                   ['dealer_pos', 'sb_player_index', 'bb_player_index'])
        is_current_turn = self.state.get('current_player_index') == original_index
        box_color = (200, 200, 0) if is_current_turn else (40, 40, 40)
        if player.get('is_spectator'): box_color = (20, 20, 20)

        # Scale player box
        box_rect = pygame.Rect(pos[0], pos[1], int(180 * self.scale_w), int(80 * self.scale_h))
        pygame.draw.rect(self.screen, box_color, box_rect, border_radius=10)

        if player.get('is_spectator'):
            spec_text = self.font.render("SPECTATOR", True, (200, 200, 200))
            self.screen.blit(spec_text, (pos[0] + int(30 * self.scale_w), pos[1] - int(30 * self.scale_h)))

        # Scale text offsets
        for j, (text, color) in enumerate([(player['name'], (255, 255, 255)), (f"${player['stack']}", (255, 255, 255)),
                                           (f"Bet: ${player['bet_this_street']}", (255, 255, 0))]):
            self.screen.blit(self.font.render(text, True, color), (
                pos[0] + int(10 * self.scale_w), pos[1] + int(5 * self.scale_h) + j * int(25 * self.scale_h)))

        if is_dealer: self.screen.blit(self.dealer_chip_img,
                                       (pos[0] + int(140 * self.scale_w), pos[1] + int(5 * self.scale_h)))
        if is_sb: self.screen.blit(self.font_small.render("SB", True, (232, 10, 252)),
                                   (pos[0] + int(145 * self.scale_w), pos[1] + int(30 * self.scale_h)))
        if is_bb: self.screen.blit(self.font_small.render("BB", True, (10, 252, 232)),
                                   (pos[0] + int(145 * self.scale_w), pos[1] + int(50 * self.scale_h)))

        if 'cards' in player and player['cards']:
            if not player.get('is_spectator') and player.get('is_playing'):
                for j, card in enumerate(player['cards']):
                    card_img = self.card_images.get(f"{card['rank']}{card['suit']}")
                    if card_img:
                        is_top_row_pos = pos[1] < int(180 * self.scale_h)
                        card_y_offset = pos[1] + int(90 * self.scale_h) if is_top_row_pos else pos[1] - int(
                            140 * self.scale_h)
                        self.screen.blit(card_img, (pos[0] + j * int(50 * self.scale_w), card_y_offset))

        if not player.get('is_playing') and not player.get('is_spectator'):
            fold_text = self.font.render("FOLDED", True, (255, 0, 0))
            self.screen.blit(fold_text, (pos[0] + int(50 * self.scale_w), pos[1] - int(50 * self.scale_h)))

    def draw_action_ui(self):
        players = self.state.get('players', [])
        current_player_idx = self.state.get('current_player_index')
        is_my_turn = False
        me = None
        if current_player_idx is not None and -1 < current_player_idx < len(players):
            current_player = players[current_player_idx]
            me = next((p for p in players if p['player_id'] == self.player_id), None)
            if me and current_player['player_id'] == self.player_id and me['is_playing']:
                is_my_turn = True

        if not is_my_turn:
            self.slider_dragging = False
            self.just_started_turn = True  # FIX: Reset flag when it's not our turn
            return

        # Scale UI Layout & Sizing
        BUTTON_WIDTH = int(120 * self.scale_w)
        BUTTON_HEIGHT = int(50 * self.scale_h)
        BUTTON_GAP = int(10 * self.scale_w)
        start_x = int(760 * self.scale_w)
        UI_Y_BUTTONS = int(585 * self.scale_h)
        UI_Y_SLIDER = UI_Y_BUTTONS + BUTTON_HEIGHT + int(15 * self.scale_h)
        total_ui_width = (BUTTON_WIDTH * 3) + (BUTTON_GAP * 2)

        mouse_pos = pygame.mouse.get_pos()
        self.buttons.clear()

        BUTTON_COLORS = {'fold': (200, 40, 40), 'call': (40, 180, 40), 'check': (40, 180, 40), 'raise': (230, 150, 0)}
        BUTTON_HOVER_COLORS = {'fold': (255, 60, 60), 'call': (60, 230, 60), 'check': (60, 230, 60),
                               'raise': (255, 190, 40)}

        fold_rect = pygame.Rect(start_x, UI_Y_BUTTONS, BUTTON_WIDTH, BUTTON_HEIGHT)
        call_check_rect = pygame.Rect(start_x + BUTTON_WIDTH + BUTTON_GAP, UI_Y_BUTTONS, BUTTON_WIDTH, BUTTON_HEIGHT)
        raise_rect = pygame.Rect(start_x + (BUTTON_WIDTH + BUTTON_GAP) * 2, UI_Y_BUTTONS, BUTTON_WIDTH, BUTTON_HEIGHT)

        self.buttons['fold'] = fold_rect
        fold_color = BUTTON_HOVER_COLORS['fold'] if fold_rect.collidepoint(mouse_pos) else BUTTON_COLORS['fold']
        pygame.draw.rect(self.screen, fold_color, fold_rect, border_radius=10)
        fold_text = self.font.render("Fold", True, (0, 0, 0))
        self.screen.blit(fold_text, fold_text.get_rect(center=fold_rect.center))

        current_bet = self.state.get('current_bet', 0)
        my_bet_this_street = me.get('bet_this_street', 0)
        can_check = my_bet_this_street == current_bet

        if can_check:
            self.buttons['check'] = call_check_rect
            label, color_key = "Check", 'check'
        else:
            self.buttons['call'] = call_check_rect
            amount_to_call = current_bet - my_bet_this_street
            final_call_amount = min(amount_to_call, me.get('stack', 0))
            label, color_key = f"Call ${final_call_amount}", 'call'

        cc_color = BUTTON_HOVER_COLORS[color_key] if call_check_rect.collidepoint(mouse_pos) else BUTTON_COLORS[
            color_key]
        pygame.draw.rect(self.screen, cc_color, call_check_rect, border_radius=10)
        cc_text = self.font.render(label, True, (0, 0, 0))
        self.screen.blit(cc_text, cc_text.get_rect(center=call_check_rect.center))

        my_bet = me.get('bet_this_street', 0)
        last_raise_amount = self.state.get('last_raise_amount', self.state.get('big_blind_amount', 20))
        min_r = current_bet + last_raise_amount
        self.slider_min_raise = min(min_r, me['stack'] + my_bet)
        self.slider_max_raise = me['stack'] + my_bet

        # FIX: Check the flag here to initialize the slider's value only once.
        if self.just_started_turn:
            self.slider_current_raise = self.slider_min_raise
            self.just_started_turn = False

        self.slider_track_rect = pygame.Rect(start_x, UI_Y_SLIDER, total_ui_width, int(10 * self.scale_h))
        pygame.draw.rect(self.screen, (80, 80, 80), self.slider_track_rect, border_radius=5)
        raise_range = self.slider_max_raise - self.slider_min_raise
        progress = (self.slider_current_raise - self.slider_min_raise) / raise_range if raise_range > 0 else 1.0
        handle_x = self.slider_track_rect.x + int(progress * self.slider_track_rect.width)
        handle_size = int(20 * self.scale_w)
        self.slider_handle_rect = pygame.Rect(handle_x - handle_size // 2,
                                              self.slider_track_rect.centery - handle_size // 2, handle_size,
                                              handle_size)
        pygame.draw.rect(self.screen, (255, 190, 40), self.slider_handle_rect, border_radius=10)

        self.buttons['raise'] = raise_rect
        raise_color = BUTTON_HOVER_COLORS['raise'] if raise_rect.collidepoint(mouse_pos) else BUTTON_COLORS['raise']
        pygame.draw.rect(self.screen, raise_color, raise_rect, border_radius=10)
        if self.slider_current_raise >= self.slider_max_raise:
            raise_label = "All-In"
        else:
            raise_label = f"${self.slider_current_raise}"

        raise_text_title = self.font.render("Raise To", True, (0, 0, 0))
        raise_text_amount = self.font_small.render(raise_label, True, (0, 0, 0))
        self.screen.blit(raise_text_title,
                         raise_text_title.get_rect(centerx=raise_rect.centerx, y=raise_rect.y + int(8 * self.scale_h)))
        self.screen.blit(raise_text_amount, raise_text_amount.get_rect(centerx=raise_rect.centerx,
                                                                       y=raise_rect.y + int(30 * self.scale_h)))

    def start_graphics_mode(self):
        self.init_pygame()
        clock = pygame.time.Clock()
        auto_start_timer = 0
        while self.is_running:
            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                    self.is_running = False
                self.log_box.handle_event(event)

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.slider_handle_rect and self.slider_handle_rect.collidepoint(event.pos):
                        self.slider_dragging = True
                    else:
                        for action_label, rect in self.buttons.items():
                            if rect.collidepoint(event.pos):
                                if action_label == 'raise':
                                    amount = self.slider_current_raise
                                    if amount >= self.slider_max_raise: amount = self.slider_max_raise
                                    self.send_action({"action": "raise", "amount": amount})
                                else:
                                    self.send_action({"action": action_label})
                                break

                elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    self.slider_dragging = False

                elif event.type == pygame.MOUSEMOTION and self.slider_dragging:
                    if self.slider_track_rect:
                        relative_x = event.pos[0] - self.slider_track_rect.x
                        progress = max(0, min(1, relative_x / self.slider_track_rect.width))
                        raise_range = self.slider_max_raise - self.slider_min_raise
                        amount = self.slider_min_raise + int(progress * raise_range)
                        if progress > 0.98:
                            self.slider_current_raise = self.slider_max_raise
                        else:
                            self.slider_current_raise = amount

            with self.lock:
                game_stage = self.state.get('game_stage')
                if game_stage == "PREFLOP" and self.last_game_stage != "PREFLOP":
                    self.log_box.add_log("--- New Round ---")
                    self.last_log_count = 0

                current_logs = self.state.get('log', [])
                if len(current_logs) > self.last_log_count:
                    new_logs = current_logs[self.last_log_count:]
                    for log in new_logs: self.log_box.add_log(log); print(f"> {log}")
                    self.last_log_count = len(current_logs)

                self.last_game_stage = game_stage

                players = self.state.get('players', [])
                if game_stage in ["END", "WAITING"] and len(players) >= 2 and players[0]['player_id'] == self.player_id:
                    players_with_money = [p for p in players if p['stack'] > 0]
                    if len(players_with_money) >= 2:
                        auto_start_timer += clock.get_time()
                        if auto_start_timer > 8000: self.send_action({"action": "start_round"}); auto_start_timer = 0
                    else:
                        auto_start_timer = 0
                else:
                    auto_start_timer = 0

            self.draw_game()
            clock.tick(60)
        pygame.quit()


if __name__ == "__main__":
    client = GameClient()
    client.start()