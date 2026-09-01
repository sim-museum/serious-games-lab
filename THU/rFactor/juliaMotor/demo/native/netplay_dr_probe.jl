# E85-S4: dead reckoning measured across TWO REAL PROCESSES, not against analysis.
#
# S2 and S3 measured `predict` against a closed-form arc inside one process. That is the right way
# to establish the model, and it cannot see anything the WIRING does wrong: real latency, real
# jitter, a peer learned late, a clock read at the wrong moment.
#
# Here the CLIENT drives the same analytic arc in real time and sends at 10 Hz; the HOST runs at
# ~60 Hz, dead-reckons the newest pose with `remote_poses_at`, and compares it against where the
# client actually was at that instant. The client stamps each packet with its OWN elapsed
# milliseconds, so the comparison needs no shared clock -- only the packet's age, which the host
# already tracks. Anything much beyond the S2/S3 envelope is the wiring, not the model.
using Printf
include(joinpath(@__DIR__, "netplay.jl"));  using .NetPlay

const PORT_H = 47730
const V, ALAT = 60.0, 15.0
const W = ALAT / V                      # rad/s; radius V/W = 240 m
const RATE = 10.0                       # packets/s
const RUN_S = 12.0

truth(t) = ((V/W)*sin(W*t), (V/W)*(1 - cos(W*t)))
yaw_at(t) = W*t

function run_client()
    n = netopen(port = PORT_H + 1, peer = ("127.0.0.1", PORT_H))
    t0 = time(); sent = 0; nextsend = 0.0
    while time() - t0 < RUN_S
        poll!(n)
        el = time() - t0
        if el >= nextsend
            x, z = truth(el)
            send_pose!(n, 2, round(Int, el*1000), x, 3.5, z, yaw_at(el), V, 0.0)
            sent += 1; nextsend += 1/RATE
        end
        sleep(0.002)
    end
    netclose(n)
    @printf("client: sent=%d over %.1fs (%.1f Hz)\n", sent, RUN_S, sent/RUN_S)
    sent > Int(RATE*RUN_S*0.7)
end

function run_host()
    n = netopen(port = PORT_H)
    println("host up on ", PORT_H); flush(stdout)
    errs = Float64[]; ages = Float64[]
    t0 = time()
    while time() - t0 < RUN_S + 3.0
        poll!(n)
        now = time()
        for (id, p) in remote_poses_at(n, now)
            age = now - get(n.rxtime, id, now)
            # where the client actually was when this frame was drawn: its own stamp plus the age
            tc = p.tick/1000 + age
            tx, tz = truth(tc)
            push!(errs, hypot(tx - p.x, tz - p.z)); push!(ages, age)
        end
        sleep(0.016)
    end
    netclose(n)
    if isempty(errs)
        println("host: NO remote poses seen"); return false
    end
    mean(v) = sum(v)/length(v)
    @printf("host: samples=%d  age mean=%.3fs max=%.3fs  ERR mean=%.4f m max=%.4f m\n",
            length(errs), mean(ages), maximum(ages), mean(errs), maximum(errs))
    # Envelope from S2/S3: mean ~1/2*a*E[t^2] at 10 Hz ~= 0.025 m, worst at the cap.
    # Allow generous headroom for real scheduling jitter -- this arm is here to catch a WIRING
    # fault (metres), not to re-measure the model to four decimal places.
    ok = mean(errs) < 0.20 && maximum(errs) < 1.0
    println(ok ? "PASS host" : "FAIL host: outside the predicted envelope")
    ok
end

mode = length(ARGS) >= 1 ? ARGS[1] : "host"
exit((mode == "client" ? run_client() : run_host()) ? 0 : 1)
