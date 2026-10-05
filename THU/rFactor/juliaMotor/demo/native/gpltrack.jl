# GPL track integration: parse the .trk centreline, build a JuliaMotor TriangleHAT
# (ground/elevation) + TrackSurface (racing ribbon for spawn/on-track) from the GPL
# Zandvoort .3do + .trk, so the validated physics can drive the real GPL circuit.
#
# Frames: GPL world is (x, y horizontal, z up).  Physics/HAT/render use Y-up:
# (x, z_gpl→y_height, y_gpl→z).  So a GPL point (gx,gy) maps to physics (x=gx, z=gy),
# height from the HAT.  The renderer draws the track remapped the same way (no mirror).
module GPLTrack
using JuliaMotor

const VERTICAL = Set(["wiref_s","Hayba_s","Hayba_t","Hayba_e","Armco_s","Armco_t","Armco_e"])

"""Walk the .trk centreline (constant-curvature arcs) → GPL (x,y) points, densified."""
# TRACKSMOOTH-1 (PO 2026-09-05): subdiv was 5 points per track SECTION, i.e. a 5-chord approximation
# of each of GPL's arcs. GPL stores the circuit as arcs (a length and a heading per section), so the
# original is smooth and ours was a coarse polygon of it. Raising it to 20, together with the loop
# closure below, cuts the worst heading step per node from 21.4 deg to 4.5 (watglen) and 19.9 to 5.0
# (monza). Cost is only in this function's intermediate points -- build_line resamples to a uniform
# 3 m afterwards, so the node count barely moves (1251 -> 1252). JM_TRK_SUBDIV overrides.
function trk_centreline(path; subdiv::Int=parse(Int, get(ENV, "JM_TRK_SUBDIV", "20")))
    b = read(path)
    u32(o) = UInt32(b[o+1]) | UInt32(b[o+2])<<8 | UInt32(b[o+3])<<16 | UInt32(b[o+4])<<24
    i32(o) = reinterpret(Int32, u32(o)); TRK = 19685.03937
    traces = Int(u32(12)); sections = Int(u32(16)); wallsize = Int(u32(20))
    secbase = 28 + 64 + sections*4 + 32*traces*sections + wallsize
    altbase = 28 + 64 + sections*4
    toff = [i32(28+t*4) for t in 0:15]; ctr = argmin(abs.(toff[1:traces])) - 1
    x = i32(altbase + ctr*32 + 24)/TRK; y = i32(altbase + ctr*32 + 28)/TRK
    ang(s) = i32(secbase + s*52 + 12) * 2pi / 2.0^32
    wrap(d) = d > pi ? d-2pi : d < -pi ? d+2pi : d
    pts = NTuple{2,Float64}[]
    for s in 0:sections-1
        L = i32(secbase + s*52 + 8)/TRK
        th0 = ang(s); dth = wrap(ang(mod(s+1, sections)) - th0)
        for k in 0:subdiv-1                              # densify along the arc
            f = k/subdiv; push!(pts, (x, y))
            ll = L/subdiv; th = th0 + dth*f
            if abs(dth) < 1e-5
                x += ll*cos(th); y += ll*sin(th)
            else
                t1 = th + dth/subdiv
                x += (ll/(dth/subdiv))*(sin(t1)-sin(th)); y += (ll/(dth/subdiv))*(cos(th)-cos(t1))
            end
        end
    end
    # ⭐ TRACKSMOOTH-1 (PO 2026-09-05): CLOSE THE LOOP.
    # The arc walk integrates each section from the previous section's end, so rounding across
    # hundreds of sections leaves the last point short of (or past) the first -- the track does not
    # close. build_line then joins last->first with one straight chord, and that chord's heading is
    # nothing like its neighbours'. Measured on watglen: the two worst heading steps in the whole
    # circuit are the LAST two nodes -- 21.4 deg and 20.0 deg at subdiv=5, and 103.3 deg at
    # subdiv=60 where every other node is <= 2.24 deg. One broken joint was producing the yaw spike
    # the PO sees as AI cars snapping, and denser sampling made it WORSE because the same positional
    # gap is turned through a shorter segment.
    # Distribute the closure error smoothly around the loop (each point shifted in proportion to how
    # far round it is) so the polyline closes exactly and no single joint absorbs it. This is the
    # standard fix for an integrated closed curve and it moves every point by a fraction of a
    # millimetre-scale error rather than bending any one corner. JM_NO_LOOP_CLOSE=1 reverts.
    if length(pts) > 2 && get(ENV, "JM_NO_LOOP_CLOSE", "0") == "0"
        gx = pts[1][1] - pts[end][1]
        gz = pts[1][2] - pts[end][2]
        np = length(pts)
        for i in 1:np
            w = (i - 1) / (np - 1)          # 0 at the start, 1 at the end
            pts[i] = (pts[i][1] + gx*w, pts[i][2] + gz*w)
        end
        if get(ENV, "JM_TRACE_CLOSE", "0") != "0"
            @info "trk_centreline: closed loop gap" gap_m=sqrt(gx^2+gz^2) points=np
        end
    end
    pts
end

"""Build the ground TriangleHAT from a parsed GPL track mesh (Render.GPL3DO.Mesh3DO).

`exclude` = extra texture names dropped from the COLLISION HAT.

`drop_overpass` (Monza): drop any triangle that has ANOTHER surface more than `over_gap` m
BELOW its centroid — i.e. an overpass deck / embankment sitting over a lower surface.  GPL
Monza '67 is the road course; the high-speed BANKING (sopraelevata) crosses OVER the road but
is decorative (never driven), and its deck + grass embankment share the general `grasss1`/asphalt
textures (so they can't be name-excluded).  Keeping the LOWER surface wherever two stack leaves the
road course intact under the banking.  (The banking is still RENDERED — this only touches collision.)
Safe here because the road course never drives OVER anything; do NOT enable on tracks with real
drive-over bridges (Nürburgring)."""
function build_hat(mesh; cell=20.0, exclude=Set{String}(), exclude_pred=nothing, drop_overpass=false, over_gap=2.0, road_pred=nothing)
    g(t,i) = (Float64(t.p[i][1]), Float64(t.p[i][3]), Float64(t.p[i][2]))   # GPL(x,y,z) → Y-up (x, z_up→y, y→z)
    keep = trues(length(mesh.tris))
    for (k,t) in enumerate(mesh.tris)
        lt = lowercase(t.tex)
        (t.tex in VERTICAL || lt in exclude || (exclude_pred !== nothing && exclude_pred(lt))) && (keep[k] = false)
    end
    if drop_overpass
        # Drop a triangle only if ANOTHER surface lies directly beneath its centroid (precise
        # point-in-triangle in XZ) by more than `over_gap` — true vertical stacking = an overpass
        # deck / embankment over the road.  (A grass ditch BESIDE the road is not under the road's
        # centroid, so the road survives — the bug a coarse cell-min check had.)  Candidates are
        # bucketed on a grid so this stays ~O(n).
        gc = 12.0
        cen = Vector{NTuple{3,Float64}}(undef, length(mesh.tris))
        grid = Dict{NTuple{2,Int},Vector{Int}}()
        for (k,t) in enumerate(mesh.tris)
            cx = (Float64(t.p[1][1])+Float64(t.p[2][1])+Float64(t.p[3][1]))/3
            cy = (Float64(t.p[1][3])+Float64(t.p[2][3])+Float64(t.p[3][3]))/3   # GPL-z = height
            cz = (Float64(t.p[1][2])+Float64(t.p[2][2])+Float64(t.p[3][2]))/3   # GPL-y = world Z
            cen[k] = (cx, cy, cz)
            push!(get!(grid, (floor(Int,cx/gc), floor(Int,cz/gc)), Int[]), k)
        end
        # height of triangle u's plane at (qx,qz) if the point is inside u's XZ projection, else nothing
        function under_h(u, qx, qz)
            ax,az = Float64(u.p[1][1]), Float64(u.p[1][2]); bx,bz = Float64(u.p[2][1]), Float64(u.p[2][2]); cx2,cz2 = Float64(u.p[3][1]), Float64(u.p[3][2])
            d = (bz-cz2)*(ax-cx2)+(cx2-bx)*(az-cz2); abs(d) < 1e-9 && return nothing
            wa = ((bz-cz2)*(qx-cx2)+(cx2-bx)*(qz-cz2))/d; wb = ((cz2-az)*(qx-cx2)+(ax-cx2)*(qz-cz2))/d; wc = 1-wa-wb
            (wa >= -0.02 && wb >= -0.02 && wc >= -0.02) || return nothing
            wa*Float64(u.p[1][3]) + wb*Float64(u.p[2][3]) + wc*Float64(u.p[3][3])
        end
        for k in eachindex(mesh.tris)
            keep[k] || continue
            cx,cy,cz = cen[k]; gkey = (floor(Int,cx/gc), floor(Int,cz/gc))
            dropped = false
            for dz in -1:1, dx in -1:1
                cands = get(grid, (gkey[1]+dx, gkey[2]+dz), nothing); cands === nothing && continue
                for j in cands
                    j == k && continue
                    # only a ROAD surface below counts (the underpass): the banking deck over the road
                    # is dropped, but the drivable banking OVAL — deck over GRASS — is kept.
                    (road_pred === nothing || road_pred(lowercase(mesh.tris[j].tex))) || continue
                    h = under_h(mesh.tris[j], cx, cz)
                    if h !== nothing && h < cy - over_gap
                        dropped = true; break
                    end
                end
                dropped && break
            end
            dropped && (keep[k] = false)
        end
        # (The banking ISLAND over the road-mesh GAP at the first underpass — no road tri beneath it,
        # so pass 1 can't see it — is handled at the physics level by groundz's anti-wall-climb guard:
        # the car can't instantly climb 9 m, so that height is rejected and it coasts the gap.)
    end
    tris = JuliaMotor.Tri[]
    for (k,t) in enumerate(mesh.tris)
        keep[k] || continue
        push!(tris, JuliaMotor.Tri(g(t,1), g(t,2), g(t,3)))
    end
    JuliaMotor.TriangleHAT(tris; cell=cell)
end

"""A placed trackside object: an external .3do instanced at a GPL-world transform."""
struct ObjInst
    name::String      # object .3do basename (lowercase)
    x::Float64; y::Float64; z::Float64    # GPL world position (x,y horizontal, z up)
    yaw::Float64      # rotation about vertical (rad)
    scale::Float64
    pitch::Float64    # E81-S9: GPL placement pitch (rad, record +32) -- read but, until then, never applied
    roll::Float64     # E81-S9: GPL placement roll (rad, record +36)
    node::Int         # GREY-1: the record's offset in PRIM (the 0x0E node), -1 = unknown; keys segment_visibility
end
ObjInst(name, x, y, z, yaw, scale) = ObjInst(name, x, y, z, yaw, scale, 0.0, 0.0, -1)
ObjInst(name, x, y, z, yaw, scale, pitch, roll) = ObjInst(name, x, y, z, yaw, scale, pitch, roll, -1)

"""
    segment_visibility(path3do) -> (segs, vis)

GREY-1 (2026-10-05): GPL draws a track object only while the CAMERA is in a segment whose tree reaches it.
`nurburg.3do`'s root group holds a group of segment trees; each tree is a group(8): slots 1..7 = BSP planes /
cells (0x0F, whose object lists are (x,y,z,positioner) and which chain to coarser copies), slot 8 = a 0x10
table of four lap positions (TRK units). Returns `segs` = each segment's start lap position [m, GPL dlong],
and `vis[node]` = BitVector over segments for every 0x0E record reached. `tools/gpl_segvis.jl` is the probe.
"""
function segment_visibility(path3do)
    b = read(path3do)
    u32(o) = (o < 0 || o+4 > length(b)) ? UInt32(0) : UInt32(b[o+1]) | UInt32(b[o+2])<<8 | UInt32(b[o+3])<<16 | UInt32(b[o+4])<<24
    i32(o) = reinterpret(Int32, u32(o))
    prim = 0; primsz = 0; o = 12
    while o + 12 <= length(b)
        t = String(b[o+1:o+4]); sz = Int(u32(o+8)); d = o + 12
        t == "MIRP" && (prim = d; primsz = sz)
        o = d + sz; o += (4 - o % 4) % 4
    end
    prim == 0 && return (Float64[], Dict{Int,BitVector}())
    # the segment group: the root group's child that is a group of group(8)s with a 0x10 in slot 8
    isseg(g) = u32(prim+g) == 0x04 && u32(prim+g+4) == 8 && u32(prim + Int(i32(prim+g+36))) == 0x10
    root = Int(u32(prim)); segroot = -1
    if u32(prim+root) == 0x04
        for k in 1:Int(u32(prim+root+4))
            c = Int(i32(prim+root+4+4k)); (c >= 0 && u32(prim+c) == 0x04) || continue
            n = Int(u32(prim+c+4)); n > 16 || continue
            ns = count(j -> (g = Int(i32(prim+c+4+4j)); g >= 0 && isseg(g)), 1:min(n, 64))
            ns >= 32 && (segroot = c; break)
        end
    end
    segroot < 0 && return (Float64[], Dict{Int,BitVector}())
    nseg = Int(u32(prim+segroot+4))
    segtrees = [Int(i32(prim+segroot+4+4k)) for k in 1:nseg]
    segs = [isseg(g) ? i32(prim + Int(i32(prim+g+36)) + 8) / 19685.03937 : NaN for g in segtrees]
    vis = Dict{Int,BitVector}()
    children(off) = begin
        p = prim + off; t = u32(p); out = Int[]
        if t == 0x04
            n = Int(u32(p+4)); 0 < n < 5000 && for k in 1:n; push!(out, Int(i32(p+4+4k))); end
        elseif t == 0x05; push!(out, Int(i32(p+4)))
        elseif 0x06 <= t <= 0x0B
            for k in 1:(t == 0x06 ? 1 : t in (0x07, 0x0B) ? 2 : t == 0x08 ? 4 : 3); push!(out, Int(i32(p+8+4(k-1)))); end
        elseif t in (0x0D, 0x13, 0x16); push!(out, Int(i32(p+32)))
        elseif t == 0x19; push!(out, Int(i32(p+36)))
        elseif t == 0x11
            n = Int(u32(p+16)); 0 < n < 4096 && for k in 1:n; push!(out, Int(i32(p+24+8(k-1)))); end
        elseif t == 0x0F
            nd = Int(i32(p+36)); nd >= 0 && push!(out, nd)
            n = Int(u32(p+60)); 0 < n < 4096 && for k in 1:n; push!(out, Int(i32(p+64+16(k-1)+12))); end
        end
        filter(c -> 0 <= c < primsz, out)
    end
    for (k, g) in enumerate(segtrees)
        seen = Set{Int}(); st = Int[g]
        while !isempty(st)
            off = pop!(st); off in seen && continue; push!(seen, off)
            if u32(prim+off) == 0x0E
                get!(() -> falses(nseg), vis, off)[k] = true
                continue                                  # the object's own subtree is its mesh
            end
            append!(st, children(off))
        end
    end
    (segs, vis)
end

"""
    trackside_objects(path3do; objnames) -> Vector{ObjInst}

Scan a GPL track .3do's PRIM section for object-INSTANCE records and return the
placements.  Each record is 11 words: [0]=name string-offset, [1]=0, [2]=0x13
(positioner marker), [3..5]=X,Y,Z (GPL world), [6]=yaw, [7..8]=other rot (≈0),
[9]=scale.  `objnames` is the set of valid object basenames (lowercase) — names
matching one of these (with [1]==0,[2]==0x13 and finite/in-range floats) are the
authored trackside objects (crowds, grandstands, signs, billboards, vegetation).
"""
function trackside_objects(path3do; objnames::Set{String})
    b = read(path3do)
    u32(o)=(o<0||o+4>length(b)) ? UInt32(0) : UInt32(b[o+1])|(UInt32(b[o+2])<<8)|(UInt32(b[o+3])<<16)|(UInt32(b[o+4])<<24)
    f32(o)=reinterpret(Float32,u32(o)); tg(o)=String(b[o+1:o+4])
    strn=prim=0; strnsz=0; o=12
    while o+12<=length(b)
        t=tg(o); sz=Int(u32(o+8)); data=o+12
        t=="NRTS" && (strn=data; strnsz=sz)
        t=="MIRP" && (prim=data)
        o=data+sz; o+=(4-o%4)%4
    end
    (strn==0 || prim==0) && return ObjInst[]
    off2name=Dict{Int,String}(); cur=UInt8[]; p=0
    for i in strn:strn+strnsz-1
        c=b[i+1]
        if c==0xFF; break
        elseif c==0x00; off2name[p]=String(copy(cur)); p+=length(cur)+1; empty!(cur)
        else push!(cur,c); end
    end
    out=ObjInst[]; primlen=length(b)-prim; k=0
    # Anchor on the GPL 0x0E "named external sub-object reference" signature
    # [14, name-offset, 0, 19(=0x13 inline positioner), dx,dy,dz, rx,ry,rz, scale, child]
    # rather than the (fragile) name-offset word.  The 3-word type/marker (14,_,0,19) makes
    # this self-validating — the old name-anchored scan produced 442k coincidental hits that
    # only a tight coord clamp could trim, which silently dropped most of the hilly large
    # layouts (Spa: 9121 real placements, but z reaches 470 m → the old z<200 net kept 65).
    while k+44 <= primlen
        if u32(prim+k)==14 && u32(prim+k+8)==0 && u32(prim+k+12)==19
            wn=Int(u32(prim+k+4))
            if haskey(off2name,wn) && lowercase(off2name[wn]) in objnames
                X=f32(prim+k+16); Y=f32(prim+k+20); Z=f32(prim+k+24); yaw=f32(prim+k+28); sc=f32(prim+k+40)
                # loose sanity only — the 0x0E signature already rejects garbage; bounds sized
                # for the largest classic layouts (Spa/Monza ~±8 km horizontal, hillsides ~500 m).
                if all(isfinite,(X,Y,Z,yaw,sc)) && abs(X)<50000 && abs(Y)<50000 && abs(Z)<5000 && 0<sc<1000
                    pt = f32(prim+k+32); rl = f32(prim+k+36)
                    (isfinite(pt) && abs(pt) < 1.6) || (pt = 0.0); (isfinite(rl) && abs(rl) < 1.6) || (rl = 0.0)
                    push!(out, ObjInst(lowercase(off2name[wn]), X, Y, Z, yaw, sc, pt, rl, k))
                end
            end
        end
        k+=4
    end
    out
end

# TRACKSMOOTH-3 (PO 2026-09-19): THE SURFACE GPL DROVE. Each .trk section carries, per lateral trace
# (16 traces at fixed offsets), a 32-byte record = 8 int32 in TRK units: words 0..3 are the cubic
# coefficients a3 a2 a1 a0 of the altitude in the section's normalised length u in [0,1] (words 4,5
# are 3a3 and 2a2). S1 measured the joins C1 across all 47 Watkins Glen sections (max height jump
# 0.01 cm, max slope jump 1e-4) and the profile against the sim's mesh HAT along the ribbon:
# r = 0.9999, no shift, no sign flip, offset -0.11 m, residual p50 0.10 m -- the mesh is a strip-wise
# approximation of THIS spline, and its creases are what the player felt as the jounce.
struct TrkAlt
    S0::Vector{Float64}          # section start distance [m], length nsec+1 (last = lap)
    L::Vector{Float64}           # section length [m]
    lat::Vector{Float64}         # trace lateral offsets [m], ascending
    coef::Array{Float64,3}       # (section, trace, 1:4) = a0 a1 a2 a3 in metres, u in [0,1]
    total::Float64
end
function trk_altitude(path)
    b = read(path)
    u32(o) = UInt32(b[o+1]) | UInt32(b[o+2])<<8 | UInt32(b[o+3])<<16 | UInt32(b[o+4])<<24
    i32(o) = reinterpret(Int32, u32(o)); TRK = 19685.03937
    traces = Int(u32(12)); sections = Int(u32(16)); wallsize = Int(u32(20))
    toff = [i32(28+t*4)/TRK for t in 0:traces-1]
    altbase = 28 + 64 + sections*4; secbase = altbase + 32*traces*sections + wallsize
    L = [i32(secbase + s*52 + 8)/TRK for s in 0:sections-1]
    S0 = zeros(sections+1); for s in 1:sections; S0[s+1] = S0[s] + L[s]; end
    ord = sortperm(toff)
    coef = zeros(sections, traces, 4)
    for s in 0:sections-1, (k, t) in enumerate(ord .- 1)
        o = altbase + (s*traces + t)*32
        coef[s+1, k, 1] = i32(o+12)/TRK; coef[s+1, k, 2] = i32(o+8)/TRK
        coef[s+1, k, 3] = i32(o+4)/TRK;  coef[s+1, k, 4] = i32(o)/TRK
    end
    TrkAlt(S0, L, toff[ord], coef, S0[end])
end
"""Altitude of the .trk surface at lap distance `s` [m] and lateral offset `lat` [m] (trace frame,
positive toward the higher trace offsets); linear between traces, cubic along the section."""
function trk_height(ta::TrkAlt, s::Real, lat::Real)
    sm = mod(s, ta.total)
    sec = clamp(searchsortedlast(ta.S0, sm), 1, length(ta.L))
    u = clamp((sm - ta.S0[sec]) / max(ta.L[sec], 1e-6), 0.0, 1.0)
    nt = length(ta.lat)
    l = clamp(lat, ta.lat[1], ta.lat[end])
    k = clamp(searchsortedlast(ta.lat, l), 1, nt-1)
    f = (l - ta.lat[k]) / max(ta.lat[k+1] - ta.lat[k], 1e-6)
    h(t) = ((ta.coef[sec,t,4]*u + ta.coef[sec,t,3])*u + ta.coef[sec,t,2])*u + ta.coef[sec,t,1]
    h(k)*(1-f) + h(k+1)*f
end

"""
    defold(cl; label) -> centreline

Drop centreline nodes that DOUBLE BACK on the path (SEAM-1, PO 2026-09-26).

The aligned centreline is re-centred on the visible road over several passes, and those passes move
each node laterally -- which can leave the path reversing at a node. Where it does, the track frame
`(lapdist, lateral)` is MULTI-VALUED: two different lap distances name nearly the same patch of
tarmac, and the nearest-foot rule flips between them as a car drives through. MEASURED at Watkins
Glen, sampling the ribbon at 0.2 m steps of lapdist near the start/finish: the world point jumped
2.1 m between lapdist 3734.0 and 3734.2 and 2.9 m back at 3736.6, and the driven road height with it
(0.19 m and 0.23 m in ONE FRAME -- the largest steps left in the lap once the ribbon was resampled
uniformly, and present in BOTH projection arms, which is how the fold was told apart from the
projection). The AI rail is built from the same centreline and inherits the same folds, so its arc
length jumps there too -- one fold, both symptoms, at one place on the track.

A fold is a node whose two chords point in opposite directions. On a 3-4 m centreline even a 20 m
hairpin turns only ~11 deg per node, so more than 90 deg is never real geometry. Several passes,
because adjacent folded nodes hide each other. JM_RIBBON_DEFOLD=0 keeps them (the control arm).
"""
function defold(cl; label = "centreline")
    (get(ENV, "JM_RIBBON_DEFOLD", "1") == "0" || length(cl) <= 8) && return cl
    out = collect(cl); nrm = 0
    for _ in 1:4
        m = length(out); m > 8 || break
        keep = trues(m)
        for k in 1:m
            a = out[mod1(k-1, m)]; b = out[k]; c = out[mod1(k+1, m)]
            ax = b[1]-a[1]; az = b[2]-a[2]; bx = c[1]-b[1]; bz = c[2]-b[2]
            (ax*bx + az*bz < 0) && (keep[k] = false)
        end
        all(keep) && break
        out = out[keep]; nrm += m - length(out)
    end
    nrm > 0 && println("  [", label, "] de-folded: dropped ", nrm, " node(s) that doubled back ",
                       "(JM_RIBBON_DEFOLD=0 keeps them)")
    out
end

"""Build the racing-ribbon TrackSurface from the centreline, lifted to ground height.

SEAM-1 (PO 2026-09-26: "seams in the road surface, where the track is piecewise linear rather than
smooth"). The centreline handed in here has been ALIGNED and then re-centred on the visible road over
four passes, and those passes move each node laterally -- which bunches some nodes together and
stretches others apart. MEASURED on the sim's own Watkins Glen ribbon: 940 segments with spacing from
**0.017 m to 27.1 m** (median 2.31, p05 0.55). This ribbon is not just geometry: it carries the
(lapdist, lateral) frame that the .trk altitude spline and the SINK-1 correction table are read
through, so a 2 cm segment beside a 3 m one is a fault in the FRAME. It showed up as isolated 0.2-0.4 m
steps in the driven road height (p99 2.3 m/s of vertical velocity per frame, worst 23 m/s at lapdist
3750 -- and the ribbon's shortest segment, 0.017 m, sits at lapdist 3752).

So resample to a uniform `spacing` by arc length before building. A polyline resampled along its own
chords has the same shape (no smoothing, no shortcutting), and every consumer of the frame gets nodes
it can interpolate: this is what `RaceAI.build_line` has always done for the AI rail (3.0 m) and what
the ribbon never did. JM_RIBBON_SPACING overrides; 0 keeps the raw nodes."""
function build_surface(centreline, hat; halfwidth=9.0,
                       spacing=parse(Float64, get(ENV, "JM_RIBBON_SPACING", "3.0")))
    cl = collect(centreline)
    # SEAM-1 part two: the re-centring passes can leave the centreline DOUBLING BACK on itself. Where it
    # does, (lapdist, lateral) is MULTI-VALUED -- two different lap distances name nearly the same patch
    # of tarmac -- and the nearest-foot rule flips between them as the car drives. MEASURED at Watkins
    # Glen: sampling the ribbon at 0.2 m steps of lapdist near the start/finish, the world point jumped
    # 2.1 m between lapdist 3734.0 and 3734.2 and 2.9 m back at 3736.6, and the driven road height with
    # it (0.19 m and 0.23 m in one frame -- the largest steps left in the lap after the ribbon was made
    # uniform, and present in BOTH projection arms, which is what identified the fold rather than the
    # projection). A fold is a node whose two chords point in opposite directions: on a 3-4 m ribbon even
    # a 20 m-radius hairpin turns only ~11 deg per node, so >90 deg is never real geometry. Drop those
    # nodes (a few passes, since neighbours can hide each other) before resampling.
    cl = defold(cl; label = "ribbon")
    if spacing > 0 && length(cl) > 2
        m = length(cl)
        cum = zeros(m+1)
        for i in 1:m
            j = i % m + 1
            cum[i+1] = cum[i] + hypot(cl[j][1]-cl[i][1], cl[j][2]-cl[i][2])
        end
        total = cum[m+1]
        nf = max(m ÷ 2, round(Int, total/spacing))      # never coarser than half the input
        fine = Vector{NTuple{2,Float64}}(undef, nf)
        for k in 1:nf
            d = (k-1)/nf * total
            j = clamp(searchsortedlast(cum, d), 1, m)
            f = (d - cum[j]) / max(cum[j+1]-cum[j], 1e-9)
            a = cl[j]; b = cl[j % m + 1]
            fine[k] = (a[1] + (b[1]-a[1])*f, a[2] + (b[2]-a[2])*f)
        end
        cl = fine
    end
    # SEAM-1 part three: the frame's own CURVATURE. `(lapdist, lateral)` is single-valued only out to the
    # local radius of curvature: where the re-centred centreline has a jog tighter than the lateral offset
    # a car is running at, that car has TWO feet on the ribbon and the nearest one flips as it drives --
    # the last family of ~0.2 m one-frame steps in the driven road height. MEASURED minimum radius before
    # any repair: Watkins Glen 1.80 m, the Ring 1.74 m (73 nodes under 12 m), Spa 1.76 m (79), Monza
    # 2.77 m (21), Zandvoort 6.07 m (2) -- "centrelines" with 2 m kinks in them.
    #
    # The repair smooths the NEIGHBOURHOOD of each offending node and then LOOKS AGAIN, widening nothing
    # and repeating until no node is left under the bar. Three shapes were measured, and the order of
    # preference is the measurement's, not mine:
    #   * one local pass (halo +-3, 12 passes): does NOT converge -- the Ring kept 5 nodes under 12 m,
    #     Monza 3, Spa 6, because a kink whose neighbours are pinned cannot be pulled straight. Monza's
    #     worst surface step went to 20.5 m/s (against 2.6 for the global filter) and the Ring's road
    #     corridor got slightly WORSE than the control (123 anomalies vs 121).
    #   * a global Laplacian (every node, 6 passes): converged and measured well everywhere (Monza max
    #     2.6 m/s, Ring corridor 115 vs the control's 121) but moves all ~8,451 Ring nodes to repair 73.
    #   * ITERATED local (this): converges like the global one while moving only the neighbourhoods that
    #     need it. Rounds are capped so a pathological ribbon cannot loop forever.
    # JM_RIBBON_SMOOTH=0 disables; JM_RIBBON_RMIN sets the radius bar; JM_RIBBON_ROUNDS caps the rounds.
    let passes = parse(Int, get(ENV, "JM_RIBBON_SMOOTH", "6")), lam = 0.3,
        rmin = parse(Float64, get(ENV, "JM_RIBBON_RMIN", "12.0")),
        rounds = parse(Int, get(ENV, "JM_RIBBON_ROUNDS", "12")), halo = 3
        radii(v) = begin
            m = length(v); r = fill(Inf, m)
            for k in 1:m
                a = v[mod1(k-1,m)]; b = v[k]; c = v[mod1(k+1,m)]
                ax = b[1]-a[1]; az = b[2]-a[2]; bx = c[1]-b[1]; bz = c[2]-b[2]
                la = hypot(ax,az); lb = hypot(bx,bz)
                (la < 1e-6 || lb < 1e-6) && continue
                dth = atan(ax*bz - az*bx, ax*bx + az*bz)
                r[k] = abs(dth) < 1e-9 ? Inf : (la+lb)/2 / abs(dth)
            end
            r
        end
        if passes > 0 && length(cl) > 8
            r0 = radii(cl); m = length(cl)
            tight0 = count(<(rmin), r0)
            if tight0 > 0
                touched = falses(m); rnd = 0
                for _ in 1:rounds
                    r = radii(cl); tight = findall(<(rmin), r)
                    isempty(tight) && break
                    rnd += 1
                    mask = falses(m)
                    for k in tight, d in -halo:halo; mask[mod1(k+d, m)] = true; touched[mod1(k+d, m)] = true; end
                    for _ in 1:passes
                        nxt = copy(cl)
                        for k in 1:m
                            mask[k] || continue
                            a = cl[mod1(k-1,m)]; b = cl[k]; c = cl[mod1(k+1,m)]
                            nxt[k] = (b[1] + lam*(a[1] + c[1] - 2b[1]), b[2] + lam*(a[2] + c[2] - 2b[2]))
                        end
                        cl = nxt
                    end
                end
                r1 = radii(cl)
                println("  [ribbon] curvature repaired: ", tight0, " node(s) under ", rmin, " m -> ",
                        count(<(rmin), r1), " in ", rnd, " round(s); min radius ",
                        round(minimum(r0), digits=2), " -> ", round(minimum(r1), digits=2), " m; ",
                        count(touched), " of ", m, " nodes moved (JM_RIBBON_SMOOTH=0 disables)")
            end
        end
    end
    pos = NTuple{3,Float64}[]
    for (cx, cy) in cl
        h = JuliaMotor.hat3d(hat, cx, cy; ref=Inf)
        push!(pos, (cx, h[3] ? h[1] : 0.0, cy))      # (x=gx, y=height, z=gy)
    end
    JuliaMotor.TrackSurface(pos; halfwidth=halfwidth, cell=25.0)
end

# GPL .trk centreline ↔ mesh alignment.  The .trk start point can be parsed with a
# large constant offset from the .3do mesh (the GPL Nürburgring start sits ~87 km off
# in z), which would float the racing line off the ground.  The line's SHAPE is
# correct, so we slide it (pure translation) to maximise overlap with the terrain HAT:
# estimate the offset from bbox centres, then grid-search + refine.  Zandvoort already
# aligns (offset ≈ 0) so it's returned untouched.
function align_centreline(cl, hat)
    sample = cl[1:max(1, length(cl) ÷ 400):end]
    cov(dx, dz) = count(p -> JuliaMotor.hat3d(hat, p[1]+dx, p[2]+dz; ref=Inf)[3], sample) / length(sample)
    cov(0.0, 0.0) > 0.6 && return cl                              # already on the mesh (Zandvoort)
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
    println("centreline aligned: ", round(Int, best[1]*100), "% on terrain, offset (",
            round(Int, best[2]), ", ", round(Int, best[3]), ")")
    [(p[1]+best[2], p[2]+best[3]) for p in cl]
end

"""The .trk elevation as a height field over the ribbon's own (node index, lateral) frame -- the field
ROADCURVE warps the drawn road onto (GPLROAD-1). `hat` is the RAW track HAT, used to calibrate: the
lateral SIGN of the .trk trace frame against ours, the bulk vertical OFFSET, and a low-passed
(mesh - spline) correction so the field follows the drawn road's mean without inheriting its creases.
Returns `(u, lat) -> height`, or `nothing` when the .trk does not describe this ribbon."""
function trk_height_field(ta, ribbon, hat; corrsig = 8.0, outlier = 2.0)
    if abs(ta.total - ribbon.lap_length) > 0.02 * ribbon.lap_length
        println("  [roadcurve] vertical OFF: .trk lap ", round(ta.total, digits=1), " m vs ribbon ",
                round(ribbon.lap_length, digits=1), " m")
        nothing
    else
        np = length(ribbon.pos)
        res1 = Float64[]; resm = Float64[]; off0 = Float64[]
        for i in 1:6:np
            q = ribbon.pos[i]; pq = ribbon.perp[i]; sv = ribbon.lapdist[i]
            h0 = JuliaMotor.hat3d(hat, q[1], q[3]; ref = q[2] + 3.0)
            h0[3] || continue
            abs(Float64(h0[1]) - q[2]) <= outlier || continue
            push!(off0, Float64(h0[1]) - GPLTrack.trk_height(ta, sv, 0.0))
            for lat in (-4.0, 4.0)
                hm = JuliaMotor.hat3d(hat, q[1] + lat*pq[1], q[3] + lat*pq[3]; ref = q[2] + 3.0)
                hm[3] || continue
                push!(res1, abs(Float64(hm[1]) - GPLTrack.trk_height(ta, sv,  lat) - off0[end]))
                push!(resm, abs(Float64(hm[1]) - GPLTrack.trk_height(ta, sv, -lat) - off0[end]))
            end
        end
        med(v) = isempty(v) ? 0.0 : (u = sort(v); u[div(length(u)+1, 2)])
        if length(off0) < 20
            println("  [roadcurve] vertical OFF: only ", length(off0), " mesh samples on the centreline")
            nothing
        else
            rc_off = med(copy(off0)); rc_sgn = med(copy(res1)) <= med(copy(resm)) ? 1.0 : -1.0
            println("  [roadcurve] vertical ON: .trk elevation spline, lateral sign ", rc_sgn,
                    " (residual +", round(med(copy(res1)), digits=3), " / -", round(med(copy(resm)), digits=3),
                    " m), offset ", round(rc_off, digits=3), " m over ", length(off0), " samples")
            # u is the 1-based node index into the curve's node list; map it to lap distance the same
            # way the curve interpolates position, then read the spline. Wrap through the closing node.
            sv = ribbon.lapdist; lapl = ribbon.lap_length
            nn = (length(sv) > 2 && hypot(ribbon.pos[end][1]-ribbon.pos[1][1],
                                          ribbon.pos[end][3]-ribbon.pos[1][3]) < 0.5) ? length(sv)-1 : length(sv)
            s_of(u) = (i = floor(Int, u); f = u - i;
                       s0 = sv[mod1(i, nn)]; s1 = i+1 > nn ? lapl : sv[mod1(i+1, nn)];
                       s1 < s0 && (s1 += lapl); s0 + (s1-s0)*f)
            # A single offset is not enough. The .trk elevation and the .3do differ by up to ~1 m in
            # places (SINK-1 measured raw mesh - spline from -0.20 to +1.05 m at Watkins Glen), so a
            # flat spline would drag the drawn road off the mesh there -- and, with a safety cap, would
            # move some vertices and not their neighbours, which is a worse seam than the one being
            # fixed. Same remedy as SINK-1 for the physics: add the (mesh - spline) difference,
            # LOW-PASSED along the lap, so the field keeps the spline's smoothness (the Gaussian
            # cannot introduce curvature the samples did not have) while its mean follows the drawn
            # road. Sampled on the RAW mesh, which is what this pass is about to reshape.
            rc_dl = [-5.0, -2.5, 0.0, 2.5, 5.0]
            rc_ds = 2.0
            rc_ns = max(8, ceil(Int, lapl / rc_ds))
            rc_raw = zeros(rc_ns, length(rc_dl))
            for k in 1:rc_ns
                sq = (k-1) * lapl / rc_ns
                i = clamp(searchsortedlast(sv, sq), 1, length(sv))
                j = mod1(i+1, length(sv)); f = (sq - sv[i]) / max((i == length(sv) ? lapl : sv[i+1]) - sv[i], 1e-9)
                pa = ribbon.pos[i]; pb = ribbon.pos[j]; pq = ribbon.perp[i]
                bx = pa[1] + (pb[1]-pa[1])*f; bz = pa[3] + (pb[3]-pa[3])*f
                hb = pa[2] + (pb[2]-pa[2])*f
                for (c, lat) in enumerate(rc_dl)
                    # ref, not Inf: on a raw track HAT the TOPMOST surface at a point on the road is often
                    # a banner, a bridge or a tree. Read with Inf, the Nurburgring's correction came out
                    # spanning -11.8 to +10.2 m -- that is scenery, not road. `outlier` drops whatever
                    # survives that and still cannot be a road surface.
                    hm = JuliaMotor.hat3d(hat, bx + lat*pq[1], bz + lat*pq[3]; ref = hb + 3.0)
                    d = hm[3] ? Float64(hm[1]) - GPLTrack.trk_height(ta, sq, rc_sgn*lat) - rc_off : NaN
                    rc_raw[k, c] = (isfinite(d) && abs(d) <= outlier) ? d : NaN
                end
            end
            # fill gaps (off-mesh samples) from the nearest valid station, then Gaussian low-pass
            for c in 1:length(rc_dl)
                any(isfinite, view(rc_raw, :, c)) || (rc_raw[:, c] .= 0.0; continue)
                last = 0.0
                for k in 1:rc_ns; isfinite(rc_raw[k, c]) ? (last = rc_raw[k, c]) : (rc_raw[k, c] = last); end
                for k in rc_ns:-1:1; isfinite(rc_raw[k, c]) || (rc_raw[k, c] = 0.0); end
            end
            rc_sig = corrsig / rc_ds
            rc_cor = let kk = ceil(Int, 3*rc_sig), w = [exp(-0.5*(j/rc_sig)^2) for j in -ceil(Int,3*rc_sig):ceil(Int,3*rc_sig)]
                w ./= sum(w)
                [sum(w[j+kk+1] * rc_raw[mod1(k+j, rc_ns), c] for j in -kk:kk) for k in 1:rc_ns, c in 1:length(rc_dl)]
            end
            nval = count(isfinite, rc_raw)
            rmin = minimum(x for x in rc_raw if isfinite(x); init = Inf)
            rmax = maximum(x for x in rc_raw if isfinite(x); init = -Inf)
            println("  [roadcurve] vertical correction: ", nval, "/", length(rc_raw),
                    " road samples, raw (mesh - spline) min ",
                    round(rmin, digits=3), " max ", round(rmax, digits=3),
                    " m -> low-passed (sigma ", round(rc_sig*rc_ds, digits=1), " m) min ",
                    round(minimum(rc_cor), digits=3), " max ", round(maximum(rc_cor), digits=3), " m")
            function rc_corr(sq, lat)
                fk = mod(sq, lapl) / lapl * rc_ns + 1
                k0 = floor(Int, fk); fk -= k0
                a = mod1(k0, rc_ns); b = mod1(k0+1, rc_ns)
                l = clamp(lat, rc_dl[1], rc_dl[end])
                c = clamp(searchsortedlast(rc_dl, l), 1, length(rc_dl)-1)
                g = (l - rc_dl[c]) / (rc_dl[c+1] - rc_dl[c])
                (rc_cor[a, c]*(1-g) + rc_cor[a, c+1]*g)*(1-fk) + (rc_cor[b, c]*(1-g) + rc_cor[b, c+1]*g)*fk
            end
            function rc_h(u, lat)
                sq = s_of(u)
                GPLTrack.trk_height(ta, sq, rc_sgn*lat) + rc_off + rc_corr(sq, lat)
            end
        end
    end
end

end # module
