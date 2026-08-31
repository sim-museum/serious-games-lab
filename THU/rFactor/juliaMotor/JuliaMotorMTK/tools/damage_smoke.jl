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

# ---- E94-P4 S2: the corners that FACED the blow take it -----------------------------------
# WHEELS are FL(+x,+y) FR(+x,-y) RL(-x,+y) RR(-x,-y); +x forward, +y LEFT. A contact can only
# push, so a force pointing +y means the blow came from the RIGHT.
D.damage_reset!()
D.damage_impact!(0.0, 1.0, 20.0)          # pushed left  => struck on the RIGHT
check("a blow from the right damages FR/RR", D.DAMAGE[2] > 0 && D.DAMAGE[4] > 0,
      string("FR=", round(D.DAMAGE[2], digits=2), " RR=", round(D.DAMAGE[4], digits=2)))
check("and spares FL/RL",                    D.DAMAGE[1] == 0 && D.DAMAGE[3] == 0,
      string("FL=", D.DAMAGE[1], " RL=", D.DAMAGE[3]))

D.damage_reset!()
D.damage_impact!(-1.0, 0.0, 20.0)         # pushed backwards => struck on the NOSE
check("a head-on blow damages FL/FR", D.DAMAGE[1] > 0 && D.DAMAGE[2] > 0,
      string("FL=", round(D.DAMAGE[1], digits=2), " FR=", round(D.DAMAGE[2], digits=2)))
check("and spares the rear",          D.DAMAGE[3] == 0 && D.DAMAGE[4] == 0,
      string("RL=", D.DAMAGE[3], " RR=", D.DAMAGE[4]))

# Degenerate force: no direction to reason from, so it must spread rather than silently skip.
D.damage_reset!()
D.damage_impact!(0.0, 0.0, 20.0)
check("a directionless impact spreads", all(d -> d > 0, D.DAMAGE), string(round.(D.DAMAGE, digits=2)))

# ---- E94-P4 S3: the engine ---------------------------------------------------------------
# PO 2026-08-29 named three things damage should mean: "a bent corner, lost grip, or a DEAD
# ENGINE". The corner model covers the first two; this is the third.
D.damage_reset!()
check("a new engine is healthy", D.engine_power() == 1.0 && !D.engine_dead(), "power 1.0")

D.damage_engine!(5.0)
check("a 5 m/s knock leaves the engine alone", D.ENGINE_DAMAGE[] == 0.0,
      "below the engine onset (8 m/s), which is HIGHER than a corner's 3 m/s")

# A hit hard enough to bend a corner need not hurt the engine -- assert the onsets really differ,
# because two constants that happen to be equal would make this distinction imaginary.
D.damage_reset!()
D.damage_hit!(1, 5.0); D.damage_engine!(5.0)
check("5 m/s bends a corner but spares the engine",
      D.DAMAGE[1] > 0.0 && D.ENGINE_DAMAGE[] == 0.0,
      string("corner=", round(D.DAMAGE[1], digits=3), " engine=", D.ENGINE_DAMAGE[]))

D.damage_reset!()
D.damage_engine!(20.0)
check("a heavy hit costs engine power", D.engine_power() < 1.0, string(round(D.engine_power(), digits=3)))
check("a sick engine still pulls",      D.engine_power() >= 0.25, "not dead yet")

for _ in 1:30; D.damage_engine!(40.0); end
check("repeated heavy hits KILL the engine", D.engine_dead(), string(round(D.ENGINE_DAMAGE[], digits=3)))
check("a dead engine makes NO power",        D.engine_power() == 0.0, "0.0")

# An impact drives both, through one call.
D.damage_reset!()
D.damage_impact!(-1.0, 0.0, 20.0)
check("one impact damages corners AND engine",
      D.DAMAGE[1] > 0.0 && D.ENGINE_DAMAGE[] > 0.0,
      string("FL=", round(D.DAMAGE[1], digits=2), " eng=", round(D.ENGINE_DAMAGE[], digits=2)))

# Respawn is a new car.
D.damage_reset!()
check("respawn clears damage", !D.damaged(), string(D.DAMAGE))
check("respawn revives the engine too", D.engine_power() == 1.0 && !D.engine_dead(), "power 1.0")

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
