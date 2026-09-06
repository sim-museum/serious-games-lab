# GATE: a networked session must not run an AI field.
#
# Not a preference -- a correctness limit. RaceAI.step_field! is stepped on BOTH peers and handed
# the LOCAL player's position, with `rel` capping AI speed to a fraction of that car's speed, so the
# two fields are driven by different inputs from the first frame and no AI state is on the wire.
# Two players would see different AI positions and a different finishing order.
#
# Three arms, because the interesting failure is the guard firing when it should not:
#   offline + JM_AI=3   -> AI runs        (guard must not fire when there is no network)
#   JM_NET=host + JM_AI=3 -> AI disabled  (the defect this gate exists for)
#   JM_NET=host + JM_AI=3 + JM_NET_AI=1 -> AI runs (documented override still works)
const D = normpath(joinpath(@__DIR__, "..", "..", "demo", "native"))
run_arm(env) = begin
    cmd = `env $(env) JM_SMOKE=1 JM_HEADLESS=1 julia --project=$(D) $(joinpath(D, "drive_native_mtk.jl"))`
    out = try read(cmd, String) catch e; sprint(showerror, e) end
    (disabled = occursin("AI field disabled", out), raw = out)
end
fails = Ref(0)
check(n, ok, m) = (ok || (fails[] += 1); println("  ", ok ? "PASS" : "FAIL", "  ", rpad(n, 52), m))
println("Networked-AI guard gate (3 arms)")
a = run_arm(["JM_AI=3"])
check("offline race keeps its AI field",        !a.disabled, "guard silent")
b = run_arm(["JM_AI=3", "JM_NET=host", "JM_NET_PORT=47755"])
check("networked race disables the AI field",    b.disabled,  "guard fired")
c = run_arm(["JM_AI=3", "JM_NET=host", "JM_NET_PORT=47756", "JM_NET_AI=1"])
check("JM_NET_AI=1 override still runs the AI",  !c.disabled, "override honoured")
println(fails[] == 0 ? "NETAI GATE: PASS" : "NETAI GATE: FAIL ($(fails[]))")
exit(fails[] == 0 ? 0 : 1)
