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
function trk_centreline(path; subdiv::Int=5)
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
    pts
end

"""Build the ground TriangleHAT from a parsed GPL track mesh (Render.GPL3DO.Mesh3DO)."""
function build_hat(mesh; cell=20.0)
    tris = JuliaMotor.Tri[]
    for t in mesh.tris
        t.tex in VERTICAL && continue
        v(i) = (Float64(t.p[i][1]), Float64(t.p[i][3]), Float64(t.p[i][2]))   # GPL→Y-up
        push!(tris, JuliaMotor.Tri(v(1), v(2), v(3)))
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
    while k+44 <= primlen
        w0=Int(u32(prim+k))
        if haskey(off2name,w0) && lowercase(off2name[w0]) in objnames &&
           u32(prim+k+4)==0 && u32(prim+k+8)==19
            X=f32(prim+k+12); Y=f32(prim+k+16); Z=f32(prim+k+20); yaw=f32(prim+k+24); sc=f32(prim+k+36)
            if all(isfinite,(X,Y,Z,yaw,sc)) && abs(X)<2000 && abs(Y)<2000 && abs(Z)<50 && 0<sc<100
                push!(out, ObjInst(lowercase(off2name[w0]), X, Y, Z, yaw, sc))
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
