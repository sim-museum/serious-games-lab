# SETUPMODEL-1 gate: the Lotus 49 garage (src/garage.jl + garage_lotus49.toml) against iRacing's own garage.
#   1. an untouched garage IS the session (apply_garage returns the .ibt's numbers exactly)
#   2. iRacing anchors (the PO's 261017 garage frames + .ibt), each from the default session by the knob turned
#   3. the launcher's mirror (demo/native/garage.py) solves the same numbers, and reads the same garage file
using TOML, Printf
include(joinpath(@__DIR__, "..", "src", "ibt.jl")); using .IBT
include(joinpath(@__DIR__, "..", "src", "setup.jl")); using .Setup
include(joinpath(@__DIR__, "..", "src", "garage.jl")); using .Garage

ok = true
chk(c, msg) = (global ok &= c; println(c ? "PASS " : "FAIL ", msg))

# The default session as the launcher carries it (garage_sessions.toml), rebuilt as a setup NamedTuple: the gate runs
# on any checkout, with or without the gold .ibt store.
S = TOML.parsefile(joinpath(@__DIR__, "..", "src", "garage_sessions.toml"))
function knobs_of(d)
    K = Garage.Knobs()
    for (k, v) in d
        T = fieldtype(Garage.Knobs, Symbol(k))
        setfield!(K, Symbol(k), T <: Tuple ? T(Tuple(v)) : T <: AbstractString ? String(v) : T <: AbstractVector ? Float64.(v) : T(v))
    end
    K
end
d4(v) = Dict(:LF => v[1], :RF => v[2], :LR => v[3], :RR => v[4])
function sp_of(s)
    K = knobs_of(s["knobs"]); dv = s["derived"]
    (; corner_weight_N = d4(dv["cw"]), ride_height_mm = d4(dv["rh"]),
       shock_defl_mm = d4([(x, i <= 2 ? 104.6 : 113.0) for (i, x) in enumerate(dv["shock"])]), camber_deg = d4(dv["camber"]),
       cross_weight_pct = dv["cross"], toe_front_mm = dv["toe_front"], spring_rate_Npmm = d4(collect(K.spring)),
       perch_mm = d4(collect(K.perch)), packer_mm = d4(collect(K.packer)), cold_pressure_kPa = d4(collect(K.pressure)),
       bump_clicks = d4(Float64.(collect(K.bump))), rebound_clicks = d4(Float64.(collect(K.rebound))),
       toe_rear_mm = K.toe_rear, arb_front = "$(K.farb_dia)\" $(K.farb_arm)", arb_rear = "$(K.rarb_dia)\" $(K.rarb_arm)",
       fuel_L = K.fuel, brake_bias_pct = K.brake_bias, steering_ratio = K.steering_ratio, final_drive = K.final_drive,
       gear_ratios = K.gears, diff_plates = Float64(K.diff_plates), diff_preload_Nm = K.diff_preload,
       diff_drive_ramp = K.diff_drive, diff_coast_ramp = K.diff_coast), K
end
sp, Ks = sp_of(S["default"])
c4(d) = (d[:LF], d[:RF], d[:LR], d[:RR])

# 1 ── untouched = the session
same = Garage.apply_garage(sp, Ks; Ks)
chk(c4(same.corner_weight_N) == c4(sp.corner_weight_N) && c4(same.ride_height_mm) == c4(sp.ride_height_mm) &&
    same.cross_weight_pct ≈ sp.cross_weight_pct, "an untouched garage is the session to the digit")
D0 = Garage.solve_static(Ks)
chk(D0.ok && maximum(abs.(D0.cw .- c4(sp.corner_weight_N))) < 1.0 && maximum(abs.(D0.rh .- c4(sp.ride_height_mm))) < 0.5,
    "the model alone reproduces the default session (1 N, 0.5 mm): " * Garage.describe_derived(D0))

# 2 ── iRacing anchors: (what was turned, the knobs, iRacing's numbers, tolerances N / mm)
function turn(f)
    K = deepcopy(Ks); f(K); Garage.apply_garage(sp, K; Ks)
end
const IN64 = 25.4/64
anchors = [
    ("LF perch +5/64\" (snip 34)", K -> (K.perch = (K.perch[1] + 5IN64, K.perch[2], K.perch[3], K.perch[4])),
        (1326, 1350, 1640, 1619), (NaN, NaN, 105.0, 105.2), 3, 0.6),
    ("LR perch +5/64\" (snip 47)", K -> (K.perch = (K.perch[1], K.perch[2], K.perch[3] + 5IN64, K.perch[4])),
        (1349, 1327, 1617, 1643), (83.0, 83.2, 103.5, 103.7), 3, 0.6),
    ("fuel 4.5 L (snip 6)", K -> (K.fuel = 4.5), (1244, 1244, 1582, 1582), (88.1, 88.1, 107.6, 107.6), 3, 0.6),
    ("fuel 179.5 L (snip 8)", K -> (K.fuel = 179.5), (1669, 1669, 1801, 1801), (65.5, 65.5, 96.1, 96.1), 5, 1.0),
    ("front springs 35 N/mm (.ibt 12-18-53)", K -> (K.spring = (35.0, 35.0, K.spring[3], K.spring[4])),
        (1338, 1338, 1630, 1630), (91.0, 91.0, 105.1, 105.1), 2, 0.6),
    ("front springs 18 N/mm, perch 110.3 (.ibt 12-13-04)",
        K -> (K.spring = (18.0, 18.0, K.spring[3], K.spring[4]); K.perch = (110.3, 110.3, K.perch[3], K.perch[4])),
        (1338, 1338, 1630, 1630), (112.6, 112.6, 105.1, 105.1), 2, 0.6),
    ("LF packer 19.05 mm (snip 24): nothing moves", K -> (K.packer = (19.05, 0.0, 0.0, 0.0)),
        (1338, 1338, 1630, 1630), (83.1, 83.1, 105.1, 105.1), 1, 0.1),
    # the documented gap: a perch so high the spring goes loose and the corner sits on its bump rubber
    ("LF perch 305.6 mm, spring loose (snip 14)", K -> (K.perch = (770IN64, K.perch[2], K.perch[3], K.perch[4])),
        (1012, 1663, 1920, 1341), (47.4, 53.8, 101.6, 108.3), 15, 5.0),
]
for (name, f, cw, rh, tolN, tolmm) in anchors
    r = turn(f)
    e_cw = maximum(abs.(c4(r.corner_weight_N) .- cw))
    e_rh = maximum(filter(isfinite, abs.(c4(r.ride_height_mm) .- rh)))
    chk(e_cw <= tolN && e_rh <= tolmm, @sprintf("%-46s cw %s (iRacing %s, max %.1f N)  rh max %.2f mm", name,
        join(round.(Int, c4(r.corner_weight_N)), "/"), join(cw, "/"), e_cw, e_rh))
end
r = turn(K -> (K.packer = (19.05, 0.0, 0.0, 0.0)))
chk(isapprox(r.shock_defl_mm[:LF][2], 104.6 - 19.05; atol = 0.01), "the packer takes its length off the shock's travel (85.55 of 104.6)")
r = turn(K -> (K.final_drive = 3.78; K.gears = [2.23, 1.40, 1.21, 1.04, 0.958]))
kmh = Garage.gear_speeds_kmh(knobs_of(S["ww103"]["knobs"]))
chk(maximum(abs.(kmh .- [140.7, 224.0, 259.2, 301.6, 327.4])) < 0.15, "WW103 gear speeds as iRacing shows them: " * join(round.(kmh, digits = 1), "/"))

# 3 ── the launcher's mirror: same solve, same garage file
py = joinpath(@__DIR__, "..", "..", "demo", "native")
tmp = mktempdir()
using Random; Random.seed!(17)
cases = Garage.Knobs[]
for n in 1:12
    K = deepcopy(Ks)
    K.perch = (K.perch[1] + 8(rand() - 0.5), K.perch[2] + 8(rand() - 0.5), K.perch[3] + 8(rand() - 0.5), K.perch[4] + 8(rand() - 0.5))
    K.spring = (rand(18:35), rand(18:35), rand(30:70), rand(30:70)) .* 1.0
    K.fuel = 4.5 + 175rand(); K.farb_arm = rand(["soft", "2", "4", "firm"]); K.rarb_dia = rand([0.0, 0.625, 0.6875])
    K.pressure = (152.0, 152 + 30rand(), 152.0, 152 + 30rand())
    push!(cases, K)
    Garage.write_garage_file(joinpath(tmp, "k$n.toml"), K)
end
script = """
import sys, json; sys.path.insert(0, sys.argv[1]); import garage as g
out = []
for n in range(1, $(length(cases)) + 1):
    base, K = g.read_garage_file(sys.argv[2] + f"/k{n}.toml")
    d = g.solve_static(K)
    print(" ".join(repr(x) for x in d['cw'] + d['rh'] + d['shock'] + d['camber'] + [d['toe_front']]))
"""
res = try
    read(`python3 -I -c $script $py $tmp`, String)
catch e
    ""
end
if isempty(res)
    chk(false, "the launcher's garage.py runs")
else
    vals = [parse.(Float64, split(line)) for line in split(strip(res), '\n')]
    maxd = 0.0
    for (n, K) in enumerate(cases)
        D = Garage.solve_static(K)
        jl = vcat(collect(D.cw), collect(D.rh), collect(D.shock), collect(D.camber), D.toe_front)
        global maxd = max(maxd, maximum(abs.(jl .- vals[n])))
    end
    chk(maxd < 1e-6, @sprintf("garage.py (the launcher) and garage.jl (the sim) solve the same numbers: max diff %.1e over %d garages", maxd, length(cases)))
end

# 4 ── the exported .ibt's CarSetup block (S3): an untouched session reproduces its own YAML byte for byte; a garaged one
# reads back as the garage's car. Needs a session .ibt (the gold store or the repo's data/iracing); skipped without one.
gold = filter(isfile, [expanduser("~/gold standard/julia racer/261002/lotus49_nurburgring nordschleifetourist 2026-10-02 22-26-21.ibt"),
                       expanduser("~/gold standard/julia racer/261005/lotus49_nurburgring nordschleife 2026-10-06 00-46-10.ibt")])
if isempty(gold)
    println("SKIP the CarSetup block (no session .ibt on this machine)")
else
    for fn in gold
        yf = IBT.session_yaml(IBT.ibt_open(fn))
        chk(Garage.carsetup_yaml(yf, Setup.setup_params(yf)) == yf, "CarSetup rewrite of an untouched session is the session's YAML ($(basename(fn)[9:end-4]))")
    end
    y = IBT.session_yaml(IBT.ibt_open(gold[1])); spg = Setup.setup_params(y); Kg = Garage.calibrate_session(spg); K2 = deepcopy(Kg)
    K2.perch = (K2.perch[1] + 5IN64, K2.perch[2:4]...); K2.fuel = 100.0; K2.final_drive = 4.11; K2.bump = (12, 12, 0, 0)
    pg = Garage.apply_garage(spg, K2; Ks = Kg); y2 = Garage.carsetup_yaml(y, pg); sp2 = Setup.setup_params(y2)
    chk(sp2.perch_mm[:LF] == 167.1 && sp2.fuel_L == 100.0 && sp2.final_drive == 4.11 && sp2.bump_clicks[:LF] == 12 &&
        sp2.corner_weight_N[:LF] == round(pg.corner_weight_N[:LF]) && length(y2) <= length(y) + 8,
        "a garaged CarSetup reads back as the garage's car (perch $(sp2.perch_mm[:LF]), fuel $(sp2.fuel_L), cw LF $(sp2.corner_weight_N[:LF]))")
end

println("GARAGE GATE: ", ok ? "PASS" : "FAIL")
exit(ok ? 0 : 1)
