import random
import collections
from itertools import combinations


class Card:
    """Represents a single playing card. Serializable to a dictionary."""
    VALID_SUITS = ["Hearts", "Diamonds", "Clubs", "Spades"]
    SUIT_EMOJIS = {"Hearts": '♥️', "Diamonds": '♦️', "Clubs": '♣️', "Spades": '♠️'}
    RANK_MAP = {"2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9, "10": 10, "J": 11, "Q": 12, "K": 13,
                "A": 14}

    def __init__(self, rank, suit):
        if rank not in self.RANK_MAP or suit not in self.VALID_SUITS:
            raise ValueError("Invalid card rank or suit.")
        self.rank = rank
        self.suit = suit
        self.value = self.RANK_MAP[rank]

    def __repr__(self):
        return f"{self.rank}{self.SUIT_EMOJIS[self.suit]}"

    def __eq__(self, other):
        return self.value == other.value

    def __lt__(self, other):
        return self.value < other.value

    def __gt__(self, other):
        return self.value > other.value

    def to_dict(self):
        return {"rank": self.rank, "suit": self.suit}


class Deck:
    """Represents a standard 52-card deck."""

    def __init__(self):
        self.cards = [Card(rank, suit) for suit in Card.VALID_SUITS for rank in Card.RANK_MAP]
        self.shuffle()  # CRITICAL FIX: Deck is now shuffled on creation.

    def shuffle(self):
        random.shuffle(self.cards)

    def deal(self):
        return self.cards.pop() if self.cards else None


class Hand:
    """Holds and evaluates a set of 5 cards. The hand is evaluated upon creation."""
    HAND_RANKINGS = {
        "High Card": 1, "Pair": 2, "Two Pair": 3, "Three of a Kind": 4,
        "Straight": 5, "Flush": 6, "Full House": 7, "Four of a Kind": 8,
        "Straight Flush": 9, "Royal Flush": 10
    }

    def __init__(self, cards):
        if len(cards) != 5:
            raise ValueError("Hand must be initialized with exactly 5 cards.")
        self.cards = sorted(cards, key=lambda c: c.value, reverse=True)
        self.rank_name = ""
        self.rank_value = 0
        self._evaluate()

    def __repr__(self):
        return f"Hand({[str(c) for c in self.cards]}, {self.rank_name})"

    def __eq__(self, other_hand):
        return self.rank_value == other_hand.rank_value and self._get_hand_signature() == other_hand._get_hand_signature()

    def __gt__(self, other_hand):
        if self.rank_value != other_hand.rank_value:
            return self.rank_value > other_hand.rank_value
        return self._get_hand_signature() > other_hand._get_hand_signature()

    def _get_hand_signature(self):
        value_counts = collections.defaultdict(int)
        for card in self.cards:
            value_counts[card.value] += 1
        return sorted(value_counts.keys(), key=lambda v: (value_counts[v], v), reverse=True)

    def _evaluate(self):
        is_flush = len(set(c.suit for c in self.cards)) == 1
        card_values = [c.value for c in self.cards]
        unique_values = sorted(list(set(card_values)))
        is_straight = len(unique_values) == 5 and (unique_values[-1] - unique_values[0] == 4)
        is_ace_low_straight = unique_values == [2, 3, 4, 5, 14]
        if is_ace_low_straight:
            is_straight = True
        counts = collections.Counter(card_values)
        count_values = sorted(counts.values(), reverse=True)
        if is_straight and is_flush:
            self.rank_name = "Royal Flush" if unique_values == [10, 11, 12, 13, 14] else "Straight Flush"
        elif count_values[0] == 4:
            self.rank_name = "Four of a Kind"
        elif count_values == [3, 2]:
            self.rank_name = "Full House"
        elif is_flush:
            self.rank_name = "Flush"
        elif is_straight:
            self.rank_name = "Straight"
        elif count_values[0] == 3:
            self.rank_name = "Three of a Kind"
        elif count_values == [2, 2, 1]:
            self.rank_name = "Two Pair"
        elif count_values[0] == 2:
            self.rank_name = "Pair"
        else:
            self.rank_name = "High Card"
        self.rank_value = self.HAND_RANKINGS.get(self.rank_name, 0)


class Player:
    """Represents a player. Tracks total investment and current street bet separately."""


    def __init__(self, name, stack, player_id=None):
        self.player_id = player_id or name
        self.name = name
        self.stack = stack
        self.cards = []
        self.current_bet = 0
        self.bet_this_street = 0
        self.has_acted = False
        self.is_playing = True
        self.is_all_in = False
        self.is_spectator = False # Add this line

    def to_dict(self, show_cards=False):
        state = {
            "player_id": self.player_id, "name": self.name, "stack": self.stack,
            "current_bet": self.current_bet, "bet_this_street": self.bet_this_street,
            "has_acted": self.has_acted, "is_playing": self.is_playing,
            "is_all_in": self.is_all_in,
            "is_spectator": self.is_spectator, # Add this line
        }
        if show_cards:
            state["cards"] = [card.to_dict() for card in self.cards]
        return state

    def clear_for_new_round(self):
        self.cards = []
        self.current_bet = 0
        self.bet_this_street = 0
        self.has_acted = False
        self.is_playing = True
        self.is_all_in = False

    def place_bet(self, amount):
        bet_amount = min(amount, self.stack)
        self.stack -= bet_amount
        self.current_bet += bet_amount
        self.bet_this_street += bet_amount
        if self.stack == 0:
            self.is_all_in = True
        self.has_acted = True
        return bet_amount

    def fold(self):
        self.is_playing = False
        self.has_acted = True


class Game:
    """A state machine for a poker game, driven by external actions."""
    STAGES = ["PREFLOP", "FLOP", "TURN", "RIVER", "SHOWDOWN", "END"]

    def __init__(self):
        self.players = []
        self.deck = None
        self.pot = 0
        self.community_cards = []
        self.current_bet = 0
        self.dealer_pos = -1
        self.current_player_index = -1
        # --- ADD THESE LINES ---
        self.sb_player_index = -1
        self.bb_player_index = -1
        # --- END ADD ---
        self.game_stage = "WAITING"
        self.log = []
        self.small_blind_amount = 10
        self.big_blind_amount = 20
        self.last_action_was_fold = False  # Add this line
        self.showdown_players = [] # Add this line

    def add_player(self, name, stack, player_id=None):
        # --- FIX: Limit game to 6 players ---
        if len(self.players) < 6:
            new_player = Player(name, stack, player_id)
            if self.game_stage not in ["WAITING", "END"]:
                new_player.is_playing = False
                self.log.append(f"{name} has joined and will play the next hand.")
            else:
                self.log.append(f"{name} has joined the game.")
            self.players.append(new_player)
        else:
            self.log.append(f"Game is full. Could not add player {name}.")
            print(f"Game is full. Could not add player {name}.")

    def get_state(self, for_player_id=None):
        is_showdown_phase = self.game_stage in ["SHOWDOWN", "END"]

        return {
            "players": [p.to_dict(show_cards=(
                p.player_id == for_player_id or
                (is_showdown_phase and p.player_id in self.showdown_players)
            )) for p in self.players],
            "pot": self.pot, "community_cards": [c.to_dict() for c in self.community_cards],
            "current_bet": self.current_bet,
            "dealer_pos": self.dealer_pos,
            "sb_player_index": self.sb_player_index,
            "bb_player_index": self.bb_player_index,
            "current_player_index": self.current_player_index,
            "game_stage": self.game_stage,
            "log": self.log
        }

    def start_round(self):
        if len(self.players) < 2:
            self.log.append("Not enough players to start.")
            return

        self.showdown_players.clear() # Clear showdown players from the previous round
        self.log.clear()
        self.deck = Deck()
        self.community_cards = []
        self.pot = 0
        self.dealer_pos = (self.dealer_pos + 1) % len(self.players)
        for p in self.players:
            p.clear_for_new_round()
            p.cards = [self.deck.deal(), self.deck.deal()]
        active_players = [p for p in self.players if p.stack > 0]
        if len(active_players) < 2: self.game_stage = "END"; return
        if len(active_players) == 2:
            sb_player_index = self.dealer_pos
            bb_player_index = (self.dealer_pos + 1) % len(self.players)
        else:
            sb_player_index = (self.dealer_pos + 1) % len(self.players)
            bb_player_index = (self.dealer_pos + 2) % len(self.players)

        # --- ADD THESE LINES ---
        self.sb_player_index = sb_player_index
        self.bb_player_index = bb_player_index
        # --- END ADD ---

        sb_player = self.players[sb_player_index]

        sb_player = self.players[sb_player_index]
        sb_amount = sb_player.place_bet(self.small_blind_amount)
        self.pot += sb_amount
        self.log.append(f"{sb_player.name} posts small blind of ${sb_amount}.")

        bb_player = self.players[bb_player_index]
        bb_amount = bb_player.place_bet(self.big_blind_amount)
        self.pot += bb_amount
        self.log.append(f"{bb_player.name} posts big blind of ${bb_amount}.")

        # --- BUG FIX ---
        # Posting blinds is a forced action. Reset 'has_acted' so the blind
        # players get a turn to voluntarily check, bet, or raise later.
        sb_player.has_acted = False
        bb_player.has_acted = False
        # --- END FIX ---

        self.current_bet = self.big_blind_amount
        self.game_stage = "PREFLOP"
        self.current_player_index = (bb_player_index + 1) % len(self.players)
        self.log.append("New round started.")

    def process_action(self, player_id, action, amount=0):
        player = self.players[self.current_player_index]
        if player.player_id != player_id: raise ValueError("It is not this player's turn.")

        self.last_action_was_fold = (action == "fold")

        if action == "fold":
            player.fold() 
            self.log.append(f"{player.name} folds.")
        elif action == "call":
            amount_to_call = self.current_bet - player.bet_this_street
            bet_placed = player.place_bet(amount_to_call) 
            self.pot += bet_placed
            self.log.append(f"{player.name} calls ${bet_placed}.")
        elif action == "raise":
            if amount < self.current_bet * 2 and self.current_bet > 0: raise ValueError("Raise must be at least 2x.")
            amount_to_bet = amount - player.bet_this_street
            bet_placed = player.place_bet(amount_to_bet) 
            self.pot += bet_placed
            self.current_bet = player.bet_this_street 
            self.log.append(f"{player.name} raises to ${self.current_bet}.")
            for p in self.players:
                if p.is_playing and p != player: p.has_acted = False
        elif action == "check":
            if self.current_bet > player.bet_this_street: raise ValueError("Cannot check.")
            player.has_acted = True 
            self.log.append(f"{player.name} checks.")
        else:
            raise ValueError(f"Invalid action: {action}")
        self._check_round_or_game_end()

    def _check_round_or_game_end(self):
        active_players = [p for p in self.players if p.is_playing]
        # CRITICAL FIX: If one player is left, check for all-in players before awarding pot.
        if len(active_players) == 1:
            all_in_players = [p for p in self.players if p.is_all_in]
            if all_in_players:  # If others are all-in, must go to showdown
                self._fast_forward_to_showdown()
            else:  # Otherwise, last active player wins uncontested
                winner = active_players[0]
                winner.stack += self.pot 
                self.pot = 0
                self.log.append(
                    f"{winner.name} wins the pot of ${winner.stack - self.pot} as the last remaining player.")  # Pot was already added
                self.game_stage = "END"
            return
        all_acted = all(p.has_acted or p.is_all_in for p in active_players)
        bets_settled = all(p.bet_this_street == self.current_bet or p.is_all_in for p in active_players)
        if all_acted and bets_settled:
            self._advance_stage()
        else:
            self._advance_turn()

    def _fast_forward_to_showdown(self):
        """Deals all remaining community cards without betting and starts showdown."""
        stages_to_deal = ["FLOP", "TURN", "RIVER"]
        current_stage_index = self.STAGES.index(self.game_stage)
        for stage in stages_to_deal[current_stage_index:]:
            self.game_stage = stage
            if self.game_stage == "FLOP" and len(self.community_cards) == 0:
                self.deck.deal() 
                [self.community_cards.append(self.deck.deal()) for _ in range(3)]
                self.log.append(f"Flop dealt: {' '.join(map(str, self.community_cards))}")
            elif self.game_stage in ["TURN", "RIVER"] and len(self.community_cards) < 5:
                self.deck.deal() 
                self.community_cards.append(self.deck.deal())
                self.log.append(f"{self.game_stage.capitalize()} dealt: {self.community_cards[-1]}")
        self._do_showdown()

    def _advance_turn(self):
        if not self.players: return
        self.current_player_index = (self.current_player_index + 1) % len(self.players)
        while not self.players[self.current_player_index].is_playing or self.players[
            self.current_player_index].is_all_in:
            self.current_player_index = (self.current_player_index + 1) % len(self.players)

    def _advance_stage(self):
        self.log.append(f"Betting round ends. Pot is ${self.pot}.")
        # Reset player state for the new street
        for p in self.players:
            p.bet_this_street = 0
            p.has_acted = False
        self.current_bet = 0

        # --- BUG FIX for All-In Scenarios ---
        # Check if a betting round is even possible. A betting round requires
        # at least two active players who are NOT all-in.
        players_who_can_bet = [p for p in self.players if p.is_playing and not p.is_all_in]

        if len(players_who_can_bet) < 2:
            # If not enough players can bet, skip all future betting rounds
            # and go straight to the showdown.
            self._fast_forward_to_showdown()
            return  # Stop the function here
        # --- END FIX ---

        # This is the original logic, which is fine if a betting round is possible.
        self.current_player_index = (self.dealer_pos + 1) % len(self.players)
        if self.players:
            # This loop will no longer be infinite because we've guaranteed there's
            # at least one player who is not all-in to be found.
            while not self.players[self.current_player_index].is_playing or self.players[
                self.current_player_index].is_all_in:
                self.current_player_index = (self.current_player_index + 1) % len(self.players)

        current_stage_index = self.STAGES.index(self.game_stage)
        if current_stage_index + 1 < len(self.STAGES):
            self.game_stage = self.STAGES[current_stage_index + 1]
        else:
            self.game_stage = "END"
            return

        if self.game_stage == "FLOP":
            self.deck.deal()  # Burn card
            [self.community_cards.append(self.deck.deal()) for _ in range(3)]
            self.log.append(f"Flop dealt: {' '.join(map(str, self.community_cards))}")
        elif self.game_stage == "TURN":
            self.deck.deal()  # Burn card
            self.community_cards.append(self.deck.deal())
            self.log.append(f"Turn dealt: {self.community_cards[-1]}")
        elif self.game_stage == "RIVER":
            self.deck.deal()  # Burn card
            self.community_cards.append(self.deck.deal())
            self.log.append(f"River dealt: {self.community_cards[-1]}")
        elif self.game_stage == "SHOWDOWN":
            self._do_showdown()

    def _do_showdown(self):
        self.log.append("Showdown begins!")

        # --- FIX: Create a definitive list of players for the showdown ---
        self.showdown_players = [p.player_id for p in self.players if p.is_playing or p.is_all_in]
        contenders = [p for p in self.players if p.player_id in self.showdown_players]

        if not contenders: self.game_stage = "END"; return

        if len(contenders) == 1:
            winner = contenders[0];
            winner.stack += self.pot;
            self.pot = 0
            self.log.append(f"{winner.name} wins the pot of ${winner.stack} as the last remaining player.")
        else:
            pots = self._create_pots(contenders)
            self.log.append("Evaluating hands...")
            for i, pot in enumerate(pots): self._award_one_pot(pot, i + 1)

        for player in self.players:
            if player.stack == 0 and not player.is_spectator:
                player.is_spectator = True
                player.is_playing = False
                self.log.append(f"{player.name} has been eliminated and is now a spectator.")

        players_with_money = [p for p in self.players if not p.is_spectator]
        if len(players_with_money) < 2:
            self.log.append("Game over! Waiting for new players.")
            self.game_stage = "WAITING"
        else:
            self.game_stage = "END"

    def _create_pots(self, contenders):
        pots = [] 
        investments = sorted(list(set(p.current_bet for p in contenders if p.current_bet > 0)))
        last_investment_level = 0
        for investment_level in investments:
            pot = {"amount": 0, "eligible_players": [p for p in contenders if p.current_bet >= investment_level]}
            for player in self.players:
                contribution = min(player.current_bet, investment_level) - last_investment_level
                if contribution > 0: pot['amount'] += contribution
            if pot['amount'] > 0: pots.append(pot)
            last_investment_level = investment_level
        return pots

    def _award_one_pot(self, pot, pot_number):
        eligible_players = pot['eligible_players']
        pot_amount = pot['amount']
        if not eligible_players: return

        if len(eligible_players) == 1:
            winner = eligible_players[0]
            winner.stack += pot_amount
            self.log.append(f"Pot #{pot_number} of ${pot_amount} awarded to {winner.name} (uncontested).")
            return

        hands = {p.player_id: max([Hand(list(c)) for c in combinations(p.cards + self.community_cards, 5)]) for p in
                 eligible_players}
        best_hand_in_pot = max(hands.values())
        winners = [p for p in eligible_players if hands[p.player_id] == best_hand_in_pot]

        winnings_per_player = pot_amount // len(winners)
        remainder = pot_amount % len(winners)

        for winner in winners:
            win_amount = winnings_per_player + (1 if remainder > 0 else 0)
            remainder -= 1
            winner.stack += win_amount

            # --- UPDATE for Detailed Log Message ---
            winning_hand_str = ' '.join(map(str, best_hand_in_pot.cards))
            log_message = (f"{winner.name} wins ${win_amount} with {best_hand_in_pot.rank_name}: {winning_hand_str}")
            self.log.append(log_message)