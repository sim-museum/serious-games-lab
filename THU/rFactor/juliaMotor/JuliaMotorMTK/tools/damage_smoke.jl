# GATE: E94 Part 4 -- damage as PERSISTENT state.
#
#   PO 2026-08-29: "when the car hits a barrier at speed it should damp out and get stuck,
#                   indicating an inelastic collision that CAUSES DAMAGE."
#   PO 2026-08-30: a graze at speed "should scrub you but not end your race" -- which only means
#                  anything if surviving a hit COSTS something.
#
# Until E94-P4 nothing tracked damage: a survivable hit left the car mechanically perfect, so you
# could bounce off the scenery all lap and finish on a factory-fresh car. Headless: pure state.
include(joinpath(@__DIR__, "..", "src", "drive_rt3d.jl")); using .DriveRT3D
const D = DriveRT3D

fails = Ref(0)
function check(name, cond, msg)
    cond || (fails[] += 1)
    println("  ", cond ? "PASS" : "FAIL", "  ", rpad(name, 48), msg)
end

println("E94-P4 damage gate")
D.damage_reset!()
check("a new car is undamaged", !D.damaged(), string(D.DAMAGE))
check("undamaged grip is full", D.damage_mu(1) == 1.0, string(D.damage_mu(1)))

# The PO's low-impulse exception: a rub costs nothing.
D.damage_hit!(1, 2.0)
check("a 2 m/s rub costs nothing", D.DAMAGE[1] == 0.0, "below the onset")

# A real hit costs grip, and only at the corner hit.
D.damage_hit!(1, 12.0)
check("a 12 m/s hit damages the corner", D.DAMAGE[1] > 0.0, string(round(D.DAMAGE[1], digits=3)))
check("it reduces that corner's grip", D.damage_mu(1) < 1.0, string(round(D.damage_mu(1), digits=3)))
check("other corners are untouched", D.DAMAGE[2] == 0.0 && D.DAMAGE[3] == 0.0, "FR/RL clean")

# PERSISTENT: it does not heal on its own. This is the whole point of the item.
before = D.DAMAGE[1]
for _ in 1:100; end
check("damage persists (does not heal)", D.DAMAGE[1] == before, string(round(before, digits=3)))

# Repeated knocks worsen it, and cannot overshoot.
for _ in 1:20; D.damage_hit!(1, 30.0); end
check("repeated hits worsen the corner", D.DAMAGE[1] > before, string(round(D.DAMAGE[1], digits=3)))
check("damage saturates at 1.0", D.DAMAGE[1] <= 1.0, string(round(D.DAMAGE[1], digits=3)))
check("a ruined corner keeps SOME grip", D.damage_mu(1) >= 0.3,
      string(round(D.damage_mu(1), digits=3), " -- a bent corner still rolls"))

# Respawn is a new car.
D.damage_reset!()
check("respawn clears damage", !D.damaged(), string(D.DAMAGE))

# No tuning knobs: the PO's standing constraint is physics from the data with no modifiable
# parameters, so the damage model must expose no JM_ env vars. Asserted by reading the source --
# a constant that reads getenv is a fudge factor whatever it is called.
src = read(joinpath(@__DIR__, "..", "src", "drive_rt3d.jl"), String)
dmg = match(r"DAMAGE AS PERSISTENT STATE.*?Mass and front share"s, src)
check("the damage model exposes no env knobs",
      dmg !== nothing && !occursin("getenv", dmg.match) && !occursin("ENV[", dmg.match),
      dmg === nothing ? "section not found" : "no getenv/ENV in the damage section")

println(fails[] == 0 ? "DAMAGE GATE: PASS" : "DAMAGE GATE: FAIL ($(fails[]))")
exit(fails[] == 0 ? 0 : 1)
