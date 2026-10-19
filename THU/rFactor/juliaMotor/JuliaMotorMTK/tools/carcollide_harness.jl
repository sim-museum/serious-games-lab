# CARCOLLIDE-2: car-to-car contact, julia vs iRacing. Two full Car3D cars on flat ground; car A (the "player", 229 km/h,
# lifting) runs into the back of car B at a lateral offset; the contact is the SIM's OWN code (car_contact_impulse +
# contact_d, read from drive_native_mtk.jl), applied to BOTH cars each step as the sim applies it to the player.
# Reports what iRacing's 261018 race files measure for a contact (15-11-16 t 183.2: 229 km/h, -69 m/s^2 for ~0.1 s,
# yaw rate 0 -> -1.3..-1.7 rad/s in 0.05-0.1 s, front ride 90 -> 5 mm, rear ride 114 -> 278 mm).
#
#   julia --project=JuliaMotorMTK JuliaMotorMTK/tools/carcollide_harness.jl
using Printf
include(joinpath(@__DIR__, "..", "src", "drive_rt3d.jl")); using .DriveRT3D

const SRC = read(joinpath(@__DIR__, "..", "..", "demo", "native", "drive_native_mtk.jl"), String)
grab(rx) = (m = match(rx, SRC); m === nothing && error("not found: $rx"); m.match)
for rx in (r"const CAR_HALF_L = .*", r"const CAR_HALF_W = .*", r"const CONTACT_CIRCLE = .*", r"const CONTACT_D = .*",
           r"carrad\(θ, ux, uz\) = [^\n]*\n[^\n]*", r"contact_d\(dx, dz, d, θa, θb\) =\n[^\n]*",
           )
    eval(Meta.parseall(grab(rx)))
end
include(joinpath(@__DIR__, "..", "..", "demo", "native", "carcontact.jl"))   # the sim's contact law (CARCOLLIDE-2)

flat(x, z) = 0.0
wvel(c) = (a = c.getall(c.integ); θ = a[3]; (a[4]*cos(θ) - a[5]*sin(θ), a[4]*sin(θ) + a[5]*cos(θ)))

"A at 229 km/h hits B (vB) from behind; `lat` = B's centre offset to A's left [m]. Returns the measured response."
function run(lat, vB; vA = 229/3.6, secs = 1.5, both = true)
    gap = 2*CAR_HALF_L + 0.05 + 0.3*(vA - vB)                # contact after ~0.3 s (the cars settle first)
    A = DriveRT3D.build_car3d(; x0 = 0.0, v0 = vA); B = DriveRT3D.build_car3d(; x0 = 0.0, v0 = vB)
    for c in (A, B); c.gear = 5; c.s_gr(c.integ, DriveRT3D.GEARS[5]); end
    DriveRT3D.place3d!(A, 0.0, 0.0, 0.0; v = vA); DriveRT3D.place3d!(B, gap, lat, 0.0; v = vB)
    dt = 1/60; t_hit = NaN; v0 = vA; r0 = 0.0
    rec = (dv = 0.0, ax = 0.0, dr = 0.0, rlift = 0.0, fdip = 0.0, pitch = 0.0, Bdr = 0.0, Bspin = 0.0, j = 0.0)
    rh0 = (NaN, NaN)
    for k in 1:round(Int, secs/dt)
        DriveRT3D.step_car3d!(A, 0.0, 0.0, 0.0, dt; manual = true, groundz = flat)
        DriveRT3D.step_car3d!(B, 0.0, 0.0, 0.0, dt; manual = true, groundz = flat)
        isnan(t_hit) && (rh0 = (A.rh[1], A.rh[3]))           # the ride heights on the frame before contact
        dx = B.x - A.x; dz = B.z - A.z; d = hypot(dx, dz)
        if car_near(dx, dz, d, A.θ, B.θ)
            (avx, avz) = wvel(A); (bvx, bvz) = wvel(B)
            ia = car_contact_impulse(A.x, A.z, A.θ, avx, avz, DriveRT3D.yawrate3d(A), B.x, B.z, bvx, bvz; θb = B.θ, rb = DriveRT3D.yawrate3d(B))
            ib = both ? car_contact_impulse(B.x, B.z, B.θ, bvx, bvz, DriveRT3D.yawrate3d(B), A.x, A.z, avx, avz; θb = A.θ, rb = DriveRT3D.yawrate3d(A)) : nothing
            if ia !== nothing
                isnan(t_hit) && (t_hit = A.t; v0 = hypot(avx, avz); r0 = DriveRT3D.yawrate3d(A))
                DriveRT3D.bump3d!(A, ia[1], ia[2], ia[3]); rec = merge(rec, (j = rec.j + ia[4],))
            end
            ib !== nothing && DriveRT3D.bump3d!(B, ib[1], ib[2], ib[3])
        end
        if isfinite(t_hit) && A.t - t_hit <= 0.30
            (avx, avz) = wvel(A)
            rec = merge(rec, (dv = v0 - hypot(avx, avz), dr = max(rec.dr, abs(DriveRT3D.yawrate3d(A) - r0)),
                              rlift = max(rec.rlift, A.rh[3] - rh0[2]), fdip = max(rec.fdip, rh0[1] - A.rh[1]),
                              pitch = max(rec.pitch, abs(A.pitch)), Bdr = max(rec.Bdr, abs(DriveRT3D.yawrate3d(B)))))
        end
    end
    isfinite(t_hit) && (rec = merge(rec, (Bspin = abs(B.θ),)))
    (hit = isfinite(t_hit), rec...)
end

println("CARCOLLIDE-2 harness: A 229 km/h, lifting, hits B from behind (the sim's car_contact_impulse on both cars)")
println("  iRacing 261018 15-11-16 t 183.2:  dv ~10 m/s in 0.25 s, yaw kick 1.3-1.7 rad/s, front ride -85 mm, rear ride +164 mm")
@printf("  %-8s %-9s %7s %8s %8s %9s %9s %8s %8s %9s\n", "lat m", "close m/s", "dv m/s", "J kN.s", "dyaw", "fdip mm",
        "rlift mm", "pitch°", "B yaw", "B head°")
for lat in (0.0, 0.8, 1.4), close in (5.0, 10.0, 20.0)
    r = run(lat, 229/3.6 - close)
    r.hit || (@printf("  %-8.1f %-9.0f  no contact\n", lat, close); continue)
    @printf("  %-8.1f %-9.0f %7.2f %8.2f %8.2f %9.0f %9.0f %8.2f %8.2f %9.1f\n", lat, close, r.dv, r.j/1000, r.dr,
            1000r.fdip, 1000r.rlift, rad2deg(r.pitch), r.Bdr, rad2deg(r.Bspin))
end

"Side-swipe: B alongside A (centres `xoff` apart along the road), B moving toward A at `vlat` m/s; both at `v`."
function run_side(xoff, vlat; v = 75/3.6, secs = 1.0)
    A = DriveRT3D.build_car3d(; x0 = 0.0, v0 = v); B = DriveRT3D.build_car3d(; x0 = 0.0, v0 = v)
    for c in (A, B); c.gear = 3; c.s_gr(c.integ, DriveRT3D.GEARS[3]); end
    ψ = atan(vlat, v)                                              # B angled toward A
    DriveRT3D.place3d!(A, 0.0, 0.0, 0.0; v = v); DriveRT3D.place3d!(B, xoff, 2*CAR_HALF_W + 0.05 + 0.2*vlat, -ψ; v = hypot(v, vlat))
    dt = 1/60; t_hit = NaN; r0 = 0.0; v0 = v; dr = 0.0; dv = 0.0; bdr = 0.0
    for k in 1:round(Int, secs/dt)
        DriveRT3D.step_car3d!(A, 0.0, 0.0, 0.0, dt; manual = true, groundz = flat)
        DriveRT3D.step_car3d!(B, 0.0, 0.0, 0.0, dt; manual = true, groundz = flat)
        dx = B.x - A.x; dz = B.z - A.z; d = hypot(dx, dz)
        if car_near(dx, dz, d, A.θ, B.θ)
            (avx, avz) = wvel(A); (bvx, bvz) = wvel(B)
            ia = car_contact_impulse(A.x, A.z, A.θ, avx, avz, DriveRT3D.yawrate3d(A), B.x, B.z, bvx, bvz; θb = B.θ, rb = DriveRT3D.yawrate3d(B))
            ib = car_contact_impulse(B.x, B.z, B.θ, bvx, bvz, DriveRT3D.yawrate3d(B), A.x, A.z, avx, avz; θb = A.θ, rb = DriveRT3D.yawrate3d(A))
            ia !== nothing && (isnan(t_hit) && (t_hit = A.t; r0 = DriveRT3D.yawrate3d(A)); DriveRT3D.bump3d!(A, ia[1], ia[2], ia[3]))
            ib !== nothing && DriveRT3D.bump3d!(B, ib[1], ib[2], ib[3])
        end
        if isfinite(t_hit) && A.t - t_hit <= 0.3
            (avx, avz) = wvel(A); dv = max(dv, v0 - hypot(avx, avz))
            dr = max(dr, abs(DriveRT3D.yawrate3d(A) - r0)); bdr = max(bdr, abs(DriveRT3D.yawrate3d(B)))
        end
    end
    (hit = isfinite(t_hit), dv, dr, bdr)
end
println("\nSide-swipe at 75 km/h (iRacing 261018 side contacts: yaw-rate steps 1.1-2.3 rad/s, speed loss a few km/h)")
@printf("  %-10s %-10s %8s %8s %8s\n", "xoff m", "vlat m/s", "dv m/s", "A dyaw", "B yaw")
for xoff in (-1.5, 0.0, 1.5), vlat in (1.0, 3.0)
    r = run_side(xoff, vlat)
    r.hit ? @printf("  %-10.1f %-10.1f %8.2f %8.2f %8.2f\n", xoff, vlat, r.dv, r.dr, r.bdr) : @printf("  %-10.1f %-10.1f  no contact\n", xoff, vlat)
end
