# TERRAIN-STEP guard (epic #2, 2026-09-05): the pure rule, kept out of main() so a gate can test it.
# `last` is the PLAYER's own previous accepted ground (NaN = none), `g` the new query, `thresh` the
# largest upward jump per query that real ground can produce (measured: 1.58 m; set 3.0 m).
# Returns (accepted::Bool, ground::Float64). Downward steps and small climbs are always accepted;
# an upward jump beyond `thresh` is a wall/island/building in the HAT and the last ground is held.
module StepGuard
export step_guard
function step_guard(g::Float64, last::Float64, thresh::Float64)
    (isnan(last) || g <= last + thresh) && return (true, g)
    (false, last)
end
end
