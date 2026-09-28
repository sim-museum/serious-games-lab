# GATE: AI lateral motion must be GPL's spring/damper, and it must be SMOOTHER than what it replaced.
#
# E107-S1 (PO 2026-09-28: "make julia AI as close as possible to gold standard GPL AI ... Wherever
# possible, use GPL algorithms and data structures as much as possible"; and 2026-09-26: "GPL AI does
# slot from one line to another, it can move laterally, but it does so smoothly unlike the current
# jerky julia AI").
#
# GPL's own gpl_ai.ini says how: `dlat_accel_k1` / `dlat_accel_k2` are "k1/k2 for dlat accel. goal
# spring/damper", one pair per fuzzy-line mode, with a cornering pair switched in at
# `switch_to_cornering_dlat_velocity`, and the acceleration capped by `max_lat_acc_from_speed *
# speed`. SEAM-1 had instead written a velocity clamp here: a desired lateral speed
# min(LANE_V, LANE_K|e|, sqrt(2a|e|)) chased under a constant acceleration bound.
#
# WHY JERK IS THE MEASURE. Both laws settle, and SEAM-1's already removed the gross skitter, so
# "does it reach the target" separates nothing. What the PO sees as jerky is the ACCELERATION
# changing in steps: SEAM-1's desired-speed curve is piecewise, so its derivative jumps at each
# breakpoint, and the chase is bang-bang against +-a*dt. GPL's law is a linear second-order ODE, so
# its acceleration is continuous except at the one cornering switch. Lateral JERK is exactly that
# difference, and it is what a passenger feels.
#
# ASSERTED, both arms in-process via RaceAI.dlat_gpl!:
#  1. PREMISE -- the control arm really is jerky. If it is not, there is nothing to improve.
#  2. GPL's law cuts peak and p99 lateral jerk.
#  3. It still does the job: reaches the target, with bounded overshoot and no limit cycle.
#  4. It respects GPL's own speed-dependent acceleration cap.
const D = normpath(joinpath(@__DIR__, "..", "..", "demo", "native"))
include(joinpath(D, "ai.jl")); using .RaceAI
using Printf

pct(v, p) = isempty(v) ? NaN : (u = sort(copy(v)); u[clamp(ceil(Int, p*length(u)), 1, length(u))])

"""Drive one lateral manoeuvre and return the traces. `targets` is a list of (t_switch, lane target),
so a slot-out-slot-back is one call. `tlane` mirrors the target so the mode selector sees a
transition, as it would in the sim."""
function manoeuvre(; gpl::Bool, targets, v = 40.0, dt = 1/60, T = 6.0, lim = 3.8)
    RaceAI.dlat_gpl!(gpl)
    car = RaceAI.AICar(0.0, v, 0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    lane = Float64[]; vl = Float64[]; al = Float64[]; ts = Float64[]
    n = round(Int, T/dt)
    for k in 0:n
        t = k*dt
        tgt = 0.0
        for (t0, g) in targets; t >= t0 && (tgt = g); end
        car.tlane = tgt
        vprev = car.vlane
        RaceAI.lane_step!(car, tgt, dt, lim)
        push!(ts, t); push!(lane, car.lane); push!(vl, car.vlane); push!(al, (car.vlane - vprev)/dt)
    end
    jerk = [abs(al[i+1] - al[i])/dt for i in 1:length(al)-1]
    # The frames where the TARGET itself steps are reported separately. A spring/damper on a step
    # goal necessarily steps its acceleration (a = -k1*e, and e jumps), so those frames measure the
    # call site's instantaneous `tlane` switch, not the law -- and in GPL the goal moves continuously
    # with lap distance. Lumping them in would let one artificial frame decide the verdict.
    sw = falses(length(jerk))
    for (t0, _) in targets, i in eachindex(jerk)
        abs(ts[i] - t0) <= 2*dt && (sw[i] = true)
    end
    (t = ts, lane = lane, vl = vl, al = al, jerk = jerk,
     jsteady = jerk[.!sw], jswitch = isempty(jerk[sw]) ? [0.0] : jerk[sw])
end

"""Settling time for the target held over [t0, t1): the last moment in that window at which
|lane - tgt| still exceeded `tol`. The window END is required -- scanning to the end of the trace
instead measures past the NEXT target switch, which reported both arms as "5.50 s" on a manoeuvre
that is over by 2 s."""
function settle(tr, tgt, t0, t1, tol = 0.05)
    last = NaN
    for i in length(tr.t):-1:1
        tr.t[i] >= t1 && continue
        tr.t[i] < t0 && break
        abs(tr.lane[i] - tgt) > tol && (last = tr.t[i]; break)
    end
    isnan(last) ? 0.0 : last - t0
end

const fails = Ref(0); const checks = Ref(0)
function ck(ok, label, detail)
    checks[] += 1; ok || (fails[] += 1)
    @printf("  %s  %-54s %s\n", ok ? "PASS" : "FAIL", label, detail)
end

function main()
    println("E107-S1 gate: GPL's dlat spring/damper vs SEAM-1's velocity clamp")
    g = RaceAI.dlat_basic()          # forces the load; GPL_AI_SRC is empty until gpl_ai() has run once
    println("GPL parameters from: ", RaceAI.GPL_AI_SRC[] == "" ? "(file absent -- stock defaults compiled in)" :
                                     RaceAI.GPL_AI_SRC[])
    @printf("  basic_line_transition: omega %.3f rad/s zeta %.3f straight, %.3f / %.3f cornering, switch %.2f m/s\n",
            sqrt(g.k1), g.k2/(2sqrt(g.k1)), sqrt(g.k1c), g.k2c/(2sqrt(g.k1c)), g.vsw)
    @printf("  max lateral accel = %.3f * speed  =  %.2f m/s^2 at 40 m/s\n",
            RaceAI.dlat_amax_k(), RaceAI.dlat_amax_k()*40)

    tg = [(0.5, 2.4), (3.0, 0.0)]
    c = manoeuvre(gpl = false, targets = tg)
    t = manoeuvre(gpl = true,  targets = tg)
    @printf("\n  slot out to +2.4 m at t=0.5 s, back at t=3.0 s, 40 m/s\n")
    for (nm, r) in (("control SEAM-1 clamp", c), ("treatment GPL", t))
        @printf("   %-22s jerk p50 %8.2f p99 %9.2f max %9.2f m/s^3 | at the target switch %8.2f | peak |accel| %5.2f  peak |vlat| %.2f\n",
                nm, pct(r.jsteady, 0.5), pct(r.jsteady, 0.99), maximum(r.jsteady),
                maximum(r.jswitch), maximum(abs, r.al), maximum(abs, r.vl))
    end
    @printf("   control   settles to +2.4 m in %.2f s, overshoot %.3f m\n",
            settle(c, 2.4, 0.5, 3.0), max(0.0, maximum(c.lane) - 2.4))
    @printf("   treatment settles to +2.4 m in %.2f s, overshoot %.3f m\n",
            settle(t, 2.4, 0.5, 3.0), max(0.0, maximum(t.lane) - 2.4))

    ck(pct(c.jsteady, 0.99) > 100.0, "premise: the control arm is jerky",
       @sprintf("p99 %.1f m/s^3 > 100", pct(c.jsteady, 0.99)))
    ck(pct(t.jsteady, 0.99) < pct(c.jsteady, 0.99), "GPL's law cuts p99 lateral jerk",
       @sprintf("%.2f < %.2f m/s^3 (%.0fx)", pct(t.jsteady, 0.99), pct(c.jsteady, 0.99),
                pct(c.jsteady, 0.99)/max(pct(t.jsteady, 0.99), 1e-9)))
    ck(maximum(t.jsteady) < maximum(c.jsteady), "GPL's law cuts PEAK lateral jerk",
       @sprintf("%.2f < %.2f m/s^3", maximum(t.jsteady), maximum(c.jsteady)))
    ck(abs(t.lane[end]) < 0.05, "it returns to the racing line",
       @sprintf("|lane| %.4f m < 0.05", abs(t.lane[end])))
    ck(settle(t, 2.4, 0.5, 3.0) < 2.0, "it reaches the pass rail promptly",
       @sprintf("settled in %.2f s < 2.0", settle(t, 2.4, 0.5, 3.0)))
    ck(max(0.0, maximum(t.lane) - 2.4) < 0.30, "overshoot stays small",
       @sprintf("%.3f m < 0.30", max(0.0, maximum(t.lane) - 2.4)))
    ck(maximum(abs, t.al) <= RaceAI.dlat_amax_k()*40 + 1e-6, "GPL's speed-dependent accel cap holds",
       @sprintf("peak %.2f <= %.2f m/s^2", maximum(abs, t.al), RaceAI.dlat_amax_k()*40))

    h  = manoeuvre(gpl = true,  targets = [(0.0, 0.0)], T = 4.0)
    hc = manoeuvre(gpl = false, targets = [(0.0, 0.0)], T = 4.0)
    tail(r) = r.lane[round(Int, 0.6*length(r.lane)):end]
    @printf("\n  holding the racing line for 4 s, no manoeuvre\n")
    @printf("   control   |lane| max over the last 40%% of the run %.2e m, jerk max %.3f m/s^3\n",
            maximum(abs, tail(hc)), maximum(hc.jsteady))
    @printf("   treatment |lane| max over the last 40%% of the run %.2e m, jerk max %.3f m/s^3\n",
            maximum(abs, tail(h)), maximum(h.jsteady))
    ck(maximum(abs, tail(h)) < 1e-6, "no limit cycle while holding the line",
       @sprintf("%.2e m < 1e-6", maximum(abs, tail(h))))

    big = manoeuvre(gpl = true, targets = [(0.5, 3.8)], T = 4.0)
    @printf("\n  full-width slot to +3.8 m: peak |vlat| %.2f m/s vs cornering switch %.2f m/s -> %s\n",
            maximum(abs, big.vl), RaceAI.dlat_basic().vsw,
            maximum(abs, big.vl) >= RaceAI.dlat_basic().vsw ? "cornering pair ENGAGES" :
            "cornering pair never engages at this width, straight gains only")

    println()
    println("GPLDLAT GATE: ", fails[] == 0 ? "PASS" : "FAIL", "  (", checks[] - fails[], "/", checks[], " checks)")
    exit(fails[] == 0 ? 0 : 1)
end
main()
