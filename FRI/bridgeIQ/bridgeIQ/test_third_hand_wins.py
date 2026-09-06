"""GATE (PO 2026-09-06): "bridgeIQ now signals on defense even when it could win a trick
instead, which spoils its cardplay."

Third hand, partner's lead currently winning, declarer (4th hand) still to play. Before the
fix `_follow` saw "our side winning" and signalled a low spot; declarer then won cheaply.
Three authored positions, redacted the way the engine sees them (partner + declarer hidden,
dummy exposed), decided with search=False (the deterministic policy):

  A  W leads S5, dummy plays S2, biq (E) holds S K 9 4 -- the ace and queen are UNSEEN, so
     partner's 5 is not a sure winner: biq must play the KING (third hand high), with a
     reason that is not a signal.
  B  same, biq holds S A 9 4 -- the ace WINS outright: play it, reason "Wins the trick".
  C  CONTROL: W leads S K after the ace and queen have already been played (seen), dummy S2,
     biq holds S 9 4 -- partner's king IS a sure winner, so the free signal is still right:
     the reason must be a Signal and the card must not be a K (biq has none).
"""
from backend.models import (BoardState, Hand, Card, Suit, Rank, Seat, Contract, Trick,
                            Vulnerability)
from backend import nopeek

S = Suit.SPADES
def c(suit, rank): return Card(suit=suit, rank=rank)

def board(east_cards, played_tricks=()):
    b = BoardState(board_number=1, dealer=Seat.SOUTH, vulnerability=Vulnerability.NONE, hands={})
    b.contract = Contract(level=3, suit=Suit.NOTRUMP, declarer=Seat.SOUTH)
    b.hands[Seat.EAST]  = Hand(cards=list(east_cards))
    b.hands[Seat.NORTH] = Hand(cards=[c(S, Rank.TWO), c(S, Rank.SEVEN),          # dummy, exposed
                                      c(Suit.HEARTS, Rank.THREE), c(Suit.DIAMONDS, Rank.FOUR)])
    b.hands[Seat.WEST]  = Hand(cards=[])          # partner: hidden (redacted)
    b.hands[Seat.SOUTH] = Hand(cards=[])          # declarer: hidden
    b.tricks = list(played_tricks)
    return b

def decide(b, trick):
    e = {}
    card = nopeek.decide(b, Seat.EAST, current_trick_cards=trick, search=False, explain=e)
    return card, e.get("tag"), e.get("reason", "")

fails = 0
def chk(name, ok, detail):
    global fails
    print(f"  {'PASS' if ok else 'FAIL'}  {name:58s} {detail}")
    fails += 0 if ok else 1

# A: K 9 4 behind dummy's 2, partner's 5 winning so far, A/Q unseen -> play the K, not a signal
hand_a = [c(S, Rank.KING), c(S, Rank.NINE), c(S, Rank.FOUR), c(Suit.HEARTS, Rank.EIGHT), c(Suit.CLUBS, Rank.SIX)]
card, tag, why = decide(board(hand_a), [c(S, Rank.FIVE), c(S, Rank.TWO)])
chk("A: third hand plays the KING over dummy's 2", card == c(S, Rank.KING), f"played {card}  tag={tag}")
chk("A: the reason is not a signal", tag != "Signal", f"tag={tag}")

# B: A 9 4 -> the ace wins outright
hand_b = [c(S, Rank.ACE), c(S, Rank.NINE), c(S, Rank.FOUR), c(Suit.HEARTS, Rank.EIGHT), c(Suit.CLUBS, Rank.SIX)]
card, tag, why = decide(board(hand_b), [c(S, Rank.FIVE), c(S, Rank.TWO)])
chk("B: third hand takes the trick with the ACE", card == c(S, Rank.ACE), f"played {card}")
chk("B: the reason says it wins the trick", tag == "Wins the trick", f"tag={tag}")

# C: control -- partner's K is a SURE winner (A and Q already played), biq holds 9 4: signal
t1 = Trick(leader=Seat.WEST); [t1.add_card(x) for x in (c(S, Rank.ACE), c(S, Rank.THREE), c(S, Rank.QUEEN), c(S, Rank.EIGHT))]
hand_c = [c(S, Rank.NINE), c(S, Rank.FOUR), c(Suit.HEARTS, Rank.EIGHT), c(Suit.CLUBS, Rank.SIX), c(Suit.DIAMONDS, Rank.NINE)]
card, tag, why = decide(board(hand_c, [t1]), [c(S, Rank.KING), c(S, Rank.TWO)])
chk("C: control -- partner's sure winner: biq still signals", tag == "Signal", f"tag={tag} played {card}")
chk("C: control -- and plays a spade spot", card is not None and card.suit == S, f"played {card}")

print("ALL PASS" if fails == 0 else f"FAILURES: {fails}")
raise SystemExit(fails)
