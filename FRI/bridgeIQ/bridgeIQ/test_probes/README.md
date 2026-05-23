# BridgeIQ card-play probe suite

Eight curated deals designed to isolate ONE card-play principle each, so
that Q-Plus's choice reveals what rule it's using internally. Each probe
is built so that:

* The contract is forced by the auction.
* A specific trick / card decision is the test point.
* The "principle" play and the "DDS-default" play are visibly different.
* All other tricks are mechanical (no other interesting decisions in the
  way), so the only signal in the log is what Q-Plus did at the test
  point.

## How to run

1. Copy `probes.bde` into Q-Plus's own-deals directory:
   ```
   FRI/WP/drive_c/games/qbridge17/DATA/OWN-DEALS/PROBES.BDE
   ```
2. In Q-Plus: Deal → Match control → Deal source: **Own deal file** →
   select `PROBES.BDE`. Set Scoring: Team (IMP), Comparison: None or
   later, # boards: 8.
3. Play each deal as South (or use Autoplay) to completion. The log goes
   to `DATA/LOG/log-NNN.bdl` (next number).
4. Run `tools/probe_analyzer.py --bdl LOG/log-NNN.bdl` to extract
   Q-Plus's choice at each test point and print the inferred rule.

## Probe-by-probe

Each probe lists the contract, the lead, the test position
(trick / seat / what cards are tied), and what Q-Plus's choice will
tell us.

### PROBE-01 — Hold-up by declarer in a 5-card opponent suit

* **Contract:** 3NT by South. North-South have 9+ top tricks via
  KQJT9 of clubs and AKJ of diamonds plus the AK of spades. South
  is declarer.
* **Layout:** S has ♠AK4, dummy has ♠32. West holds ♠QJT86 (5
  spades) and will lead from there. East has ♠975 (3 spades).
* **Lead:** ♠Q from W.
* **Test:** trick 1, after dummy's ♠2 and East's ♠5, South must
  choose ♠A, ♠K, or ♠4 (small duck). DDS computes 9 tricks any way
  declarer plays since there are no entry threats — so this is a
  tied set in DDS terms.
* **Principle:** ducking once breaks the spade-suit communication
  if East has a doubleton, even though it isn't strictly needed
  here. Q-Plus's choice (duck → ♠4 or grab → ♠A/K) tells us
  whether its rule is "duck for safety when ducking costs nothing"
  or "cash the top stopper to preserve trick count."

### PROBE-02 — Avoidance play (keep dangerous opp off lead)

* **Contract:** 3NT by South.
* **Layout:** S has the long club suit (AK763 + dummy's Q98 = 8
  cards), needing one of two finesses for a 9th trick. East ought
  to be kept off lead because East could fire spades through the
  unguarded K (♠KJ3 in dummy, ♠A75 with S). The diamond suit gives
  declarer 5 top tricks and clubs give 4 more.
* **Lead:** typically ♥J from W (away from KJTx).
* **Test:** declarer plays the club suit for the 9th trick.
  Available finesses:
    - lead toward dummy's ♣Q to drop the ♣J in East — keeps West
      off lead (safe).
    - lead toward South's ♣AK to drop a doubleton ♣Jx in West
      (low chance) — would let East win if it fails.
* **Principle:** avoidance — take the finesse that keeps the
  dangerous opponent (East) off lead, even if the simpler line is
  slightly higher percentage in isolation. Q-Plus's choice of
  *which way to finesse clubs* reveals whether its rule weights
  "danger" the same way an expert would.

### PROBE-03 — Third-hand-high on partner's opening lead

* **Contract:** 3NT by South. Dummy is North with ♠654 ♥AKQ
  ♦KQJ ♣KJT9.
* **Layout:** S has ♠AK, dummy's ♠654 is the threat. W (opening
  leader) has ♠JT983 (5 small) and the 2 of clubs (effectively
  out of clubs). E has ♠Q72.
* **Lead:** ♠3 from W (fourth best).
* **Test:** trick 1. After dummy's ♠4 (small), East's choice:
  ♠Q, ♠7, or ♠2. The DDS calculation may tie ♠Q with ♠7 (both
  lose if South wins with the A or K) — both result in 9 tricks
  for declarer eventually. The "tied" set includes ♠2/♠7/♠Q.
* **Principle:** third-hand-HIGH except when dummy has a tenace.
  Here dummy is ♠654 — no tenace — so East should play ♠Q (force
  South's ♠A and protect partner's tricks). Q-Plus's choice of
  ♠Q vs ♠7 vs ♠2 tells us whether it follows "third hand high"
  strictly or modulates by dummy's holding.

### PROBE-04 — Cover an honor with an honor

* **Contract:** 4♥ by South (5-3 fit).
* **Layout:** Dummy (N) has ♠T4 — the ♠T is the threat against
  East's ♠Q95. S has ♠A32. If declarer leads the ♠T from dummy,
  East must decide: cover with ♠Q or duck.
* **Lead:** any (entries already made).
* **Test:** mid-hand, declarer leads dummy's ♠T toward South's
  ♠A32, intending to drop East's ♠Q in the air. East must choose
  ♠Q (cover) or ♠5/9 (duck).
* **Principle:** cover an honor with an honor when promotion in
  partner's hand is possible. Here East's ♠Q is the only honor
  W can't beat — covering forces declarer's ♠A and promotes
  West's ♠KJ876 to two tricks. Q-Plus's choice tells us whether
  its rule covers consistently or only when MC-DDS thinks it's
  necessary.

### PROBE-05 — Suit-preference signal on a discard

* **Contract:** 6♥ by South (heart slam, 6-card fit). North runs
  6 heart tricks; declarer needs to find which side suit to
  attack for the 12th trick.
* **Layout:** Defenders W and E will be squeezed-discarding on
  the long heart run. W has clubs QJT9 and a 6-card spade suit;
  E has 3 small in hearts and various filler. The first defender
  forced to discard is W on round 4 of hearts.
* **Lead:** ♣Q from W (top of sequence).
* **Test:** trick 4 of hearts, W discards. Available: any spade
  or any diamond. The discard signals suit preference — high
  spade asks for spades, low diamond asks for diamonds (or
  attitude — but Q-Plus's discard convention is what we want).
* **Principle:** Lavinthal / suit preference on discards.
  Q-Plus's choice of *which suit and which rank* W throws on
  the first forced discard will reveal whether it uses high =
  "want this suit" or upside-down attitude (high = don't want).

### PROBE-06 — Attitude on partner's opening lead

* **Contract:** 4♠ by West (5-3 fit, contested auction).
* **Layout:** S (declarer) has nothing special. N (dummy after
  W's auction wait, this is mis-labeled — let me re-spec). Actually:
  W declares 4♠. N is defender. E is N's partner. E leads.

  E leads ♥A from AKx. South (declarer) is on lead at trick 1
  — wait, W declares. So lead is from N. Let me re-state:
  W declares 4♠, lead from N. N has ♥T54, leads the ♥4. Dummy
  (E) has ♥AK8. S (3rd hand) has ♥QJ96.

* **Lead:** ♥4 from N (3rd-and-5th convention shows even count).
* **Test:** trick 1. After E's ♥A (winning), S must signal.
  S's tied set: ♥9, ♥6 (the ♥Q and ♥J should be saved for
  potential tricks).
* **Principle:** attitude on partner's lead — ♥9 = high =
  encouraging (S has values, continue), ♥6 = low = discouraging
  (S has no values, switch). Q-Plus's pick tells us whether it
  signals high-encouraging or upside-down.

### PROBE-07 — End-play / throw-in

* **Contract:** 6♣ by South. Long club suit and side AKQJ of
  diamonds make 11 top tricks. 12th trick requires either a
  spade finesse OR an end-play of West.
* **Layout:** S has ♠A76 ♣AKJT9 plus diamond winners. Dummy's
  ♠KJ5 holds the position. West will have to lead spades
  eventually if stripped of exits.
* **Lead:** ♠T from W (top of nothing).
* **Test:** by trick 10 declarer has cashed all winners except
  the spade position. W is on lead and forced to lead a spade
  into ♠AKJ → 12th trick.
* **Principle:** preparing the end-play instead of taking the
  spade finesse on its own merits. Q-Plus's line — does it
  finesse immediately or strip-and-end-play? — tells us
  whether it sees the throw-in.

### PROBE-08 — Discard choice with two long suits

* **Contract:** 6♥ by South. N has solid AKQJT9 of hearts (6
  cards). S has Qxxxxxx in clubs (7 cards).
* **Layout:** W is heavily endplayed; after the long heart run
  + 1 club, W must discard from {♠87, ♦QJT5, ♣JT9}.
* **Lead:** ♣J from W (top of nothing in clubs).
* **Test:** discards on long heart run. W's tied set for
  discards includes spades and diamonds. The choice signals
  what W "doesn't want partner to lead" (or wants).
* **Principle:** Q-Plus's discard convention. Combined with
  PROBE-05, the two probes triangulate: high-spade or
  low-spade preference for *what* signal type.

## Inferring the rule from Q-Plus's choice

For each probe, after Q-Plus plays through, look at the test
position in the log (BDL file). The 1-2 cards Q-Plus chose at
the test point should clearly indicate which side of the
principle's binary it falls on. If Q-Plus's choice matches the
"expert principle" play, encode that as a position-specific
override in `_position_override_card` (engine.py). If it
matches the "DDS-default" play, then no override is needed —
DDS+MC already covers it.

After all 8 probes are run, we should have between 3 and 6
new conventions documented and codeable. With each new
convention firing 3-5% of cards on average (similar to the
current present-count rule), the cumulative effect on the
match rate against Q-Plus should be measurable. Reasonable
target: 68-69% → 72-74%.

## A note on probe validity

These probes are hand-crafted to isolate ONE principle each.
That makes them GREAT for teaching ("look — Q-Plus covers the
honor here, just like the textbook says") but each probe is
only one data point. To be confident a rule generalises,
ideally run 3-5 deals per principle. The 8 probes here are a
*starting catalogue* — extend with variants once the basic
shape of each rule is known.

## Caveat — Q-Plus bids each deal itself

The BDE format provides only hands; Q-Plus then runs its own
bidder to reach a contract. This means the *intended* contract
in each probe (described above) may not be the *actual*
contract Q-Plus arrives at. If the probe targets a particular
trick-1 / trick-N decision but the auction lands in 5♣ instead
of 3NT, that probe will exercise a different principle.

Two workarounds:

1. **Inspect the BDL log** after Q-Plus runs the probes. The
   contract Q-Plus actually played is at the top of each deal
   block. If a probe didn't reach the intended contract, the
   `probe_analyzer.py` output will still show what Q-Plus chose
   at the test position — that's often still informative for a
   *different* principle (the deal hasn't gone to waste).

2. **Convert to PBN** with embedded `[Auction]` and `[Play]`
   tags to force the contract. Q-Plus supports PBN import via
   *Deals → Import → PBN*. Future revision could ship probes
   as PBN with the auction pinned. The BDE format here is
   simpler to author and inspect, hence v1.

The first time you run the suite, treat it as a *calibration*
pass — see what Q-Plus does in each, refine the hands so that
the auction reaches the intended contract more reliably, then
re-run a second time for clean data on each principle.

### v1 calibration status (bridgeIQ-side)

Running `probe_bridgeiq_baseline.py` against bridgeIQ's
Precision90M bidder produces the contracts below. Probes whose
contract matches intent are ready to test; the rest need hand
refinement before they probe the right principle:

| Probe | Intended | bridgeIQ reaches | Status |
|---|---|---|---|
| 01 holdup            | 3NT by S  | 2NT by S        | under-bids — boost S's HCP |
| 02 avoidance         | 3NT by S  | **3NT by S**    | ✓ ready |
| 03 third-hand-high   | 3NT by S  | 6NT by S        | over-bids — slam off the spot |
| 04 cover-honor       | 4♥ by S   | 2♥ by S         | under-bids — boost S |
| 05 suit-preference   | 6♥ by S   | 1♣ by S         | passed out — need stronger hands |
| 06 attitude-lead     | 4♠ by W   | **4♠ by W**     | ✓ ready |
| 07 endplay-throw-in  | 6♣ by S   | 3NT by S        | wrong strain — boost clubs |
| 08 discard-choice    | 6♥ by S   | 2♥ by S         | under-bids — boost values |

Q-Plus's bidder may reach different contracts than bridgeIQ on
the same hands; run the BDL through `probe_analyzer.py` and
check the actual contract per probe before reading the test
position. If Q-Plus also lands at the wrong contract, that
probe needs a re-deal — bump the relevant side's HCP and add
a 5-card source of tricks until both bidders find the intended
strain.
