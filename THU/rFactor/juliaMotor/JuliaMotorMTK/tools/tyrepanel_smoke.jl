# REPLAY-6 (PO 2026-10-09: "add the effective contact patch and traction budget for all 4 wheels overlay from zandracer
# ... to the replay screen"). Headless checks of what the replay's tyre panel shows and records:
#   * DriveRT3D.tyregrip3d reads the tyre model: in a steady LEFT turn the outer (right) tyres carry the bigger grip
#     ellipse, every lateral force points left (+Fy, drawn left of centre), and no tyre is past its ellipse unless sliding;
#   * under braking the front force points back (-Fx, drawn below centre) and the grip ellipse is μx·Fz by μy·Fz;
#   * the sim records the 20 tyre channels (appended after the old ones, so old replays still load) and draws the panel
#     in replay only for the player's car.
include(joinpath(@__DIR__, "..", "src", "drive_rt3d.jl")); using .DriveRT3D
fails = Ref(0)
chk(name, ok, detail = "") = (println("  ", rpad(name, 64), ok ? "PASS" : "FAIL", "   ", detail); ok || (fails[] += 1); ok)
c = DriveRT3D.build_car3d(; v0 = 25.0)
for _ in 1:240; DriveRT3D.step_car3d!(c, 0.35, 0.0, 0.5, 1/60); end
tm = DriveRT3D.telemetry3d(c); t = DriveRT3D.tyregrip3d(c)
chk("the car is turning left (control)", tm.r > 0.2 && tm.ay > 5, "r $(round(tm.r, digits = 2)) rad/s, ay $(round(tm.ay, digits = 1))")
chk("outer front's grip ellipse > inner's (load transfer)", t[2][4] > 1.5t[1][4], "FR $(round(t[2][4], digits = 2)) vs FL $(round(t[1][4], digits = 2))")
chk("outer rear's grip ellipse > inner's", t[4][4] > 1.5t[3][4], "RR $(round(t[4][4], digits = 2)) vs RL $(round(t[3][4], digits = 2))")
chk("every lateral force points into the turn (+Fy = left)", all(w -> w[2] > 0, t), join((round(w[2], digits = 2) for w in t), " "))
chk("a gripping tyre's force is inside its ellipse", all(w -> w[5] >= 1 || hypot(w[1]/w[3], w[2]/w[4]) <= 1.02, t),
    join((round(hypot(w[1]/w[3], w[2]/w[4]), digits = 2) for w in t), " "))
c2 = DriveRT3D.build_car3d(; v0 = 40.0)
for _ in 1:60; DriveRT3D.step_car3d!(c2, 0.3, 0.0, 0.0, 1/60); end
for _ in 1:16; DriveRT3D.step_car3d!(c2, 0.0, 0.6, 0.0, 1/60); end
b = DriveRT3D.tyregrip3d(c2)
chk("braking: both axles' force points back (-Fx)", b[1][1] < -0.5 && b[3][1] < -0.3, "front $(round(b[1][1], digits = 2)), rear $(round(b[3][1], digits = 2))")
chk("braking: the ellipse is μx·Fz tall by μy·Fz wide (μx > μy)", b[1][3] > b[1][4] > 0, "$(round(b[1][3], digits = 2)) x $(round(b[1][4], digits = 2))")
src = read(joinpath(@__DIR__, "..", "..", "demo", "native", "drive_native_mtk.jl"), String)
chk("the replay records the 20 tyre channels after the old 12", occursin("[string(q, \"_\", w) for w in (\"FL\", \"FR\", \"RL\", \"RR\") for q in (\"fx\", \"fy\", \"gx\", \"gy\", \"xi\")]...]", src) &&
    occursin("for w in tyre_lp[], q in w; push!(tele_buf, Float32(q)); end", src))
chk("the panel is drawn in replay, player car only", occursin("if REPLAY && rep_tyshow[] && rep_focus[] == 0 && rep_tyres[] !== nothing", src))
println(fails[] == 0 ? "ALL PASS" : "FAILURES: $(fails[])")
exit(fails[] == 0 ? 0 : 1)
