import socket
import threading
import json
from game_logic import Game
import time

# --- Server Configuration ---
HOST = '0.0.0.0'  # Listen on all available network interfaces
TCP_PORT = 12345
UDP_PORT = 12346  # Port for discovery broadcasts
BROADCAST_MESSAGE = "POKER_SERVER_DISCOVERY"

# --- Shared State ---
# These objects are shared across all client threads
game = Game()
clients = {}  # Dictionary to store client connections and their player_id
lock = threading.Lock()

def udp_broadcast_thread():
    """Broadcasts the server's presence on the network via UDP."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        # Message includes the main TCP port the game is running on
        message = f"{BROADCAST_MESSAGE}:{TCP_PORT}".encode('utf-8')
        while True:
            sock.sendto(message, ('<broadcast>', UDP_PORT))
            time.sleep(5) # Broadcast every 5 seconds

def broadcast_state():
    """
    Sends the current game state to all connected clients.
    Each client receives a personalized state (e.g., only they can see their cards).
    """
    with lock:
        if not clients:
            return
        # Create a list of clients to iterate over to avoid issues if clients disconnect
        current_clients = list(clients.items())
        for player_id, conn in current_clients:
            try:
                state = game.get_state(for_player_id=player_id)
                conn.sendall(json.dumps(state).encode('utf-8'))
            except (socket.error, BrokenPipeError):
                # If sending fails, the client has likely disconnected.
                print(f"Client {player_id} disconnected. Removing.")
                del clients[player_id]
                # Optional: Handle player removal from the game if they disconnect mid-hand
                player_to_remove = next((p for p in game.players if p.player_id == player_id), None)
                if player_to_remove and player_to_remove.is_playing:
                    player_to_remove.fold()
                    # After removing, we might need to check the game end condition again
                    game._check_round_or_game_end()


def handle_client(conn, addr):
    """
    This function runs in a separate thread for each client.
    It handles joining, actions, and disconnections.
    """
    player_id = None
    try:
        # 1. Handle Player Join
        join_data = json.loads(conn.recv(1024).decode('utf-8'))
        if join_data.get("action") == "join":
            player_id = f"{addr[0]}:{addr[1]}"  # Unique ID based on host/port
            player_name = join_data.get("name", "Player")

            with lock:
                clients[player_id] = conn
                game.add_player(name=player_name, stack=1000, player_id=player_id)

            print(f"Player {player_name} ({player_id}) has joined.")
            broadcast_state()

        # 2. Listen for Player Actions
        while True:
            message = conn.recv(4096).decode('utf-8')
            if not message:
                break

            action_data = json.loads(message)
            action = action_data.get("action")

            with lock:
                current_player_data = game.players[
                    game.current_player_index] if game.current_player_index != -1 else None

                if action in ["fold", "call", "raise", "check"]:
                    # --- ADD THIS CHECK ---
                    if game.game_stage in ["WAITING", "END"]:
                        continue # Ignore player actions when no game is active
                    # --- END ADD ---
                    if current_player_data and current_player_data.player_id == player_id:
                        game.process_action(player_id, action, action_data.get("amount", 0))
                    else:
                        print(f"Ignoring out-of-turn action from {player_id}")

                # --- THIS BLOCK IS THE FIX ---
                elif action == "start_round":
                    if game.game_stage in ["END", "WAITING"]:
                        # Check if there are enough players with chips to start a new round
                        players_with_money = [p for p in game.players if p.stack > 0]
                        if len(players_with_money) < 2:
                            game.log.append("Game over. Not enough players to continue.")
                            print("Game over. Not enough players to continue.")
                        else:
                            print("A player requested to start a new round.")
                            game.start_round()

            broadcast_state()

    except (ConnectionResetError, json.JSONDecodeError, UnicodeDecodeError) as e:
        print(f"An error occurred with client {addr}: {e}")
    finally:
        # (The finally block remains the same)
        if player_id:
            print(f"Player {player_id} has disconnected.")
            with lock:
                if player_id in clients:
                    del clients[player_id]
                player_to_remove = next((p for p in game.players if p.player_id == player_id), None)
                if player_to_remove:
                    game.players.remove(player_to_remove)
                    # If they were in a hand, fold them
                    if player_to_remove.is_playing:
                        player_to_remove.fold()
                        game._check_round_or_game_end()
        conn.close()
        broadcast_state()

def main_server():
    """The main function to run the poker server."""
    # Start the UDP broadcast thread
    broadcast_t = threading.Thread(target=udp_broadcast_thread, daemon=True)
    broadcast_t.start()
    print("Server discovery broadcast started.")

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, TCP_PORT))
    server_socket.listen()
    print(f"Poker server listening for game connections on TCP port {TCP_PORT}")
    game.game_stage = "WAITING"

    while True:
        conn, addr = server_socket.accept()
        print(f"New game connection from {addr}")
        thread = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
        thread.start()

if __name__ == '__main__':
    main_server()

if __name__ == '__main__':
    if OFFLINE_TESTING:
        # Keeping the offline loop for easy testing
        from offline_test_loop import offline_game_loop

        offline_game_loop()
    else:
        main_server()