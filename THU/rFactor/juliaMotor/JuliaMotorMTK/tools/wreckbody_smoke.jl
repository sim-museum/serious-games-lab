# CRASHBODY-1 (PO 2026-10-20: "The car should be treated as a rigid body with rotation, including rotation of each wheel,
# with moments of inertia. This levitation where the wheels stay level is non-physical."): the crash-mode rigid body
# (demo/native/wreck_body.jl) on its own -- no track, no window. Runs under the demo/native project (StaticArrays).
#   1. dropped upright: lands on its four tyres, level, at its static height, and comes to rest
#   2. dropped upside down: rests on the roll hoop / nose / tail -- nothing below the ground
#   3. launched rolling (the PO's wreck: a roll rate, a lift): it lands and comes to rest ON THE GROUND, no frame jump,
#      and its energy (kinetic + potential) never grows
#   4. each wheel spins with its own inertia: locked wheels on a rolling car spin up to road speed
#   5. into a wall off-centre: it does not pass through, and the hit turns it
#   6. at rest it stays exactly still
using Printf, LinearAlgebra
include(joinpath(@__DIR__, "..", "..", "demo", "native", "wreck_body.jl")); using .WreckBody
const WB = WreckBody
ok = true
check(c, msg) = (global ok &= c; println(c ? "  PASS " : "  FAIL ", msg))
deg(x) = round(rad2deg(x), digits = 1)
V3 = WB.V3
flat = WB.Plane(0.0)

function run!(b, secs; plane = flat, walls = WB.WallPlane[], every = nothing)
    dt = 1/60; maxjump = 0.0; egain = 0.0; pprev = b.p
    epot(b) = b.g.m*WB.G*(b.p[2] - WB.plane_y(plane, b.p[1], b.p[3]))
    e0 = WB.energy(b) + epot(b)
    for k in 1:round(Int, secs/dt)
        WB.step!(b, dt, plane; walls = walls)
        maxjump = max(maxjump, norm(b.p - pprev) - norm(b.v)*dt*1.5); pprev = b.p
        e = WB.energy(b) + epot(b); egain = max(egain, e - e0); e0 = min(e0, e)
        every === nothing || every(b, k)
    end
    (maxjump = maxjump, egain = egain)
end
lowest(b; plane = flat) = minimum(q -> (p = b.p + b.R*q; p[2] - WB.plane_y(plane, p[1], p[3])), b.g.hull)
# the lowest point of the whole car -- hull or tyre (a wheel's rim toward the ground) -- above the ground
support(b) = min(lowest(b), minimum(i -> (h = b.p + b.R*V3(b.g.wheel_x[i], b.g.wheel_r[i] - b.g.hcg, b.g.wheel_z[i]);
                                          b.on[i] ? h[2] - b.g.wheel_r[i]*abs(b.R[2, 2]) : Inf), 1:4))
grounded(b) = support(b) < 0.02        # touching: a rest in mid-air (the 2026-10-20 snap) fails this

# 1. dropped upright from 0.3 m
b = WB.Body(); WB.start!(b, 0.0, 0.0, 0.3, 0.0, 0.0, 0.0, V3(0, 0, 0), V3(0, 0, 0))
r = run!(b, 4.0)
θ, pt, rl = WB.attitude(b)
check(b.rest && grounded(b) && abs(b.p[2] - 0.264) < 0.03 && abs(pt) < deg2rad(1) && abs(rl) < deg2rad(1),
      @sprintf("dropped upright: at rest on its tyres, CG %.3f m (static ~0.26), pitch %.1f roll %.1f deg", b.p[2], deg(pt), deg(rl)))

# 2. dropped upside down from 1 m
b = WB.Body(); WB.start!(b, 0.0, 0.0, 1.0, 0.0, 0.0, π, V3(0, 0, 0), V3(0, 0, 0))
r = run!(b, 5.0)
θ, pt, rl = WB.attitude(b)
check(b.rest && grounded(b) && abs(abs(rl) - π) < deg2rad(15) && lowest(b) > -0.03,
      @sprintf("dropped upside down: rests inverted on the hull (roll %.0f deg), lowest point %.3f m", deg(rl), lowest(b)))

# 3. the PO's wreck, schematically: 45 km/h, a roll rate of 4 rad/s and 3 m/s up, the right-front wheel gone
b = WB.Body(); WB.start!(b, 0.0, 0.0, 0.0, 0.3, 0.0, 0.0, V3(12.5, 3.0, 0.0), V3(-4.0, 0.5, 0.0); on = (true, false, true, true))
b.brake = 1.0                         # the driver stands on the brakes
maxroll = 0.0
r = run!(b, 8.0; every = (b, k) -> (global maxroll = max(maxroll, abs(WB.attitude(b)[3]))))
check(maxroll > deg2rad(30), @sprintf("the roll rate rotates the whole car (max roll %.0f deg)", deg(maxroll)))
check(b.rest && grounded(b) && lowest(b) > -0.03,
      @sprintf("it comes to rest ON the ground (support %.3f m, lowest hull point %.3f m, peak CG height %.2f m)", support(b), lowest(b), b.peak_h))
check(r.maxjump < 0.05, @sprintf("no frame jump (largest step beyond its speed: %.3f m)", r.maxjump))
check(r.egain < 50.0, @sprintf("energy never grows (largest gain %.1f J)", r.egain))

# 4. wheels spin with their own inertia: a car rolling at 20 m/s with locked wheels spins them up
b = WB.Body(); WB.start!(b, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, V3(20.0, 0, 0), V3(0, 0, 0); spin = (0.0, 0.0, 0.0, 0.0))
run!(b, 0.5)
vf = norm(b.v)
check(all(i -> abs(b.spin[i]*b.g.wheel_r[i] - vf) < 0.5, 1:4) && vf > 15.0,
      @sprintf("locked wheels spin up to road speed: %.1f m/s, rims %s m/s", vf, join([@sprintf("%.1f", b.spin[i]*b.g.wheel_r[i]) for i in 1:4], " ")))
run!(b, 2.0)
check(norm(b.v) > 15.0, @sprintf("then it rolls freely (%.1f m/s after 2.5 s)", norm(b.v)))

# 5. into a wall at 25 m/s, hitting with the right-front corner: the wall face is X = 4, normal -X
const WALL = [WB.WallPlane(V3(4.0, 0.0, 0.0), V3(-1.0, 0.0, 0.0))]
b = WB.Body(); WB.start!(b, -2.0, 0.0, 0.0, -0.35, 0.0, 0.0, V3(25.0*cos(0.35), 0, 25.0*sin(0.35)), V3(0, 0, 0))
maxpen = 0.0; θ0 = WB.attitude(b)[1]
for k in 1:240
    WB.step!(b, 1/60, flat; walls = WALL)
    pen = maximum(q -> (b.p + b.R*q)[1] - 4.0, b.g.hull); global maxpen = max(maxpen, pen)
end
θ1 = WB.attitude(b)[1]
check(maxpen < 0.25, @sprintf("the wall holds (deepest point %.3f m past its face)", maxpen))
check(abs(θ1 - θ0) > deg2rad(10), @sprintf("an off-centre hit turns the car (heading %.0f -> %.0f deg)", deg(θ0), deg(θ1)))

# 5a. handed over already INSIDE the wall it hit (the driving model's car was up to 0.44 m in at the PO's Monza wreck):
# it is put back out, not thrown -- before the de-penetration the stiff wall met several deep points at once and flipped it
b = WB.Body(); a = deg2rad(30)
WB.start!(b, 0.0, -2.3, 0.0, -a, 0.0, 0.0, V3(30cos(a), 0, 30sin(a)), V3(0, 0, 0))   # right-front corner ~0.4 m into Z = 3
pen0 = maximum(q -> (b.p + b.R*q)[3] - 3.0, b.g.hull)
peak = 0.0; maxroll = 0.0
for k in 1:180
    WB.step!(b, 1/60, flat; walls = [WB.WallPlane(V3(0.0, 0.0, 3.0), V3(0.0, 0.0, -1.0))])
    global peak = max(peak, b.p[2]); global maxroll = max(maxroll, abs(WB.attitude(b)[3]))
end
check(pen0 > 0.3 && peak < 0.6 && maxroll < deg2rad(30),
      @sprintf("handed over %.2f m inside a wall: not thrown (peak CG %.2f m, max roll %.0f deg)", pen0, peak, deg(maxroll)))

# 5c. sliding along a wall whose verge rises 0.5 m in its last metre (the PO's Monza wall): the ground is the terrain
# under each point. A single plane fitted around the car tilted across that step and threw it 1.4 m up (2026-10-20)
verge(X, Z, yref) = Z > 1.0 ? 0.5*clamp((Z - 1.0)/0.3, 0.0, 1.0) : 0.0          # render frame; the wall face at Z = 2.2
function slide(ground_of)
    b = WB.Body(); WB.start!(b, 0.0, -0.3, 0.0, -0.05, 0.0, 0.0, V3(20.0, 0, 1.0), V3(0, 0, 0))
    peak = 0.0
    for k in 1:240
        WB.step!(b, 1/60, ground_of(b); walls = [WB.WallPlane(V3(0.0, 0.0, 2.2), V3(0.0, 0.0, -1.0))])
        peak = max(peak, b.p[2] - 0.0)
    end
    peak
end
pk_t = slide(b -> WB.Terrain(verge, WB.fit_plane((X, Z) -> verge(X, Z, Inf), b.p[1], b.p[3])))
pk_p = slide(b -> WB.fit_plane((X, Z) -> verge(X, Z, Inf), b.p[1], b.p[3]))
check(pk_t < 0.75, @sprintf("along a wall with a rising verge, terrain ground: no launch (peak CG %.2f m; one fitted plane: %.2f m)", pk_t, pk_p))

# 5b. into a hedge at 15 m/s, square on: it buries itself and stays (no bounce back out)
b = WB.Body(); WB.start!(b, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, V3(15.0, 0, 0), V3(0, 0, 0)); b.brake = 1.0
hedge = [WB.WallPlane(V3(3.0, 0.0, 0.0), V3(-1.0, 0.0, 0.0), true)]
vback = 0.0; deepest = 0.0
for k in 1:300
    WB.step!(b, 1/60, flat; walls = hedge)
    global vback = max(vback, -b.v[1]); global deepest = max(deepest, maximum(q -> (b.p + b.R*q)[1] - 3.0, b.g.hull))
end
check(0.2 < deepest < 1.5 && vback < 2.0, @sprintf("a hedge buries the car (%.2f m in) and holds it (back out at most %.1f m/s)", deepest, vback))

# 6. at rest it stays exactly still
b = WB.Body(); WB.start!(b, 0.0, 0.0, 0.05, 0.0, 0.0, 0.0, V3(0, 0, 0), V3(0, 0, 0))
run!(b, 3.0); p0 = b.p; R0 = b.R
run!(b, 2.0)
check(b.rest && b.p == p0 && b.R == R0, "at rest it does not move at all (no rocking)")

println("WRECKBODY GATE: ", ok ? "PASS" : "FAIL")
exit(ok ? 0 : 1)
