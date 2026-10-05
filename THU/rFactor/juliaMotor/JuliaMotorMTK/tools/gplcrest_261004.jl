# VFRAME-1 check on GPL's OWN crests: drive the 3-D Lotus straight over the .trk road height (the analytic spline the
# physics reads, GPLTrack.trk_height on the centreline) at a crest, flat out, and report time light (VertAccel < 0.5 g),
# the lowest g and the landing peak. Run once per frame: JM_VFRAME=legacy / inertial.
#   julia --project=../demo/native tools/gplcrest_261004.jl nurburg 3700 4400 200
const D = normpath(joinpath(@__DIR__, "..", "..", "demo", "native"))
const GT = normpath(joinpath(@__DIR__, "..", "..", "..", "..", "WP", "drive_c", "Sierra", "GPL", "tracks"))
include(joinpath(D, "gpldat.jl")); using .GPLDat
include(joinpath(D, "gpltrack.jl")); using .GPLTrack
include(joinpath(@__DIR__, "..", "src", "drive_rt3d.jl")); using .DriveRT3D
using Printf
name, s0, s1, kmh = ARGS[1], parse(Float64, ARGS[2]), parse(Float64, ARGS[3]), parse(Float64, ARGS[4])
trk = let dir = joinpath(GT, name), p = joinpath(dir, name*".trk")
    isfile(p) ? p : (q = tempname()*".trk"; write(q, GPLDat.parse_dat(joinpath(dir, name*".dat"))[name*".trk"]); q)
end
ta = GPLTrack.trk_altitude(trk)
groundz(x, z) = GPLTrack.trk_height(ta, mod(Float64(x), ta.total), 0.0)
DriveRT3D.set_transmission!([2.23, 1.72, 1.32, 1.04, 0.846], 4.22; source = "Ring setup")
V = kmh/3.6; g = V > 62 ? 5 : 4
c = DriveRT3D.build_car3d(; x0 = s0, v0 = V, y0 = groundz(s0, 0.0))
c.gear = g; c.s_gr(c.integ, DriveRT3D.gearratio(g)); c.s_we(c.integ, V/DriveRT3D.RW_R*DriveRT3D.GEARS[g]*DriveRT3D.FINAL[])
light = 0.0; vmin = 9.0; peak = 0.0; events = String[]; inair = false; t0 = 0.0; t = 0.0
while c.x < s1 && t < 30
    global t += 1/360
    DriveRT3D.step_car3d!(c, 1.0, 0.0, 0.0, 1/360; clutch = 0.0, manual = true, groundz = groundz)
    a = c.vacc/9.80665
    global vmin = min(vmin, a); global peak = max(peak, a)
    haskey(ENV, "JM_GCDBG") && a > parse(Float64, ENV["JM_GCDBG"]) && @printf("   s %.1f a %.1f g  heave %.3f pitch %.3f  grounded %s  zref %.2f terr %.2f  v %.1f\n", c.x, a, c.heave, c.pitch, c.grounded, c.zref, groundz(c.x, 0.0), 3.6c.v)
    if a < 0.5
        inair || (global t0 = t; global inair = true); global light += 1/360
    elseif inair
        global inair = false; (t - t0) > 0.05 && push!(events, @sprintf("s %.0f %.2fs", c.x, t - t0))
    end
end
@printf("%s %s frame, %.0f km/h, s %.0f-%.0f: light %.2f s total, min %+.2f g, peak %.2f g; light spells > 0.05 s: %s\n",
        name, DriveRT3D.VFRAME_INERTIAL ? "inertial" : "legacy", kmh, s0, s1, light, vmin, peak, join(events, ", "))
