# The Instrumented (Teaching / Analysis) View

The instrumented view is an alternative to the normal card table, toggled with
the **Instrumented** toolbar button. Instead of fanned cards it shows a
four-hand *cross* — each hand is a grid of four suit rows (♠♥♦♣) × two columns
(**Known | Other**) — surrounded by analysis panels:

```
Contract / Tricks |      NORTH       | Plan (winners / losers / trumps)
------------------+------------------+--------------------------------
       WEST       |  table (trick)   |            EAST
------------------+------------------+--------------------------------
 Count / Honours  |      SOUTH       | Coaching / Signals
```

It is meant to serve **both** a trainee (count your tricks, where are the
entries, what is partner signalling?) **and** a strong player (full count,
proven card placement, honour location, squeeze / BLUE readiness). The **Detail**
selector scales how much is shown.

Source: `ui/teaching_view.py`. Pure inference helpers are unit-tested in
`test_teaching_view.py`.

---

## 1. What the books taught us (and where each idea lives)

Everything in the view is grounded in the bridge library under
`/home/h/Documents/260619/rumi3_library/`. The concepts below are organised the
way the panels are.

### Counting — *Klinger, Better Bridge With a Better Memory*; ACBL Encyclopedia
- **A-priori suit breaks** — "odd numbers break evenly, even numbers break
  oddly" (Klinger, ch.4, p.34): 5 out → 3-2 ≈68%, 4 out → 3-1 ≈50% / 2-2 ≈40%,
  etc. → the *split-odds chip* on the Plan panel and the `split_odds()` table.
- **Count the unseen hand** — 40 HCP minus what you can see bounds the two
  hidden hands (Klinger ch.1; ACBL "Probabilities of HCP", p.575) → the
  **Count / Honours** panel's *Unseen HCP* line and per-defender HCP ranges.
- **Vacant spaces** — the chance a missing honour sits in a hand is proportional
  to its remaining empty slots (ACBL "Probabilities A Priori / A Posteriori",
  the 6♠ → ♦Q example, p.434) → `honour_placement()` and the *honour-hint*
  chips in the **Other** column.

### Declarer planning — *Reese, Begin Bridge With Reese*; Frey; Bayone; Klinger
- **Count winners, then ask the dangers** (Reese, "Forming a Plan", p.93) →
  the Plan panel's *Top tricks* line; Klinger's **ARCH** routine (Analyse the
  lead, Review the bidding, Count tricks, How to play) is the panel's spirit.
- **Count losers (LTC) and "shall I draw trumps? if not, why not?"** (Reese,
  "The Count of Losers", p.103; Frey, "Counting Losers") → the *Declarer losers
  (LTC)* line and the verbatim draw-trumps question.
- **The race** — establish your tricks before the defenders cash theirs; lose
  losers early (Bayone ch.21) → the Contract panel's *"declarer needs N more,
  defence needs M to beat it."*
- **Hold-up / Rule of 7** — duck `7 − (cards you and dummy hold)` times to cut
  the danger hand's communication (Klinger ch.4, p.33; ACBL "Hold-Up", p.389)
  → the Plan panel's hold-up counter (`holdup_rule_of_seven()`).
- **Finesses & marked finesses** — a finesse is a-priori 50% until the count
  *marks* the honour's location (Frey, "The Finesse", p.217-219) → Expert
  *finesse hints* (`finesse_hints()`).
- **Entries / transportation** — alternate winners hand-to-hand; use a long
  suit's own honours as entries (ACBL "Entry", p.382; Bayone ch.21) → the Plan
  panel's *Entries:* summary and the cross-hand **→** marker.
- **Danger hand / avoidance** — keep the dangerous defender off lead (ACBL
  "Danger Hand", p.160) → the red ⚠ hand frame, the danger line in the Plan
  panel, and the **KO** knock-out marker.

### Defensive signalling — *ACBL Encyclopedia "Carding"; Sheinwold*
- **Attitude** (high = encourage), **count** (hi-lo = even), **suit-preference /
  Lavinthal** (high = higher side suit), **Smith echo** (NT, on declarer's first
  suit), **trump echo** (hi-lo = odd / a ruff), and **upside-down (UDCA)** — the
  inversion of attitude+count (ACBL "Carding", pp.433-445; Sheinwold "29th Day").
- **Honesty vs false-cards** — signals are sent in clear, so good defenders are
  *mostly* honest but occasionally false-card to scramble declarer's count (ACBL
  "Count Signal" psychology, p.434) → biq's reads carry an honesty flag (✗) when
  the signaller's hand is face-up.

### Inference — *Sheinwold; ACBL Encyclopedia; Frey*
- **Rule of 11** — on a 4th-best lead, `11 − pip` = higher cards in the other
  three hands (Sheinwold "Rule of Eleven"; ACBL p.588) → the Coaching panel's
  *Lead / Rule of 11* read (`rule_of_eleven()`).
- **Marked cards** — a card whose location is now certain (a show-out, the count
  is complete) → placed honours appear in the owner's **Known** column with a
  dashed outline.

---

## 2. What is implemented

### The two columns
- **Known** — cards we can *prove* are in that hand now: exact cards for a
  face-up hand (your hand, dummy, or after Show All), plus, for a hidden hand,
  any card *forced* there (every other hidden hand is void or full). Forced
  cards are drawn with a **dashed outline** — "known, but not seen".
- **Other** — derived information for that suit: the inferred length (a range
  like `2-4`, `void`, or an exact number once pinned), **the latest defensive
  signal** biq has read in that suit (a coloured chip), and **where a missing
  honour probably sits** (e.g. `K?60%`).

### Known-column markers (vivid chips, not superscripts)
| Marker | Meaning |
|--------|---------|
| gold-filled rank | current **master** (boss) of the suit |
| green-boxed rank | a **sure winner** (top of a run you hold) |
| dashed-outline rank | a card **placed by deduction** (hidden hand) |
| **E** chip | **entry** — a sure winner that is access to declarer/dummy |
| **S** chip | **stopper** (notrump) |
| **KO** chip | the danger hand's **knock-out** entry to its long suit |
| **→** chip | a low card that **reaches partner's** winner (transportation) |
| green wash on the suit glyph | the **trump** suit |

### The panels
- **Contract / Tricks** — the contract, tricks won each side, and "the race".
- **Plan** — top tricks, LTC losers, the draw-trumps question, trumps-out + the
  a-priori break, the master trump's location, the **defenders' trump split**
  once it becomes clear (a defender shows out → partner holds the rest), the
  entries summary, the Rule-of-7 hold-up, the danger hand / knock-out, and
  Expert finesse hints.
- **Count / Honours** — unseen HCP, per-defender HCP ranges, a full per-suit
  length table (Expert), honour placement, and squeeze threats / "busy"
  defender (Expert).
- **Coaching / Signals** — the Rule-of-11 lead read, the running list of
  defensive **signal reads** (attitude / count / suit-preference / Smith / trump
  echo) with a ✗ when biq knows a card was a false-card, and play tips.
- **Table** — the current trick and who is on lead.

### Keyboard play
Card play works from this view with the keyboard exactly as on the normal table
(suit key S/H/D/C then a rank, or the rank alone when following suit) — an
app-wide key filter routes the keystroke to the play handler even though a combo
box has focus here.

---

## 3. The header controls

### Detail — `Beginner` / `Intermediate` / `Expert`
Scales how much instrumentation is shown, so the same view suits a learner or an
expert.

| | Beginner | Intermediate | Expert |
|---|---|---|---|
| Known markers | master only | master, winners, entries, stoppers, KO | + cross-hand **→** |
| Other column | proven **void** only | length range + signal + honour hint | + (full count table in the panel) |
| Count / Honours panel | hidden | unseen HCP + ranges | + per-suit table, honour placement, squeeze |
| Signal reads shown | last 2 | last 6 | all, plus ✓ on confirmed-honest |
| Plan extras | basic | hold-up, danger, trumps | + finesse hints, transportation |

### Carding N/S and Carding E/W
The two sides can play **different** signalling agreements, and every signal is
decoded under the **signaller's own** convention — so N/S's cards are read with
the N/S setting and E/W's with the E/W setting. Each is one of four presets:

| Preset | Attitude | Count | Discards |
|--------|----------|-------|----------|
| **Standard** | high = encourage | hi-lo = even | attitude (about the suit thrown) |
| **Upside-down** | low = encourage (UDCA) | lo-hi = even (reverse) | attitude |
| **Std + Lavinthal** | high = encourage | hi-lo = even | **suit-preference** (Lavinthal) |
| **UDCA + Lavinthal** | low = encourage (UDCA) | lo-hi = even | suit-preference (Lavinthal) |

- *Attitude* — the first spot played to partner's suit: encourage or discourage.
- *Count* — high-low vs low-high shows an even / odd number; tightens the
  length range in the Other column.
- *Discards* — **attitude** discards say "I like / don't like the suit I threw";
  **Lavinthal** discards are suit-preference (a high discard asks for the higher
  of the two other side suits, a low one for the lower).

The default preset follows the app's **Preferences → signalling convention**
(Standard or UDCA).

### Smith — `Off` / `Standard` / `Reverse`
The **Smith echo** is a notrump-only agreement made by the *defending* side, so
there is a single control (only one side defends a given deal). On declarer's
**first** suit (after the opening lead), the defender's spot card says whether
the opening lead's suit should be continued:

- **Off** — Smith echo is not in use; those spot cards are read as ordinary count.
- **Standard** — a **high** card means "I liked the opening lead — continue it";
  a low card means "switch".
- **Reverse** — the inversion (high = switch, low = continue), used by pairs who
  play reverse Smith.

When Smith is on, the cards used for the echo are removed from the ordinary
count reads so the same card isn't reported twice.

---

## 4. Notes / limitations
- All reads use **public information only** — biq never peeks at hidden cards to
  produce a read; the honesty (✗) flag only appears when the signaller's hand is
  actually face-up (your hand, dummy, or after Show All).
- Honour-placement percentages are vacant-space estimates and update as the
  count narrows; a *proven* honour (sole possible holder) moves into the Known
  column instead, with a dashed outline.
- The view is safe to refresh at any point in a hand; everything degrades
  gracefully when state is missing.
