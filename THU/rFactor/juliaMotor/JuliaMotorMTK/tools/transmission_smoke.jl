# GATE: E100 -- the gearbox must come from the ibt session, never from source constants.
#
# PO 2026-08-27: "the car physics should be determined entirely by the iracing ibt data, there
# should be no modifiable parameters." This asserts that for the transmission specifically,
# because it was measurably violated: GEARS/FINAL were constants holding the SKIDPAD setup
# while every circuit ran the Nordschleife session.
#
# Headless -- reads the ibt store and the physics module, no window and no car.
const S = normpath(joinpath(@__DIR__, "..", "src"))
include(joinpath(S, "ibt.jl"));       using .IBT
include(joinpath(S, "setup.jl"));     using .Setup
include(joinpath(S, "drive_rt3d.jl")); using .DriveRT3D

const STORE = let gold = "/home/admin/gold standard/julia racer",
                  repo = normpath(joinpath(@__DIR__, "..", "..", "data", "iracing"))
    isdir(gold) ? gold : repo
end
fails = Ref(0)
function check(name, cond, msg)
    cond || (fails[] += 1)
    println("  ", cond ? "PASS" : "FAIL", "  ", rpad(name, 46), msg)
end

println("E100 transmission-from-ibt gate   (store: ", STORE, ")")

# 1. The defaults must NOT be trusted: prove the module starts on a fallback that SAYS so.
check("fresh module reports a fallback source", occursin("fallback", DriveRT3D.transmission_source()),
      DriveRT3D.transmission_source())

# 2. Every capture parses, and the ratios really do differ between sessions -- if they did not,
#    hardcoding would be harmless and this gate would be pointless. Assert the premise.
files = sort(filter(f -> endswith(lowercase(f), ".ibt"), readdir(STORE; join = true)))
check("ibt captures found", !isempty(files), string(length(files), " file(s)"))
seen = Dict{String,Vector{Float64}}()
for f in files
    p = Setup.setup_params(IBT.session_yaml(IBT.ibt_open(f)))
    seen[basename(f)] = Float64.(p.gear_ratios)
end
distinct = unique(values(seen))
check("gear ratios VARY between sessions", length(distinct) > 1,
      string(length(distinct), " distinct setups -- hardcoding any one is wrong for the others"))

# 3. Installing a session's gearbox must actually take.
if !isempty(files)
    f = first(files)
    p = Setup.setup_params(IBT.session_yaml(IBT.ibt_open(f)))
    DriveRT3D.set_transmission!(p.gear_ratios, p.final_drive; source = basename(f))
    check("live GEARS equal the session's ratios", DriveRT3D.GEARS == Float64.(p.gear_ratios),
          string(DriveRT3D.GEARS))
    check("live FINAL equals the session's final",  DriveRT3D.FINAL[] == float(p.final_drive),
          string(DriveRT3D.FINAL[]))
    check("source names the capture, not a fallback",
          DriveRT3D.transmission_source() == basename(f), DriveRT3D.transmission_source())
end

# 3b. Mass comes from the same session's corner weights, and it VARIES between sessions too.
masses = Dict{String,Tuple{Float64,Float64}}()
for f in files
    p2 = Setup.setup_params(IBT.session_yaml(IBT.ibt_open(f)))
    masses[basename(f)] = DriveRT3D.mass_from_corner_weights(p2.corner_weight_N)
end
check("corner-weight mass VARIES between sessions", length(unique(values(masses))) > 1,
      string(length(unique(values(masses))), " distinct (mass, front_frac) pairs"))
if !isempty(files)
    f = first(files)
    p2 = Setup.setup_params(IBT.session_yaml(IBT.ibt_open(f)))
    (mm, ff) = DriveRT3D.mass_from_corner_weights(p2.corner_weight_N)
    DriveRT3D.set_mass!(mm, ff; source = basename(f))
    check("live MASS equals the session's",  DriveRT3D.MASS[] == mm, string(round(mm, digits=1), " kg"))
    check("live FRONT_FRAC equals session's", DriveRT3D.FRONT_FRAC[] == ff, string(round(ff, digits=4)))
end

# 3b. E100 S4: SPRING RATES are session data too, and per CORNER. Real setups are asymmetric --
# the skidpad runs LF 26 / RF 28 / LR 39 / RR 53 N/mm against the Nordschleife's 30/30/48/48 -- and
# DrivenVehicle3D used to share ONE spec per axle, so an asymmetric setup could not be represented
# at all and the rates stayed frozen wherever they were copied from.
let springs = Dict{String,NTuple{4,Float64}}()
    for f in files
        p3 = Setup.setup_params(IBT.session_yaml(IBT.ibt_open(f)))
        sp = p3.spring_rate_Npmm
        all(k -> haskey(sp, k) && isfinite(sp[k]), (:LF,:RF,:LR,:RR)) || continue
        springs[basename(f)] = Tuple(DriveRT3D.wheel_rate(sp[k]) for k in (:LF,:RF,:LR,:RR))
    end
    check("ibt carries a SpringRate for all four corners", !isempty(springs),
          string(length(springs), " session(s)"))
    check("spring rates VARY between sessions", length(unique(values(springs))) > 1,
          string(length(unique(values(springs))), " distinct rate sets"))
    # The point of the change: at least one session must be genuinely asymmetric, or per-corner
    # plumbing would be untested by construction and the axle-shared model would still pass.
    check("at least one session is ASYMMETRIC left/right",
          any(v -> v[1] != v[2] || v[3] != v[4], values(springs)),
          string(count(v -> v[1] != v[2] || v[3] != v[4], collect(values(springs))), " asymmetric"))
    if !isempty(springs)
        (nm, v) = first(sort(collect(springs); by = first))
        DriveRT3D.set_suspension!(v...; source = nm)
        check("live KS equals the session's four rates", DriveRT3D.KS[] == v,
              join((round(Int, k) for k in DriveRT3D.KS[]), "/"))
    end
    # The motion ratio is real physics, not a fudge: the shipped constants ARE the ibt values
    # through wheel_rate(). E100-S3 nearly "fixed" them to the raw ibt numbers, which would have
    # stiffened the car 64% while looking like the removal of a hardcoded parameter.
    check("wheel_rate reproduces the shipped front constant",
          round(DriveRT3D.wheel_rate(30.0)) == 18_249, string(round(DriveRT3D.wheel_rate(30.0))))
    check("wheel_rate reproduces the shipped rear constant",
          round(DriveRT3D.wheel_rate(48.0)) == 29_198, string(round(DriveRT3D.wheel_rate(48.0))))
end

# 4. Rubbish must be refused rather than silently installed.
for (name, gears, final) in (("wrong count", [1.0, 2.0], 4.11),
                             ("non-positive ratio", [2.23, 1.72, 1.32, 1.04, -0.5], 4.11),
                             ("non-positive final", [2.23, 1.72, 1.32, 1.04, 0.846], 0.0))
    threw = false
    try; DriveRT3D.set_transmission!(gears, final); catch; threw = true; end
    check("rejects $name", threw, threw ? "threw" : "ACCEPTED IT")
end
for (name, m, ff) in (("non-positive mass", 0.0, 0.45), ("front_frac >= 1", 617.0, 1.0),
                      ("front_frac <= 0", 617.0, 0.0))
    threw = false
    try; DriveRT3D.set_mass!(m, ff); catch; threw = true; end
    check("rejects $name", threw, threw ? "threw" : "ACCEPTED IT")
end
for (name, r) in (("non-positive spring rate", (18_250.0, 0.0, 29_200.0, 29_200.0)),
                  ("negative spring rate", (18_250.0, 18_250.0, -1.0, 29_200.0)))
    threw = false
    try; DriveRT3D.set_suspension!(r...); catch; threw = true; end
    check("rejects $name", threw, threw ? "threw" : "ACCEPTED IT")
end

println(fails[] == 0 ? "E100 GATE: PASS" : "E100 GATE: FAIL ($(fails[]) check(s))")
exit(fails[] == 0 ? 0 : 1)
