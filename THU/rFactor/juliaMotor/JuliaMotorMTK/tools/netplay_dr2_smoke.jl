# GATE: E85-S4 -- dead reckoning across TWO REAL PROCESSES.
#
# S2/S3 measured `predict` against a closed-form arc inside one process, which establishes the model
# but cannot see what the WIRING does: real latency, jitter, a peer learned late, a clock read at
# the wrong moment. This gate runs an actual host and an actual client over UDP and measures the
# error the host would DRAW.
#
# Predicted before the first run, from S2/S3: at 10 Hz the newest packet is 0-100 ms old (mean 50),
# and the residual is the curvature term -- mean ~0.025 m, worst ~0.075 m. Loopback latency is
# sub-millisecond, so anything materially larger is a wiring fault, not a model limit.
# First measurement: age mean 0.041 s / max 0.086 s, ERR mean 0.0269 m / max 0.0629 m.
#
# The thresholds below are deliberately loose (0.20 m mean, 1.0 m max). This arm exists to catch a
# WIRING fault -- which shows up as metres, or as no samples at all -- not to re-measure the model
# to four decimals; the tight numbers are asserted in netplay_dr_smoke against closed form, where
# no scheduler can perturb them.
const D = normpath(joinpath(@__DIR__, "..", "..", "demo", "native"))
const PROBE = joinpath(D, "netplay_dr_probe.jl")

fails = Ref(0)
chk(name, ok, detail="") = (println("  ", rpad(name, 52), ok ? "PASS" : "FAIL", "   ", detail);
                            ok || (fails[] += 1); ok)

hostout = tempname(); clientout = tempname()
hp = run(pipeline(`julia --project=$D $PROBE host`; stdout=hostout, stderr=hostout); wait=false)
sleep(6)                                    # Julia startup: the host must be listening first
crc = try; run(pipeline(`julia --project=$D $PROBE client`; stdout=clientout, stderr=clientout)); true
      catch; false; end
sleep(6)
try; wait(hp); catch; end

htxt = read(hostout, String); ctxt = read(clientout, String)
print(htxt); print(ctxt)

chk("the client actually sent at ~10 Hz", occursin(r"sent=\d+ over .* \(1[01]\.\d Hz\)", ctxt), "10 Hz")
chk("the host SAW the remote car", !occursin("NO remote poses seen", htxt), "samples > 0")

m = match(r"ERR mean=([0-9.]+) m max=([0-9.]+) m", htxt)
if m === nothing
    chk("the host reported an error figure", false, "no ERR line -- the run did not complete")
else
    emean = parse(Float64, m[1]); emax = parse(Float64, m[2])
    chk("mean error is within the S2/S3 envelope", emean < 0.20, "$(emean) m (model says ~0.025)")
    chk("worst error is not a wiring fault", emax < 1.0, "$(emax) m")
    # A zero here would mean the comparison is not actually comparing anything.
    chk("the error is NON-ZERO (the arm is live)", emean > 1e-6, "a perfect 0 would mean no samples")
end
a = match(r"age mean=([0-9.]+)s max=([0-9.]+)s", htxt)
if a !== nothing
    amax = parse(Float64, a[2])
    chk("packet age stays near one interval (10 Hz)", amax < 0.35, "max $(amax) s")
end
chk("the host process exited cleanly", success(hp), "exit $(hp.exitcode)")

println(fails[] == 0 ? "\n  TWO-PROCESS DEAD RECKONING GATE: PASS ✓" :
                       "\n  TWO-PROCESS DEAD RECKONING GATE: FAIL ($(fails[]))")
exit(fails[] == 0 ? 0 : 1)
