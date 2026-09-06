# RACESTART-1 probe: a stationary player on a standing grid, with AI starting BEHIND.
#
# Reproduces the PO's geometry of 2026-09-05 ("stopped at start of race, in 3rd position out of 5
# cars ... AI cars behind me clip off both my front wheels"). Prints one RESULT line for the gate.
# Arm with JM_AI_YIELD_RATE=1000 for the pre-fix per-frame lateral teleport.
include(joinpath(@__DIR__, "gpldat.jl"));   using .GPLDat
include(joinpath(@__DIR__, "gpltrack.jl")); using .GPLTrack
include(joinpath(@__DIR__, "ai.jl"));       using .RaceAI
using Random

function main()
    Random.seed!(7)
    T = "/home/admin/sgl-julia-racer/THU/WP/drive_c/Sierra/GPL/tracks/watglen"
    dat = GPLDat.parse_dat(joinpath(T, "watglen.dat"))
    tmp = tempname()*".trk"; write(tmp, dat["watglen.trk"])
    line = RaceAI.build_line(GPLTrack.trk_centreline(tmp), (x,z) -> 0.0)
    RaceAI.aistat_reset!()
    # A five-car standing grid at s = 0. init_cars staggers ~9 m and ALTERNATES lanes, which is the
    # whole point: the car behind the player is in the other grid column, so the blocker scan in
    # step 1 (which needs |player_lane - car.lane| < CAR_WID + 0.6) does not see the player at all.
    cars = RaceAI.init_cars(line, 4; start_s = 0.0)
    ps    = mod(0.0 - 9.0*2, line.total)     # the P3 slot, two rows back
    plane = 0.0                              # the player sits ON the racing line
    deleteat!(cars, 2)                       # that slot belongs to the human, not an AI
    # The cars BEHIND are put in the player's lane. That is not a convenience: the alternating grid
    # columns last only until the AI steer back to the racing line, which is where a car stalled on
    # the grid is sitting -- and lateral overlap is the whole complaint ("clip off both my front
    # wheels"). A car that goes past 4.8 m clear in the other column is overtaking, not driving
    # through, and a gate that counted that would fail an innocent pass and prove nothing.
    rel(c) = mod(c.s - ps + line.total/2, line.total) - line.total/2
    behind = [c for c in cars if rel(c) < 0]
    for c in behind; c.lane = plane; c.tlane = plane; end
    passed = 0; hits = 0
    for _ in 1:round(Int, 12*60)             # 12 s covers the whole getaway
        # v = 0.0: the player is STATIONARY, exactly as described.
        (_, hit) = RaceAI.step_field!(cars, line, 1/60; amax = 8.0, vmax = 74.0,
                                      player = (ps, plane, 0.0))
        any(c -> rel(c) > 0, behind) && (passed += 1)
        # CONTACT MUST BE READ FROM step_field! ITSELF. Testing the overlap here, after the call,
        # counts zero in BOTH arms: step 3 shoves the AI 1.3 m sideways the instant it overlaps, so
        # the condition is already resolved by the time the caller can look. The instrument has to
        # sit where the event happens, not downstream of the code that erases it.
        hit && (hits += 1)
    end
    println("RESULT behind=", length(behind), " passframes=", passed, " hits=", hits,
            " hardyield=", RaceAI.AISTAT.hardyield)
end
main()
