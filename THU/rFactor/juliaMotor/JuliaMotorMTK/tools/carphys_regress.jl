# CARPHYS-1 regression harness: does a REFACTOR of the car model reproduce the reference model's trajectories?
#
# The reference is `DrivenVehicle3D` as committed at git revision JM_REGRESS_REF (default HEAD), loaded into the
# DriveRT3D module beside the working copy's. Both are built with the same chassis and driven by the same inputs --
# no adapter, no terrain sampling, the bare ODEs at the sim's 1/300 s step -- through six manoeuvres for two setups
# (the default spool car and the WW103 LSD + camber + bars car). Prints the largest difference per channel, scaled.
#
#   julia --project=. tools/carphys_regress.jl            # PASS when every channel agrees to JM_REGRESS_TOL (1e-6)
#
# A physics CHANGE fails this on purpose; it is for proving that restructuring changed nothing, before any change.
using Printf
include(joinpath(@__DIR__, "..", "src", "drive_rt3d.jl")); using .DriveRT3D
using ModelingToolkit, OrdinaryDiffEq
const D3 = DriveRT3D
const REF = get(ENV, "JM_REGRESS_REF", "HEAD")
const TOL = parse(Float64, get(ENV, "JM_REGRESS_TOL", "1e-6"))

# the reference vehicle, renamed, evaluated in DriveRT3D's scope (its helpers and constants)
let src = read(Cmd(`git show $REF:./src/components/vehicle_3d.jl`; dir = joinpath(@__DIR__, "..")), String)
    src = replace(src, "function DrivenVehicle3D(" => "function DrivenVehicle3D_ref(")
    f = tempname() * ".jl"; write(f, src); Base.include(D3, f); rm(f)
end

const CH_DEFAULT = D3.Chassis()
const CH_WW103 = D3.Chassis(diff = (41.0, 35.0, 85.0, 4.0), toe = (D3.toe_rad(-6), D3.toe_rad(3; rear = true)),
                            karb = (1758.0, 19940.0), cscale = (1.00, 1.15), bias = D3.bias_torque(54.0),
                            camber = Tuple(deg2rad.((-0.4, 0.0, -0.4, 0.2))))

function build(builder, ch)
    D3.set_chassis!(ch)
    KS = D3.KS[]
    sys = mtkcompile(builder(name = :car, brush = true, final = D3.FINAL[], m = D3.MASS[], front_frac = D3.FRONT_FRAC[],
                     fl_corner = D3._corner(:f, KS[1]), fr_corner = D3._corner(:f, KS[2]),
                     rl_corner = D3._corner(:r, KS[3]), rr_corner = D3._corner(:r, KS[4]); D3._chassis_kw(ch)...))
    sys
end

# a manoeuvre: v0 [m/s], gear, and inputs(t) -> (throttle, brake, steer [rad road], road(t) -> 4 heights)
const MANOEUVRES = [
    ("WOT in 2nd from 36 km/h", 10.0, 2, t -> (1.0, 0.0, 0.0), t -> (0.0, 0.0, 0.0, 0.0)),
    ("braking 0.8 from 216 km/h", 60.0, 5, t -> (0.0, t > 0.5 ? 0.8 : 0.0, 0.0), t -> (0.0, 0.0, 0.0, 0.0)),
    ("step steer 2.9° at 126 km/h", 35.0, 3, t -> (0.3, 0.0, t > 0.3 ? 0.05 : 0.0), t -> (0.0, 0.0, 0.0, 0.0)),
    ("sine steer 1 Hz at 144 km/h", 40.0, 4, t -> (0.4, 0.0, 0.04*sin(2π*t)), t -> (0.0, 0.0, 0.0, 0.0)),
    ("lift-off at the limit, 144 km/h", 40.0, 3, t -> (t < 3.0 ? 0.7 : 0.0, 0.0, 0.085), t -> (0.0, 0.0, 0.0, 0.0)),
    ("5 cm bump, then a 0.3 m drop", 30.0, 3, t -> (0.3, 0.0, 0.01),
        t -> (bump(t - 0.5) + drop(t - 2.0), bump(t - 0.5) + drop(t - 2.0), bump(t - 0.6) + drop(t - 2.1), bump(t - 0.6) + drop(t - 2.1))),
]
bump(τ) = 0 < τ < 0.1 ? 0.05*sin(π*τ/0.1) : 0.0
drop(τ) = τ < 0 ? 0.0 : -0.3*min(τ/0.05, 1.0)

const OUTS = (:u, :v, :r, :z, :th, :ph, :FzFL, :FzFR, :FzRL, :FzRR, :ωe)
const SCALE = (u = 10.0, v = 1.0, r = 0.5, z = 0.02, th = 0.01, ph = 0.01, FzFL = 1000.0, FzFR = 1000.0, FzRL = 1000.0, FzRR = 1000.0, ωe = 100.0)

function drive(sys, ch, m)
    name, v0, gear, inp, road = m
    D3.set_chassis!(ch)
    u0 = [sys.u => v0, sys.ωf => v0/0.30, D3._wheel_u0(sys, v0)..., sys.ωe => v0/D3.RW_R*D3.GEARS[gear]*D3.FINAL[]]
    prob = ODEProblem(sys, u0, (0.0, 1e7))
    integ = init(prob, Rosenbrock23(); save_everystep = false, dense = false, adaptive = false, dt = 1/300)
    sp(x) = ModelingToolkit.setp(sys, x)
    s_thr, s_brk, s_st, s_gr = sp(sys.throttle), sp(sys.brake), sp(sys.δ), sp(sys.gear)
    s_zr = (sp(sys.zrFL), sp(sys.zrFR), sp(sys.zrRL), sp(sys.zrRR)); s_vr = (sp(sys.vrFL), sp(sys.vrFR), sp(sys.vrRL), sp(sys.vrRR))
    get = ModelingToolkit.getsym(sys, [getproperty(sys, o) for o in OUTS])
    s_gr(integ, D3.GEARS[gear])
    rec = Vector{Vector{Float64}}()
    dt = 1/300
    for k in 1:round(Int, 6.0/dt)
        t = (k - 1)*dt
        th, br, st = inp(t); s_thr(integ, th); s_brk(integ, br); s_st(integ, st)
        z0 = road(t); z1 = road(t + 1e-3)
        for i in 1:4; s_zr[i](integ, z0[i]); s_vr[i](integ, (z1[i] - z0[i])/1e-3); end
        step!(integ, dt, true)
        push!(rec, copy(get(integ)))
    end
    reduce(hcat, rec)
end

worst = 0.0
for (chname, ch) in (("default (spool)", CH_DEFAULT), ("WW103 (LSD, camber, bars)", CH_WW103))
    sref = build(D3.DrivenVehicle3D_ref, ch); snew = build(D3.DrivenVehicle3D, ch)
    @printf("%s: reference %d unknowns, component model %d\n", chname, length(unknowns(sref)), length(unknowns(snew)))
    for m in MANOEUVRES
        a = drive(sref, ch, m); b = drive(snew, ch, m)
        errs = [maximum(abs.(a[i, :] .- b[i, :]))/SCALE[o] for (i, o) in enumerate(OUTS)]
        e, ie = findmax(errs); global worst = max(worst, e)
        fin = @sprintf("end: %.1f km/h, β %.1f°", 3.6*hypot(b[1, end], b[2, end]), rad2deg(atan(b[2, end], max(b[1, end], 1.0))))
        @printf("  %-34s max scaled diff %.2e (%s)   %s\n", m[1], e, OUTS[ie], fin)
    end
end
D3.set_chassis!(D3.Chassis())
@printf("\nCARPHYS REGRESSION vs %s: %s (worst %.2e, tolerance %.0e)\n", REF, worst <= TOL ? "PASS" : "FAIL", worst, TOL)
exit(worst <= TOL ? 0 : 1)
