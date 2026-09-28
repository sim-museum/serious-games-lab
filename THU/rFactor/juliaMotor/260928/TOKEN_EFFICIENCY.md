# Token efficiency — rules for working on this project

Written 2026-09-28, after a 6-hour session consumed ~26 % of a weekly token budget.
Kept short on purpose.

## The mechanism (why costs explode here)

Every tool call re-sends the **entire conversation**. Cost scales as
*(context length × number of calls)*. A long session with many small calls is the worst case:
150+ calls against a context of several hundred thousand tokens means tens of millions of
token-reads, even though no single action looked expensive.

Two things make this project especially exposed:

- **Sim runs are slow** (3–12 min per track parse), which invites polling.
- **Tool outputs are large** (gate logs, censuses, placement dumps), and once in context they are
  re-sent for the rest of the session.

## Rules for Claude

1. **Wait once per background job.** One blocking wait with an `until` condition — never a series
   of "has it finished yet" calls. Repeated polling was the single biggest waste in the 2026-09-28
   session.
2. **Filter every tool output at the source.** `grep`/`head`/`cut` before it reaches context. Never
   `cat` a log.
3. **Iterate in throwaway scripts, report only the result.** Five attempts at one measurement
   should cost one context entry, not five full outputs.
4. **Short commit messages.** Facts and numbers only. Detail belongs in `PRODUCT_BACKLOG.md`, written
   once. Several 40-line messages in one session is too much.
5. **Say when the session is getting expensive**, and suggest a reset, rather than letting it run.
6. **Prefer one decisive measurement over three cheap ones.** Design the instrument before running
   it; a wrong ruler costs the run *and* the re-run.
7. **Do not re-read files already in context.** The harness tracks file state.

## Rules for the product owner

1. **Start a fresh session per backlog item.** By far the largest lever — it resets the multiplier.
2. **Avoid `/loop` with a short interval for multi-hour work.** A 20-minute tick inside a long
   session is close to worst-case: each tick pays for everything that came before. Prefer an
   explicit *"do item X, report, stop"*.
3. **Say "terse mode"** when throughput matters more than documentation.
4. **Use a cheaper model for exploration.** Greps, log reading and file hunting do not need a
   1M-context model; save that for reasoning and design.
5. **Ask for a cost estimate** before authorising anything unattended and long-running.

## Cheap vs expensive, in this codebase specifically

| task | cheap way | expensive way |
|---|---|---|
| wait for a gate suite | one `until … done` call | repeated status checks |
| find a defect location | a standalone `julia` script over the `.dat`/`.trk` | a full sim launch per question |
| compare two settings | one script that sweeps both arms and prints a table | one sim run per arm, output dumped |
| record a finding | one backlog entry | a long commit **and** a long backlog entry |
| inspect a texture/placement list | `grep`-filtered to the rows in question | full census printed |

## What this cost last time, concretely

The 2026-09-28 session ran 16 commits across 5 backlog items in one unbroken context, with a
20-minute self-scheduled loop. Avoidable waste, in rough order of size:

1. Polling loops waiting on gates and sim runs.
2. Five iterations of one measurement, each with full sim output in context.
3. Large censuses printed unfiltered.
4. Very long commit messages duplicating the backlog.
5. Never resetting the session between the five items.
