# Q-Plus card-play findings — run 1 (2026-05-23)

Source: `DATA/LOG/log-032.bdl`, probes PROBE-01 … PROBE-04
(probe 5 onward was aborted by a `qbridge.exe not responding`
crash on the 6♥ slam-discard probe).

## Probe-by-probe

### PROBE-01 — Hold-up (overshot to 6NT)

| Field | Value |
|---|---|
| Intended contract | 3NT by S |
| Actual contract | 6NT by S |
| Test position | trick 1, S follows W's ♠Q lead |
| Q-Plus played | **♠A** (grabbed the stopper) |
| What this tells us | In a SLAM contract, declarer cashes the stopper immediately — no time for the holdup. The probe didn't isolate the 3NT-holdup principle because the auction overshot. |
| Action | Re-deal so 3NT is the cap (drop a few HCP from N) and re-run. |

### PROBE-02 — Avoidance ✓

| Field | Value |
|---|---|
| Intended contract | 3NT by S |
| Actual contract | **3NT by S ✓** |
| Test sequence | Tricks 1-4: W's ♦4 lead won by dummy's ♦K; declarer sets up clubs (♣Q-♣8 finesse and cashes the ♣A); declarer attacks spades at trick 4 by leading ♠5 from hand toward dummy's ♠KJ3. |
| Q-Plus's plan | LEAD from S toward dummy's ♠K — finessing W. |
| What this tells us | Q-Plus correctly identifies E as the dangerous opponent (could fire diamonds through declarer's unguarded ♦J62) and chooses the finesse direction that keeps E off lead. ✓ This matches the "avoidance" principle from textbooks. |
| Action | This probe is a textbook teaching example — keep as-is. |

### PROBE-03 — Third-hand-high (a different rule fires!) ✓ DATA

| Field | Value |
|---|---|
| Intended contract | 3NT by S |
| Actual contract | 6NT by S |
| Test position | trick 1, E follows W's ♠J lead with E holding ♠Q72 |
| Q-Plus played | **♠7** (high small) |
| What this tells us | Q-Plus does NOT play third-hand-high here (would have been ♠Q). It also does NOT play lowest (would have been ♠2). Instead it plays the HIGH SMALL — showing **odd count (3 cards)** by present-count convention, even on the FIRST round of the suit under partner's lead. |
| Convention identified | **Standard count under partner's opening lead**: high small = odd count, lowest = even count. This is a *first-round* signal, not just a 2nd-round one. |
| Action | **Broaden `_position_override_card`** so the present-count rule fires on partner-led tricks too, not only opp-led. Done in this session — override now fires 41× per match vs the previous 18×. |

### PROBE-04 — Cover an honor (observed in slam, off-target)

| Field | Value |
|---|---|
| Intended contract | 4♥ by S |
| Actual contract | 6♥ by S |
| Test sequence | Spades not played until trick 12 (declarer drew trumps, ran diamonds, lost ♣A). At trick 12, dummy led ♠4 toward declarer; E with ♠Q played the ♠Q (split-honors). |
| Q-Plus played | **♠Q from Q-bare** on dummy's ♠4 lead. |
| What this tells us | When 2nd hand has Q over dummy's low + can see declarer's AK through inference, the right play is to split (drop the Q to limit declarer to one spade trick). This is "second-hand-high" with split-honors logic. NOT what the probe was supposed to test (cover-of-the-ten-with-the-queen), but a separate principle worth noting. |
| Action | Re-deal probe so 4♥ is the cap and the ♠T is led from dummy at trick 3-4 (before trumps are drawn). |

## Conventions extracted (so far)

1. **Standard count under partner's opening lead.** With Q72 on
   partner's small lead, high small (the 7) = odd, lowest (the 2)
   = even. **Implemented**: `_position_override_card` in
   `engine.py` now covers first-round partner-led case too.

2. **Avoidance: finesse direction picks safe opponent.** When
   dangerous opp threatens, lead toward dummy through the safe
   opp. Q-Plus does this. Not yet encoded — DDS+MC usually
   picks it correctly via expectation; this is more about
   *which suit to attack first* than tie-breaking.

3. **Split honors second-hand-high.** With Qx under partner's
   suit when partner has the AK behind, play Q to limit
   declarer's tricks. Probably a DDS-driven decision (not a
   tie-break); flagged for future investigation.

## Lessons for v2 probes

* **Cap HCP so the auction lands at the intended contract.**
  V1 over-bid 3 of 4 probes into slams. For v2, dial each side
  back ~2-3 HCP and confirm with `probe_bridgeiq_baseline.py`
  before sending to Q-Plus.
* **Test position should be in the first 4 tricks** for
  probes targeting opening-lead reactions or first-suit-attack
  decisions. Cover-honor type tests want the relevant lead in
  trick 2-4, before the long-suit run displaces it.
* **PROBE-02 worked perfectly** — use that as the template:
  reach the intended contract, force the test situation early,
  observe the Q-Plus decision cleanly.

## Next steps

1. Get PROBE-05 through PROBE-08 to complete (re-run after
   bridgeIQ-side bidder fixes, or simplify those deals so
   Q-Plus doesn't crash). The 6♥ slam in PROBE-05 likely
   triggered a Q-Plus stack overflow on long-suit play.
2. Re-deal PROBE-01, 03, 04 to land at 3NT / 4♥ rather than
   slams.
3. Add new probes for specific principles still unprobed:
   suit-preference on discards (PROBE-05 retry), Smith echo,
   trump promotion / uppercut, hold-up by *defender*
   (declarer's long suit + defender's Axx-style holding).

# Run 3 — probes_v2.pbn (2026-05-23, log-033)

All 6 v2 probes completed cleanly (no crash, no hang — the
"no suit > 5 cards" rule worked). PBN [Auction] tags landed
each at the intended contract. Results:

| Probe | Contract | Result | Test fired cleanly? |
|---|---|---|---|
| 09 Smith echo | 4♠-S | +3 | ambiguous |
| 10 Trump promotion | 4♠-S | +1 | no (no forced ruff) |
| 11 Bath Coup | 3NT-S | **-3** | YES — Q-Plus grabbed |
| 12 Suit preference | 3NT-S | +2 | no (no forced discard) |
| 13 Avoidance retry | 3NT-S | = | no (declarer's club line different) |
| 14 Cover honor retry | 3NT-S | -2 | no (♠T never led from dummy) |

## Probe-by-probe

### PROBE-11 (Bath Coup) — clear data ✓

Trick 1: W led ♠K from ♠KQJ32. Dummy ♠T87 played ♠7. E
(short in spades, only ♠6) played ♠6. **S played ♠A** with
the Axxx holding. Declarer then lost 4 tricks in spades plus
others, going -3.

**Finding:** Q-Plus's declarer GRABS the Ace immediately with
Axxx vs KQJxx led. It does not hold up even when ducking would
break the suit (since E was short). This is consistent with
PROBE-01 (the slam-context grab) — Q-Plus's rule appears to
be "cash the stopper" regardless of suit length, not "hold
up to break communications."

**Bridge note:** ducking once here may not have helped anyway
because E was short and would have led elsewhere on the
return — but the principle in textbooks says ALWAYS duck the
first time with Axxx vs the long suit unless you're SURE of
9 tricks. Q-Plus appears not to model that decision.

**Action:** add this as a documented behaviour. The teaching
dashboard could show "Q-Plus grabbed the A here — a beginner
might be tempted to hold up. Both have arguments; in this
hand Q-Plus's choice cost 3 tricks."

### PROBE-09 (Smith echo) — ambiguous

Trick 5: declarer's first club lead (♣K from S). E followed
with ♣2 (lowest). This is consistent with:
  a) Smith-echo LOW = discouraging continuation of hearts
     (which fits E's hand — no heart values), OR
  b) Lowest-equivalent tie-break (no convention at all).

Cannot distinguish without a probe where Smith-echo HIGH
disagrees with lowest-equiv. For v3: design a probe where E
has good hearts AND tied small clubs; Smith says high, default
says low.

### PROBE-10, 12, 13, 14 — test position didn't fire

Each probe's intended decision didn't arise because:
- 10: declarer drew trumps cleanly without needing dummy ruff
- 12: defenders weren't forced into discards
- 13: declarer played clubs without a clear finesse direction
- 14: declarer never led the ♠T from dummy

These probes need redesign. Root cause: at game level (3NT,
4♠) declarer often takes shortcut lines that don't exercise
the principle. Slam contracts force more decisions but also
crash Q-Plus.

## Conventions extracted across all 3 runs

1. **Standard count under partner's opening lead** (from run-1
   PROBE-03). Implemented in `_position_override_card`.

2. **"Cash the stopper" not hold-up with Axxx vs KQJxx**
   (from run-3 PROBE-11). Q-Plus grabs the A on the first
   round even when textbook holds up. Note: this is debatable
   bridge — it might cost tricks (as it did here, -3) but
   Q-Plus does it consistently.

3. **Avoidance: finesse direction picks safe opponent** (from
   run-1 PROBE-02). Q-Plus identifies the dangerous opp and
   finesses through the safe one. Already noted; DDS+MC
   usually catches this without an override.

## Lessons for probe design (v3, if pursued)

* **Game-level contracts undertest declarer's choices.** Many
  decisions don't arise because declarer can win without them.
* **Forcing the test position requires constructed positions**
  where alternatives are clearly worse OR the test card is
  literally the only legal one. Pure "show me a hand and let
  it play" probes miss too often.
* **Pair each new probe with a "control" probe** where the
  expert and default plays differ in opposite directions —
  the comparison disambiguates which rule fires.

## Conclusion

After 3 runs and 14 unique probes:
- 2 conventions cleanly identified and 1 implemented.
- Several probes had inconclusive test positions.
- Q-Plus's stability is fragile under specific patterns (long
  solid suits, slam contracts) — limits the design space.

Diminishing returns on more probe runs without a deeper rework
of probe construction. Recommend: pause probe iteration, ship
the present-count override and the documented "Q-Plus grabs
the stopper" finding as the Phase 3 deliverable, and proceed
to Phase 4 (integration/robustness).
