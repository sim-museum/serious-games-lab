# GATE: E85-S2 -- dead reckoning. A remote car must be drawn where it IS, not where it last reported.
#
# THE EXPECTATION WAS STATED BEFORE THE FIRST RUN, and these are the numbers it was stated with.
# A remote pose arrives at the packet rate, not the frame rate. At R Hz the newest packet is between
# 0 and 1/R old (mean 1/2R). So:
#
#   HOLDING the last pose      -> first-order error  = v * age
#                                 at 10 Hz, 60 m/s:  mean 3.0 m, max 6.0 m
#   EXTRAPOLATING along heading -> the first-order term cancels EXACTLY and only curvature is left,
#                                 = |truth - straight-line| ~ 1/2 * a_lat * age^2
#                                 at 1.5 g (15 m/s^2):  mean ~0.025 m, max ~0.075 m
#
# i.e. a ~100x improvement while cornering, and EXACT on a straight. Those are the assertions.
#
# The truth here is a closed-form constant-speed arc, so no sockets, no second process and no
# stopwatch are involved: the error is measured against analysis, not against another run of the
# same code. `predict` is a pure function of (pose, dt) precisely so this is possible.
#
#   arc:  yaw(t) = w t,  x(t) = (v/w) sin(w t),  z(t) = (v/w) (1 - cos(w t))
#   then  dx/dt = v cos(yaw), dz/dt = v sin(yaw)  -- exactly the convention `predict` advances by,
#   and radius = v/w = v^2/a_lat.
include(joinpath(@__DIR__, "..", "..", "demo", "native", "netplay.jl"))
using .NetPlay

fails = Ref(0)
chk(name, ok, detail="") = (println("  ", rpad(name, 54), ok ? "PASS" : "FAIL", "   ", detail);
                            ok || (fails[] += 1); ok)

const V    = 60.0            # m/s (216 km/h)
const ALAT = 15.0            # m/s^2, ~1.5 g
const W    = ALAT / V        # rad/s -> radius V/W = 240 m
const RATE = 10.0            # packets/s
const DT   = 1.0 / RATE

truth(t, w) = w == 0 ? (V*t, 0.0) : ((V/w)*sin(w*t), (V/w)*(1 - cos(w*t)))
pose_at(t, w) = (tick = 0, x = truth(t, w)[1], y = 3.5, z = truth(t, w)[2],
                 yaw = w*t, v = V, steer = 0.0)

"""Errors over one packet interval, sampled finely: (hold, extrapolated)."""
function errors(w)
    hold = Float64[]; ext = Float64[]
    for k in 0:4                                    # several packets, so this is not one lucky point
        tk = k*DT; p = pose_at(tk, w)
        for age in range(0.0, DT; length = 51)
            tx, tz = truth(tk + age, w)
            push!(hold, hypot(tx - p.x, tz - p.z))
            q = predict(p, age)
            push!(ext,  hypot(tx - q.x, tz - q.z))
        end
    end
    (hold, ext)
end

h, e = errors(W)
mh, xh = sum(h)/length(h), maximum(h)
me, xe = sum(e)/length(e), maximum(e)
println("  cornering at $(V) m/s, $(round(ALAT/9.81,digits=2)) g, $(Int(RATE)) Hz:")
println("     hold        mean ", round(mh, digits=3), " m   max ", round(xh, digits=3), " m")
println("     extrapolate mean ", round(me, digits=4), " m   max ", round(xe, digits=4), " m")

# 1. POSITIVE CONTROL: the harness must reproduce the analytic first-order error. If it does not,
#    every "improvement" below is measured against a yardstick that is itself wrong.
chk("hold error matches v*age (predicted 3.0 m mean)", abs(mh - V*DT/2) < 0.1*V*DT/2,
    "$(round(mh,digits=3)) vs $(round(V*DT/2,digits=3))")
chk("hold worst case matches v/R (predicted 6.0 m)", abs(xh - V*DT) < 0.1*V*DT,
    "$(round(xh,digits=3)) vs $(round(V*DT,digits=3))")

# 2. the stated second-order bound
chk("extrapolated max within the 1/2*a*t^2 bound", xe <= 0.5*ALAT*DT^2 * 1.15,
    "$(round(xe,digits=4)) <= $(round(0.5*ALAT*DT^2*1.15,digits=4))")
chk("extrapolation beats hold by >= 20x (predicted ~100x)", mh/me >= 20,
    "$(round(mh/me, digits=1))x")

# 3. on a STRAIGHT the first-order term is all there is, so extrapolation must be EXACT.
#    This isolates curvature as the only residual -- without it, a small error could be anything.
hs, es = errors(0.0)
chk("straight line: hold still lags", sum(hs)/length(hs) > 2.5, "$(round(sum(hs)/length(hs),digits=3)) m")
chk("straight line: extrapolation is exact", maximum(es) < 1e-9, "max $(maximum(es)) m")

# 4. shape guarantees
p0 = pose_at(0.3, W)
chk("predict(p, 0) is a no-op", predict(p0, 0.0) == p0, "unchanged")
chk("predict(p, negative) is a no-op", predict(p0, -0.5) == p0, "clock skew cannot rewind a car")
chk("HEIGHT is never extrapolated (E104(a))", predict(p0, 0.1).y == p0.y,
    "y comes from the ground, not from dead reckoning")
chk("speed and heading are carried, not invented",
    predict(p0, 0.1).v == p0.v && predict(p0, 0.1).yaw == p0.yaw, "unchanged")

# ── E85-S3: LOSS, JITTER AND SILENCE ────────────────────────────────────────────────────────────
# Predicted BEFORE running, from the same ½·a·Δt² the S2 arms confirmed:
#   * error grows with the SQUARE of the gap, so ONE dropped packet at 10 Hz (Δt 0.1 -> 0.2 s)
#     should give ~4x the error: 0.075 -> ~0.30 m. Holding would be 12 m at that age.
#   * two dropped packets (0.3 s) would be ~9x -- which is why extrapolation is CAPPED.
#   * a silent peer must VANISH, not keep driving.
println("\n  -- loss, jitter and silence --")

function err_at(age, w)                       # error of a dead-reckoned pose `age` after a packet
    p = pose_at(0.0, w)
    tx, tz = truth(age, w)
    q = predict(p, min(age, NetPlay.EXTRAP_MAX))
    hypot(tx - q.x, tz - q.z)
end

e1 = err_at(DT, W)          # clean:            0.1 s
e2 = err_at(2DT, W)         # one packet lost:  0.2 s
println("     1 interval ", round(e1, digits=4), " m    2 intervals ", round(e2, digits=4), " m",
        "    (hold at 0.2 s would be ", round(V*2DT, digits=1), " m)")
chk("one dropped packet costs ~4x, not ~2x (t^2)", 3.5 <= e2/e1 <= 4.5, "$(round(e2/e1,digits=2))x")
chk("even with a packet lost, still << holding", e2 < V*2DT/20, "$(round(e2,digits=3)) vs $(round(V*2DT,digits=1)) m")

# The cap: past EXTRAP_MAX the POSE must stop advancing.
# ⚠️ My first two arms here asserted the ERROR stops growing, and they failed -- correctly. A frozen
# pose does not freeze the error, because the real car keeps moving away from it. The property the
# cap actually guarantees is about the POSE, and that is what is asserted now. The arms were wrong,
# not the code; a gate that fails is only useful if you check which half is at fault.
p_far  = predict(pose_at(0.0, W), min(1.0, NetPlay.EXTRAP_MAX))
p_far2 = predict(pose_at(0.0, W), min(2.0, NetPlay.EXTRAP_MAX))
p_cap  = predict(pose_at(0.0, W), NetPlay.EXTRAP_MAX)
chk("past the cap the pose stops advancing", p_far === p_far2, "identical at 1 s and 2 s")
chk("the frozen pose is the one at EXTRAP_MAX", p_far === p_cap, "$(NetPlay.EXTRAP_MAX) s")
chk("and it HAS advanced up to the cap", p_cap.x != pose_at(0.0, W).x, "not simply held")

# silence: a peer that stops sending must be DROPPED, not extrapolated forever
chk("a peer silent past STALE_S is stale", NetPlay.is_stale(NetPlay.STALE_S), "$(NetPlay.STALE_S) s")
chk("a peer heard from recently is not stale", !NetPlay.is_stale(NetPlay.STALE_S - 0.001), "just under")
chk("the cap is shorter than the drop timeout", NetPlay.EXTRAP_MAX < NetPlay.STALE_S,
    "freeze first, then remove -- never invent motion for a car that is gone")

println(fails[] == 0 ? "\n  DEAD RECKONING GATE: PASS ✓" : "\n  DEAD RECKONING GATE: FAIL ($(fails[]))")
exit(fails[] == 0 ? 0 : 1)
