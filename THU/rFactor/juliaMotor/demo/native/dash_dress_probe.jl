# ⚠ THIS PROBE SAMPLES THE WRONG POPULATION.  It rebuilds the extraction with its own kwargs
# instead of the demo's, so it reports 34 dash triangles (dash7a 20 + dash7 7 + ldashr 7) where
# the shipped CARPIN has 14 and NO dash7a at all -- dedup=:orient plus the exclusion lists drop
# it.  The UV slopes it measures are still right (they are properties of the authored UVs), but
# any count or prediction taken from here is not about what the renderer draws.  The authoritative
# reading is JM_DASH_DIAG=1 in drive_native_mtk.jl, which prints from inside the real extraction.
# CARGOLD-1 S9c, part 2.  The dash the PO actually sees is NOT the dash7a billboard (GAUGEP):
# since E106-S7 `gaugeItems` is empty whenever JM_COCKPIT_DRESS is on, which is the default.
# The visible dash is inside CARPIN -- lotd.3DO, extracted with DEFAULT vflip and NO y-mirror.
# So measure THAT, with the same call drive_native_mtk.jl makes.
#
# PREDICTION (before the run): dash7a's art has v=0 at the visual TOP (measured: luma 100.8 at
# v 0-0.125 = sky/track above the cowl, 26.6 at v 0.875-1.0 = dark footwell), and the lotus.3do
# billboard panel had slope(v on y)=+3.42 -- high y carrying the art's BOTTOM, i.e. inverted.
# If the dressed dash shares that convention, slope(v on y) over lotd's dash-textured triangles
# is POSITIVE too, and the dressed dash is upside down on screen.  A NEGATIVE slope means the
# dress path is already right and the PO's complaint is about something else.
using Printf
include(joinpath(@__DIR__, "render.jl"))
const LOTDIR = get(ENV, "JM_LOTDIR", "")
isempty(LOTDIR) && error("set JM_LOTDIR")
_HAND_EXC = ("lothand","lotarms")
P = Render.extract_gpl_car(joinpath(LOTDIR,"lotd.3DO");
        exclude=("plaface","plahelm","pipe3"),
        cockpit_clean=true,
        maxlat=parse(Float32,get(ENV,"JM_COCKPIT_MAXLAT","0.30")))
@printf("CARPIN-like parts=%d\n", length(P))
DASHTEX = ("dash7a","dash7","ldashr")
function slope(a, b)
    ma = sum(a)/length(a); mb = sum(b)/length(b)
    sab = sum((a .- ma) .* (b .- mb)); saa = sum((a .- ma).^2); sbb = sum((b .- mb).^2)
    (saa == 0 || sbb == 0) ? (NaN, NaN) : (sab/saa, sab/sqrt(saa*sbb))
end
found = false
for p in P
    key = lowercase(p.tex)
    key in DASHTEX || continue
    found = true
    v = p.verts; ys=Float32[]; vs=Float32[]; zs=Float32[]; xs=Float32[]; nys=Float32[]
    for i in 1:11:length(v)-10
        push!(xs,v[i]); push!(ys,v[i+1]); push!(zs,v[i+2]); push!(nys,v[i+4])
        push!(vs,v[i+10])
    end
    sy,ry = slope(ys,vs); sz,rz = slope(zs,vs)
    @printf("%-8s tris=%-4d  x[%.3f,%.3f] y[%.3f,%.3f] z[%.3f,%.3f]  v[%.3f,%.3f]\n",
            key, length(v)÷33, minimum(xs),maximum(xs), minimum(ys),maximum(ys),
            minimum(zs),maximum(zs), minimum(vs),maximum(vs))
    @printf("           slope(v on y)=%+.4f r=%+.3f   slope(v on z)=%+.4f r=%+.3f  n.y med=%+.3f\n",
            sy,ry, sz,rz, sort(nys)[cld(length(nys),2)])
end
found || println("NO dash-textured part in the cockpit extraction -- the premise is wrong")
# and the full texture census, so "the dash is in there at all" is not assumed
println("cockpit textures present:")
for p in sort(P, by=x->lowercase(x.tex))
    @printf("  %-14s %d tris\n", p.tex, length(p.verts)÷33)
end
