# graze_sweep.jl — E99-S2. WHY DOES A GRAZE AND A NEAR-SQUARE HIT END THE SAME?
#
# E99's first sprint measured a 108 km/h glancing impact keeping 5.6% of its energy — and the SAME
# 5.6% at lateral offsets 3.0, 4.2, 4.6 and 4.9 m against a 5 m obstacle. Geometry that different
# should not converge; the note filed it as "the contact is saturating somewhere and the obliqueness
# is not reaching the result".
#
# This walks the offset finely and reports, per run, what the CONTACT itself saw — first-contact
# normal, peak penetration, peak force, impulse — next to the outcome. If the normals differ but the
# outcomes do not, the saturation is in the force law; if the normals are identical, the obliqueness
# never reached the contact at all.
#
#   julia --project=JuliaMotorMTK JuliaMotorMTK/tools/graze_sweep.jl [v_kmh] [radius_m]

include(joinpath(@__DIR__, "..", "src", "drive_rt3d.jl")); using .DriveRT3D
using Printf

const dt = 1/60; const M = 617.0; const CARHALF = 2.0
flat(x, z) = 0.0

# E99-S3: per-frame contact dump for ONE offset (JM_GRAZE_TRACE=<offset>). The sweep found a band
# (2.60-2.75 m) where the car ends on the FAR side of the obstacle; a flipped normal mid-contact is
# the usual cause, and it is only visible frame by frame.
const TRACE_OFF = haskey(ENV, "JM_GRAZE_TRACE") ? parse(Float64, ENV["JM_GRAZE_TRACE"]) : NaN

function graze(v0, lateral; r = 3.0, wallx = 60.0, nsteps = 600)
    c = build_car3d(; x0 = wallx - 12.0, z0 = lateral, θ0 = 0.0, v0 = v0, y0 = 0.0)
    rr = r + CARHALF
    wvx = 0.0; wvz = 0.0
    epre = 0.5*M*v0*v0
    e(cc) = (a = cc.getall(cc.integ); 0.5*M*(a[4]^2 + a[5]^2))
    nx0 = nz0 = NaN; pen_max = 0.0; f_max = 0.0; imp = 0.0; nct = 0; closing = 0.0
    for i in 1:nsteps
        dx = c.x - wallx; dz = c.z - 0.0; d = hypot(dx, dz)
        Fx = Fy = Mz = 0.0
        if d < rr && d > 1e-3
            nx = dx/d; nz = dz/d; vn = wvx*nx + wvz*nz
            closing = max(closing, -vn)
            (Fx, Fy, Mz) = DriveRT3D.contact_force(rr - d, nx, nz, vn, c.θ; kind = :wall, dt = dt)
            if nct == 0; nx0 = nx; nz0 = nz; end
            if !isnan(TRACE_OFF) && abs(lateral - TRACE_OFF) < 1e-9 && nct < 60
                @printf("   f%-4d x=%7.2f z=%7.2f d=%6.3f pen=%6.3f  n=(%+.3f,%+.3f) vn=%+8.2f  F=(%+9.1f,%+9.1f) Mz=%+9.1f\n",
                        i, c.x, c.z, d, rr - d, nx, nz, vn, Fx, Fy, Mz)
            end
            nct += 1
            pen_max = max(pen_max, rr - d)
            f = hypot(Fx, Fy); f_max = max(f_max, f); imp += f*dt
        end
        extforce3d!(c; Fx = Fx, Fy = Fy, Mz = Mz)
        step_car3d!(c, 0.0, 0.0, 0.0, dt; groundz = flat)
        (wvx, wvz) = DriveRT3D.world_velocity(c)
    end
    a = c.getall(c.integ)
    (kept = 100*e(c)/epre, vend = hypot(a[4], a[5]), nx0 = nx0, nz0 = nz0,
     pen = pen_max, fmax = f_max, imp = imp, nct = nct, closing = closing,
     zend = c.z, theta = c.θ)
end

v_kmh = length(ARGS) >= 1 ? parse(Float64, ARGS[1]) : 108.0
r     = length(ARGS) >= 2 ? parse(Float64, ARGS[2]) : 3.0
v0 = v_kmh/3.6
rr = r + CARHALF
@printf("\nE99-S2 graze sweep: %.0f km/h into a %.1f m obstacle (contact radius %.1f m)\n\n", v_kmh, r, rr)
@printf("%-7s %-7s %-7s %-8s %-8s %-9s %-7s %-8s %-8s %-8s\n",
        "offset", "kept%", "vend", "n0x", "n0z", "pen_max", "steps", "Fmax kN", "imp kNs", "z_end")
for off in (haskey(ENV,"JM_GRAZE_OFFSETS") ? [parse(Float64,x) for x in split(ENV["JM_GRAZE_OFFSETS"],",")] : collect(0.0:0.25:(rr + 0.5)))
    g = graze(v0, off; r = r)
    @printf("%-7.2f %-7.2f %-7.2f %-8.4f %-8.4f %-9.4f %-7d %-8.1f %-8.2f %-8.2f\n",
            off, g.kept, g.vend, g.nx0, g.nz0, g.pen, g.nct, g.fmax/1000, g.imp/1000, g.zend)
end
println("\n  n0x/n0z = the contact normal at FIRST touch. If it varies with the offset but `kept`",
        "\n  does not, the obliqueness reaches the contact and is lost in the force law.\n")
