# GATE: CTRL+R must reset EVERY piece of per-session state.
#
#   PO 2026-09-04: "add a key command to julia racer to restart the session on the current track.
#   This should be instantaneous - otherwise you have to wait for the track to reload after goofing
#   up."
#
# WHY THIS EXISTS. A restart that forgets one field is worse than no restart: the session looks new
# and behaves stale, and nothing reports it. The compiler cannot catch a missing line here because
# every one of these names is valid on its own -- the defect is an ABSENCE. So the gate reads the
# restart block out of the sim source and asserts each required reset is present.
#
# The list is not arbitrary. `player_prog` / `player_s_prev` are the accumulator behind
# `prog_delta`; leaving them would carry the OLD lap count into the new session, which is exactly
# the bug class already fixed for teleports (the PO's 1.19 s lap). `LOOSE_WHEELS` must be EMPTIED or
# a wheel detached in the previous session is never redrawn.
#
# Headless: pure text.

const SRC = normpath(joinpath(@__DIR__, "..", "..", "demo", "native", "drive_native_mtk.jl"))
src = read(SRC, String)

i = findfirst("if restart", src)
i === nothing && error("no `if restart` block in $SRC -- has CTRL+R been removed?")
# take a generous window; the block is short
blk = src[first(i):min(length(src), first(i) + 3000)]
j = findfirst("\n        end\n", blk)
blk = j === nothing ? blk : blk[1:last(j)]

fails = Ref(0)
check(name, cond, msg) = (cond || (fails[] += 1); println("  ", cond ? "PASS" : "FAIL", "  ", rpad(name, 46), msg))

println("Session-restart completeness gate (PO: CTRL+R restarts on the current track)")

required = [
    ("car respawned",            "respawnX!"),
    ("damage reset",             "damage_reset!"),
    ("wreck latch cleared",      "WRECKED[] = false"),
    ("detached wheels cleared",  "empty!(LOOSE_WHEELS)"),
    ("lap counter",              "cs.laps = 0"),
    ("lap clock",                "lap_t0"),
    ("best/last lap",            "best_lap = 0.0"),
    ("race-done latch",          "race_done = false"),
    ("per-lap results",          "empty!(player_laps)"),
    ("finish position",          "player_finpos[] = 0"),
    ("launch assist re-armed",   "launch_done[] = false"),
    ("ARC-LENGTH PROGRESS",      "player_prog = 0.0"),
    ("progress anchor re-seeded", "player_s_prev = RaceAI.project"),
    ("phase",                    "phase[] ="),
    ("race-go flag",             "race_go[] ="),
    ("countdown",                "cd_t0[]"),
    ("AI field re-gridded",      "init_cars"),
    ("AI lap clocks",            "ai_lapt0"),
    ("AI stats",                 "aistat_reset!"),
    ("fuel",                     "fuel[] ="),
]
for (name, needle) in required
    check(name, occursin(needle, blk), occursin(needle, blk) ? "" : "MISSING `$needle`")
end

# The progress anchor must be re-seeded FROM THE CAR, not zeroed: `player_s_prev = 0.0` would make
# the next frame's delta a whole lap's worth of progress -- the teleport bug, reintroduced.
check("anchor is re-seeded, not zeroed", !occursin("player_s_prev = 0.0", blk),
      occursin("player_s_prev = 0.0", blk) ? "zeroing it re-creates the teleport lap bug" : "")

# It must NOT reload the track: that is the whole point of the feature.
for bad in ("load_track", "GPLTrack.load", "build_hat", "extract_geometry")
    check("does not reload the track ($bad)", !occursin(bad, blk), "")
end

# NEGATIVE CONTROL: the same check against a block with one reset removed must FAIL.
# (First cut commented the line out instead of deleting it -- and "# player_prog = 0.0" still
#  CONTAINS the needle, so the control could never pass. The control has to remove the text.)
maimed = replace(blk, "player_prog = 0.0" => "")
check("control: a missing reset is detected", !occursin("player_prog = 0.0", maimed),
      "removing the line makes its check fail, as it must")

println()
println(fails[] == 0 ? "  RESTART COMPLETENESS GATE: PASS ✓" : "  RESTART COMPLETENESS GATE: FAIL ($(fails[]))")
exit(fails[] == 0 ? 0 : 1)
