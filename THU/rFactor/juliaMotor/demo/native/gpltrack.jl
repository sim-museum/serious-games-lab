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
