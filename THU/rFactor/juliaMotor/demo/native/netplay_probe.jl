# netplay_probe.jl — E85 sprint 1 gate: two processes, one car each, poses on the wire.
#
# Proves the TRANSPORT without the sim, deliberately. Julia's sim takes ~2 min to start and needs
# the display, so driving it twice would confound netcode faults with startup and gl-lock. This
# drives NetPlay directly — the same module the sim will use — so if this passes and the game still
# cannot see a remote car, the fault is provably in the sim wiring, not the wire.
#
#   netplay_probe.jl host    -- bind, wait for the client's poses, check what arrived
#   netplay_probe.jl join    -- send a known pose sequence to the host, check the host's replies
#   netplay_probe.jl solo    -- bind with NO peer: must receive NOTHING (the negative control)
using Printf
include(joinpath(@__DIR__, "netplay.jl")); using .NetPlay

const PORT_H = parse(Int, get(ENV, "JM_NET_PORT",  "47700"))
const PORT_C = parse(Int, get(ENV, "JM_NET_PORT2", "47701"))
const N      = parse(Int, get(ENV, "JM_NET_PKTS",  "20"))

# A known, non-trivial trajectory: constant values would pass even if the payload were zeroed.
pose(i) = (100.0 + 3.5i, 0.25 + 0.01i, -50.0 - 2.0i, 0.1i, 40.0 + i, -0.02i)

# Each arm is a FUNCTION, not top-level code. Julia's soft-scope rule makes `i += 1` inside a
# top-level `while` a NEW LOCAL, so the loop threw UndefVarError after warning about it twice.
# A function body has ordinary scope and the whole class of problem disappears.

function run_host()
    n = netopen(port = PORT_H)
    println("hosting on ", PORT_H); flush(stdout)
    # ONE continuous loop: poll, then send to whoever is known. The first cut waited for the
    # client's first packet and only THEN echoed -- but Julia's startup meant those packets arrived
    # after the wait expired, so the echo loop ran with an EMPTY peer list, sent nothing, and the 20
    # packets were collected afterwards in the drain. Host reported rx=20 and client rx=0, which
    # reads like a one-way transport and was really a one-way TEST.
    sent = 0; i = 0; t0 = time()
    while time() - t0 < 25.0
        poll!(n)
        i += 1
        if !isempty(n.peers) && sent < N
            p = pose(i); send_pose!(n, 1, i, p...); sent += 1
        end
        if haskey(n.remote, UInt8(2)) && sent >= N && (time() - t0 > 3.0)
            break
        end
        sleep(0.02)
    end
    ok = false
    if haskey(n.remote, UInt8(2))
        r = n.remote[UInt8(2)]; e = pose(r.tick)
        err = maximum(abs.((r.x - e[1], r.y - e[2], r.z - e[3], r.yaw - e[4])))
        @printf("host: rx=%d dropped=%d sent=%d  car2 tick=%d pos=(%.2f,%.2f,%.2f) maxerr=%.4f\n",
                n.rx, n.dropped, sent, r.tick, r.x, r.y, r.z, err)
        println("host: peers = ", n.peers)
        ok = err < 1e-3 && sent > 0
    else
        @printf("host: rx=%d dropped=%d sent=%d peers=%d  NO car 2 received\n",
                n.rx, n.dropped, sent, length(n.peers))
    end
    netclose(n)
    println(ok ? "PASS host" : "FAIL host")
    ok
end

function run_join()
    n = netopen(port = PORT_C, peer = ("127.0.0.1", PORT_H))
    sent = 0; i = 0; t0 = time()
    while time() - t0 < 20.0
        poll!(n)
        i += 1
        if sent < N
            p = pose(i); send_pose!(n, 2, i, p...); sent += 1
        end
        if haskey(n.remote, UInt8(1)) && sent >= N
            break
        end
        sleep(0.02)
    end
    t1 = time(); while time() - t1 < 1.0; poll!(n); sleep(0.02); end
    ok = false
    if haskey(n.remote, UInt8(1))
        r = n.remote[UInt8(1)]; e = pose(r.tick)
        err = maximum(abs.((r.x - e[1], r.y - e[2], r.z - e[3], r.yaw - e[4])))
        @printf("join: rx=%d dropped=%d sent=%d  car1 tick=%d pos=(%.2f,%.2f,%.2f) maxerr=%.4f\n",
                n.rx, n.dropped, sent, r.tick, r.x, r.y, r.z, err)
        ok = err < 1e-3
    else
        @printf("join: rx=%d dropped=%d sent=%d peers=%d readererr=%s  NO car 1 received\n",
                n.rx, n.dropped, sent, length(n.peers), isempty(n.readererr) ? "none" : n.readererr)
    end
    netclose(n)
    println(ok ? "PASS join" : "FAIL join")
    ok
end

function run_solo()
    n = netopen(port = PORT_H)
    t0 = time(); while time() - t0 < 3.0; poll!(n); sleep(0.05); end
    @printf("solo: rx=%d dropped=%d remote=%d\n", n.rx, n.dropped, length(n.remote))
    ok = n.rx == 0 && isempty(n.remote)
    netclose(n)
    ok
end

mode = length(ARGS) >= 1 ? ARGS[1] : "solo"
if     mode == "solo"; exit(run_solo() ? 0 : 1)
elseif mode == "host"; exit(run_host() ? 0 : 1)
elseif mode == "join"; exit(run_join() ? 0 : 1)
else   println("usage: netplay_probe.jl host|join|solo"); exit(2)
end
