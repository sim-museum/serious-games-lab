# GATE: the DRAWN road must be the road the .trk describes, vertically as well as horizontally.
#
# GPLROAD-1 (PO 2026-09-26: "Tracks in GPL are continuous, with no sharp edges. Julia tracks are
# noticably piecewise linear, with polygon corners you can see when there's a white boundary at the edge
# of the road. GPL and Julia are starting from the same track files.")
#
# The .trk holds the road analytically: constant-curvature arcs plus, per section and per lateral trace,
# a CUBIC elevation. The .3do holds a baked polygon copy whose road-edge nodes measure 4.4 m apart at
# Zandvoort but 9.2 m at the Ring, 13.7 m at Spa and 18.3 m at Monza -- and the Ring, Spa and Monza are
# the three tracks the PO named. ROADCURVE-1 already rounded that mesh HORIZONTALLY onto the ribbon's
# curve; it left every inserted vertex at the chord average of its edge's endpoints, so the drawn road
# stayed piecewise LINEAR in the vertical over those same chords. The physics has read the .trk cubic
# since TRACKSMOOTH-3. The drawn surface had not.
#
# WHAT THIS GATE SETTLED, and what it now guards. It was written to prove a VERTICAL defect: the .trk
# stores elevation as a cubic per section per trace, ROADCURVE-1 rounded the road only horizontally, and
# every vertex it inserted took the chord average of its edge -- so the drawn road should have been
# piecewise linear in the vertical over 9-18 m chords. It is not. Measured against the .trk's own
# elevation field, the road ROADCURVE already draws is within 0.4 cm (Monza p50) to 5.7 cm (Watkins Glen
# p90) of it, and warping the vertices onto that field made both tracks slightly WORSE (Watkins p50
# 0.004 -> 0.032 m, curvature p99 0.0228 -> 0.0480 /m). So the warp was not shipped, and the visible
# faceting the PO reports is not vertical -- it is horizontal or shading.
#
# (Two instrument faults were booked getting to that number, and both inflated the defect: a ribbon
# standing on the .trk walk instead of on the mesh -- the GPL Nurburgring's walk starts ~87 km off in z
# -- and `ref = Inf` ground reads, which on a raw track HAT return the banner, the bridge or the tree
# above the road rather than the road. Uncorrected they reported the road as 1.49 m off the .trk.)
#
# WHAT IS ASSERTED now. Both arms run in-process on the real track .3do; the mesh is turned into a HAT
# and read along the lap exactly as the sim reads it.
# This is a REGRESSION GUARD, not a proof that ROADCURVE works. ROADCURVE is a horizontal fix, so a
# vertical ruler cannot show a gain from it, and indeed does not: the raw .3do sits 0.043 m from the .trk
# at p90 at Watkins Glen and the rounded mesh 0.057 m. Whether the rounding removes the faceting the PO
# sees needs a PLAN-VIEW measurement, which is a separate instrument and is not in this file. What is
# asserted here, on both arms (rounding off / on, so each number has its control):
#  1. The drawn road tracks the .trk surface to within 10 cm at p90. This is the number that would move
#     if the alignment, the lateral sign, the offset or the SINK-1 correction regressed.
#  2. Rounding does not ADD vertical creasing: curvature p99 stays at or below the raw mesh's.
#  3. ROADCURVE does not move the road in bulk -- the MEDIAN height must not shift. The car collides
#     with this same mesh.
const D = normpath(joinpath(@__DIR__, "..", "..", "demo", "native"))
const G = get(ENV, "JM_GPL_TRACKS",
              normpath(joinpath(@__DIR__, "..", "..", "..", "..", "WP", "drive_c", "Sierra", "GPL", "tracks")))
include(joinpath(D, "gpldat.jl"));   using .GPLDat
include(joinpath(D, "gpl3do.jl"))
# roadcurve.jl is written as a submodule of the renderer (`using ..Render.GPL3DO`); the renderer itself
# needs a GL context, so bind the loader under that name instead of pulling OpenGL into a gate.
module Render
    const GPL3DO = Main.GPL3DO
end
include(joinpath(D, "roadcurve.jl")); using .RoadCurve
include(joinpath(D, "gpltrack.jl")); using .GPLTrack
using JuliaMotor, Statistics, Printf

pct(v, p) = isempty(v) ? NaN : (u = sort(copy(v)); u[clamp(ceil(Int, p*length(u)), 1, length(u))])

function load_track(name)
    dir = joinpath(G, name)
    ci(n) = (m = filter(f -> lowercase(f) == lowercase(n), readdir(dir)); isempty(m) ? "" : joinpath(dir, m[1]))
    dat = (p = ci(name*".dat"); p == "" ? Dict{String,Vector{UInt8}}() : GPLDat.parse_dat(p))
    function getf(ext)
        p = ci(name*ext); p != "" && return p
        v = get(dat, lowercase(name*ext), nothing); v === nothing && return ""
        q = tempname()*ext; write(q, v); q
    end
    (trk = getf(".trk"), mesh = getf(".3do"))
end

"""The ribbon ROADCURVE warps onto: the .trk centreline ALIGNED TO THE MESH, with the .trk's own
elevation on it. The alignment is not optional -- the GPL Nurburgring's .trk walk starts ~87 km off the
.3do in z, and an unaligned ribbon sits nowhere near the track, so the warp is a no-op and the
calibration gets zero samples (measured: "sign -1 offset NaN (0 samples)")."""
function build_ribbon(ta, cl0, hat)
    cl = GPLTrack.align_centreline(cl0, hat)
    # build_surface, as the sim does (RIBBON0 = GPLTrack.build_surface(ALIGNED, TERRAIN0)): the node
    # heights come off the MESH. Standing the ribbon on the .trk spline instead left its nodes an
    # unknown constant off the mesh, and the height field's own `ref = node + 3 m` window -- which is
    # how it tells road from banner -- was then measured from the wrong datum.
    GPLTrack.build_surface(cl, hat)
end

"""One arm. `rounded = false` is the control: the raw .3do, exactly what the sim draws with
JM_ROADCURVE=0. `rounded = true` is the shipped path, through the same RoadCurve.curve_mesh call the sim
makes -- not a copy of it, so this gate moves when the shipped code moves."""
function arm(mesh, ribbon; rounded::Bool)
    rounded || return (mesh = mesh, st = nothing)
    P = [(p[1], p[3]) for p in ribbon.pos]; HS = [p[2] for p in ribbon.pos]
    length(P) > 2 && hypot(P[end][1]-P[1][1], P[end][2]-P[1][2]) < 0.5 && (pop!(P); pop!(HS))
    q = ribbon.perp[1]
    mc, st = RoadCurve.curve_mesh(mesh, P, (q[1], q[3]); tol = 0.05, sig = 2.0, heights = HS)
    (mesh = mc, st = st)
end

"Read the drawn mesh along the lap and compare it with the .trk surface."
function measure(ref, mc, ribbon; step = 1.0, lats = (-5.0, -2.5, 0.0, 2.5, 5.0))
    hat = GPLTrack.build_hat(mc)
    np = length(ribbon.pos); ld = ribbon.lapdist; lapl = ribbon.lap_length
    # the reference field is parameterised by NODE INDEX, as the warp is; u(s) inverts ribbon.lapdist
    function u_of(s)
        i = clamp(searchsortedlast(ld, mod(s, lapl)), 1, np)
        send = i == np ? lapl : ld[i+1]
        Float64(i) + (mod(s, lapl) - ld[i]) / max(send - ld[i], 1e-9)
    end
    function at(sv, lat)
        s = mod(sv, lapl)
        i = clamp(searchsortedlast(ld, s), 1, np)
        send = i == np ? lapl : ld[i+1]
        f = (s - ld[i]) / max(send - ld[i], 1e-9)
        j = mod1(i+1, np); pa = ribbon.pos[i]; pb = ribbon.pos[j]; q = ribbon.perp[i]
        (pa[1] + (pb[1]-pa[1])*f + lat*q[1], pa[3] + (pb[3]-pa[3])*f + lat*q[3])
    end
    dev = Float64[]; curv = Float64[]; hmed = Float64[]
    for lat in lats
        hs = Float64[]; ss = Float64[]
        sv = 0.0
        while sv < lapl
            x, z = at(sv, lat)
            # ref = the ribbon's own height + 3 m: `Inf` takes the TOPMOST surface, which on a raw
            # track HAT is a banner, a bridge or a tree, not the road (the first run of this gate read
            # Watkins Glen's road as 1.5 m off the .trk because of exactly that).
            h = JuliaMotor.hat3d(hat, x, z; ref = ribbon.pos[clamp(searchsortedlast(ld, mod(sv, lapl)), 1, np)][2] + 3.0)
            push!(hs, h[3] ? Float64(h[1]) : NaN); push!(ss, sv)
            sv += step
        end
        for k in eachindex(hs)
            isnan(hs[k]) && continue
            push!(hmed, hs[k])
            push!(dev, abs(hs[k] - ref(u_of(ss[k]), lat)))
        end
        for k in 2:length(hs)-1
            (isnan(hs[k-1]) || isnan(hs[k]) || isnan(hs[k+1])) && continue
            push!(curv, abs(hs[k-1] - 2hs[k] + hs[k+1]) / step^2)
        end
    end
    (dev = dev, curv = curv, hmed = pct(hmed, 0.5))
end

"Calibrate the spline against the RAW mesh, the way drive_native_mtk.jl does before the warp."
function calibrate(ta, mesh, ribbon)
    hat = GPLTrack.build_hat(mesh)
    res1 = Float64[]; resm = Float64[]; off0 = Float64[]
    for i in 1:6:length(ribbon.pos)
        p = ribbon.pos[i]; q = ribbon.perp[i]; sv = ribbon.lapdist[i]
        h0 = JuliaMotor.hat3d(hat, p[1], p[3]; ref = Inf); h0[3] || continue
        push!(off0, Float64(h0[1]) - GPLTrack.trk_height(ta, sv, 0.0))
        for lat in (-4.0, 4.0)
            hm = JuliaMotor.hat3d(hat, p[1] + lat*q[1], p[3] + lat*q[3]; ref = Inf); hm[3] || continue
            push!(res1, abs(Float64(hm[1]) - GPLTrack.trk_height(ta, sv,  lat) - off0[end]))
            push!(resm, abs(Float64(hm[1]) - GPLTrack.trk_height(ta, sv, -lat) - off0[end]))
        end
    end
    (sgn = pct(res1, 0.5) <= pct(resm, 0.5) ? 1.0 : -1.0, off = pct(off0, 0.5), n = length(off0))
end

const TRACKS = split(get(ENV, "JM_GPLROAD_TRACKS", "watglen monza spa67"))
const fails = Ref(0); const checks = Ref(0)
function ck(ok, label, detail)
    checks[] += 1; ok || (fails[] += 1)
    @printf("  %s  %-52s %s\n", ok ? "PASS" : "FAIL", label, detail)
end

println("GPLROAD-1 gate: the drawn road vs the .trk elevation spline")
for name in TRACKS
    f = load_track(name)
    (f.trk == "" || f.mesh == "") && (println("  ", name, ": no .trk/.3do -- skipped"); continue)
    ta = GPLTrack.trk_altitude(f.trk)
    cl = GPLTrack.trk_centreline(f.trk)
    raw = GPL3DO.parse_3do(f.mesh)
    rawhat = GPLTrack.build_hat(raw)
    ribbon = build_ribbon(ta, cl, rawhat)
    cal = calibrate(ta, raw, ribbon)
    @printf("\n== %s: %d tris, .trk lap %.1f m, calibration sign %+.0f offset %.3f m (%d samples)\n",
            name, length(raw.tris), ta.total, cal.sgn, cal.off, cal.n)
    c = arm(raw, ribbon; rounded = false)
    t = arm(raw, ribbon; rounded = true)
    ref = GPLTrack.trk_height_field(ta, ribbon, rawhat)
    ref === nothing && (println("  ", name, ": the .trk does not describe this ribbon -- skipped"); continue)
    mc = measure(ref, c.mesh, ribbon)
    mt = measure(ref, t.mesh, ribbon)
    @printf("   raw .3do  |drawn - .trk| p50 %.3f p90 %.3f p99 %.3f m   curvature p90 %.4f p99 %.4f /m\n",
            pct(mc.dev,0.5), pct(mc.dev,0.9), pct(mc.dev,0.99), pct(mc.curv,0.9), pct(mc.curv,0.99))
    @printf("   ROADCURVE |drawn - .trk| p50 %.3f p90 %.3f p99 %.3f m   curvature p90 %.4f p99 %.4f /m  (%d tris, %d rounded)\n",
            pct(mt.dev,0.5), pct(mt.dev,0.9), pct(mt.dev,0.99), pct(mt.curv,0.9), pct(mt.curv,0.99),
            t.st.tris_out, t.st.curved)
    ck(t.st.curved > 100, "premise: ROADCURVE rounded a substantial part of the road",
       @sprintf("%d polygons", t.st.curved))
    ck(pct(mc.dev, 0.9) < 0.10, "the raw road already tracks the .trk surface (control)",
       @sprintf("p90 %.3f m < 0.10", pct(mc.dev, 0.9)))
    ck(pct(mt.dev, 0.9) < 0.10, "the drawn road tracks the .trk surface",
       @sprintf("p90 %.3f m < 0.10", pct(mt.dev, 0.9)))
    ck(pct(mt.curv, 0.99) <= pct(mc.curv, 0.99) + 1e-9, "rounding does not add creasing",
       @sprintf("curvature p99 %.4f <= %.4f /m", pct(mt.curv, 0.99), pct(mc.curv, 0.99)))
    ck(abs(mt.hmed - mc.hmed) < 0.05, "the road is not lifted or dropped in bulk",
       @sprintf("median height moved %.4f m (cap 0.05)", mt.hmed - mc.hmed))
end
println()
println("GPLROAD GATE: ", fails[] == 0 ? "PASS" : "FAIL", "  (", checks[] - fails[], "/", checks[], " checks)")
exit(fails[] == 0 ? 0 : 1)
