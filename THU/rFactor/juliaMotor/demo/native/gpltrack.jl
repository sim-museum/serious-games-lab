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
                    push!(out, ObjInst(lowercase(off2name[wn]), X, Y, Z, yaw, sc))
                end
            end
        end
        k+=4
    end
    out
end

"""Build the racing-ribbon TrackSurface from the centreline, lifted to ground height."""
function build_surface(centreline, hat; halfwidth=9.0)
    pos = NTuple{3,Float64}[]
    for (cx, cy) in centreline
        h = JuliaMotor.hat3d(hat, cx, cy; ref=Inf)
        push!(pos, (cx, h[3] ? h[1] : 0.0, cy))      # (x=gx, y=height, z=gy)
    end
    JuliaMotor.TrackSurface(pos; halfwidth=halfwidth, cell=25.0)
end

end # module
