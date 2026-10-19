# GATE: CARCOLLIDE-2 S2 -- open-wheel car-to-car contact geometry (demo/native/carcontact.jl).
#
# PO 2026-10-18: "a collision involving contact with a spinning tire causes both cars to spin around ... Right now in
# Julia, two cars hitting is like two beanbags hitting." The old law put the contact point at the 4 x 1.8 m rectangle's
# mid-side, so a side-swipe had no lever arm and turned neither car. A Lotus 49 touches another car with its TYRES, at
# the axles. Checks: where cars touch, rubber vs bodywork, and the yaw a side-swipe gives -- with the old law as control.
include(normpath(joinpath(@__DIR__, "..", "..", "demo", "native", "carcontact.jl")))
fails = Ref(0)
check(name, ok, d = "") = (ok || (fails[] += 1); println("  ", ok ? "PASS" : "FAIL", "  ", rpad(name, 64), d))
println("CARCONTACT gate: open-wheel car-to-car contact")

# two cars heading +x, B alongside at 1.78 m (its tyres overlap A's by 4 cm; the tubs are 1 m apart)
g = car_contact_geom(0.0, 0.0, 0.0, 0.2, 1.78, 0.0)
check("alongside: the cars touch", g !== nothing)
if g !== nothing
    check("alongside: at a TYRE (rubber), not the tub", g[6], "tyre = $(g[6])")
    check("alongside: at an axle, > 0.9 m from the CG along the car", abs(g[1]) > 0.9, "x = $(round(g[1], digits = 2)) m")
    check("alongside: the normal points across (from A to B)", g[4] > 0.9, "n = ($(round(g[3], digits = 2)), $(round(g[4], digits = 2)))")
end
check("1.0 m clear of the tyres: no contact", car_contact_geom(0.0, 0.0, 0.0, 0.0, 2.9, 0.0) === nothing)
# nose to tail on the centreline: nose cone meets gearbox, bodywork
g = car_contact_geom(0.0, 0.0, 0.0, 3.45, 0.0, 0.0)
check("nose to tail: nose cone meets gearbox (bodywork)", g !== nothing && !g[6], g === nothing ? "none" : "tyre = $(g[6])")
check("nose to tail at 3.6 m (an open wheeler is 3.5 m from nose to gearbox): apart", car_contact_geom(0.0, 0.0, 0.0, 3.6, 0.0, 0.0) === nothing)
# a centred side-swipe at 75 km/h, B closing 3 m/s: the yaw it gives A
v = 75/3.6
imp = car_contact_impulse(0.0, 0.0, 0.0, v, 0.0, 0.0, 0.3, 1.76, v, -3.0; θb = 0.0)
check("side-swipe: an impulse", imp !== nothing)
imp !== nothing && check("side-swipe: yaw kick >= 0.5 rad/s (iRacing steps 1.1-2.3)", abs(imp[3]) >= 0.5, "$(round(imp[3], digits = 2)) rad/s")
imp !== nothing && check("side-swipe: costs < 2 m/s of speed", abs(imp[1]) < 2.0, "dvx $(round(imp[1], digits = 2)) m/s")
old = _car_contact_impulse_old(0.0, 0.0, 0.0, v, 0.0, 0.0, 0.3, 1.76, v, -3.0)
check("control (the old law): the same swipe barely turns the car", old !== nothing && abs(old[3]) < 0.4, old === nothing ? "none" : "$(round(old[3], digits = 2)) rad/s")
# S3: the vertical response. A nose cone into a gearbox is low -> nose DOWN (Car3D +pitch = nose up, so dq < 0)
imp = car_contact_impulse(0.0, 0.0, 0.0, 25.0, 0.0, 0.0, 3.5, 0.0, 15.0, 0.0; θb = 0.0)
check("nose into gearbox: an impulse", imp !== nothing)
imp !== nothing && check("nose into gearbox: pitches nose DOWN (rear lifts, as iRacing)", imp[7] < -0.1, "dq $(round(imp[7], digits = 2)) rad/s")
imp !== nothing && check("nose into gearbox: no launch (bodywork, not tread)", abs(imp[5]) < 1e-9, "dvy $(round(imp[5], digits = 2))")
# tread on tread: A's left-front tyre runs into B's right-rear tyre, B 5 m/s slower -> A's front driven UP, nose up
imp = car_contact_impulse(0.0, 0.0, 0.0, 30.0, 0.0, 0.0, 3.0, 1.4, 25.0, 0.0; θb = 0.0)
check("tyre into tyre: an impulse", imp !== nothing)
if imp !== nothing
    check("tyre into tyre: the trailing car is launched (heave up)", imp[5] > 0.5, "dvy $(round(imp[5], digits = 2)) m/s")
    check("tyre into tyre: its nose goes up", imp[7] > 0.5, "dq $(round(imp[7], digits = 2)) rad/s")
end
ib = car_contact_impulse(3.0, 1.4, 0.0, 25.0, 0.0, 0.0, 0.0, 0.0, 30.0, 0.0; θb = 0.0)
ib !== nothing && check("tyre into tyre: the LEADING car's rear is pushed down", ib[5] < 0.0, "dvy $(round(ib[5], digits = 2)) m/s")
# separating cars get nothing
check("separating: no impulse", car_contact_impulse(0.0, 0.0, 0.0, v, 0.0, 0.0, 0.3, 1.76, v, 3.0; θb = 0.0) === nothing)
println(fails[] == 0 ? "CARCONTACT: PASS" : "CARCONTACT: FAIL ($(fails[]))")
exit(fails[] == 0 ? 0 : 1)
