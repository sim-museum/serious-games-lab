#!/usr/bin/env python3
"""Cardplay diff — how far is biq's MC play from double-dummy optimal?

For each deal: biq bids a contract, then biq's MC engine plays ALL FOUR hands
trick-by-trick; we count declarer's tricks and compare to the double-dummy
trick count for that exact contract. A negative deficit = biq's actual play
falls short of perfect (declarer mis-plays AND/OR defenders mis-defend, net).
Run at several --samples to see whether the gap is Monte-Carlo NOISE (closes
as samples rise → fixable cheaply) or a TECHNIQUE gap (persists → real work).

  python3 tools/cardplay_eval.py --deals 120 --seed 5 --samples 50,150
"""
from __future__ import annotations
import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.models import (Bid, Seat, Suit, Rank, Card, Hand, BoardState,   # noqa
                            Contract, Trick, Vulnerability)
from backend.native_bidder import parse_auction, evaluate_hand, decide_bid    # noqa
from backend.bidding_systems import get_system                                # noqa
from backend.engine import BridgeEngine                                       # noqa
from backend.dds import DDSolver                                              # noqa

_SEATS = [Seat.NORTH, Seat.EAST, Seat.SOUTH, Seat.WEST]
_STRAIN = {Suit.SPADES: "S", Suit.HEARTS: "H", Suit.DIAMONDS: "D",
           Suit.CLUBS: "C", Suit.NOTRUMP: "NT"}
_RANKS = "AKQJT98765432"
_VUL = {1: "None", 2: "NS", 3: "EW", 4: "Both", 5: "NS", 6: "EW", 7: "Both",
        8: "None", 9: "EW", 10: "Both", 11: "None", 12: "NS", 13: "Both",
        14: "None", 15: "NS", 16: "EW"}
_VMAP = {"None": Vulnerability.NONE, "NS": Vulnerability.NS,
         "EW": Vulnerability.EW, "Both": Vulnerability.BOTH}


def _deal(seed, board):
    rng = random.Random(f"{seed}:{board}")
    deck = [Card(s, r) for s in (Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS,
                                 Suit.CLUBS) for r in Rank]
    rng.shuffle(deck)
    hands = {_SEATS[i]: Hand(cards=sorted(deck[i * 13:(i + 1) * 13],
             key=lambda c: (c.suit.value, c.rank.value))) for i in range(4)}
    return _SEATS[(board - 1) % 4], _VMAP[_VUL[((board - 1) % 16) + 1]], hands


def _pbn(hands):
    def h(hd):
        by = {s: [] for s in (Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS,
                              Suit.CLUBS)}
        for c in hd.cards:
            by[c.suit].append(c.rank.value)
        return ".".join("".join(_RANKS[v] for v in sorted(by[s]))
                        for s in (Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS,
                                  Suit.CLUBS))
    return "N:" + " ".join(h(hands[s]) for s in _SEATS)


def _over(a):
    return (len(a) >= 4 and all(b.is_pass for b in a[-3:])
            and any(not b.is_pass for b in a[:-3])) or \
           (len(a) >= 4 and all(b.is_pass for b in a))


def _contract(auction, dealer):
    seat, last, last_seat, by = dealer, None, None, {}
    for b in auction:
        if not b.is_pass and not b.is_double and not b.is_redouble:
            last, last_seat = b, seat
            by.setdefault((seat.is_ns(), b.suit), seat)
        seat = seat.next()
    if last is None:
        return None
    decl = by[(last_seat.is_ns(), last.suit)]
    return Contract(level=last.level, suit=last.suit, declarer=decl)


def _dd_card(dds, board, contract, trick_cards):
    """The double-dummy-best card for the side on play, given the ACTUAL
    remaining hands (perfect-information single-card play)."""
    strain_i = contract.suit.value + 1
    cur = [c.suit.value * 13 + c.rank.value for c in trick_cards]
    res = dds.solve(strain_i, board.current_trick.leader.value, cur,
                    [_pbn(board.hands)], solutions=2)
    if not res:
        return None
    best = max(res, key=lambda c: res[c][0])
    return Card(Suit(best // 13), Rank(best % 13))


def _play(engine, dds, hands, contract, vul, samples, dd_side):
    """Play the contract; the side named by dd_side ('declarer'/'defense'/
    'none') plays DOUBLE-DUMMY-optimal, the other side plays biq's MC engine.
    'declarer' DD => isolates biq's DEFENSE; 'defense' DD => isolates biq's
    DECLARER; 'none' => both biq (the cancelling net)."""
    trump = None if contract.suit == Suit.NOTRUMP else contract.suit
    board = BoardState(board_number=1, dealer=contract.declarer,
                       vulnerability=vul,
                       hands={s: Hand(cards=list(hands[s].cards)) for s in hands},
                       auction=[], contract=contract)
    decl_ns = contract.declarer.is_ns()
    decl_tricks, leader = 0, contract.declarer.next()
    for _ in range(13):
        trick = Trick(leader=leader)
        board.current_trick = trick
        cur = leader
        for _ in range(4):
            cur_is_decl = (cur.is_ns() == decl_ns)
            use_dd = ((dd_side == "declarer" and cur_is_decl)
                      or (dd_side == "defense" and not cur_is_decl))
            card = None
            if use_dd:
                card = _dd_card(dds, board, contract, list(trick.cards))
            if card is None:
                if not board.tricks and not trick.cards:
                    card = engine.get_opening_lead(board).action
                else:
                    card = engine.get_mc_card_play(
                        board, cur, list(trick.cards), num_samples=samples).action
            board.hands[cur].remove_card(card)
            trick.add_card(card, trump)
            cur = cur.next()
        board.current_trick = None
        board.tricks.append(trick)
        w = trick.winner
        if w.is_ns() == decl_ns:
            decl_tricks += 1
        leader = w
    return decl_tricks


def _c2s(c52):
    return f"{'SHDC'[c52 // 13]}{_RANKS[c52 % 13]}"


_HONOR_RV = {0, 1, 2, 3}        # A K Q J as rank.value


def _defense_fixclass(kind, pos, card, trick_cards, my_suit_ranks, dd_best_rv,
                      opening):
    """Label a DD-suboptimal defensive play by single-dummy FIXABILITY.
    FIXABLE (a real defender would find it): winner/honor pitch, 3rd-hand-low
    (had a higher card, ducked), failure-to-cover an honor. NOT FIXABLE (the
    double-dummy advantage of seeing all hands): 2nd-hand-low (single-dummy-
    correct), small-card parity, omniscient underleads, the DD opening-lead
    problem. Later defensive leads get a 'review' tag (eyeball for cash/return
    failures) rather than being dismissed as quirk."""
    rv = card.rank.value
    if kind == "discard":
        # pitched a top honor on a discard -> usually a thrown winner/guard
        return "winner-pitch" if rv in (0, 1, 2) else "parity-quirk"
    if kind == "lead":
        # opening lead: the classic un-findable DD lead. later leads: maybe a
        # missed cash / suit-return -> review separately.
        return "lead-open-quirk" if opening else "lead-later-review"
    # follow:
    led = trick_cards[0] if trick_cards else None
    # cover-an-honor: an honor was led, biq holds a higher card, played low
    if (led is not None and led.rank.value in _HONOR_RV
            and any(r < led.rank.value for r in my_suit_ranks)
            and rv > led.rank.value):
        return "cover"
    if pos == 2:                       # 3rd hand
        # 3rd-hand-high: biq held a card higher than what it played and DD
        # wanted higher -> a real defender plays high here.
        if any(r < rv for r in my_suit_ranks) and dd_best_rv < rv:
            return "3rd-hand-low"
        return "3rd-review"
    if pos == 1:                       # 2nd hand: low is single-dummy-correct
        return "2nd-hand-quirk"
    return "4th-review"


def _audit_defense(engine, dds, hands, contract, vul, samples):
    """DD declarer + biq defense; at each biq DEFENSIVE play flag when biq's
    card is double-dummy-SUBOPTIMAL (concedes defensive tricks). Returns a list
    of {tn, kind, led, biq, best, cost, pos, fix} — mis-plays + fixability."""
    trump = None if contract.suit == Suit.NOTRUMP else contract.suit
    board = BoardState(board_number=1, dealer=contract.declarer,
                       vulnerability=vul,
                       hands={s: Hand(cards=list(hands[s].cards)) for s in hands},
                       auction=[], contract=contract)
    decl_ns = contract.declarer.is_ns()
    strain_i = contract.suit.value + 1
    errs, leader = [], contract.declarer.next()
    for tn in range(13):
        trick = Trick(leader=leader)
        board.current_trick = trick
        cur = leader
        for _ in range(4):
            if cur.is_ns() == decl_ns:
                card = _dd_card(dds, board, contract, list(trick.cards))
                if card is None:
                    card = engine.get_mc_card_play(
                        board, cur, list(trick.cards), num_samples=samples).action
            else:
                cur52 = [c.suit.value * 13 + c.rank.value for c in trick.cards]
                res = dds.solve(strain_i, trick.leader.value, cur52,
                                [_pbn(board.hands)], solutions=3)
                best = max((t[0] for t in res.values()), default=0)
                if not board.tricks and not trick.cards:
                    card = engine.get_opening_lead(board).action
                else:
                    card = engine.get_mc_card_play(
                        board, cur, list(trick.cards), num_samples=samples).action
                bc = card.suit.value * 13 + card.rank.value
                bd = res.get(bc, [best])[0]
                if bd < best:
                    led = trick.cards[0].suit if trick.cards else None
                    has = led is None or any(c.suit == led
                                             for c in board.hands[cur].cards)
                    kind = ("lead" if not trick.cards
                            else "follow" if has else "discard")
                    pos = len(trick.cards)
                    my_suit_ranks = [c.rank.value for c in board.hands[cur].cards
                                     if c.suit == card.suit]
                    best_same = [cc % 13 for cc in res
                                 if res[cc][0] == best
                                 and cc // 13 == card.suit.value]
                    dd_best_rv = min(best_same) if best_same else 99
                    fix = _defense_fixclass(kind, pos, card, list(trick.cards),
                                            my_suit_ranks, dd_best_rv,
                                            opening=(not board.tricks))
                    ctx = ""
                    if kind == "follow":
                        def _h(seat):
                            return "".join(_RANKS[c.rank.value] for c in sorted(
                                [c for c in board.hands[seat].cards
                                 if c.suit == led], key=lambda c: c.rank.value)) \
                                or "-"
                        dum = contract.declarer.partner()
                        tc = " ".join(_c2s(c.suit.value * 13 + c.rank.value)
                                      for c in trick.cards)
                        ctx = (f"{len(trick.cards)+1}h led {'SHDC'[led.value]} | "
                               f"mine[{_h(cur)}] dummy[{_h(dum)}] | trick: {tc}")
                    errs.append({"tn": tn + 1, "kind": kind, "biq": _c2s(bc),
                                 "best": "/".join(_c2s(c) for c, t in res.items()
                                                  if t[0] == best),
                                 "cost": best - bd, "ctx": ctx,
                                 "pos": pos, "fix": fix})
            board.hands[cur].remove_card(card)
            trick.add_card(card, trump)
            cur = cur.next()
        board.current_trick = None
        board.tricks.append(trick)
        leader = trick.winner
    return errs


_HONORS = {0: "A", 1: "K", 2: "Q", 3: "J", 4: "T"}  # rank.value -> honor


def _side_holding(board, decl, suit):
    """Combined declarer+dummy ranks in a suit, as a string (high->low)."""
    seats = (decl, decl.partner())
    rv = sorted((c.rank.value for s in seats for c in board.hands[s].cards
                 if c.suit == suit))
    return "".join(_RANKS[v] for v in rv) or "-"


def _missing_guess(board, decl, suit):
    """If the declarer side is missing a finesse-or-drop honor in this suit
    (a two-way guess deferral could resolve), return the missing-honor string;
    else ''. Heuristic: own side holds 7+ cards including the suit's top honor
    but is missing the NEXT honor down (classic Qxx-vs-finesse / Jxx guess)."""
    own = sorted((c.rank.value for s in (decl, decl.partner())
                  for c in board.hands[s].cards if c.suit == suit))
    played = {c.rank.value for t in board.tricks for c in t.cards
              if c.suit == suit}
    if len(own) < 7 or 0 not in own and 0 not in played:
        return ""
    # smallest honor rank (0..4) the own side is missing and is still live
    for hv in (1, 2, 3):           # K, Q, J
        if hv not in own and hv not in played and (hv - 1) in own:
            return _HONORS[hv]
    return ""


def _audit_declarer(engine, dds, hands, contract, vul, samples):
    """DD defense + biq declarer/dummy; flag each biq DECLARER-SIDE play that is
    double-dummy-SUBOPTIMAL (vs the true layout). Classify lead/follow/discard
    and whether it BROACHED a two-way-guess suit while on lead (deferrable)."""
    trump = None if contract.suit == Suit.NOTRUMP else contract.suit
    board = BoardState(board_number=1, dealer=contract.declarer,
                       vulnerability=vul,
                       hands={s: Hand(cards=list(hands[s].cards)) for s in hands},
                       auction=[], contract=contract)
    decl = contract.declarer
    decl_ns = decl.is_ns()
    strain_i = contract.suit.value + 1
    errs, leader = [], decl.next()
    for tn in range(13):
        trick = Trick(leader=leader)
        board.current_trick = trick
        cur = leader
        for _ in range(4):
            if cur.is_ns() != decl_ns:                       # DD defender
                card = _dd_card(dds, board, contract, list(trick.cards))
                if card is None:
                    card = engine.get_mc_card_play(
                        board, cur, list(trick.cards), num_samples=samples).action
            else:                                            # biq declarer side
                cur52 = [c.suit.value * 13 + c.rank.value for c in trick.cards]
                res = dds.solve(strain_i, trick.leader.value, cur52,
                                [_pbn(board.hands)], solutions=3)
                best = max((t[0] for t in res.values()), default=0)
                card = engine.get_mc_card_play(
                    board, cur, list(trick.cards), num_samples=samples).action
                bc = card.suit.value * 13 + card.rank.value
                bd = res.get(bc, [best])[0]
                if bd < best:
                    on_lead = not trick.cards
                    led = trick.cards[0].suit if trick.cards else card.suit
                    has = on_lead or any(c.suit == led
                                         for c in board.hands[cur].cards)
                    kind = ("lead" if on_lead
                            else "follow" if has else "discard")
                    guess = _missing_guess(board, decl, card.suit) if on_lead else ""
                    dd_best = "/".join(_c2s(cc) for cc, t in res.items()
                                       if t[0] == best)
                    errs.append({
                        "tn": tn + 1, "kind": kind, "cost": best - bd,
                        "suit": "SHDC"[card.suit.value],
                        "is_trump": (trump is not None and card.suit == trump),
                        "biq": _c2s(bc), "on_lead": on_lead,
                        "guess": guess, "best": dd_best,
                        "hold": _side_holding(board, decl, card.suit)})
            board.hands[cur].remove_card(card)
            trick.add_card(card, trump)
            cur = cur.next()
        board.current_trick = None
        board.tricks.append(trick)
        leader = trick.winner
    return errs


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--deals", type=int, default=120)
    ap.add_argument("--seed", type=int, default=5)
    ap.add_argument("--samples", default="50,150")
    ap.add_argument("--ns-system", default="SAYC")
    ap.add_argument("--ew-system", default="SAYC")
    ap.add_argument("--audit-defense", action="store_true",
                    help="dump each biq defensive mis-play (vs DD-best) by type")
    ap.add_argument("--audit-declarer", action="store_true",
                    help="size the #2 prize: biq declarer mis-plays, how many "
                         "are deferrable two-way-guess broaches vs forced loss")
    a = ap.parse_args()
    sample_counts = [int(x) for x in a.samples.split(",")]
    engine = BridgeEngine()
    dds = DDSolver()
    ns_sys, ew_sys = get_system(a.ns_system), get_system(a.ew_system)

    # Build the contracts once (biq's auction), with their DD trick counts.
    boards = []
    for b in range(1, a.deals + 1):
        dealer, vul, hands = _deal(a.seed, b)
        auction, seat = [], dealer
        for _ in range(60):
            st = parse_auction(seat, dealer, list(auction), vulnerability=vul)
            auction.append(decide_bid(st, evaluate_hand(hands[seat]),
                           ns_sys if seat.is_ns() else ew_sys))
            if _over(auction):
                break
            seat = seat.next()
        c = _contract(auction, dealer)
        if c is None:
            continue
        t = dds.solve_dd_table(_pbn(hands))
        dd = t["NESW"[c.declarer.value]][_STRAIN[c.suit]]
        boards.append((hands, c, vul, dd))

    if a.audit_defense:
        from collections import Counter
        s = sample_counts[0]
        by_kind, cost_kind, total = Counter(), Counter(), 0
        fix_cost, fixable_rows, review_rows = Counter(), [], []
        _FIXABLE = {"winner-pitch", "3rd-hand-low", "cover"}
        for hands, c, vul, dd in boards:
            for e in _audit_defense(engine, dds, hands, c, vul, s):
                by_kind[e["kind"]] += 1
                cost_kind[e["kind"]] += e["cost"]
                total += e["cost"]
                fix_cost[e["fix"]] += e["cost"]
                if e["fix"] in _FIXABLE:
                    fixable_rows.append((c, e))
                elif e["fix"] == "lead-later-review":
                    review_rows.append((c, e))
        print(f"defense mis-play audit — {len(boards)} contracts "
              f"(seed {a.seed}, {s} samples)")
        print(f"  DD-suboptimal defensive plays: {sum(by_kind.values())}, "
              f"costing {total} trick-instances")
        for k in ("lead", "follow", "discard"):
            print(f"    {k:8}: {by_kind[k]:3} mis-plays, {cost_kind[k]} cost")
        fixable = sum(fix_cost[k] for k in _FIXABLE)
        pct = (100.0 * fixable / total) if total else 0.0
        print(f"  FIXABILITY split (single-dummy-findable vs DD-omniscient):")
        for k in ("winner-pitch", "3rd-hand-low", "cover"):
            print(f"    FIXABLE  {k:13}: {fix_cost[k]} cost")
        for k in ("2nd-hand-quirk", "parity-quirk", "lead-open-quirk",
                  "lead-later-review", "3rd-review", "4th-review"):
            tag = "review" if k.endswith("review") else "quirk "
            print(f"    {tag}   {k:18}: {fix_cost[k]} cost")
        review = fix_cost["lead-later-review"]
        print(f"  => FIXABLE defense leak: {fixable}/{total} = {pct:.0f}% "
              f"(+{review} later-lead 'review' to eyeball; rest is "
              f"double-dummy omniscience, not technique)")
        print("  FIXABLE + later-lead mis-plays — biq vs DD-best, position:")
        for c, e in sorted(fixable_rows + review_rows,
                           key=lambda x: -x[1]["cost"])[:18]:
            cs = f"{c.level}{_STRAIN[c.suit]}{c.declarer.name[0]}"
            print(f"    {cs:5} t{e['tn']:<2} [{e['fix']}] biq {e['biq']}->DD "
                  f"{e['best']:<9} | {e['ctx']}")
        return 0

    if a.audit_declarer:
        from collections import Counter
        s = sample_counts[0]
        by_kind, cost_kind = Counter(), Counter()
        defer_cost = defer_n = total = 0
        rows, disc = [], []
        for hands, c, vul, dd in boards:
            for e in _audit_declarer(engine, dds, hands, c, vul, s):
                by_kind[e["kind"]] += 1
                cost_kind[e["kind"]] += e["cost"]
                total += e["cost"]
                if e["kind"] == "discard":
                    disc.append((c, e))
                if e["on_lead"] and e["guess"]:
                    defer_cost += e["cost"]
                    defer_n += 1
                    rows.append((c, e))
        print(f"declarer mis-play audit — {len(boards)} contracts "
              f"(seed {a.seed}, {s} samples). Sizing the #2 (deferral) prize:")
        print(f"  DD-suboptimal declarer-side plays: {sum(by_kind.values())}, "
              f"costing {total} trick-instances")
        for k in ("lead", "follow", "discard"):
            print(f"    {k:8}: {by_kind[k]:3} mis-plays, {cost_kind[k]} cost")
        pct = (100.0 * defer_cost / total) if total else 0.0
        print(f"  DEFERRABLE (on-lead broach of a two-way-guess suit): "
              f"{defer_n} plays, {defer_cost} cost = {pct:.0f}% of declarer leak")
        print("  these are the boards #2 (defer two-way decisions) can address:")
        for c, e in sorted(rows, key=lambda x: -x[1]["cost"])[:12]:
            cs = f"{c.level}{_STRAIN[c.suit]}{c.declarer.name[0]}"
            print(f"    {cs:5} t{e['tn']:<2} broach {e['suit']} (own {e['hold']}, "
                  f"missing {e['guess']}) biq {e['biq']} cost {e['cost']}")
        print(f"  DISCARD mis-plays ({len(disc)}) — biq pitched vs DD-best "
              f"(judge single-dummy fixability):")
        for c, e in sorted(disc, key=lambda x: -x[1]["cost"])[:14]:
            cs = f"{c.level}{_STRAIN[c.suit]}{c.declarer.name[0]}"
            print(f"    {cs:5} t{e['tn']:<2} pitched {e['biq']} ({e['suit']} own "
                  f"{e['hold']}) DD-best {e['best']:<9} cost {e['cost']}")
        return 0

    s = sample_counts[0]
    n = len(boards)
    print(f"cardplay SPLIT — {n} contracts (seed {a.seed}, "
          f"{a.ns_system}/{a.ew_system}, {s} samples). Each side vs DD-perfect:")
    decl_leak = def_leak = decl_b = def_b = 0
    for hands, c, vul, dd in boards:
        biq_decl = _play(engine, dds, hands, c, vul, s, "defense")   # biq DECLARES
        biq_def = _play(engine, dds, hands, c, vul, s, "declarer")   # biq DEFENDS
        decl_leak += dd - biq_decl     # >0 = biq declarer lost tricks vs DD
        def_leak += biq_def - dd       # >0 = biq defense gave tricks vs DD
        if biq_decl < dd:
            decl_b += 1
        if biq_def > dd:
            def_b += 1
    print(f"  biq DECLARER (vs DD defense): loses {decl_leak} tricks over {n} "
          f"deals = {decl_leak/n:+.3f}/deal  (worse on {decl_b}/{n} boards)")
    print(f"  biq DEFENSE  (vs DD declarer): gives {def_leak} tricks over {n} "
          f"deals = {def_leak/n:+.3f}/deal  (worse on {def_b}/{n} boards)")
    print("  (the bigger of these is biq's real cardplay leak; the net "
          "biq-vs-biq measure cancels them.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
