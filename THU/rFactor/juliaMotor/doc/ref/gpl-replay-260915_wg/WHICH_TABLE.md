# Which table is which in `*_Complete.txt`

_Added GOLDVID-JR-2 S7 (2026-09-16), after one sprint quoted the wrong column and three others
built on it._

GPL Replay Analyser's `Complete` report contains **several per-driver time tables**. They are not
interchangeable, and on a short race some of them agree by coincidence — which is exactly how a
wrong one survives a spot-check.

| heading | time column | what it is | safe to quote as |
|---|---|---|---|
| `RACE RESULT` | `Race Time` / `Diff` | cumulative elapsed, and gap to the winner | **race time, finishing gaps** |
| `RACE FASTEST LAPS` | `Time` (+ the lap it was set on) | each driver's **best** lap | **best lap** |
| `RACE LAPTIME CONSISTENCY (first lap excluded)` | `Avg Laptime` | the **mean** of the laps after the first | *not* a best lap |
| `PRACTICE TIMES` | `Time` / `Diff` / `Laps` | practice best and gap | practice best |

## The trap, concretely

`260915_wg` is a **2-lap** race. With the first lap excluded, `Avg Laptime` averages **one lap —
lap 2**. Four of the five AI set their best on lap 2, so for them `Avg Laptime` **equals** the best
lap. **Graham Hill set his best on lap 1** (`Lap 1: 1m36.426s`, `Lap 2: 1m39.001s`), so his does not:

```
RACE FASTEST LAPS              Graham Hill   1m36.426s   1     <- his best
RACE LAPTIME CONSISTENCY       Graham Hill   1m39.001s   2     <- his lap 2
```

TELEMSTATE-1 S3 built its AI-pace calibration from the second table, labelled the column *"gold lap"*,
and recorded Hill at 99.001 s. That single row set the bottom of the field, so the gold's spread came
out **9.79 %** instead of **6.93 %** — and AISPREAD-1 S1, S3 and S4 all compared against it. The
correction (GOLDVID-JR-2 S6) reversed the recommendation on `JM_AI_TEMPER`.

⚠️ The analyser's own `Laps` column reads **2** in the consistency table while averaging one lap.
That is the tool's quirk, not a mis-read.

## Rule

Quote the table by its **heading**, never by column position — and prefer an extraction another
sprint has already written into the backlog over a fresh read of the raw report, because the fresh
read is where the column gets picked again.
