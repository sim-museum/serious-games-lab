"""Regression tests for the fixes from the 2026-09-24/25 biq-vs-Q-Plus runs.

Every bidding case is a real position from `tools/runs/results/run3_signalling_on_same_deals.qss`
(the same deals as run 2): the dealer, vulnerability, the recorded auction up
to biq's turn, biq's hand, the call biq made in the match, and the call(s) it
must make now. The card-play cases replay exact positions from the same file.

Run: python3 test_qplus_match_fixes.py   (exit 0 = all pass)
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.models import (Bid, Seat, Suit, Hand, Card, Rank,        # noqa: E402
                            Vulnerability, Contract)
from backend.native_bidder import (parse_auction, evaluate_hand,      # noqa: E402
                                   decide_bid)
from backend.bidding_systems import get_system                        # noqa: E402

_R = {'A': Rank.ACE, 'K': Rank.KING, 'Q': Rank.QUEEN, 'J': Rank.JACK,
      'T': Rank.TEN, '9': Rank.NINE, '8': Rank.EIGHT, '7': Rank.SEVEN,
      '6': Rank.SIX, '5': Rank.FIVE, '4': Rank.FOUR, '3': Rank.THREE,
      '2': Rank.TWO}
_SC = {'c': Suit.CLUBS, 'd': Suit.DIAMONDS, 'h': Suit.HEARTS,
       's': Suit.SPADES, 'n': Suit.NOTRUMP}
_S = [Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS]
_SEAT = {"N": Seat.NORTH, "E": Seat.EAST, "S": Seat.SOUTH, "W": Seat.WEST}
_VUL = {"None": Vulnerability.NONE, "NS": Vulnerability.NS,
        "EW": Vulnerability.EW, "All": Vulnerability.BOTH}


def _mk(tok):
    t = tok.lower()
    if t == "p":
        return Bid(is_pass=True)
    if t == "x":
        return Bid(is_double=True)
    if t == "xx":
        return Bid(is_redouble=True)
    m = re.match(r"(\d)(nt|n|[cdhs])", t)
    suit = Suit.NOTRUMP if m.group(2) in ("nt", "n") else _SC[m.group(2)]
    return Bid(level=int(m.group(1)), suit=suit)


def _hand(s):
    return Hand(cards=[Card(su, _R[c]) for su, part in zip(_S, s.split("."))
                       for c in part if c != '-'])


def _str(b):
    if b.is_pass:
        return "P"
    if b.is_double:
        return "X"
    if b.is_redouble:
        return "XX"
    return f"{b.level}{'N' if b.suit == Suit.NOTRUMP else b.suit.to_char()}"


# (board, what was wrong, dealer, vul, auction so far, seat, hand,
#  call in the match, acceptable calls now)
BIDDING = [
    ("RUN2-007", "top of 12-14 declines quant 4NT (used the 15-17 range)",
     "W", "NS", "p 1d p 1h p 1n p 4n p", "N", "Q65.KJ7.AQT97.Q7", "P", {"6N"}),
    ("RUN2-009", "negative doubler passes with game values",
     "E", "None", "p 1d 1h x p 1s p", "N", "AK95.62.QT.KQJ85", "P", {"3N", "4S"}),
    ("RUN2-015", "penalty pass of partner's takeout X with 2 HCP",
     "W", "All", "p p p 1h 2d p 3d x p", "N", "J654.62.98.JT532", "P",
     {"3S", "4C"}),
    ("RUN2-017", "17-count with three small in opener's suit stays silent",
     "E", "EW", "p p 1d", "N", "AKQJ.76.753.AK97", "P", {"X"}),
    ("RUN2-019", "illegal 3D rebid -> pass with 4-card support for partner",
     "W", "None", "p 1d 2h 2s 4h p", "N", "AK92.T.KQJT86.52", "P", {"4S"}),
    ("RUN2-021", "opener passes partner's lebensohl 2NT relay when doubled",
     "E", "All", "p p p 1n 2c 2n x", "N", "64.AQ8.AJT8.AJT2", "P", {"3C"}),
    ("RUN2-021b", "responder passes the completed relay with a long suit",
     "E", "All", "p p p 1n 2c 2n x 3c p", "S", "Q73.53.76532.Q53", "P",
     {"3D"}),
    ("RUN2-025", "advancer passes with six hearts and 10 HCP",
     "E", "None", "1d 2c p", "N", "Q642.KQ9542.K32.", "P", {"2H"}),
    ("RUN2-027", "8 diamonds never bid after partner's 1NT overcall",
     "W", "EW", "1c 1n 2h", "S", ".85.QT987654.Q53", "P", {"3D"}),
    ("RUN2-030", "partner's competitive 3H read as a jump-raise (16-19)",
     "S", "EW", "p p 1h p 2h p p x p 2s 3h p", "S", "Q42.AT97.J865.73",
     "4H", {"P"}),
    ("RUN2-035", "no balancing double over a 3S preempt",
     "W", "None", "3s p p", "S", "8.AK95.AT76.J942", "P", {"X"}),
    ("RUN2-035b", "forced advance of the balancing X bids 3NT on one stopper",
     "W", "None", "3s p p x p", "N", "A3.Q74.K54.Q8753", "3N", {"4C"}),
    ("RUN2-038", "opener's raise of my suit read as a forcing reverse",
     "S", "None", "1d p 1h p 2h 3c", "N", "852.J6543.2.KQ54", "3H", {"P"}),
    ("RUN2-038b", "partner competing in their own suit read as a new major",
     "S", "None", "1d p 1h p 2h 3c 3h p", "S", "QT73.Q98.KQ864.A", "4H",
     {"P"}),
    ("RUN2-046", "8-count invites opposite a 12-14 1NT rebid",
     "S", "EW", "1d p 1h x 1n p", "N", "T754.7652.K7.AJ6", "2N", {"P"}),
    ("RUN2-046b", "a later natural 2NT read as Truscott",
     "S", "EW", "1d p 1h x 1n p 2n p", "S", "Q986.AQ8.A943.84", "3D", {"P"}),
    ("RUN2-047", "19 HCP opposite a limit raise signs off (6H cold)",
     "W", "All", "p 1h p 3h p", "N", "KT.AK975.K3.AQ64", "4H", {"4N"}),
    ("RUN2-050", "5 HCP with AJ962 passes partner's 1D",
     "S", "All", "1d p", "N", "AJ962.T9.54.9754", "P", {"1S"}),
    ("RUN2-053", "21-count with six spades -> 'Jacoby 2NT? no support'",
     "E", "All", "p 1h p", "N", "AKQ543.K.Q84.AK2", "2N", {"1S"}),
    ("RUN2-053b", "the 21-count must drive after opener's 2D",
     "E", "All", "p 1h p 1s p 2d p", "N", "AKQ543.K.Q84.AK2", "-",
     {"4N"}),
    ("RUN2-053c", "keycard asker places the slam in its own spades, not 6D",
     "E", "All", "p 1h p 1s p 2d p 4n p 5h p", "N", "AKQ543.K.Q84.AK2", "6H",
     {"6S"}),
    ("RUN2-054", "seven clubs to the AQJ never bid",
     "W", "NS", "1d p 1s", "S", "T7.852.4.AQJ7632", "P", {"3C"}),
    ("RUN2-057", "18 balanced with every suit stopped bids 4C, not 3NT",
     "S", "NS", "p p 1c 2c 3c p", "N", "K953.A2.AJ8.AQ96", "4C", {"3N"}),
    ("RUN2-060", "singleton in their suit, opener passes the negative X",
     "E", "NS", "p 1h 1s x p", "S", "T.AQJ76.432.A642", "P", {"2C", "2H"}),
    ("RUN2-008", "no preference to opener's first suit",
     "N", "All", "1h p 1s p 2c p", "S", "KT86.32.KJ9765.Q", "P", {"2H"}),
    ("RUN2-049", "competitive raise of partner's overcall must survive",
     "E", "EW", "p p 1d 1s x", "S", "8754.T4.Q53.J972", "2S", {"2S"}),
    # Found by the random-deal teams A/B, not the match.
    ("AB-129", "negative-X answer must go to the cheapest LEGAL level",
     "N", "NS", "p 1d 2s x p", "E", "T3.53.KQ982.AQJ7", "-", {"3C"}),
    ("AB-538", "forced takeout-X advance needs no HCP; no double of a double",
     "E", "NS", "1h p 2h x p", "S", "T75.2.JT43.AJ842", "-", {"3C"}),
    ("AB-2NT", "13 opposite a 20-21 2NT is 33: bid the slam",
     "W", "None", "2n p", "E", "Q.Q87.AKJ962.J64", "-", {"6N"}),
    # Found on the fresh FRESH64.BDE deck (seed 260925), the overfitting check.
    ("F64-8", "forced advance, but five of their trumps: penalty pass",
     "W", "None", "1h p 1n x 2h p p x 3h p p x p", "N", "AJ.QT652.T7.7542",
     "-", {"P"}),
    ("F64-50", "a PENALTY double of 1NT is not a forced takeout advance",
     "E", "NS", "1n x p", "N", "J42.Q9632.Q85.42", "-", {"P"}),
    ("F64-16", "they bid over partner's competitive 3H: 4 trumps + max -> 4H",
     "W", "EW", "1h p 2h 2s 3h 3s", "E", "JT83.KJT9.AT5.72", "-", {"4H"}),
    # Live run 4 on the blind deck FRESH64B.BDE (tools/runs/results/run4_*).
    ("R4-026", "5-5 minors + void in partner's suit: new suit, not natural 2NT",
     "E", "All", "p 1s 2h", "N", ".A63.QT875.AQT64", "2N", {"3D"}),
    ("R4-026b", "a contested 2NT is natural, not Jacoby: no shortness reply",
     "E", "All", "p 1s 2h 2n p", "S", "AK853.T92.AJ32.7", "3C", {"P", "3S", "3N"}),
    ("R4-026c", "opener must answer partner's forcing new suit in competition",
     "E", "All", "p 1s 2h 3d p", "S", "AK853.T92.AJ32.7", "P", {"4D", "3S"}),
    ("R4-026d", "12 + void + raised minor: bid the minor game",
     "E", "All", "p 1s 2h 3d p 4d p", "N", ".A63.QT875.AQT64", "-", {"5D"}),
    ("R4-032", "Michaels 2H must be advanced (2NT asks for the minor)",
     "W", "EW", "p p 1h 2h p", "N", "9.54.T87642.K954", "P", {"2N"}),
    ("R4-032b", "Michaels bidder answers 2NT with the minor",
     "W", "EW", "p p 1h 2h p 2n p", "S", "KQT43.A86..AQ862", "-", {"3C"}),
    ("R4-035", "2 HCP must not make a 'forcing' free bid",
     "S", "EW", "1c p p 2d x 3c", "N", "QT9652.954.6.JT5", "3S", {"P"}),
    ("R4-035b", "a passed partner answering my X is not forcing",
     "S", "EW", "1c p p 2d x 3c 3s p", "S", "AK3.A63.J5.Q8764", "4S", {"P"}),
    ("R4-040", "doubler passes partner's forced answer without extras",
     "W", "None", "p p 1h x 2h p p x p 3d p", "S", "QT54.A4.984.AKJ5", "3N",
     {"P"}),
    ("R4-005", "4 trumps + 7-9 over an overcall: competitive jump raise",
     "N", "NS", "p p 1s 2h", "N", "Q752.K6.A9865.T2", "2S", {"3S"}),
    ("R4-005b", "opener with 5 trumps + singleton competes 4S over 4H",
     "N", "NS", "p p 1s 2h 2s 4h", "S", "AKT93.T.KQ73.964", "P", {"4S"}),
    ("R4-011", "1NT opener accepts the transfer invite with 15 + a 5-card suit",
     "S", "None", "p p 1n p 2h p 2s p 2n p", "N", "J7.A83.AT8.AQ953", "P",
     {"3N", "4S"}),
    ("R4-051", "2/1 GF, both unbid suits stopped, no fit: 3NT",
     "S", "EW", "1s p 2d p 2s p", "N", ".A963.AK9853.A95", "3D", {"3N"}),
    ("R4-045", "2 HCP must not bid a 'forcing' 2H",
     "N", "All", "p p 1d 1s", "N", "Q84.97432.97.652", "2H", {"P"}),
    ("AB-882", "doubler: partner's JUMP answer + 19 with a fit = game",
     "E", "None", "1d p p x p 2s p", "N", "AK97.KJ985.8.KQJ", "-", {"4S"}),
    ("AB-173", "no lone 5-level rebid or penalty X of their game",
     "N", "None", "p p 1d x p 2s 3d 4s p p", "S", "Q7.AK93.AT9642.5", "-",
     {"P"}),
    # Live run 5 on the blind deck FRESH64C.BDE (tools/runs/results/run5_*).
    ("R5-007", "seven hearts: rebid 2H, don't pass opener's 2C",
     "S", "All", "p p 1c p 1h p 2c p", "S", "KT4.QJ97532.QJ.4", "P", {"2H"}),
    ("R5-024", "17 balanced with a stopper must not pass a weak two",
     "W", "None", "2s p p", "S", "A973.AT5.K.AQT53", "P", {"2N", "X", "3C"}),
    ("R5-029", "Landy doubled must be advanced (alerts don't cross Q-NET)",
     "N", "All", "p 1n p p 2c x", "S", "AQT3.A7.KJ72.T43", "P",
     {"2S", "3S", "4S"}),
    ("R5-031", "opener reopens with a 5-card second suit, not X",
     "S", "NS", "1h p p 2c", "S", "A2.AQT43.JT985.A", "X", {"2D"}),
    ("R5-037", "raise partner's 4H preempt to 5H over their 5D (LAW)",
     "N", "NS", "4h p p 4n p 5d", "S", "QJ9762.K92.Q.A62", "P", {"5H"}),
    ("R5-043", "flat 6-count leaves partner's double of 4S in",
     "S", "None", "p 4s x p", "S", "Q872.K63.T982.J7", "5D", {"P"}),
    ("R5-047", "15 HCP + six spades overcalls 1S",
     "S", "NS", "p 1h", "N", "KT7654.J.AQ74.KQ", "P", {"1S"}),
    ("R5-049", "a passed hand makes no lebensohl relay",
     "N", "None", "1n p p 2c p 2d", "S", "96.87.J953.AQ542", "2N", {"P"}),
    ("R5-050", "six-card support: raise partner's minor",
     "E", "NS", "p p p 1d p", "S", "T8.A76.JT8754.K7", "1N", {"2D"}),
    ("R5-058", "15-count minor overcaller accepts the cue-bid raise",
     "E", "All", "1s p p 2c p 2s 3s", "N", "52.K9.K53.AKQ643", "4C", {"5C", "3N"}),
    ("R5-061", "11 HCP + void accepts the limit raise",
     "N", "All", "1h p 3h p", "N", ".AT876.AT52.QJT6", "P", {"4H"}),
    ("R5-022", "3 trumps + long minor + stopper after negative X: NT",
     "E", "EW", "p 1d 1s x p", "S", "K8.A95.AKQ963.K6", "4H", {"3N"}),
    ("AB-55", "21 HCP void in their suit: reopening X, not the 2nd suit",
     "S", "None", "p p 1s 3d p p", "N", "AKQ96.A8432..AQJ", "-", {"X"}),
    ("AB-426", "reply to partner's cue-bid once, not every round",
     "E", "All", "1s p p x p 2s p 3h 3s p p", "N", "5.KJ842.A643.A83", "-",
     {"P"}),
    ("AB-687", "18 HCP six hearts: jump to 4H over their raise",
     "S", "None", "p p 1h 1s p 2s", "N", "A.AQT954.Q4.AJT4", "-", {"4H"}),
    ("AB-421", "7 diamonds + void in their hearts: 5D save/make",
     "N", "None", "1d 2h p 3d 4d 4h p p", "N", "AT6..AKQT832.J54", "-", {"5D"}),
    # Live run 6 on the blind deck FRESH64D.BDE (tools/runs/results/run6_*).
    ("R6-015", "after a super-accept (4 trumps) play the major, not 3NT",
     "S", "NS", "p p 1n p 2d p 3h p", "S", "Q6.K9752.QT.K942", "3N", {"4H"}),
    ("R6-029", "18-count opener jump-shifts over 1NT instead of a passable 2C",
     "N", "All", "p p 1s p 1n p", "S", "AK954.K.J52.AK63", "2C", {"3C"}),
    ("R6-037", "3-card support for partner's major over the overcall",
     "N", "NS", "1c p 1s 2h", "N", "KQJ.865.KT2.QJ53", "2N", {"2S"}),
    ("R6-045", "10 + singleton opposite 2NT with a 4-4 fit: keycards",
     "N", "All", "p p 2n p 3c p 3s p", "N", "T652.J.AJ972.AT6", "4S", {"4N"}),
    ("R6-028", "partner raised my answer to the X: game with 9",
     "W", "NS", "p p 1h x p 2d 2h 3d p p", "N", "872.K5.AQ762.932", "P",
     {"3N", "5D"}),
    ("R6-013", "8-card major overcall: preempt 4H",
     "N", "All", "p 1d", "S", "65.AKJ76542.83.J", "1H", {"4H"}),
    ("R6-017", "9 HCP over partner's reverse: 3NT, not a new 3-level minor",
     "N", "None", "p p 1c p 1s p 2h p", "N", "KJ92.J9.J8764.K9", "3D", {"3N"}),
    ("AB-116", "5-card major opener in a GF auction rebids the major",
     "W", "None", "p 1s p 2d p 2s p 2n p", "N", "QJ862.AT.K98.A93", "-", {"3S"}),
    # Q-Plus auction mining (tools/qplus_auction_mine.py --live), 2026-09-26.
    ("R9-018", "opener completes partner's Texas transfer",
     "E", "NS", "p 1n p 4d p", "S", "KQT7.T52.AQJ3.A2", "P", {"4H"}),
    ("R10-012", "14 HCP 5-3-3-2 with a five-card minor opens 1NT",
     "W", "NS", "p", "N", "Q65.KJ7.AQT97.Q7", "1D", {"1N"}),
    ("R10-WJO", "vulnerable 5-count: no weak jump to the 3-level",
     "W", "All", "1d", "N", "4.T543.93.AJ7532", "3C", {"P"}),
    ("R10-REB", "11-count opener doesn't rebid six clubs at the 3-level alone",
     "E", "EW", "p 1c 1h p 2h", "S", "Q974.A73..A98432", "3C", {"P"}),
    # Weak / wacky audit (tools/wacky_audit.py), 2026-09-30.
    ("W-F22", "14 HCP + six hearts (QJT) over their 3S: bid 4H",
     "E", "EW", "3s", "S", "6.QJT765.AK7.A83", "P", {"4H"}),
    ("W-C29", "flat 4-4 seven-count does not balance with Landy vulnerable",
     "N", "All", "p 1n p p", "N", "8642.KT64.A53.96", "2C", {"P"}),
    ("W-H46", "20 HCP over a weak 2D: double first, not a 2S overcall",
     "E", "None", "2d", "S", "AKJ95.KQT4.K6.A8", "2S", {"X"}),
    ("W-H62", "unbalanced 10 with six diamonds answers 1C with 1D, not 2NT",
     "E", "None", "p 1c p", "N", "T73.732.AKT973.K", "2N", {"1D"}),
    ("W-I44", "9 HCP + five hearts bids over 1C-(X), not pass",
     "W", "NS", "p 1c x", "S", "AJ95.A8653.T72.9", "P", {"1H"}),
    ("W-E42", "12 HCP after 1S-1NT-2H invites (was a pass, game cold)",
     "E", "All", "p 1s p 1n p 2h p", "N", "8.Q84.AQJ3.KT532", "P",
     {"2N", "3H", "3N", "4H"}),
    ("W-E42b", "17 HCP opener accepts the 2NT invitation",
     "E", "All", "p 1s p 1n p 2h p 2n p", "S", "AKQ64.A953.86.A4", "-",
     {"3N", "4H", "4S"}),
    ("W-G56", "17 HCP opener accepts responder's 3D raise",
     "W", "None", "p 1s p 1n p 2d p 3d p", "N", "A7653.A4.AKQ5.87", "P",
     {"3N", "3H"}),
    ("W-E15", "1NT opener answers the Stayman cue-bid 1NT-(2D)-3D",
     "S", "NS", "1n 2d 3d p", "S", "K3.Q863.AT6.KQJ9", "P", {"3H"}),
    ("W-G09", "QJT74 + 12 HCP overcalls 1S, doesn't double 1H",
     "N", "EW", "p 1h", "S", "QJT74.5.A92.KQ64", "X", {"1S"}),
    ("W-H12", "no takeout X of 1C-P-1H holding four hearts",
     "W", "NS", "1c p 1h", "S", "AQ52.T632.AQ5.74", "X", {"P"}),
    ("W-I30", "no takeout X of 1H-P-1S holding four spades",
     "E", "None", "1h p 1s", "N", "AJ32.T3.Q742.AJT", "X", {"P"}),
    ("W-H25", "2C-(2S): weak hand passes (waiting), no natural 3D",
     "N", "EW", "p p 2c 2s", "N", "T765.J.QT42.8652", "3D", {"P"}),
    ("W-I31", "weak two on QJ7642 + AQ outside",
     "S", "NS", "", "S", "QJ7642.AQ.4.8732", "P", {"2S"}),
    ("W-D05", "weak 2D on KJT872 vulnerable",
     "N", "NS", "", "N", "A.85.KJT872.T874", "P", {"2D"}),
    ("W-B30", "12 HCP + five clubs bids over 1D-(1S)",
     "E", "None", "p 1d 1s", "N", "86.KJ2.K95.KQ874", "P", {"2C"}),
    ("W-E36", "four trumps raise over 1S-(X)",
     "W", "All", "p 1s x", "S", "5432.T6.A863.J53", "P", {"2S", "3S"}),
    ("W-I44b", "weak four-card major over 1C-(X): 6 HCP passes",
     "W", "NS", "p 1c x", "S", "JT85.Q73.86432.K", "-", {"P", "2C"}),
    ("W-D21", "four trumps + singleton: 3H over 1H-(2S)",
     "N", "NS", "1h 2s", "S", "J98.J985.9.K8762", "P", {"3H"}),
    ("W-B42", "QJ863 + 5 HCP responds 1H to 1C",
     "E", "All", "p 1c p", "N", "T42.QJ863.Q986.3", "P", {"1H"}),
    ("W-E57", "KQJ75 non-vul overcalls 1H on 6 HCP",
     "N", "EW", "p 1d", "S", "T96.KQJ75.9854.T", "P", {"1H", "2H"}),
    ("W-D56", "seven spades JT-headed, non-vul: preempt over 1H",
     "W", "None", "1h", "N", "JT65432.94.A64.7", "P", {"2S", "3S"}),
    ("W-I35", "six clubs rebid over 1C-P-P-X",
     "S", "EW", "1c p p x", "S", "87.K7.A97.AKQT52", "P", {"2C", "XX"}),
    ("W-H11", "21 HCP 2/1 responder bids the 33-point slam",
     "S", "None", "1s p 2h p 2s p", "N", "Q7.AKQJ6.AQ5.KT7", "3N", {"6N", "4N"}),
]

# Other systems: (board, what, system, dealer, vul, auction, seat, hand, was, ok)
BIDDING_SYSTEMS = [
    ("H-P64", "never double partner's own bid (Precision 1C-(1S)-P-(P)-2D)",
     "Precision90M", "W", "EW", "p p p 1c 1s p p 2d p", "N",
     "873.AT93.AT7.982", "X", {"3D", "P", "2N", "3N"}),
    # Calls arrive over Q-NET without alerts: partner's 1C is still strong
    # and 1C-1NT is game forcing (FRESH64H/I Precision, boards 47 and 2).
    ("W-P47", "1C-1NT-2S-3S is game forcing: opener must not pass",
     "Precision90M", "S", "NS", "p p 1c p 1n p 2s p 3s p", "N",
     "AKT92.A5.AJ.KJ52", "P", {"4S", "4N", "4C", "4D", "4H"}),
    ("W-P02", "same with partner's 1C unalerted (wire), 19 HCP opener",
     "Precision90M", "E", "NS", "p 1c p 1n p 2s p 3s p", "S",
     "AT974.A8.KJ5.AQ2", "P", {"4S", "4N", "4C", "4D", "4H"}),
    ("W-P07", "strong 1C, partner rebids 1S over their 1D: raise with three",
     "Precision90M", "S", "All", "1c 1d p p 1s p", "N",
     "T52.T754.74.AQ32", "P", {"2S"}),
    ("W-P61", "1C-2D: unbalanced opener shows four hearts",
     "Precision90M", "N", "All", "1c p 2d p", "N",
     "2.AJ75.AJ4.AQ975", "2N", {"2H"}),
    ("W-P33", "Precision 2C-(2S): five clubs, weak -> 4C",
     "Precision90M", "N", "None", "2c 2s", "S",
     "T8.AT62.43.KT652", "3C", {"4C"}),
    # All-systems simulation (tools/system_matrix.py), 2026-10-01.
    # Live A/B on FRESH64M (runs 20-23), 2026-10-02.
    ("L-P048", "1C-2C positive: 19+ with four clubs asks for keys",
     "Precision90M", "W", "EW", "p 1c p 2c p", "N", "A.K742.AJ75.AKT3", "2H", {"4N"}),
    ("L-P013", "1C-1D-2NT: 7 HCP raises to 3NT",
     "Precision90M", "N", "All", "1c p 1d p 2n p", "S", "95.Q87.A8532.J52", "P", {"3N"}),
    ("L-P054", "1S-(X): four trumps and 9 HCP raise to 3S (as Q-Plus)",
     "Precision90M", "E", "EW", "p 1s x", "N", "QJ62.98.K95.KT86", "2S", {"3S"}),
    ("L-S048", "1D: unbalanced 10 with six clubs bids 2C, not 2NT",
     "SAYC", "W", "EW", "p 1d p", "S", "KQ5.AT3.6.J98542", "2N", {"2C"}),
    # Live A/B on FRESH64N / FRESH64O (runs 24-27), 2026-10-03.
    ("N-S021", "partner's 1NT overcall: 11 HCP + four hearts uses Stayman",
     "SAYC", "N", "NS", "p 1d 1n p", "N", "K84.AJ85.63.K974", "P", {"2C"}),
    ("N-S021b", "1NT overcaller answers Stayman (not a raise of clubs)",
     "SAYC", "N", "NS", "p 1d 1n p 2c p", "S", "QT9.K963.AQ9.AQ8", "3C", {"2H"}),
    ("N-S021c", "advancer places the contract after the Stayman answer",
     "SAYC", "N", "NS", "p 1d 1n p 2c p 2h p", "N", "K84.AJ85.63.K974", "P", {"4H"}),
    ("N-S021d", "1NT overcaller completes partner's transfer",
     "SAYC", "N", "None", "p 1d 1n p 2d p", "S", "QT9.K96.AQ93.AQ9", "3D", {"2H"}),
    ("N-S021e", "1NT overcaller accepts 2NT with 17 (was read as a raise)",
     "SAYC", "N", "None", "p 1d 1n p 2n p", "S", "QT9.K963.AQ9.AQ8", "P", {"3N"}),
    ("O-S034", "16 HCP 4-2-5-2, spades stopped: 1NT overcall, not pass",
     "SAYC", "E", "NS", "p p 1s", "N", "K962.Q5.KQJ52.A6", "P", {"1N"}),
    ("O-S002", "partner's 3S overcall, they bid 4D: 4 trumps + 12 HCP raise",
     "SAYC", "E", "NS", "3d 3s 4d", "N", "A973.T94.KJ.AT82", "P", {"4S"}),
    ("O-S028", "Smolen, opener 3NT: 18 HCP + AKQT9 bids 6NT",
     "SAYC", "W", "NS", "p 1n p 2c p 2d p 3s p 3n p", "S", "KJ52.AKQT9.AT9.J",
     "P", {"6N", "4N"}),
    # WBridge5 dataset (2026-10-03): an overcall or double EARLIER in the
    # auction made partner pass our keycard 4NT (4NT -13, valid line 68).
    ("W-V068", "1S-(X)-3S-(P)-4NT-(P): answer keycards despite the double",
     "SAYC", "N", "None", "p p 1s x 3s p 4n p", "N", "6543.6.QT5.J9752",
     "P", {"5C"}),
    ("W-V1653", "1H-(2D)-3H-(P)-4NT-(P): answer keycards despite the overcall",
     "SAYC", "N", "None", "p 1h 2d 3h p 4n p", "W", "KQT8543.T983.5.4",
     "P", {"5C"}),
    ("W-RKCX", "1S-(2H)-3S-(P)-4NT-(X): ignore the double, answer keycards",
     "SAYC", "N", "None", "1s 2h 3s p 4n x", "S", "KJ54.73.A842.Q63",
     "P", {"5H"}),
    ("W-RKCA", "asker reads 5H over interference: 6S off one key",
     "SAYC", "N", "None", "1s 2h 3s p 4n p 5h p", "N", "AKQT9.K4.KQ5.K72",
     "6S", {"6S"}),
    # WBridge5 test set (2026-10-04): calls where WBridge5's choice beat
    # biq's with biq's rules finishing both auctions.
    ("W5-NT9", "1NT-?: 9 HCP, no major -> 3NT, not a 2NT invite",
     "SAYC", "N", "None", "1n p", "S", "K83.T97.JT84.AJ7", "2N", {"3N"}),
    ("W5-XF3N", "1NT-2D-2H-3NT: opener with three hearts bids 4H",
     "SAYC", "N", "None", "1n p 2d p 2h p 3n p", "N", "AQ5.K93.KJ85.Q74",
     "P", {"4H"}),
    ("W5-XF3C", "1NT-2D-2H-3C is forcing: opener never passes",
     "SAYC", "N", "None", "p p p 1n p 2d p 2h p 3c p", "W",
     "AT5.QT7.A865.AK8", "P", {"4H"}),
    ("M-NAMY", "NAMYATS 4C: partner completes to 4H",
     "Precision90M", "E", "None", "p 4c p", "N", "QJ62.A.QT4.AKJT7", "P", {"4H"}),
    ("M-2DX", "Precision 2D three-suiter doubled: never raise diamonds",
     "Precision90M", "W", "All", "p 2d x", "S", "T3.853.AT842.642", "3D",
     {"2H", "2S", "XX", "P"}),
    ("M-1D2N", "Precision 1D-2NT is forcing: opener answers",
     "Precision90M", "E", "None", "p 1d p 2n p", "S", "KQ98.2.AQ63.QT87", "P",
     {"3N", "3C", "3D"}),
    ("M-INV3", "inverted minors: 1D-3D is weak, no slam drive",
     "TwoOverOne", "E", "None", "p 1d p 3d p", "S", "AK62.T.AKJ86.J87", "4N",
     {"P", "3N", "5D"}),
    ("M-INV2", "inverted 2D raise: balanced 18 bids NT, not 4D",
     "TwoOverOne", "E", "None", "p 1d p 2d p", "S", "KT65.KQ32.AQ3.A8", "4D",
     {"3N", "2N"}),
    ("M-BERG", "Bergen 3C agrees opener's major (not clubs)",
     "TwoOverOne", "E", "None", "p 1h p 3c p", "S", "AJT84.AQJ73.Q4.8", "6C",
     {"3H", "4H", "4N"}),
    ("M-TRUS", "after Truscott 3NT partner's 4NT asks for keycards",
     "StandardFrench", "E", "None", "p 1s p 3n p 4n p", "N", "K72.Q4.A765.KJ86", "P",
     {"5C", "5D", "5H", "5S"}),
    ("M-CLTR", "1NT-2S (transfer to clubs): opener bids 3C",
     "StandardFrench", "N", "None", "1n p 2s p", "N", "K43.JT952.AT5.AK", "3S",
     {"3C"}),
    ("M-GHES", "no Ghestem 3C in the sandwich seat",
     "StandardFrench", "N", "None", "1d p 1h", "W", "AK542.5.T8.AKJ73", "3C",
     {"1S", "X"}),
    ("M-ACNT", "Acol: no 1NT on an 11-count 5-3-3-2",
     "StandardAcol", "W", "All", "p p p", "S", "AJ9.Q7.T9843.A43", "1N",
     {"P", "1D"}),
    ("M-AC6C", "Acol: six clubs and four hearts open 1C",
     "StandardAcol", "E", "All", "", "E", "AQ.A943.7.AJT854", "1H", {"1C"}),
    ("M-ACRK", "no Jacoby 2NT: 16 HCP and six trumps ask for keys",
     "StandardAcol", "E", "None", "p 1s p", "N", "KQ9764.92.KJ.AK2", "4S",
     {"4N"}),
    ("W-P37", "1NT-(2S)-P-(P)-X: run to clubs with a singleton spade",
     "Precision90M", "N", "NS", "p p 1n 2s p p x p", "N",
     "9.K87.J972.JT752", "P", {"3C"}),
    # Slam bidding (2026-10-04, Precision vs Q-Plus and WBridge5 deals).
    ("S-1N3N", "1C-1NT-3NT: 13 opposite 19+ invites slam, never 3NT again",
     "Precision90M", "N", "None", "p 1c p 1n p 3n p", "W",
     "K74.KJ92.65.AQT9", "P", {"4N", "6N"}),
    ("S-1N4N", "1C-1H(balanced, switch)-4NT: 11 is the top half of 8-13, accept",
     "Precision90M", "N", "None", "p p 1c p 1h p 4n p", "N",
     "K872.A98.AT4.732", "P", {"6N"}),
    ("S-1C1N", "1C-1H(balanced, switch): 20 balanced invites slam with 4NT",
     "Precision90M", "N", "None", "1c p 1h p", "N",
     "AQJ6.KQJ3.K6.A98", "3N", {"4N"}),
    ("S-1C3N", "1C-3NT is 17+ balanced: 16+17 is slam",
     "Precision90M", "N", "None", "1c p 3n p", "N",
     "AQ6.AQ87.AJ7.762", "P", {"6N"}),
    ("S-1N3D", "1C-1H(balanced, switch): 1-1-6-5 shows diamonds, not 3NT",
     "Precision90M", "N", "None", "p p p 1c p 1h p", "W",
     "A.J.AKQ972.KQJT5", "3N", {"3D"}),
    ("S-1N3D4", "1C-1H(balanced, switch)-3D: three-card support raises",
     "Precision90M", "N", "None", "p p p 1c p 1h p 3d p", "E",
     "753.AQ92.JT3.A82", "3N", {"4D"}),
    ("S-REBID", "1H-2C-2H-2NT-3H: 21 with AJ2 asks for keys",
     "Precision90M", "N", "None", "p 1h p 2c p 2h p 2n p 3h p", "W",
     "A53.AJ2.AJ9.AK96", "4H", {"4N"}),
    ("S-1S19", "1S-?: 19 balanced bids 2/1, not 3NT (13-15)",
     "SAYC", "N", "None", "p 1s p", "W", "A32.AKJ8.K32.A93", "3N",
     {"2C", "2D"}),
    # Mined from the Precision run vs Q-Plus (2026-10-04, 129 boards).
    ("P-74", "1NT-P-2C(Stayman): no Landy, 6-5 majors overcall 2S",
     "Precision90M", "E", "All", "1n p 2c", "N",
     "AQJT64.Q9732.85.", "3C", {"2S", "P"}),
    ("P-129", "1D-(1H)-?: 2 HCP does not free-bid 1S",
     "Precision90M", "N", "None", "1d 1h", "S", "65432.J2.83.JT74",
     "1S", {"P"}),
    ("P-38", "third seat: QJT53.A43.84.K64 opens 1S",
     "Precision90M", "S", "NS", "p p", "N", "QJT53.A43.84.K64", "P",
     {"1S"}),
    ("P-16", "1H-1NT-2H: 12 HCP with QJ invites",
     "Precision90M", "N", "None", "1h p 1n p 2h p", "S",
     "K5.QJ.QT63.AT864", "P", {"3H", "4H"}),
    ("P-8", "1C-1D-2NT (20-24): six clubs and 6 HCP bid 3NT",
     "Precision90M", "N", "None", "1c p 1d p 2n p", "S",
     "32.JT72.7.KQ9653", "P", {"3N"}),
    ("P-91", "1D-(1S)-X-(2S): 13 HCP and three hearts bid 3H, not 4H",
     "Precision90M", "N", "None", "1d 1s x 2s", "N", "7.K72.AQ732.AT74",
     "4H", {"3H", "3D", "P"}),
    # Mined from the 194-board Precision run vs Q-Plus (2026-10-05).
    ("Q3-52", "1C-2D-2H-3D: 20 HCP, singleton K in partner's suit, rest stopped: 3NT",
     "Precision90M", "W", "All", "p p p 1c p 2d p 2h p 3d p", "S",
     "K54.AJ62.K.AKQ42", "4C", {"3N"}),
    ("Q3-83", "1NT-P-?: 17 HCP opposite 14-16 invites with 4NT, not Gerber",
     "Precision90M", "W", "NS", "p 1n p", "S", "AK6.KJT.J8763.AJ",
     "4C", {"4N"}),
    ("Q3-85", "1NT-(X): 0 HCP 3-4-3-3 escapes via 2C Stayman",
     "Precision90M", "N", "NS", "1n x", "S", "843.8632.975.743",
     "P", {"2C"}),
    ("Q3-85b", "1NT-(X)-2C-(P)-2H-(P): the weak escape passes",
     "Precision90M", "N", "NS", "1n x 2c p 2h p", "S", "843.8632.975.743",
     "3H", {"P"}),
    # biq South with three Q-Plus players, Precision (2026-10-07/08 run).
    ("Q4-58", "1C-1H is Q-Plus's balanced positive (switch): rebid 1NT, no RKC on 3 hearts",
     "Precision90M", "E", "All", "p 1c p 1h p", "S", "A32.Q54.AK4.KQT6",
     "4N", {"1N"}),
    ("Q4-SW1", "1C-P-?: 8-13 balanced answers 1H (switch)",
     "Precision90M", "N", "None", "1c p", "S", "T43.AQ8.964.A832",
     "1N", {"1H"}),
    ("Q4-SW2", "1C-P-?: five hearts answer 1NT (switch)",
     "Precision90M", "N", "None", "1c p", "S", "73.KQ832.Q75.AJ5",
     "1H", {"1N"}),
    ("Q4-149", "1NT-(X): 3 HCP with four-card majors passes, like Q-Plus",
     "Precision90M", "N", "NS", "1n x", "S", "QT32.9743.3.JT76",
     "2C", {"P"}),
    ("Q3-119", "(2C natural)-?: AQT95 hearts, 13 HCP overcalls 2H",
     "Precision90M", "W", "All", "2c", "N", "A94.AQT95.T.K963",
     "P", {"2H"}),
    ("Q3-119b", "(2C)-P-(P)-?: 5-6 with 13 HCP balances",
     "Precision90M", "W", "All", "2c p p", "S", "KQJ32.2.AQJ754.8",
     "P", {"2D", "2S"}),
    ("Q3-16", "(1NT)-?: 6-5 clubs and hearts, 13 HCP bids 2H",
     "Precision90M", "W", "EW", "1n", "N", "4.KT952.8.AKQJ75",
     "P", {"2H"}),
    ("Q3-115", "(2S)-?: 5-5 majors, 12 HCP bids 3H",
     "Precision90M", "S", "EW", "p 2s", "N", "98754.AK986.AJ.2",
     "P", {"3H"}),
    ("Q3-45", "(3C)-P-(P)-?: AJ983 and 15 HCP bids 3S",
     "Precision90M", "E", "All", "3c p p", "N", "AJ983.Q3.AKT2.J5",
     "P", {"3S"}),
    # biq South with three Q-Plus players (run 261005_qplus_biqS).
    ("M-10", "P-P-1D-(X)-2NT-(X)-P-(P)-?: Truscott 2NT doubled runs to 3D",
     "Precision90M", "S", "All", "p p 1d x 2n x p", "S", "K53.Q8.K97642.52",
     "P", {"3D"}),
    ("M-51", "partner's balancing X of 2S redoubled: run to 3H",
     "Precision90M", "S", "EW", "p 1s p 1n p 2d p 2s p p x xx", "S",
     "875.J742.J95.KT2", "P", {"3H"}),
    ("M-41", "1C-2C-2H-?: four spades shown at the two level, not 3NT",
     "Precision90M", "N", "EW", "1c p 2c p 2h p", "S", "AKJ5.J9.95.Q9763",
     "3N", {"2S"}),
    ("M-57", "1C-2D-2NT-4D: 19 HCP with four aces asks for keycards, never passes",
     "Precision90M", "E", "NS", "p 1c p 2d p 2n p 4d p", "S", "AK43.A5.A92.A653",
     "P", {"4N"}),
    ("M-64", "(3D)-?: 13 HCP with both majors doubles for takeout",
     "Precision90M", "N", "NS", "p 3d", "S", "AKT2.A954.T94.Q7",
     "P", {"X"}),
    ("21-790", "(3S)-?: ten hearts AKQJ (11 playing tricks) bids game, never passes",
     "TwoOverOne", "E", "None", "3s", "S", "-.AKQJT65432.K4.6",
     "P", {"4H"}),
    ("21-779", "4S-(5H)-5S-(6H): our 5S was a save over partner's preempt, no double of their slam",
     "TwoOverOne", "N", "None", "4s 5h 5s 6h p p", "S", "K86.7.QT9876.J42",
     "X", {"P"}),
    ("P-862", "1C-(P)-2D-(2H)-3D-(3H)-P-(P)-4H: partner's cue of their suit is never passed",
     "Precision90M", "N", "NS", "1c p 2d 2h 3d 3h p p 4h p", "S", "K942.K53.Q8652.9",
     "P", {"4S", "5D"}),
    # Standard Acol (Q-Plus B-ACL-S), before the first SAYC + Acol run:
    # strong forcing twos (18-22, 2NT negative), 12-14 1NT without a
    # five-card major, no transfers, 2NT 21-22, 1NT rebid 15-16 / 2NT 17-18.
    ("A-s2-neg", "2H-(P)-?: partner's Acol strong two is forcing; weak hand bids 2NT negative",
     "StandardAcol", "N", "None", "2h p", "S", "8762.Q43.T843.54",
     "P", {"2N"}),
    ("A-s2-raise", "2H-(P)-?: positive with three trumps raises (game forcing)",
     "StandardAcol", "N", "None", "2h p", "S", "A762.K43.T84.954",
     "P", {"3H"}),
    ("A-s2-new", "2H-(P)-?: positive with a good five-card suit bids it",
     "StandardAcol", "N", "None", "2h p", "S", "KQJ62.43.A84.954",
     "P", {"2S"}),
    ("A-s2-min", "2H-2NT-3H: opener's minimum is passed with nothing",
     "StandardAcol", "N", "None", "2h p 2n p 3h p", "S", "8762.43.T8432.54",
     "4H", {"P"}),
    ("A-s2-open", "18-22 with six spades opens a strong 2S",
     "StandardAcol", "S", "None", "", "S", "AKQJ62.A4.KQ4.54",
     "1S", {"2S"}),
    ("A-no-weak2d", "six diamonds and 7 HCP: no weak 2D in Acol (2D is strong)",
     "StandardAcol", "S", "None", "", "S", "4.Q43.KQT843.954",
     "2D", {"P"}),
    ("A-s2-def", "(2H strong)-?: 13 HCP balanced passes",
     "StandardAcol", "E", "None", "2h", "S", "K762.A3.KJ84.Q54",
     "X", {"P"}),
    ("A-nt-5M", "12-14 with five spades opens 1S, not 1NT (no-5-card-major)",
     "StandardAcol", "S", "None", "", "S", "AQJ52.K43.Q82.54",
     "1N", {"1S"}),
    ("A-nt-takeout", "1NT-(P)-?: weak with five spades bids a natural 2S (no transfers)",
     "StandardAcol", "N", "None", "1n p", "S", "Q8762.J43.T82.54",
     "2H", {"2S"}),
    ("A-nt-pass", "1NT-2H: partner's weak takeout is passed",
     "StandardAcol", "S", "None", "1n p 2h p", "S", "AQ2.K4.QT82.J543",
     "2S", {"P"}),
    ("A-2nt", "22 balanced opens 2NT (21-22), not 2C",
     "StandardAcol", "S", "None", "", "S", "AQ2.KQ4.AQT8.KQ5",
     "2C", {"2N"}),
    ("A-rebid17", "1D-1S-? 17 balanced jumps to 2NT (17-18; 1NT is 15-16)",
     "StandardAcol", "S", "None", "1d p 1s p", "S", "A42.KQ4.AQT8.Q95",
     "1N", {"2N"}),
    # Acol run 261013 (Acol boards 129-260) and the 2C-2D-2M "preference".
    ("A-156", "2D(strong)-(2S)-?: 9 HCP with five hearts doubles (Q-Plus X, 6H made)",
     "StandardAcol", "W", "NS", "p 2d 2s", "S", "J4.J8752.Q2.AJT5",
     "P", {"X"}),
    ("A-236", "(1NT weak)-?: six hearts and four spades bids 2H, not Landy",
     "StandardAcol", "E", "None", "1n", "S", "J843.A98432.A2.J",
     "2C", {"2H"}),
    ("A-253", "(1NT weak)-?: 5-4 majors, 8 HCP: Landy 2C",
     "StandardAcol", "E", "None", "1n", "S", "97652.QJ85.A3.J2",
     "P", {"2C"}),
    ("A-248", "(1NT weak)-?: six hearts, 8 HCP: natural 2H",
     "StandardAcol", "E", "None", "1n", "S", "Q2.KJ8532.T73.QT",
     "P", {"2H"}),
    ("A-180", "2C-2D-2H-?: three trumps and nothing raises to 4H, no 3C 'preference'",
     "StandardAcol", "N", "None", "2c p 2d p 2h p", "S", "8762.Q43.T843.54",
     "3C", {"4H"}),
    ("S-2c2m", "2C-2D-2H-? (SAYC): no fit and 2 HCP: second negative 3C",
     "SAYC", "N", "None", "2c p 2d p 2h p", "S", "8762.43.QT843.54",
     "3C", {"3C"}),
    ("S-2nt-xfer", "2C-2D-2NT-3D: opener completes the transfer (biq raised it to 4D)",
     "SAYC", "S", "None", "2c p 2d p 2n p 3d p", "S", "AQ2.KQ54.AQT8.KQ",
     "4D", {"3H", "4H"}),
    ("S-2nt-fit", "2C-2D-2NT-3C-3S: four spades and 4 HCP bid game opposite 22+",
     "SAYC", "N", "None", "2c p 2d p 2n p 3c p 3s p", "S", "KJ54.T862.854.32",
     "P", {"4S"}),
    ("A-257", "2C-2D-2NT-? (Acol, no transfers): five spades bid a natural 3S",
     "StandardAcol", "N", "EW", "2c p 2d p 2n p", "S", "AJT42.T5.86.JT93",
     "3H", {"3S"}),
    ("F-2nt-stay", "2C-2D-2NT-3C: opener answers Stayman (biq passed)",
     "StandardFrench", "S", "None", "2c p 2d p 2n p 3c p", "S", "AQ32.KQ4.AQT8.KQ",
     "P", {"3S"}),
    ("A-261014-23", "22 HCP with six hearts opens 2C (Q-Plus), not a strong 2H",
     "StandardAcol", "S", "All", "", "S", "AK2.AKQ874.K7.K4",
     "2H", {"2C"}),
    ("A-2c-20pt", "20 HCP, 9 playing tricks: 2C (Q-Plus); 20 with 7 tricks stays a strong two",
     "StandardAcol", "S", "None", "", "S", "AQT987.A97.KQJ.A",
     "2S", {"2C"}),
    ("A-s2-20", "20 HCP, 7 playing tricks: strong 2S (Q-Plus)",
     "StandardAcol", "S", "None", "", "S", "AJ9542.AK9.AQ.Q7",
     "2S", {"2S"}),
    ("A-261014-28", "2C-2D-? seven diamonds, spade void: 3D, not a catch-all 3NT",
     "StandardAcol", "S", "EW", "2c p 2d p", "S", "-.AKQ.AQ98532.AQ2",
     "3N", {"3D"}),
    ("A-261014-44", "2S-? three trumps, 8 HCP, no ace: 4S (Q-Plus), not a 3S cue-bid auction",
     "StandardAcol", "N", "None", "2s p", "S", "T53.QJ.Q864.K532",
     "3S", {"4S"}),
    ("A-261014-53", "1S-? 11 HCP, doubleton spade, five diamonds: 2D (Acol has no forcing 1NT)",
     "StandardAcol", "N", "NS", "1s p", "S", "AQ.T643.KJT98.J6",
     "1N", {"2D"}),
    ("A-261014-84", "2C-? 12 HCP balanced: 3NT (11-13), not the negative 2D (Q-Plus 6H)",
     "StandardAcol", "W", "All", "p 2c p", "S", "AT5.J8.953.AKT94",
     "2D", {"3N"}),
    ("A-261014-93", "1D-1H-4C: opener's splinter; responder bids 4H, never passes 4C",
     "StandardAcol", "N", "All", "1d p 1h p 4c p", "S", "K54.AQ84.T9.8653",
     "P", {"4H"}),
    ("A-261014-6", "2D-3D (strong two raised, 4+ HCP): 19 HCP passes, no Blackwood / 7D",
     "StandardAcol", "S", "None", "2d p 3d p", "S", "AK7.T4.AQJ852.KQ",
     "4N", {"P"}),
    ("A-s2-raise4", "2D-? 4 HCP with four diamonds raises (as Q-Plus does)",
     "StandardAcol", "S", "None", "2d p", "N", "962.A975.T763.T7",
     "2N", {"3D"}),
    # Modern Standard French (Q-Plus F-FRA-M): Benjamin 2C/2D, gambling 3NT,
    # minor transfers, Stayman 2NT with both majors, 1NT-4D both majors.
    ("F-no-weak2d", "six diamonds, 7 HCP: no weak 2D (2D = Benjamin game force)",
     "StandardFrench", "S", "None", "", "S", "4.Q43.KQT843.954",
     "2D", {"P"}),
    ("F-2d-open", "25 balanced opens Benjamin 2D, not 2C",
     "StandardFrench", "S", "None", "", "S", "AKQ2.AK4.AQT8.K5",
     "2C", {"2D"}),
    ("F-2c-open", "22 balanced opens Benjamin 2C",
     "StandardFrench", "S", "None", "", "S", "AQ2.KQ4.AQT8.KQ5",
     "2C", {"2C"}),
    ("F-2d-neg", "2D(Benjamin)-? 2 HCP answers 2H (0-7), no 'preemptive raise'",
     "StandardFrench", "N", "None", "2d p", "S", "8762.Q43.T843.54",
     "3D", {"2H"}),
    ("F-2d-pos", "2D(Benjamin)-? 12 balanced answers 3NT (11-13)",
     "StandardFrench", "N", "None", "2d p", "S", "K762.A43.KQ4.954",
     "P", {"3N"}),
    ("F-2c-pass", "2C-2D-2H-? 0 HCP, no support: pass (Benjamin 2C is passable)",
     "StandardFrench", "N", "None", "2c p 2d p 2h p", "S", "8762.43.T8432.54",
     "3C", {"P"}),
    ("F-2d-rebid", "2D-2H-? 25 balanced rebids 2NT (24-25)",
     "StandardFrench", "S", "None", "2d p 2h p", "S", "AKQ2.AK4.AQT8.K5",
     "4N", {"2N"}),
    ("F-xfer-d", "1NT-? weak with six diamonds: 3C transfer (3C = diamonds)",
     "StandardFrench", "N", "None", "1n p", "S", "4.Q43.KT8643.954",
     "3D", {"3C"}),
    ("F-xfer-c", "1NT-? weak with six clubs: 2S transfer (not a natural 3C)",
     "StandardFrench", "N", "None", "1n p", "S", "4.Q43.T84.KT8643",
     "3C", {"2S"}),
    ("F-xfer-done", "1NT-3C-3D: weak transfer completed, pass",
     "StandardFrench", "N", "None", "1n p 3c p 3d p", "S", "4.Q43.KT8643.954",
     "4D", {"P"}),
    ("F-open-xfer", "1NT-3C: opener completes the transfer to diamonds",
     "StandardFrench", "S", "None", "1n p 3c p", "S", "AQ2.KQ4.QT8.K954",
     "4C", {"3D"}),
    ("F-stay-2nt", "1NT-2C-? both majors answer 2NT",
     "StandardFrench", "S", "None", "1n p 2c p", "S", "AQ32.KQ54.QT8.K9",
     "2H", {"2N"}),
    ("F-stay-fit", "1NT-2C-2NT-? four spades, 10 HCP: 4S",
     "StandardFrench", "N", "None", "1n p 2c p 2n p", "S", "KJ32.J54.QT8.K87",
     "P", {"4S"}),
    ("F-4d", "1NT-4D: both majors, opener picks one",
     "StandardFrench", "S", "None", "1n p 4d p", "S", "AQ2.KQ4.QT8.K954",
     "5D", {"4H", "4S"}),
    ("F-261014-130", "1NT-(2C Landy)-2H-(2S): 2H shows a stopper, not a transfer; pass",
     "StandardFrench", "E", "NS", "p 1n 2c 2h 2s", "S", "K87.AQ.AT72.A985",
     "3S", {"P"}),
    ("F-261014-137", "1D-2S (French: very strong jump shift, GF)-3D-3S: opener does not pass",
     "StandardFrench", "E", "None", "p 1d p 2s p 3d p 3s p", "S", "7.Q8.KJT74.AKQ52",
     "P", {"4D", "4C", "4S", "3N"}),
    ("F-261014-134", "(1D)-P-(1H)-2C-(3D)-? a simple raise is not pushed to 4C on 7 HCP",
     "StandardFrench", "E", "EW", "1d p 1h 2c 3d", "S", "A63.9876.Q52.J62",
     "4C", {"P"}),
    ("F-261014-150", "1H-4C (splinter): 16 HCP, 7 controls goes for slam, not 4H",
     "StandardFrench", "S", "EW", "1h p 4c p", "S", "A43.A8752.8.AKJ9",
     "4H", {"4N", "4D", "4S"}),
    ("F-gamb", "3NT(gambling)-? nothing: 4C pass or correct",
     "StandardFrench", "N", "None", "3n p", "S", "4.Q43.T8643.9543",
     "P", {"4C"}),
    ("F-gamb-4c", "3NT-4C: not Gerber; opener with diamonds bids 4D",
     "StandardFrench", "S", "None", "3n p 4c p", "S", "4.32.AKQ8643.954",
     "4H", {"4D"}),
]


def run_bidding():
    bad = 0
    sayc = get_system("SAYC")
    for (bd, what, dlr, vul, auc, seat, hand, was, ok) in BIDDING:
        calls = [_mk(t) for t in auc.split()]
        st = parse_auction(_SEAT[seat], _SEAT[dlr], calls,
                           vulnerability=_VUL[vul])
        b = decide_bid(st, evaluate_hand(_hand(hand)), sayc)
        got = _str(b)
        flag = "ok " if got in ok else "BAD"
        if got not in ok:
            bad += 1
        print(f"[{flag}] {bd:10s} {what}\n        match={was} now={got} "
              f"want={sorted(ok)}  | {b.explanation}")
    return bad


def run_bidding_systems():
    bad = 0
    for (bd, what, sysname, dlr, vul, auc, seat, hand, was, ok) in BIDDING_SYSTEMS:
        calls = [_mk(t) for t in auc.split()]
        st = parse_auction(_SEAT[seat], _SEAT[dlr], calls,
                           vulnerability=_VUL[vul])
        b = decide_bid(st, evaluate_hand(_hand(hand)), get_system(sysname))
        got = _str(b)
        flag = "ok " if got in ok else "BAD"
        if got not in ok:
            bad += 1
        print(f"[{flag}] {bd:10s} {what}\n        match={was} now={got} "
              f"want={sorted(ok)}  | {b.explanation}")
    return bad


def run_leads():
    """RUN2-062: partner's Unusual 2NT showed clubs; lead one vs 3NT."""
    from backend import native_lead
    auc = [_mk(t) for t in "1d 2n x 3c p p 3n p p p".split()]
    d = native_lead.select_opening_lead(
        _hand("Q984..QT9532.T93"),
        Contract(level=3, suit=Suit.NOTRUMP, declarer=Seat.EAST),
        auc, Seat.SOUTH, Seat.WEST, Vulnerability.BOTH)
    ok = d.card.suit == Suit.CLUBS
    print(f"[{'ok ' if ok else 'BAD'}] RUN2-062   lead partner's Unusual-2NT "
          f"suit vs 3NT: {d.card}")
    return 0 if ok else 1


def run_leads_artificial():
    """Run 5: artificial opponent bids must not repel the right lead."""
    from backend import native_lead
    bad = 0
    for tag, hand, auc, dlr, leader, decl, want in (
            ("R5-018", "AT92.QT74.QJ7.64", "1d p 1n p 2h p 2s p 3n p p p",
             Seat.WEST, Seat.NORTH, Seat.WEST, Suit.SPADES),
            ("R5-033", "T7.A8.AT73.KT432", "p p 1c x p 2h p 3c p 3n p p p",
             Seat.NORTH, Seat.SOUTH, Seat.EAST, Suit.CLUBS)):
        d = native_lead.select_opening_lead(
            _hand(hand), Contract(level=3, suit=Suit.NOTRUMP, declarer=decl),
            [_mk(t) for t in auc.split()], dlr, leader, Vulnerability.NONE)
        ok = d.card.suit == want
        bad += 0 if ok else 1
        print(f"[{'ok ' if ok else 'BAD'}] {tag}     lead vs 3NT past artificial "
              f"bids: {d.card} ({d.suit_choice_reason})")
    return bad


def run_dds():
    """libdds mode 0 returns score -2 when the hand to play has only one
    distinct card; the wrapper must return the real trick count."""
    from backend.dds import DDSolver
    # North holds only touching clubs; everything else is irrelevant.
    pbn = "N:...32 ..QT. ..96. .7.K."
    res = DDSolver().solve(5, 0, [], [pbn], solutions=1)
    tricks = max(v[0] for v in res.values())
    ok = tricks == 2
    print(f"[{'ok ' if ok else 'BAD'}] DDS        single-card leaf scores "
          f"real tricks: {tricks} (want 2)")
    return 0 if ok else 1


def main():
    bad = (run_bidding() + run_bidding_systems() + run_leads()
           + run_leads_artificial() + run_dds())
    print(f"\n{len(BIDDING) + len(BIDDING_SYSTEMS) + 4} checks, {bad} failing")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
