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
