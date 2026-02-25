import argparse
import random
import eval7
import sys
import time

# --- Configuration & Constants ---
STREETS = ["Preflop", "Flop", "Turn", "River"]
SB_AMOUNT = 1
BB_AMOUNT = 2
STARTING_STACK = 200

# --- Helper Functions ---

def calc_equity_hidden(hero_hand, board, iterations=100):
    """
    Standard Monte Carlo: Hero vs Random Cards.
    Used by bots (always) and human (if God Mode is OFF).
    """
    if not hero_hand: return 0.0
    hero_cards = hero_hand
    board_cards = [eval7.Card(s) for s in board]
    dead_card_strs = {str(c) for c in hero_cards}
    dead_card_strs.update(str(c) for c in board_cards)
    wins = 0
    ties = 0
    for _ in range(iterations):
        sim_deck = eval7.Deck()
        sim_deck.cards = [c for c in sim_deck.cards if str(c) not in dead_card_strs]
        sim_deck.shuffle()
        if len(sim_deck.cards) < 2: break
        opp_hand = sim_deck.deal(2)
        cards_needed = 5 - len(board_cards)
        if cards_needed > 0:
            if len(sim_deck.cards) < cards_needed: break
            runout = sim_deck.deal(cards_needed)
            full_board = board_cards + runout
        else:
            full_board = board_cards
        hero_score = eval7.evaluate(hero_cards + full_board)
        opp_score = eval7.evaluate(opp_hand + full_board)
        if hero_score > opp_score: wins += 1
        elif hero_score == opp_score: ties += 1
    return (wins + (ties / 2)) / iterations

def calc_equity_perfect(hero_hand, villain_hands, board, iterations=100):
    """
    Perfect Information Monte Carlo: Hero vs Specific Villain Hands.
    Used ONLY by Human when --god flag is active.
    """
    if not hero_hand: return 0.0
    hero_cards = hero_hand
    opp_cards_list = [h for h in villain_hands if h] 
    board_cards = [eval7.Card(s) for s in board]
    known_cards = hero_cards + [c for hand in opp_cards_list for c in hand] + board_cards
    known_strs = {str(c) for c in known_cards}
    wins = 0
    ties = 0
    for _ in range(iterations):
        sim_deck = eval7.Deck()
        sim_deck.cards = [c for c in sim_deck.cards if str(c) not in known_strs]
        sim_deck.shuffle()
        cards_needed = 5 - len(board_cards)
        if cards_needed > 0:
            if len(sim_deck.cards) < cards_needed: break
            runout = sim_deck.deal(cards_needed)
        else:
            runout = []
        full_board = board_cards + runout
        hero_score = eval7.evaluate(hero_cards + full_board)
        best_opp_score = -1
        for v_hand in opp_cards_list:
            score = eval7.evaluate(v_hand + full_board)
            if score > best_opp_score: best_opp_score = score
        if hero_score > best_opp_score: wins += 1
        elif hero_score == best_opp_score: ties += 1
    return (wins + (ties / (len(opp_cards_list) + 1))) / iterations

def format_cards(cards):
    return " ".join([str(c) for c in cards])

# --- Player Classes ---
class Player:
    def __init__(self, name, style):
        self.name = name
        self.style = style 
        self.stack = STARTING_STACK
        self.hand = []
        self.active = True
        self.bet_in_round = 0
        self.actions_this_round = 0

    def reset_for_hand(self):
        self.hand = []
        self.active = True
        self.bet_in_round = 0
        self.actions_this_round = 0

    def calculate_current_stats(self, game_state, is_god_mode):
        current_bet = game_state['current_bet']
        to_call = current_bet - self.bet_in_round
        active_bets = sum(p.bet_in_round for p in game_state['players'])
        total_pot = game_state['pot'] + active_bets
        pot_odds = to_call / (total_pot + to_call) if (total_pot + to_call) > 0 else 0
        
        # KEY LOGIC: Bots always use hidden (random) sim.
        # Human uses perfect (god) sim if enabled.
        if is_god_mode and self.style == 'human':
            villain_hands = [p.hand for p in game_state['players'] if p != self and p.active]
            equity = calc_equity_perfect(self.hand, villain_hands, game_state['board'], iterations=500)
        else:
            # Bots or Human (Normal Mode) -> Hidden Sim
            equity = calc_equity_hidden(self.hand, game_state['board'], iterations=400)
            
        return equity, pot_odds, to_call

    def get_action(self, game_state, is_god_mode):
        self.actions_this_round += 1
        equity, pot_odds, to_call = self.calculate_current_stats(game_state, is_god_mode)
        
        # --- FOLDING SAFETY ---
        is_huge_bet = to_call > (self.stack * 0.25)
        if is_huge_bet and self.style != 'human':
            if equity < 0.60: return 'f', 0

        # --- HUMAN ---
        if self.style == 'human':
            print(f"\n[ACTION] {self.name} (To Call: {to_call})")
            while True:
                move = input(f"   Call, Raise, or Fold? [c/r/f]: ").lower()
                if move == 'f': return 'f', 0
                if move == 'c': return 'c', 0
                if move == 'r':
                    min_raise = to_call + BB_AMOUNT
                    max_raise = self.stack
                    if min_raise > max_raise:
                        print("   Not enough chips to raise. Calling all-in.")
                        return 'c', 0
                    try:
                        amt = int(input(f"   Raise Amount (min {min_raise}, max {max_raise}): "))
                        if min_raise <= amt <= max_raise: return 'r', amt
                    except ValueError: pass
                if move == 'q': sys.exit()

        # --- BOTS ---
        if self.style == 'tight':
            if equity < pot_odds + 0.15: return 'f', 0
            if equity > 0.75: return 'r', int(game_state['pot'] * 0.75)
            return 'c', 0

        elif self.style == 'loose':
            if equity < pot_odds - 0.05: return 'f', 0 
            return 'c', 0

        elif self.style == 'station':
            if equity < 0.08 and to_call > 0: return 'f', 0
            return 'c', 0

        elif self.style == 'aggressive':
            if self.actions_this_round > 2: return 'c', 0
            rng = random.random()
            if equity > 0.60:
                if rng < 0.80:
                    bet = int(game_state['pot'] * random.uniform(0.6, 1.0))
                    return 'r', max(bet, to_call + BB_AMOUNT)
                return 'c', 0
            if equity < 0.40 and rng < 0.25: 
                bet = int(game_state['pot'] * 0.5)
                return 'r', max(bet, to_call + BB_AMOUNT)
            if equity < pot_odds: return 'f', 0
            return 'c', 0

        elif self.style == 'optimal':
            if self.actions_this_round > 3: return 'c', 0
            if equity > 0.80: return 'r', int(game_state['pot'] * 0.8)
            elif equity > 0.60: return 'r', int(game_state['pot'] * 0.5)
            elif equity >= pot_odds: return 'c', 0
            else: return 'f', 0

        return 'c', 0

# --- Game Engine ---
class Game:
    def __init__(self, god_mode=False, show_stats=False):
        self.players = [
            Player("Hero (You)", "human"),
            Player("GTO Greg", "optimal"),
            Player("Tight Tim", "tight"),
            Player("Loose Larry", "loose"),
            Player("Aggro Al", "aggressive")
        ]
        self.deck = eval7.Deck()
        self.board = []
        self.pot = 0
        self.dealer_idx = 0
        self.god_mode = god_mode
        self.show_stats = show_stats

    def deal_hand(self):
        print("\n" + "="*60)
        print(f"NEW HAND - Dealer: {self.players[self.dealer_idx].name}")
        self.deck = eval7.Deck()
        self.deck.shuffle()
        self.board = []
        self.pot = 0
        
        for p in self.players:
            p.reset_for_hand()
            if p.stack <= 0: p.active = False 

        active_players = [p for p in self.players if p.active]
        if len(active_players) < 2:
            print("Game Over! Not enough players.")
            sys.exit()

        for _ in range(2):
            for p in active_players:
                p.hand.append(self.deck.deal(1)[0])

        sb_idx = (self.dealer_idx + 1) % len(self.players)
        bb_idx = (self.dealer_idx + 2) % len(self.players)
        self.post_blind(self.players[sb_idx], SB_AMOUNT)
        self.post_blind(self.players[bb_idx], BB_AMOUNT)

        for street in STREETS:
            if self.count_active_players() < 2: break
            if street == "Flop": self.board.extend(self.deck.deal(3))
            elif street in ["Turn", "River"]: self.board.extend(self.deck.deal(1))
            self.print_state(street)
            self.betting_round(street, start_idx=(bb_idx + 1) % len(self.players))

        self.showdown()
        self.dealer_idx = (self.dealer_idx + 1) % len(self.players)

    def post_blind(self, player, amount):
        amount = min(player.stack, amount)
        player.stack -= amount
        player.bet_in_round = amount
        self.pot += amount
        print(f"{player.name} posts blind: {amount}")

    def print_state(self, street):
        print(f"\n--- {street} --- Pot: {self.pot}")
        if self.board: print(f"Board: {format_cards(self.board)}")
        print(f"{'Player':<15} {'Stack':<8} {'Cards':<12} {'Status'}")
        print("-" * 50)
        for p in self.players:
            status = ""
            cards_str = "xx xx"
            if p.active:
                if p.name.startswith("Hero") or self.god_mode or street == "Showdown":
                    cards_str = format_cards(p.hand)
            else:
                status = "(Folded)"
            print(f"{p.name:<15} {p.stack:<8} {cards_str:<12} {status}")

        if self.show_stats and self.count_active_players() > 1:
            print("\n[STATS TABLE]")
            # Updated header to show Real vs View equity
            header = f"{'Player':<15} {'Eq(View)':<10} {'Eq(Real)':<10} {'PotOdds':<10}"
            print(header)
            print("-" * len(header))
            
            game_state = {
                'board': [str(c) for c in self.board],
                'pot': self.pot,
                'players': self.players,
                'current_bet': max(p.bet_in_round for p in self.players)
            }
            
            for p in self.players:
                if p.active:
                    # 1. View Equity (What the player THINKS)
                    # Bots think hidden, Hero thinks God (if enabled)
                    use_god_view = self.god_mode if p.style == 'human' else False
                    eq_view, pot_odds, _ = p.calculate_current_stats(game_state, use_god_view)
                    
                    # 2. Real Equity (The TRUTH)
                    # We calculate this using God Mode logic for everyone here just for display
                    if self.god_mode:
                        villain_hands = [other.hand for other in self.players if other != p and other.active]
                        eq_real = calc_equity_perfect(p.hand, villain_hands, game_state['board'], iterations=400)
                        real_str = f"{eq_real:<10.1%}"
                    else:
                        real_str = f"{'--':<10}"
                        
                    print(f"{p.name:<15} {eq_view:<10.1%} {real_str} {pot_odds:<10.1%}")

    def count_active_players(self):
        return sum(1 for p in self.players if p.active)

    def count_players_with_chips(self):
        return sum(1 for p in self.players if p.active and p.stack > 0)

    def betting_round(self, street, start_idx):
        current_bet = max(p.bet_in_round for p in self.players if p.active)
        if street == "Preflop": current_bet = max(current_bet, BB_AMOUNT)
        else: current_bet = 0

        if self.count_players_with_chips() <= 1: return

        players_to_act = [p for p in self.players if p.active and p.stack > 0]
        if not players_to_act: return

        ordered_indices = []
        for i in range(len(self.players)):
            idx = (start_idx + i) % len(self.players)
            if self.players[idx].active and self.players[idx].stack > 0:
                ordered_indices.append(idx)

        moves_made = 0
        last_raiser = -1 
        raises_this_round = 0

        while True:
            if self.count_players_with_chips() <= 1: break

            action_closed = True
            for idx in ordered_indices:
                p = self.players[idx]
                if not p.active or p.stack == 0: continue
                
                to_call = current_bet - p.bet_in_round
                if moves_made > 0 and to_call == 0 and street != "Preflop" and last_raiser != idx: continue
                if street == "Preflop" and to_call == 0 and moves_made >= len(ordered_indices) and last_raiser == -1: continue 

                game_state = {
                    'board': [str(c) for c in self.board],
                    'pot': self.pot,
                    'current_bet': current_bet,
                    'players': self.players
                }

                use_god_logic = self.god_mode if p.style == 'human' else False
                action, amount = p.get_action(game_state, use_god_logic)
                
                if action == 'f':
                    p.active = False
                    print(f"{p.name}: Folds")
                elif action == 'r':
                    if raises_this_round >= 4:
                        amt = min(p.stack, to_call)
                        p.stack -= amt
                        p.bet_in_round += amt
                        print(f"{p.name}: Calls {amt} (Raise Cap Reached)")
                    else:
                        min_raise = to_call + BB_AMOUNT
                        actual_raise = max(amount, min_raise)
                        if p.stack <= actual_raise: actual_raise = p.stack
                        p.stack -= actual_raise
                        p.bet_in_round += actual_raise
                        current_bet = p.bet_in_round
                        self.pot += actual_raise 
                        print(f"{p.name}: Raises to {p.bet_in_round}")
                        action_closed = False
                        last_raiser = idx
                        raises_this_round += 1
                else: 
                    if to_call > 0:
                        amt = min(p.stack, to_call)
                        p.stack -= amt
                        p.bet_in_round += amt
                        print(f"{p.name}: Calls {amt}")
                    else:
                        print(f"{p.name}: Checks")

            moves_made += 1
            if action_closed: break
            if self.count_active_players() < 2: break

        for p in self.players:
            p.bet_in_round = 0
            p.actions_this_round = 0

    def showdown(self):
        print("\n--- Showdown ---")
        active = [p for p in self.players if p.active]
        if len(active) == 1:
            print(f"{active[0].name} wins {self.pot} (Opponents folded)")
            active[0].stack += self.pot
            return

        best_rank = -1
        winners = []
        board_cards = [eval7.Card(str(c)) for c in self.board]
        
        for p in active:
            hand_cards = [eval7.Card(str(c)) for c in p.hand]
            full_hand = hand_cards + board_cards
            rank = eval7.evaluate(full_hand)
            hand_type = eval7.handtype(rank)
            print(f"{p.name} shows {format_cards(p.hand)} ({hand_type})")
            if rank > best_rank:
                best_rank = rank
                winners = [p]
            elif rank == best_rank:
                winners.append(p)

        if len(winners) > 0:
            win_amt = int(self.pot / len(winners))
            for w in winners:
                print(f"WINNER: {w.name} wins {win_amt}!")
                w.stack += win_amt

if __name__ == "__main__":
    desc = """
    Learn Texas Hold'em on Ubuntu
    -----------------------------
    A text-based poker trainer featuring 5 personalities:
    
    1. Hero (You)      : The human player.
    2. GTO Greg        : Plays logically based on odds.
    3. Tight Tim       : Only plays strong hands.
    4. Loose Larry     : Plays many hands, rarely folds.
    5. Aggro Al        : Raises aggressively to pressure you.
    """
    
    epilog = """
    Examples:
      python3 poker_learn.py
      python3 poker_learn.py --god --stats
    """

    parser = argparse.ArgumentParser(
        description=desc, 
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=epilog
    )
    
    parser.add_argument(
        "--god", 
        action="store_true", 
        help="God Mode: Reveals all player cards to YOU and calculates your equity using 'Perfect Information'."
    )
    
    parser.add_argument(
        "--stats", 
        action="store_true", 
        help="Stats Table: Shows 'Eq(View)' (what they think) vs 'Eq(Real)' (actual truth)."
    )
    
    args = parser.parse_args()

    g = Game(god_mode=args.god, show_stats=args.stats)
    while True:
        try: g.deal_hand()
        except KeyboardInterrupt: sys.exit()
        if input("\nPlay another hand? [Enter=Yes, q=Quit]: ") == 'q': break

