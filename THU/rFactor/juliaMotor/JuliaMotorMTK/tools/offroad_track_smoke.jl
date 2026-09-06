# GATE: OFFROAD-1 -- driving OFF the road on REAL track terrain must not levitate or bounce.
#
# PO 2026-09-05: "still ran into a levitate and bounce when car went off road at Watkin's Glen."
#
# WHY THIS EXISTS, when two off-road gates already pass. Neither of them drives anywhere:
#   * hat_hole_smoke is a SOURCE-TEXT gate -- it greps drive_native_mtk.jl and asserts the
#     sentinel->NaN closure is still spelled there. It loads no track.
#   * offroad_smoke drives the PHYSICS, but against a synthetic `gz(x,z) = x > 40 ? off : 0.0`.
#     Flat ground, invented boundary.
# So "both tracks are survivable" was never measured on a track. This gate closes that: REAL
# Watkins Glen geometry, the real HAT, a real ray off the road, and the real vehicle ODE. No GL --
# it samples the terrain along the ray the car drives, the way offroad_smoke does, so it runs in
# the suite instead of needing a display.
#
# TWO GROUND POLICIES, which is the whole question:
#   HOLD -- off the mesh, return the LAST valid height. This is what drive_native_mtk's groundz
#           (the nested one at :5166) actually does: it never emits the -999 sentinel at all.
#   NaN  -- off the mesh, return NaN, which is the contract E104(b) established and that
#           drive_rt3d reads as "unknown, keep the previous reference".
# If HOLD launches the car and NaN does not, then the shipped closure is the mechanism and the
# S13b sentinel conversion is guarding a value that never arrives.
using Printf
const D = normpath(joinpath(@__DIR__, "..", "..", "demo", "native"))
include(joinpath(D, "gpldat.jl")); using .GPLDat
include(joinpath(D, "gpl3do.jl"));  using .GPL3DO
include(joinpath(D, "gpltrack.jl")); using .GPLTrack
include(joinpath(@__DIR__, "..", "src", "drive_rt3d.jl")); using .DriveRT3D
using JuliaMotor

const T = "/home/admin/sgl-julia-racer/THU/WP/drive_c/Sierra/GPL/tracks/watglen"
fails = Ref(0)
chk(n, ok, d) = (@printf("  %-52s %s   %s\n", n, ok ? "PASS" : "FAIL", d); ok || (fails[] += 1))

print("  loading Watkins Glen terrain… "); flush(stdout)
# Both the mesh and the .trk live INSIDE watglen.dat -- the loose files beside it are only the
# trackside scenery. Extract them the way the other probes do.
dat     = GPLDat.parse_dat(joinpath(T, "watglen.dat"))
m3do    = tempname()*".3do"; write(m3do, dat["watglen.3do"])
mtrk    = tempname()*".trk"; write(mtrk, dat["watglen.trk"])
mesh    = GPL3DO.parse_3do(m3do)
TERRAIN = GPLTrack.build_hat(mesh)
hat(x, z) = (h = JuliaMotor.hat3d(TERRAIN, Float64(x), Float64(z); ref = Inf); (h[3], Float64(h[1])))
cl0     = GPLTrack.trk_centreline(mtrk)
# ⚠️ The .trk centreline and the terrain HAT are in DIFFERENT FRAMES. Measured on watglen: 0 of 940
# centreline points land on the mesh, and the z ranges do not even overlap (3961..5515 against
# -863..837). An unaligned probe reports "no mesh edge anywhere within 80 m", which reads exactly
# like a fact about the track and is really a fact about the frame. drive_native_mtk carries its
# own `align_centreline` (:843) for this; the same bbox-then-grid-search is reproduced here.
function align_centreline(cl, hat)
    sample = cl[1:max(1, length(cl) ÷ 400):end]
    cov(dx, dz) = count(p -> JuliaMotor.hat3d(hat, p[1]+dx, p[2]+dz; ref=Inf)[3], sample) / length(sample)
    cov(0.0, 0.0) > 0.6 && return cl
    xs = Float64[]; zs = Float64[]
    for tr in hat.tris, p in (tr.a, tr.b, tr.c); push!(xs, p[1]); push!(zs, p[3]); end
    dx0 = (minimum(xs)+maximum(xs))/2 - (minimum(p[1] for p in cl)+maximum(p[1] for p in cl))/2
    dz0 = (minimum(zs)+maximum(zs))/2 - (minimum(p[2] for p in cl)+maximum(p[2] for p in cl))/2
    best = (cov(dx0, dz0), dx0, dz0)
    for dx in dx0-400:40:dx0+400, dz in dz0-400:40:dz0+400
        c = cov(dx, dz); c > best[1] && (best = (c, dx, dz))
    end
    for dx in best[2]-40:8:best[2]+40, dz in best[3]-40:8:best[3]+40
        c = cov(dx, dz); c > best[1] && (best = (c, dx, dz))
    end
    [(p[1]+best[2], p[2]+best[3]) for p in cl]
end
cl      = align_centreline(cl0, TERRAIN)
let on = count(p -> hat(p[1], p[2])[1], cl)
    @printf("  centreline aligned: %d/%d points on the mesh\n", on, length(cl))
    on < length(cl) ÷ 2 && (println("  alignment FAILED — the probe would be measuring the wrong place"); exit(1))
end
println(length(cl), " centreline points")

# Find a ray that starts ON the mesh and leaves it: walk the centreline, step sideways until the
# HAT stops reporting a triangle. This is a REAL edge of the real track, not an invented one.
function find_exit_ray()
    n = length(cl)
    for k in 1:8:n
        (x0, z0) = cl[k]
        (x1, z1) = cl[mod1(k + 4, n)]
        dx, dz = x1 - x0, z1 - z0
        L = hypot(dx, dz); L < 1e-6 && continue
        px, pz = -dz / L, dx / L                       # perpendicular to the track
        hat(x0, z0)[1] || continue                      # must start on the mesh
        for d in 2.0:1.0:80.0
            if !hat(x0 + px*d, z0 + pz*d)[1]
                return (x0, z0, px, pz, d)              # leaves the mesh d metres out
            end
        end
    end
    nothing
end
ray = find_exit_ray()
if ray === nothing
    println("  could not find a mesh edge within 80 m of the centreline — cannot test")
    exit(1)
end
(rx, rz, px, pz, dexit) = ray
@printf("  ray: from (%.1f, %.1f) perpendicular, leaves the mesh at %.0f m\n", rx, rz, dexit)

"""Drive straight at `v0` along the exit ray under ground policy `policy`
(:hold or :nan). Returns (max upward m/s, max height above TRUE terrain, final y)."""
function run_ray(policy; v0 = 25.0, secs = 8.0)
    c = DriveRT3D.build_car3d(; v0 = v0); c.gear = 3
    lastz = Ref(hat(rx, rz)[2])
    # The car's own x is distance along the ray; map it to the world point it corresponds to.
    function gz(x, z)
        (ok, h) = hat(rx + px*Float64(x), rz + pz*Float64(x))
        ok && (lastz[] = h)
        ok ? h : (policy === :hold ? lastz[] : NaN)
    end
    # `c.y` and `c.x` are the car's own accessors -- the same ones offroad_smoke reads. Reaching
    # into `c.integ[c.sys...]` threw "System car: variable body does not exist".
    dt = 1/60; vzmax = -Inf; airmax = -Inf; prevy = NaN
    for _ in 1:round(Int, secs/dt)
        DriveRT3D.step_car3d!(c, 0.30, 0.0, 0.0, dt; manual = true, groundz = gz)
        y = Float64(c.y)
        isfinite(y) || return (Inf, Inf)          # diverged: worse than any threshold
        isfinite(prevy) && (vzmax = max(vzmax, (y - prevy)/dt))
        prevy = y
        (ok, h) = hat(rx + px*Float64(c.x), rz + pz*Float64(c.x))
        ok && (airmax = max(airmax, y - h))
    end
    (vzmax, airmax)
end

println("OFFROAD-1 gate (Watkins Glen, real HAT, car driven off the mesh edge)")
(hv, ha) = run_ray(:hold)
(nv, na) = run_ray(:nan)
@printf("  HOLD (shipped): max climb %.2f m/s   max height above terrain %.2f m\n", hv, ha)
@printf("  NaN  (E104(b)): max climb %.2f m/s   max height above terrain %.2f m\n", nv, na)
chk("NaN policy does not launch the car", nv < 6.0, @sprintf("%.2f m/s", nv))
chk("NaN policy does not levitate",       na < 0.75, @sprintf("%.2f m", na))
chk("shipped policy does not launch the car", hv < 6.0, @sprintf("%.2f m/s", hv))
chk("shipped policy does not levitate",       ha < 0.75, @sprintf("%.2f m", ha))
println(fails[] == 0 ? "OFFROAD TRACK GATE: PASS" : "OFFROAD TRACK GATE: FAIL ($(fails[]))")
exit(fails[] == 0 ? 0 : 1)
