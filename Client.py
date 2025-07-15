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
            self.draw_buttons()
            self.log_box.draw(self.screen)  # Draw the scrollable log box
            if self.is_input_active: self.draw_input_box()
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
            if not player.get('is_spectator'):
                for j, card in enumerate(player['cards']):
                    card_img = self.card_images.get(f"{card['rank']}{card['suit']}")
                    if card_img:
                        is_top_row_pos = pos[1] <= 180
                        card_y_offset = pos[1] + 90 if is_top_row_pos else pos[1] - 140
                        self.screen.blit(card_img, (pos[0] + j * 50, card_y_offset))

        if not player.get('is_playing'):
            fold_text = self.font.render("FOLDED", True, (255, 0, 0))
            self.screen.blit(fold_text, (pos[0] + 50, pos[1] - 50))

    def draw_buttons(self):
        players, current_player_idx = self.state.get('players', []), self.state.get('current_player_index')
        if current_player_idx is None or not players: return
        current_player = players[current_player_idx]
        if not (current_player.get('player_id') == self.player_id and current_player.get('is_playing')):
            return
        button_y, button_width, button_height, mouse_pos = 650, 120, 50, pygame.mouse.get_pos()
        actions = {"fold": (750, button_y)}
        can_check = current_player.get('bet_this_street', 0) == self.state.get('current_bet', 0)
        if can_check:
            actions["check"] = (880, button_y)
        else:
            actions[f"call ${self.state.get('current_bet', 0) - current_player.get('bet_this_street', 0)}"] = (
            880, button_y)
        actions["raise"] = (1010, button_y)
        self.buttons.clear()
        for action_label, pos in actions.items():
            rect = pygame.Rect(pos[0], pos[1], button_width, button_height)
            self.buttons[action_label] = rect
            color = (200, 200, 0) if rect.collidepoint(mouse_pos) else (255, 255, 0)
            pygame.draw.rect(self.screen, color, rect, border_radius=10)
            text = self.font.render(action_label.split(" ")[0].title(), True, (0, 0, 0))
            self.screen.blit(text, text.get_rect(center=rect.center))

    def draw_input_box(self):
        pygame.draw.rect(self.screen, (50, 50, 50), (400, 300, 480, 100), border_radius=10)
        prompt_surf = self.font.render(self.input_prompt, True, (255, 255, 255))
        self.screen.blit(prompt_surf, (410, 310))
        input_surf = self.font.render(self.input_text, True, (255, 255, 255))
        self.screen.blit(input_surf, (410, 350))

    def start_graphics_mode(self):
        self.init_pygame(); clock = pygame.time.Clock(); auto_start_timer = 0
        while self.is_running:
            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT: self.is_running = False
                self.log_box.handle_event(event)
                if self.is_input_active:
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_RETURN:
                            try:
                                if self.input_text: self.send_action({"action": "raise", "amount": int(self.input_text)})
                            except ValueError: pass
                            self.is_input_active, self.input_text = False, ""
                        elif event.key == pygame.K_BACKSPACE: self.input_text = self.input_text[:-1]
                        else: self.input_text += event.unicode
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for action_label, rect in self.buttons.items():
                        if rect.collidepoint(event.pos):
                            action = action_label.split(" ")[0]
                            if action == "raise": self.is_input_active, self.input_prompt = True, "Raise to amount:"
                            else: self.send_action({"action": action})
                            break
            
            with self.lock:
                game_stage = self.state.get('game_stage')
                
                # --- THIS IS THE FIX ---
                # Detect the start of a new hand to reset log tracking
                if game_stage == "PREFLOP" and self.last_game_stage != "PREFLOP":
                    # When a new hand starts, reset the log counter but don't clear the visual log
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
                    else: auto_start_timer = 0
                else: auto_start_timer = 0

            self.draw_game(); clock.tick(30)
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