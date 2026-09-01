# netplay_smoke.jl — E85 sprint 1: two PROCESSES exchange car poses over UDP.
#
# Proves the transport, not the sim. The sim takes ~2 min to start and needs the display, so running
# it twice would confound netcode faults with startup and the gl-lock queue. This drives the SAME
# NetPlay module the sim will use, in two real processes, so if this passes and the game still shows
# no remote car, the fault is provably in the sim wiring rather than the wire.
#
# THREE ARMS, all required:
#   solo  no peer      -> must receive NOTHING (the negative control)
#   host  binds, waits -> must receive the client's poses AND send its own
#   join  sends first  -> must receive the host's poses
#
# The solo arm is what makes the others mean something: it proves the probe can report ZERO, so a
# passing host/join arm is a packet that really crossed rather than an assertion that always fires.
#
# ⚠️ The `join` arm is not symmetric with `host`, and that asymmetry is the point. A peer that SENDS
# before it receives used to go permanently deaf: in Julia/libuv a `send` on a socket with a pending
# `recvfrom` CANCELS that receive. The host receives first and was unaffected; only the client hit
# it. If this gate is ever reduced to one arm, keep this one.
using Printf
const HERE  = @__DIR__
const PROBE = normpath(joinpath(HERE, "..", "..", "demo", "native", "netplay_probe.jl"))
const PROJ  = normpath(joinpath(HERE, "..", "..", "demo", "native"))

fails = Ref(0)
chk(name, ok, detail) = (@printf("  %-46s %s   %s\n", name, ok ? "PASS" : "FAIL", detail); ok || (fails[] += 1))

println("\n  E85 sprint 1 — car poses across two processes (UDP)\n")

# 1. negative control FIRST
solo = success(pipeline(`julia --project=$PROJ $PROBE solo`, stdout=devnull, stderr=devnull))
chk("control: no peer -> nothing received", solo, "solo arm exits 0 only on rx=0")

# 2. host + client, two real processes
hostout = tempname(); joinout = tempname()
hp = run(pipeline(`julia --project=$PROJ $PROBE host`, stdout=hostout, stderr=hostout); wait=false)
sleep(10)                                    # Julia startup; the host tolerates a late client
jrc = success(pipeline(`julia --project=$PROJ $PROBE join`, stdout=joinout, stderr=joinout))
sleep(6)
try; kill(hp); catch; end

hlog = isfile(hostout) ? read(hostout, String) : ""
jlog = isfile(joinout) ? read(joinout, String) : ""
hok = occursin("PASS host", hlog)
chk("host received the client's poses", hok, strip(something(match(r"host: [^\n]*", hlog) === nothing ? "" : match(r"host: [^\n]*", hlog).match, "")))
chk("client received the host's poses", jrc && occursin("PASS join", jlog),
    strip(something(match(r"join: [^\n]*", jlog) === nothing ? "" : match(r"join: [^\n]*", jlog).match, "")))

println(fails[] == 0 ? "\n  NETPLAY GATE: PASS ✓ (poses cross both ways, exact)" :
                       "\n  NETPLAY GATE: FAIL ($(fails[]))")
exit(fails[] == 0 ? 0 : 1)
