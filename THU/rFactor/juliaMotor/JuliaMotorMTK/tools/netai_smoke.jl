# GATE: a networked session must not run an AI field.
#
# Not a preference -- a correctness limit. RaceAI.step_field! is stepped on BOTH peers and handed
# the LOCAL player's position, with `rel` capping AI speed to a fraction of that car's speed, so the
# two fields are driven by different inputs from the first frame and no AI state is on the wire.
# Two players would see different AI positions and a different finishing order.
#
# Three arms, because the interesting failure is the guard firing when it should not:
#   offline + JM_AI=3   -> AI runs        (guard must not fire when there is no network)
#   JM_NET=join + JM_AI=3 -> AI disabled  (the client draws the HOST's field, MP-5)
#   JM_NET=host + JM_AI=3 -> AI runs and the host announces host-authoritative AI (MP-5)
#   JM_NET=join + JM_AI=3 + JM_NET_AI=1 -> AI runs (documented override still works)
const D = normpath(joinpath(@__DIR__, "..", "..", "demo", "native"))
run_arm(env) = begin
    cmd = `env $(env) JM_SMOKE=1 JM_HEADLESS=1 julia --project=$(D) $(joinpath(D, "drive_native_mtk.jl"))`
    out = try read(cmd, String) catch e; sprint(showerror, e) end
    (disabled = occursin("AI field disabled", out), raw = out)
end
fails = Ref(0)
check(n, ok, m) = (ok || (fails[] += 1); println("  ", ok ? "PASS" : "FAIL", "  ", rpad(n, 52), m))
println("Networked-AI guard gate (5 arms; MP-5 host-authoritative field)")
a = run_arm(["JM_AI=3"])
check("offline race keeps its AI field",         !a.disabled, "guard silent")
# MP-5 (2026-09-06): the HOST keeps its field (host-authoritative) and says so; the CLIENT drops
# its own field and draws the host's. The override still steps a local field on the client.
b = run_arm(["JM_AI=3", "JM_NET=join", "JM_NET_PORT=47755", "JM_NET_HOST=127.0.0.1"])
check("networked CLIENT disables its own AI field", b.disabled, "guard fired")
d = run_arm(["JM_AI=3", "JM_NET=host", "JM_NET_PORT=47757"])
check("networked HOST keeps its AI field",         !d.disabled, "guard silent")
check("HOST announces host-authoritative AI",      occursin("host-authoritative AI", d.raw), "broadcast line printed")
c = run_arm(["JM_AI=3", "JM_NET=join", "JM_NET_PORT=47756", "JM_NET_HOST=127.0.0.1", "JM_NET_AI=1"])
check("JM_NET_AI=1 override still runs the AI on the client", !c.disabled, "override honoured")
println(fails[] == 0 ? "NETAI GATE: PASS" : "NETAI GATE: FAIL ($(fails[]))")
exit(fails[] == 0 ? 0 : 1)
