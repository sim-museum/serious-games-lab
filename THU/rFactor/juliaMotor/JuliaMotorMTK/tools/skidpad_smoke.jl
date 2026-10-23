# skidpad_smoke.jl -- SKIDPADCRASH-1 gate (2026-10-23). The skidpad builds a synthetic flat pad and skips the GPL track
# and object build, so every name those define (TERRAIN, TMPOBJ, gplvis_seg, ...) is missing there -- and no gate drove
# the skidpad, so it could not start at all (`UndefVarError: gplvis_seg` on the first drawn frame) and nobody saw it
# (the same happened in SKIDPAD-GOLD-1 S2 with RINGSPRITES, and E102-S12 with TERRAIN in camera()).
# One headless skidpad run (JM_SKIDPAD_DRIVE: constant steer + throttle) that takes every path a driver can reach there:
#   a SHIFT+R (no centreline on the pad: the plain respawn), a forced wreck (the wreck's rigid body on the pad's ground),
#   and an R (the session restart). It must exit cleanly, the car must drive, and each respawn must put it back at rest.
# SKIDPAD_SMOKE_SRC=<file> runs another copy of the sim (the known positive: the pre-fix HEAD fails this gate).
const D = normpath(joinpath(@__DIR__, "..", "..", "demo", "native"))
const SRC = get(ENV, "SKIDPAD_SMOKE_SRC", joinpath(D, "drive_native_mtk.jl"))
fails = Ref(0)
chk(name, ok, detail = "") = (println("  ", ok ? "PASS" : "FAIL", "  ", rpad(name, 60), detail); ok || (fails[] += 1); ok)
println("SKIDPADCRASH-1 gate: the skidpad drives, respawns, wrecks and restarts")
log = tempname()
env = merge(Dict(ENV), Dict("TRACK" => "skidpad", "JM_SMOKE" => "1", "JM_NOSOUND" => "1", "JM_NOIBT" => "1",
                            "JM_FIXED_DT" => "0.016666666666666666", "JM_SKIDPAD_DRIVE" => "0.3,0.6", "JM_AUTODRIVE_DIAG" => "30",
                            "JM_RECOVER_AT" => "2", "JM_WRECK_AT" => "4", "JM_RESTART_AT" => "7", "JM_SMOKE_FRAMES" => "600",
                            "JM_CRASHBODY_DIAG" => "1"))
p = run(pipeline(ignorestatus(setenv(`julia -t 2 --project=$D $SRC`, env; dir = D)); stdout = log, stderr = log))
L = readlines(log)
err = filter(l -> occursin("ERROR", l) || occursin("UndefVarError", l), L)
foreach(l -> println("    ", l), first(err, 3))
chk("the run exits cleanly", p.exitcode == 0 && isempty(err) && any(==("bye"), strip.(L)), "exit $(p.exitcode)")
# [skid] lines every 0.5 s: (t, v km/h)
sk = Tuple{Float64,Float64}[]
for l in L
    m = match(r"\[skid\].*t=([0-9.]+) v=([0-9.]+) km/h", l); m === nothing || push!(sk, (parse(Float64, m[1]), parse(Float64, m[2])))
end
vat(t) = (k = findfirst(x -> abs(x[1] - t) < 0.01, sk); k === nothing ? NaN : sk[k][2])
chk("the car drives (v at t=1.5 > 20 km/h)", vat(1.5) > 20.0, "v $(vat(1.5)) km/h")
chk("SHIFT+R fired at t=2", any(l -> occursin("[test] recover (SHIFT+R) at t=2.0", l), L))
chk("SHIFT+R put the car back at rest (v at t=2.5 < v at t=2.0)", vat(2.5) < vat(2.0) && vat(2.5) < 15.0, "v $(vat(2.0)) -> $(vat(2.5)) km/h")
chk("the forced wreck became the rigid body", any(l -> occursin("[crashbody] the wreck is a free rigid body", l), L))
# the body 4x a second: its CG height over the pad -- the pad has no TERRAIN mesh, so the body asks for its flat 0 m
cg = Float64[parse(Float64, m[1]) for m in (match(r"\[crashbody\] t [0-9.]+ CG (-?[0-9.]+) m up", l) for l in L) if m !== nothing]
chk("the wreck rests on the pad (CG 0.1..0.8 m up, >= 8 samples)", length(cg) >= 8 && all(h -> 0.1 <= h <= 0.8, cg),
    "$(length(cg)) samples, CG $(isempty(cg) ? "-" : string(round(minimum(cg), digits = 2), "..", round(maximum(cg), digits = 2))) m")
chk("the wreck coasts down (v at 6.5 < v at 4.5)", vat(6.5) < vat(4.5), "v $(vat(4.5)) -> $(vat(6.5)) km/h")
chk("R restarted the session", any(l -> occursin("[restart] session reset on skidpad", l), L))
chk("the car drives again after R (v at t=9.5 > 20 km/h)", vat(9.5) > 20.0, "v $(vat(9.5)) km/h")
rm(log; force = true)
println(fails[] == 0 ? "\n  SKIDPAD GATE: PASS" : "\n  SKIDPAD GATE: FAIL ($(fails[]))")
exit(fails[] == 0 ? 0 : 1)
