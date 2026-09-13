# CARGOLD-1 S9c probe: is the gauge cluster's PAINTED image inverted relative to its
# geometry?  Layout of a TrackPart vert (stride 11): pos 1:3, normal 4:6, colour 7:9, uv 10:11.
#
# The question S9b left open: the mirror in GAUGEFLIP turns the dial FACES upright but the
# cluster LAYOUT (five small dials above the hub, big tacho below) did not move.  A geometry
# mirror cannot leave the layout alone unless the layout is not in the geometry -- i.e. the
# cluster is one flat panel and every dial is PAINTED in the texture.  This prints enough to
# settle that: the panel's extent, its triangle count, and the SIGN of the y<->v relation.
#
# PREDICTION (stated before the run, per parity-captures-must-record-their-state):
#   If the cluster is a flat painted panel, slope(v on y) is NEGATIVE without the mirror
#   (texture v grows downward, y grows upward -- the normal, correct convention) and POSITIVE
#   with it.  If instead the dials are separate discs, the y-histogram shows several distinct
#   clumps and this whole framing is wrong.
using Printf
include(joinpath(@__DIR__, "render.jl"))
const LOT3DO = get(ENV, "JM_LOT3DO", "")
isempty(LOT3DO) && error("set JM_LOT3DO to the Lotus .3do the demo loads")
P = Render.extract_gpl_car(LOT3DO; only=("dash7a",), maxlat=0.85f0)
@printf("parts=%d\n", length(P))
ys = Float32[]; vs = Float32[]; us = Float32[]; zs = Float32[]; xs = Float32[]
ny = Float32[]
for p in P
    v = p.verts
    @printf("  part tex=%-12s tris=%d\n", p.tex, length(v) ÷ 33)
    for i in 1:11:length(v)-10
        push!(xs, v[i]); push!(ys, v[i+1]); push!(zs, v[i+2])
        push!(ny, v[i+4])
        push!(us, v[i+9]); push!(vs, v[i+10])
    end
end
n = length(ys)
@printf("verts=%d  x[%.3f,%.3f] y[%.3f,%.3f] z[%.3f,%.3f]\n",
        n, minimum(xs), maximum(xs), minimum(ys), maximum(ys), minimum(zs), maximum(zs))
@printf("uv:  u[%.3f,%.3f]  v[%.3f,%.3f]\n", minimum(us), maximum(us), minimum(vs), maximum(vs))
@printf("normal.y: min=%.3f median=%.3f max=%.3f  (down-facing => negative)\n",
        minimum(ny), sort(ny)[cld(n,2)], maximum(ny))
# least-squares slope of v on y, and on z (the panel is tilted, so the screen-vertical axis
# may be a mix of y and z; report both and the correlation so the dominant one is visible)
function slope(a, b)
    ma = sum(a)/length(a); mb = sum(b)/length(b)
    sab = sum((a .- ma) .* (b .- mb)); saa = sum((a .- ma).^2); sbb = sum((b .- mb).^2)
    (saa == 0 || sbb == 0) ? (NaN, NaN) : (sab/saa, sab/sqrt(saa*sbb))
end
sy, ry = slope(ys, vs); sz, rz = slope(zs, vs); sx, rx = slope(xs, vs)
@printf("slope(v on y)=%+.4f r=%+.3f   slope(v on z)=%+.4f r=%+.3f   slope(v on x)=%+.4f r=%+.3f\n",
        sy, ry, sz, rz, sx, rx)
# y-histogram: distinct clumps => separate dial discs; one band => a flat painted panel
lo, hi = minimum(ys), maximum(ys); nb = 20
h = zeros(Int, nb)
for y in ys; h[clamp(1 + floor(Int, (y-lo)/(hi-lo+1f-9)*nb), 1, nb)] += 1; end
println("y histogram (", nb, " bins over [", round(lo,digits=3), ",", round(hi,digits=3), "]):")
for (i,c) in enumerate(h)
    @printf("  %6.3f %s %d\n", lo + (i-0.5)*(hi-lo)/nb, "#"^min(c,60), c)
end

# --- and the ART itself.  The panel is flat with two y rows, so the ONLY thing the y-mirror can
# do is exchange which row carries which v -- i.e. it is EXACTLY a v flip, nothing more.  Which
# way is upright is therefore a question about the image, so decode and write it: PPM row 0 is
# the first decoded row, and glTexImage2D maps the first row to v=0, so the PPM's TOP is v=0.
if get(ENV,"JM_DASH_DUMP","0") != "0"
    idx = Render.gpl_texture_index(dirname(LOT3DO))
    r = Render.tex_rgba(idx, "dash7a")
    if r === nothing
        println("dash7a: tex_rgba returned nothing")
    else
        w_, h_, px_ = r[1], r[2], r[3]
        out = get(ENV,"JM_DASH_DUMP_PATH", "/tmp/dash7a.ppm")
        open(out, "w") do io
            write(io, "P6\n$(w_) $(h_)\n255\n")
            for i in 0:(w_*h_-1); write(io, px_[4i+1], px_[4i+2], px_[4i+3]); end
        end
        @printf("dash7a decoded %dx%d -> %s  (PPM top row == v=0)\n", w_, h_, out)
        # row luminance profile: the dial faces are the bright discs, so where they sit in v
        # is measurable without looking
        for band in 0:7
            r0 = band*h_÷8; r1 = (band+1)*h_÷8
            s = 0.0; n2 = 0
            for y in r0:r1-1, x in 0:w_-1
                i = (y*w_+x); s += 0.299*px_[4i+1] + 0.587*px_[4i+2] + 0.114*px_[4i+3]; n2 += 1
            end
            @printf("  v %.3f-%.3f  mean luma %6.1f\n", r0/h_, r1/h_, s/n2)
        end
    end
end
