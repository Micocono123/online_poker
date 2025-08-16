import socket
import json
import os
import time
import pygame
import threading

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
        # Auto-scroll to the bottom when a new message is added
        self.scroll_y = max(0, len(self.all_logs) * self.line_height - self.rect.height)

    def handle_event(self, event):
        if event.type == pygame.MOUSEWHEEL:
            self.scroll_y -= event.y * self.line_height
            # Clamp scroll position
            max_scroll = max(0, len(self.all_logs) * self.line_height - self.rect.height)
            self.scroll_y = max(0, min(self.scroll_y, max_scroll))

    def draw(self, surface):
        # Draw background
        bg_surface = pygame.Surface(self.rect.size, pygame.SRCALPHA)
        bg_surface.fill(self.bg_color)
        surface.blit(bg_surface, self.rect.topleft)

        # Draw visible text
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
        self.screen, self.font, self.font_small, self.font_log = None, None, None, None
        self.card_images, self.buttons = {}, {}
        self.dealer_chip_img = None
        self.is_input_active = False
        self.input_text, self.input_prompt = "", ""
        self.log_box = None
        self.last_log_count = 0
        self.is_input_active, self.input_text, self.input_prompt = False, "", ""
        self.last_game_stage = "" # Add this line

        # Slider state management
        self.slider_track_rect = None  # We will define this rect in the drawing function
        self.slider_handle_rect = None
        self.slider_min_raise = 0
        self.slider_max_raise = 0
        self.slider_current_raise = 0
        self.slider_dragging = False

    def network_thread(self):
        while self.is_running:
            try:
                data_buffer = self.client_socket.recv(8192)
                data_buffer.decode('utf-8')
                if not data_buffer: self.is_running = False; break
                with self.lock:
                    self.state = json.loads(data_buffer)
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
            print("Failed to send action."); self.is_running = False

    def start(self):
        # --- DISCOVERY LOGIC ---
        self.server_host, self.server_port = discover_server()
        if not self.server_host:
            print("Could not find server. Exiting.")
            return

        mode = "g" # Graphic
        try:
            self.client_socket.connect((self.server_host, self.server_port))
            print("Connected to the game server.")
            self.player_name = input("Enter your name: ")
            self.send_action({"action": "join", "name": self.player_name})
            n_thread = threading.Thread(target=self.network_thread, daemon=True); n_thread.start()
            if mode == 'g': self.start_graphics_mode()
            else: self.start_text_mode()
        except (ConnectionRefusedError, ConnectionResetError) as e: print(f"\nConnection error: {e}")
        finally:
            print("Closing connection."); self.is_running = False; self.client_socket.close()


    # --- GRAPHICS MODE ---
    def init_pygame(self):
        pygame.init()
        self.screen = pygame.display.set_mode((1280, 720))
        pygame.display.set_caption(f"Poker Client - {self.player_name}")
        self.font, self.font_small = pygame.font.SysFont("Arial", 22), pygame.font.SysFont("Arial", 18, bold=True)
        self.font_log = pygame.font.SysFont("Consolas", 16)
        self.log_box = ScrollableLogBox((10, 580, 500, 130), self.font_log)
        self.dealer_chip_img = pygame.Surface((30, 30), pygame.SRCALPHA)
        pygame.draw.circle(self.dealer_chip_img, (255, 255, 255), (15, 15), 15)
        dealer_text = self.font_small.render("D", True, (0, 0, 0))
        self.dealer_chip_img.blit(dealer_text, dealer_text.get_rect(center=(15, 15)))
        self.load_card_images()

    def load_card_images(self):
        RANK_TO_FILENAME = {"A": "ace", "K": "king", "Q": "queen", "J": "jack", "10": "10", "9": "9", "8": "8",
                            "7": "7", "6": "6", "5": "5", "4": "4", "3": "3", "2": "2"}
        server_ranks, server_suits = list(RANK_TO_FILENAME.keys()), ["Hearts", "Diamonds", "Clubs", "Spades"]
        card_size = (90, 130)
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
            self.log_box.draw(self.screen)  # Draw the scrollable log box
        pygame.display.flip()

    def draw_community_cards(self):
        cards = self.state.get('community_cards', [])
        start_x = (1280 - len(cards) * 100) / 2
        for i, card in enumerate(cards):
            card_img = self.card_images.get(f"{card['rank']}{card['suit']}")
            if card_img: self.screen.blit(card_img, (start_x + i * 100, 280))

    def draw_pot(self):
        pot_text = self.font.render(f"Pot: ${self.state.get('pot', 0)}", True, (255, 255, 0))
        text_rect = pot_text.get_rect(center=(1280 / 2, 250))
        self.screen.blit(pot_text, text_rect)

    def draw_players(self):
        players = self.state.get('players', [])
        me = next((p for p in players if p['player_id'] == self.player_id), None)
        if not me: return

        # --- FIX: Simplified and corrected player drawing logic ---

        # All available seat positions
        positions = [(550, 580), (150, 420), (150, 180), (550, 80), (950, 180), (950, 420)]

        # Separate "me" from "others"
        other_players = [p for p in players if p['player_id'] != self.player_id and not p.get('is_spectator')]

        # Always draw "me" at the bottom position
        self._draw_one_player(me, positions[0], is_me=True)

        # Draw other players in the remaining seats
        for i, player in enumerate(other_players):
            # We use i + 1 to skip the first position, which is reserved for "me"
            self._draw_one_player(player, positions[i + 1], is_me=False)

    def _draw_one_player(self, player, pos, is_me):
        """Helper function to draw a single player's UI elements."""
        all_players = self.state.get('players', [])
        original_index = all_players.index(player)

        is_dealer, is_sb, is_bb = (self.state.get(k) == original_index for k in
                                   ['dealer_pos', 'sb_player_index', 'bb_player_index'])
        is_current_turn = self.state.get('current_player_index') == original_index
        box_color = (200, 200, 0) if is_current_turn else (40, 40, 40)

        if player.get('is_spectator'):
            box_color = (20, 20, 20)

        pygame.draw.rect(self.screen, box_color, (pos[0], pos[1], 180, 80), border_radius=10)

        if player.get('is_spectator'):
            spec_text = self.font.render("SPECTATOR", True, (200, 200, 200))
            self.screen.blit(spec_text, (pos[0] + 30, pos[1] - 30))

        for j, (text, color) in enumerate([(player['name'], (255, 255, 255)), (f"${player['stack']}", (255, 255, 255)),
                                           (f"Bet: ${player['bet_this_street']}", (255, 255, 0))]):
            self.screen.blit(self.font.render(text, True, color), (pos[0] + 10, pos[1] + 5 + j * 25))

        if is_dealer: self.screen.blit(self.dealer_chip_img, (pos[0] + 140, pos[1] + 5))
        if is_sb: self.screen.blit(self.font_small.render("SB", True, (232, 10, 252)), (pos[0] + 145, pos[1] + 30))
        if is_bb: self.screen.blit(self.font_small.render("BB", True, (10, 252, 232)), (pos[0] + 145, pos[1] + 50))

        # The server now correctly includes the 'cards' key for all showdown players.
        # This client logic simply draws them if they exist.
        if 'cards' in player and player['cards']:
            if not player.get('is_spectator') and player.get('is_playing'):
                for j, card in enumerate(player['cards']):
                    card_img = self.card_images.get(f"{card['rank']}{card['suit']}")
                    if card_img:
                        is_top_row_pos = pos[1] < 180 # IMPORTANT PART
                        card_y_offset = pos[1] + 90 if is_top_row_pos else pos[1] - 140
                        self.screen.blit(card_img, (pos[0] + j * 50, card_y_offset))

        if not player.get('is_playing'):
            if not player.get('is_spectator'):
                fold_text = self.font.render("FOLDED", True, (255, 0, 0))
                self.screen.blit(fold_text, (pos[0] + 50, pos[1] - 50))

    def draw_action_ui(self):
        """Draws the complete action interface: buttons and the integrated raise slider."""
        players = self.state.get('players', [])
        current_player_idx = self.state.get('current_player_index')

        # 1. Determine if the action UI should be visible
        is_my_turn = False
        me = None
        if current_player_idx is not None and current_player_idx < len(players):
            current_player = players[current_player_idx]
            me = next((p for p in players if p['player_id'] == self.player_id), None)
            if me and current_player['player_id'] == self.player_id and me['is_playing']:
                is_my_turn = True

        if not is_my_turn:
            self.slider_dragging = False  # Stop dragging if it's no longer our turn
            return

        # --- UI Layout & Sizing (No changes here) ---
        BUTTON_WIDTH, BUTTON_HEIGHT, BUTTON_GAP = 120, 50, 10
        start_x = 760
        UI_Y_BUTTONS = 585
        UI_Y_SLIDER = UI_Y_BUTTONS + BUTTON_HEIGHT + 15
        total_ui_width = (BUTTON_WIDTH * 3) + (BUTTON_GAP * 2)

        mouse_pos = pygame.mouse.get_pos()
        self.buttons.clear()

        # 2. Define Button Colors and Rects (No changes here)
        BUTTON_COLORS = {'fold': (200, 40, 40), 'call': (40, 180, 40), 'check': (40, 180, 40), 'raise': (230, 150, 0)}
        BUTTON_HOVER_COLORS = {'fold': (255, 60, 60), 'call': (60, 230, 60), 'check': (60, 230, 60),
                               'raise': (255, 190, 40)}

        fold_rect = pygame.Rect(start_x, UI_Y_BUTTONS, BUTTON_WIDTH, BUTTON_HEIGHT)
        call_check_rect = pygame.Rect(start_x + BUTTON_WIDTH + BUTTON_GAP, UI_Y_BUTTONS, BUTTON_WIDTH, BUTTON_HEIGHT)
        raise_rect = pygame.Rect(start_x + (BUTTON_WIDTH + BUTTON_GAP) * 2, UI_Y_BUTTONS, BUTTON_WIDTH, BUTTON_HEIGHT)

        # 3. Draw Fold Button (No changes here)
        self.buttons['fold'] = fold_rect
        fold_color = BUTTON_HOVER_COLORS['fold'] if fold_rect.collidepoint(mouse_pos) else BUTTON_COLORS['fold']
        pygame.draw.rect(self.screen, fold_color, fold_rect, border_radius=10)
        fold_text = self.font.render("Fold", True, (0, 0, 0))
        self.screen.blit(fold_text, fold_text.get_rect(center=fold_rect.center))

        # 4. Draw Call/Check Button
        current_bet = self.state.get('current_bet', 0)
        can_check = me.get('bet_this_street', 0) == current_bet

        if can_check:
            self.buttons['check'] = call_check_rect
            label, color_key = "Check", 'check'
        else:
            # --- UPDATE: Change Call button to "Call To" display ---
            self.buttons['call'] = call_check_rect
            # The label now shows the total bet amount, not the difference.
            label, color_key = f"Call ${current_bet}", 'call'

        cc_color = BUTTON_HOVER_COLORS[color_key] if call_check_rect.collidepoint(mouse_pos) else BUTTON_COLORS[
            color_key]
        pygame.draw.rect(self.screen, cc_color, call_check_rect, border_radius=10)
        cc_text = self.font.render(label, True, (0, 0, 0))
        self.screen.blit(cc_text, cc_text.get_rect(center=call_check_rect.center))

        # 5. Calculate Raise Slider Values (No changes here)
        my_bet = me.get('bet_this_street', 0)
        last_raise_amount = self.state.get('last_raise_amount', self.state.get('big_blind_amount', 20))
        min_r = current_bet + last_raise_amount

        self.slider_min_raise = min(min_r, me['stack'] + my_bet)
        self.slider_max_raise = me['stack'] + my_bet

        if not self.slider_dragging:
            self.slider_current_raise = self.slider_min_raise

        # 6. Draw the Slider (No changes here)
        self.slider_track_rect = pygame.Rect(start_x, UI_Y_SLIDER, total_ui_width, 10)
        pygame.draw.rect(self.screen, (80, 80, 80), self.slider_track_rect, border_radius=5)
        raise_range = self.slider_max_raise - self.slider_min_raise
        progress = (self.slider_current_raise - self.slider_min_raise) / raise_range if raise_range > 0 else 1.0
        handle_x = self.slider_track_rect.x + int(progress * self.slider_track_rect.width)
        self.slider_handle_rect = pygame.Rect(handle_x - 10, self.slider_track_rect.centery - 10, 20, 20)
        pygame.draw.rect(self.screen, (255, 190, 40), self.slider_handle_rect, border_radius=10)

        # 7. Draw the Dynamic Raise Button (No changes here)
        self.buttons['raise'] = raise_rect
        raise_color = BUTTON_HOVER_COLORS['raise'] if raise_rect.collidepoint(mouse_pos) else BUTTON_COLORS['raise']
        pygame.draw.rect(self.screen, raise_color, raise_rect, border_radius=10)

        if self.slider_current_raise >= self.slider_max_raise:
            raise_label = "All-In"
        else:
            raise_label = f"${self.slider_current_raise}"

        raise_text_title = self.font.render("Raise To", True, (0, 0, 0))
        raise_text_amount = self.font_small.render(raise_label, True, (0, 0, 0))
        self.screen.blit(raise_text_title, raise_text_title.get_rect(centerx=raise_rect.centerx, y=raise_rect.y + 8))
        self.screen.blit(raise_text_amount, raise_text_amount.get_rect(centerx=raise_rect.centerx, y=raise_rect.y + 30))

    def start_graphics_mode(self):
        self.init_pygame()
        clock = pygame.time.Clock()
        auto_start_timer = 0
        while self.is_running:
            mouse_pos = pygame.mouse.get_pos()
            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT: self.is_running = False
                self.log_box.handle_event(event)

                # --- NEW, SIMPLIFIED EVENT HANDLING ---
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    # Check for slider drag
                    if self.slider_handle_rect and self.slider_handle_rect.collidepoint(event.pos):
                        self.slider_dragging = True
                    else:
                        # Check for button clicks
                        for action_label, rect in self.buttons.items():
                            if rect.collidepoint(event.pos):
                                if action_label == 'raise':
                                    amount = self.slider_current_raise
                                    # Ensure the final raise amount is valid before sending
                                    if amount >= self.slider_max_raise:
                                        amount = self.slider_max_raise
                                    self.send_action({"action": "raise", "amount": amount})
                                else:
                                    self.send_action({"action": action_label})
                                break

                elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    self.slider_dragging = False

                elif event.type == pygame.MOUSEMOTION and self.slider_dragging:
                    if self.slider_track_rect:
                        # Calculate position relative to the start of the track
                        relative_x = event.pos[0] - self.slider_track_rect.x
                        progress = max(0, min(1, relative_x / self.slider_track_rect.width))

                        raise_range = self.slider_max_raise - self.slider_min_raise
                        amount = self.slider_min_raise + int(progress * raise_range)

                        # Add snapping for the all-in
                        if progress > 0.98:
                            self.slider_current_raise = self.slider_max_raise
                        else:
                            self.slider_current_raise = amount

                # --- UPDATED BUTTON CLICK HANDLING ---
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for action_label, rect in self.buttons.items():
                        if rect.collidepoint(event.pos):
                            action = action_label.split(" ")[0]
                            if action == "raise":
                                self._activate_slider()  # Activate our new slider
                            else:
                                self.send_action({"action": action})
                            break

            with self.lock:
                game_stage = self.state.get('game_stage')
                if game_stage == "PREFLOP" and self.last_game_stage != "PREFLOP":
                    self.log_box.add_log("--- New Round ---")
                    self.last_log_count = 0

                current_logs = self.state.get('log', [])
                if len(current_logs) > self.last_log_count:
                    new_logs = current_logs[self.last_log_count:]
                    for log in new_logs:
                        self.log_box.add_log(log)
                        print(f"> {log}")
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
            clock.tick(30)
        pygame.quit()

    # --- TEXT MODE ---
    def start_text_mode(self):
        last_state = None
        while self.is_running:
            with self.lock:
                current_state = self.state
            if current_state != last_state: self.display_state_text(current_state); last_state = current_state
            time.sleep(0.1)

    def display_state_text(self, state):
        if state and state.get('game_stage') != "END":
            os.system('cls' if os.name == 'nt' else 'clear')
        print("\n--- Texas Hold'em Poker (Text Mode) ---")
        if not state: return
        community_cards_str = ' '.join(
            [f"{c['rank']}{self.SUIT_EMOJIS.get(c['suit'])}" for c in state.get('community_cards', [])])
        print(
            f"Community Cards: [ {community_cards_str} ]\tPot: ${state.get('pot', 0)}\tStage: {state.get('game_stage')}")
        print("-" * 40)
        is_showdown = state.get('game_stage') in ["SHOWDOWN", "END"]
        for i, p in enumerate(state.get('players', [])):
            player_info = f"{p['name']} (Stack: ${p['stack']}) Bet: ${p['current_bet']}"
            if i == state.get('dealer_pos'): player_info += " (D)"
            if not p.get('is_playing'): player_info += " (Folded)";
            if p.get('is_all_in'): player_info += " (ALL-IN)"
            if 'cards' in p and p['cards']:
                cards_str = ' '.join([f"{c['rank']}{self.SUIT_EMOJIS.get(c['suit'])}" for c in p['cards']])
                if p.get('player_id') == self.player_id:
                    player_info += f" -> YOUR HAND: [ {cards_str} ]"
                elif is_showdown:
                    player_info += f" | Hand: [ {cards_str} ]"
            print(player_info)
        print("-" * 40)
        [print(f"> {log}") for log in state.get('log', [])[-len(self.log_box.all_logs):]]
        self.handle_turn_text(state)

    def handle_turn_text(self, state):
        game_stage = state.get('game_stage', '')
        if game_stage in ["PREFLOP", "FLOP", "TURN", "RIVER"] and state.get('current_player_index') is not None:
            current_player = state['players'][state['current_player_index']]
            if current_player.get('player_id') == self.player_id and current_player.get('is_playing'):
                print("\n--- YOUR TURN ---")
                self.prompt_for_action_text(current_player, state.get('current_bet', 0))
        elif game_stage in ["END", "WAITING"]:
            players_with_money = [p for p in state.get('players', []) if p.get('stack', 0) > 0]
            if len(players_with_money) >= 2 and state.get('players', [])[0]['player_id'] == self.player_id:
                print("\nRequesting new round in 8 seconds...")
                time.sleep(8)
                self.send_action({"action": "start_round"})

    def prompt_for_action_text(self, me, current_bet):
        street_bet = me.get('bet_this_street', 0)
        can_check = street_bet == current_bet
        prompt = "Actions: (f)old"
        if can_check:
            prompt += ", (c)heck"
        else:
            prompt += f", (c)all ${current_bet - street_bet}"
        prompt += ", (r)aise > "
        action_input = input(prompt).lower().strip()
        action_data = None
        if action_input == 'f':
            action_data = {"action": "fold"}
        elif action_input == 'c':
            action_data = {"action": "check"} if can_check else {"action": "call"}
        elif action_input == 'r':
            try:
                action_data = {"action": "raise", "amount": int(input("Raise to amount: "))}
            except ValueError:
                print("Invalid amount.")
        if action_data: self.send_action(action_data)


if __name__ == "__main__":
    client = GameClient()
    client.start()