# Online Poker

A game of Texas Hold'em poker online with UDP server discovery, enabling players to find and join games seamlessly on a local network.

## Features

- **Texas Hold'em Poker**: Play the classic poker variant with friends or AI.
- **Network Play**: Utilizes UDP server discovery so players can easily find and connect to poker games running on the same network.
- **Client-Server Architecture**: 
  - `Server.py` handles game management, player connections, and network communication.
  - `Client.py` provides the user interface and connects players to running games.
- **Game Logic**: All rules, hands evaluation, and betting logic are contained in `game_logic.py`.
- **Offline Testing**: Use `offline_test_loop.py` to simulate and test game behavior without requiring multiple clients.
- **Card Assets**: The `cards/` directory contains graphical or data resources for card representation.

## Getting Started

### Prerequisites

- Python 3.x

### Running the Server

```bash
python Server.py
```

### Joining a Game as a Client

```bash
python Client.py
```

Clients will automatically discover servers available on the local network.

### Offline Testing

To test game logic and simulate gameplay without a network:

```bash
python offline_test_loop.py
```

## Project Structure

- `Server.py` &mdash; Starts a poker server and manages sessions.
- `Client.py` &mdash; Connects to servers, interacts with users.
- `game_logic.py` &mdash; Implements the rules and logic of Texas Hold'em.
- `offline_test_loop.py` &mdash; Used for testing the game loop and logic (DO NOT USE).
- `cards/` &mdash; Card assets for the game.
- `.idea/` &mdash; Project files for IDE configuration (can be ignored for gameplay).

## License

This project currently does not specify a license.

## Author

[Micocono123](https://github.com/Micocono123)
