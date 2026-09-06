# SPA-BARRIER gate: stacked (duplicate) solids must not catapult the car.
# The PO's Spa replay (2026-09-03) hit house28 -- present THREE times at one spot -- at 37 m/s and
# was thrown back the way it came at 70 m/s. contact_force bounds ONE contact per frame (fling cap
# 8 m/s, outcome cap 0.25 m/s); the SUM of three obeyed neither. Simulated frame by frame here:
# a half-space wall at x = 0, the car arrives at +37 m/s, N identical contacts act every frame.
include(joinpath(@__DIR__, "..", "src", "drive_rt3d.jl"))
using .DriveRT3D
using Printf
fails = 0
pass(ok, msg, val) = (println("  ", ok ? "PASS" : "FAIL", "  ", rpad(msg, 54), val); ok || (global fails += 1))
const M = 617.0; const DT = 1/60
"drive into the wall; returns (fastest backwards speed reached, speed when the car is clear/at rest)"
function slam(ncopies; capped, v0 = 37.0, frames = 240)
    x = -0.3; vx = v0; θ = 0.0; nx = -1.0; nz = 0.0     # wall outward normal faces the car
    vback = 0.0; vend = vx
    for _ in 1:frames
        δ = x                                             # penetration past the wall face
        Fx = 0.0; Fy = 0.0
        if δ > 0.0
            vn = vx*nx                                    # world velocity along the outward normal
            for _ in 1:ncopies
                (fx, fy, _) = DriveRT3D.contact_force(δ, nx, nz, vn, θ; kind = :wall, m = M, dt = DT)
                Fx += fx; Fy += fy
            end
            capped && ((Fx, Fy, _) = DriveRT3D.cap_total_contact(Fx, Fy, vx, 0.0; m = M, dt = DT))
        end
        vx += Fx*DT/M; x += vx*DT
        vback = min(vback, vx)
        vend = vx
    end
    (-vback, abs(vend))
end
(b1c, e1c) = slam(1; capped = false); (b1t, e1t) = slam(1; capped = true)
(b3c, e3c) = slam(3; capped = false); (b3t, e3t) = slam(3; capped = true)
@printf("  one contact : back %.2f m/s (capped %.2f)   three stacked: back %.1f m/s (capped %.2f)\n", b1c, b1t, b3c, b3t)
pass(b1c <= DriveRT3D.VN_OUT_MAX + 0.05, "premise: ONE contact never throws the car back",     @sprintf("%.2f m/s", b1c))
pass(b3c > 5.0,                          "premise: THREE stacked contacts CATAPULT it",         @sprintf("%.1f m/s backwards", b3c))
pass(b3t <= DriveRT3D.VN_OUT_MAX + 0.05, "treatment: three stacked, capped -> no throw-back",  @sprintf("%.2f m/s", b3t))
pass(abs(b1t - b1c) < 1e-6 && abs(e1t - e1c) < 1e-6, "the cap is a no-op on a single contact", @sprintf("%.3f vs %.3f", e1t, e1c))
pass(e3t < 1.0,                          "treatment: the car is stopped, not skating away",    @sprintf("%.2f m/s", e3t))
# the sim must build one disc per spot and cap the sum
SRC = read(joinpath(@__DIR__, "..", "..", "demo", "native", "drive_native_mtk.jl"), String)
pass(occursin("_key in _solidseen", SRC) && occursin("push!(SOLIDS, _key)", SRC), "SOLIDS builder drops exact duplicates", "source check")
pass(occursin("DriveRT3D.cap_total_contact(Fx, Fy, vbx, vby", SRC), "solid_contact caps the summed force", "source check")
println(fails == 0 ? "STACKED-CONTACT GATE: PASS" : "STACKED-CONTACT GATE: FAIL ($fails)")
exit(fails == 0 ? 0 : 1)
