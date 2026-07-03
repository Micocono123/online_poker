# 🃏 Online Multiplayer Texas Hold'em Poker

A fully featured, networked **Texas Hold'em Poker** game built entirely in **Python**. This project includes a custom graphical interface, automatic local network server discovery, and a complete poker engine capable of handling complex game scenarios such as split pots, side pots, and all-in situations.

---

## ✨ Features

- 🌐 **Local Network Multiplayer**
  - Play with up to **6 players** over a local network using a reliable TCP socket server.

- 📡 **Zero-Configuration Server Discovery**
  - Clients automatically locate active servers using UDP broadcasts on **port 12346**, eliminating the need to manually enter an IP address.

- 🖥️ **Dynamic Graphical Interface**
  - Responsive fullscreen interface built with **Pygame** and **PyAutoGUI**.
  - Automatically scales to the user's display resolution.

- 🎮 **Interactive User Interface**
  - Betting slider
  - Dynamic action buttons (Fold, Check, Call, Raise)
  - Scrollable real-time action log

- ♠️ **Complete Poker Engine**
  - Full Texas Hold'em rules implementation
  - Accurate hand evaluation from **High Card** to **Royal Flush**
  - Proper betting rounds
  - Split pot handling
  - Side pot support
  - All-in logic

---
## Screenshot

<img width="1920" height="1080" alt="image" src="https://github.com/user-attachments/assets/48b21fc1-ed0b-4b94-a747-74d1a8d3f091" />

---

## 📦 Prerequisites

- Python 3.x

### Required Libraries

- `pygame`
- `pyautogui`

Install them with:

```bash
pip install pygame pyautogui
```

---

# 🚀 Getting Started

To play the game, use **only** the following scripts:

- `Server.py`
- `Client.py`

---

## 1️⃣ Host a Game

Run the server on the host machine:

```bash
python Server.py
```

The server will:

- Listen for TCP game connections on **port 12345**
- Broadcast its presence over UDP on **port 12346**

---

## 2️⃣ Join the Game

On each client machine, run:

```bash
python Client.py
```

The client will:

1. Search the local network for an active server.
2. Automatically connect when one is found.
3. Launch the graphical interface.
4. Prompt the user in the console to enter a display name.

---

## 🧪 Offline Testing

The project also includes:

```
offline_test_loop.py
```

This script was created **only for development and debugging**.

It allows testing of:

- Hand evaluation
- Pot distribution
- Betting logic
- Side pots
- Split pots

without requiring networking or the graphical interface.

> **Note:** This script is **not** intended for actual gameplay.

---

# 📁 Project Structure

```
.
├── Server.py
├── Client.py
├── game_logic.py
├── offline_test_loop.py
└── cards/
    ├── AS.png
    ├── KH.png
    ├── ...
```

### `Server.py`

- Runs the main game loop
- Accepts multiple client connections
- Uses threading for concurrency
- Sends personalized JSON game states to each player

### `Client.py`

- Handles the Pygame GUI
- Processes user input
- Draws the poker table and cards
- Automatically scales the interface
- Manages asynchronous communication with the server

### `game_logic.py`

Contains the complete poker engine, including:

- `Card`
- `Deck`
- `Hand`
- `Player`
- `Game`

Responsibilities include:

- Hand evaluation
- Rule enforcement
- Betting validation
- Pot management
- Turn order
- Game stage progression

### `offline_test_loop.py`

A lightweight command-line simulator used exclusively during development for testing the poker engine.

### `cards/`

Contains the PNG card assets used by the client.

If an image cannot be loaded, the client automatically falls back to rendering a placeholder card, preventing crashes due to missing assets.

---

## ⚙️ Networking

| Protocol | Port | Purpose |
|----------|------|---------|
| TCP | 12345 | Gameplay communication |
| UDP | 12346 | Automatic server discovery |

---

## 🛠 Built With

- Python 3
- Pygame
- PyAutoGUI
- TCP Sockets
- UDP Broadcasting
- JSON
- Threading

---

## 📄 License

This project is licensed under the **MIT License**.

---

## 👤 Author

**Micocono123**
