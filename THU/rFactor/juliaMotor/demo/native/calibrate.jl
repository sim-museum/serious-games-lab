# zand_racer joystick calibration wizard.  Run it, then follow the terminal prompts
# (hold a control to an extreme, then press ANY joystick button to confirm).  Writes
# joystick.conf next to this file; the driving app loads it automatically.
#
#   julia --project=. calibrate.jl
using GLFW
include(joinpath(@__DIR__, "joycfg.jl")); using .JoyCfg

const JS = GLFW.JOYSTICK_1
const CONF = joinpath(@__DIR__, "joystick.conf")

poll() = (GLFW.PollEvents(); (GLFW.GetJoystickAxes(JS), GLFW.GetJoystickButtons(JS)))
anybtn(bs) = bs !== nothing && any(b -> b != 0, bs)
function wait_released()
    flush(stdout)                           # make sure the prompt is visible before we block
    while true; _, bs = poll(); anybtn(bs) || break; sleep(0.02); end
end
function wait_button()                      # → 1-based index of the button pressed
    wait_released(); idx = 0
    while idx == 0
        _, bs = poll()
        bs !== nothing && for i in eachindex(bs); bs[i] != 0 && (idx = i; break); end
        sleep(0.02)
    end
    while true; _, bs = poll(); (bs === nothing || idx > length(bs) || bs[idx] == 0) && break; sleep(0.02); end
    idx
end
function capture_rest()                     # axes at rest (snapshot on a button press)
    wait_released(); rest = Float64[]
    while true
        js, bs = poll(); js !== nothing && (rest = collect(Float64, js))
        anybtn(bs) && break; sleep(0.02)
    end
    wait_released(); rest
end
function capture_extreme(rest)              # → (most-displaced axis, its value at the extreme)
    wait_released(); js0, _ = poll(); n = js0 === nothing ? 0 : length(js0)
    n == 0 && return (0, 0.0)
    maxd = zeros(n); val = collect(Float64, js0)
    while true
        js, bs = poll()
        if js !== nothing
            for i in 1:min(n, length(js))
                d = abs(Float64(js[i]) - rest[i]); d > maxd[i] && (maxd[i] = d; val[i] = Float64(js[i]))
            end
        end
        anybtn(bs) && break; sleep(0.02)
    end
    wait_released(); ax = argmax(maxd); (ax, val[ax])
end
function capture_value(ax)                  # value of a known axis at a button press
    wait_released(); cur = 0.0
    while true
        js, bs = poll(); (js !== nothing && ax <= length(js)) && (cur = Float64(js[ax]))
        anybtn(bs) && break; sleep(0.02)
    end
    wait_released(); cur
end

function main()
    println("\n  ── zand_racer joystick calibration ──\n")
    GLFW.Init(); GLFW.WindowHint(GLFW.VISIBLE, false)
    win = GLFW.CreateWindow(160, 120, "calibrate"); GLFW.MakeContextCurrent(win)
    GLFW.PollEvents()
    if !GLFW.JoystickPresent(JS)
        println("  No joystick detected on JOYSTICK_1.  Plug one in and re-run.")
        println("  (The app also works on the keyboard — W/S/A/D, E/Q, C.)")
        GLFW.Terminate(); return
    end
    nm = GLFW.GetJoystickName(JS); ax = GLFW.GetJoystickAxes(JS); bs = GLFW.GetJoystickButtons(JS)
    println("  Found: ", nm, "  (", length(ax), " axes, ", length(bs), " buttons)\n")
    println("  At each step, move the control as asked, then press ANY button to confirm.\n")

    println("  1/7  Center the stick, release the throttle/pedals — then press a button.")
    rest = capture_rest(); println("       rest captured.")

    println("  2/7  Hold STEER fully LEFT — press a button.")
    s_ax, s_left = capture_extreme(rest);  println("       axis $s_ax @ $(round(s_left,digits=2))")
    println("  3/7  Hold STEER fully RIGHT — press a button.")
    s_right = capture_value(s_ax);         println("       axis $s_ax @ $(round(s_right,digits=2))")

    println("  4/7  Hold FULL THROTTLE — press a button.")
    t_ax, t_full = capture_extreme(rest);  println("       axis $t_ax @ $(round(t_full,digits=2))")
    println("  5/7  Hold FULL BRAKE — press a button.")
    b_ax, b_full = capture_extreme(rest);  println("       axis $b_ax @ $(round(b_full,digits=2))")

    println("  6/7  Press the SHIFT-UP button.");   up = wait_button(); println("       button $up")
    println("       Press the SHIFT-DOWN button."); dn = wait_button(); println("       button $dn")
    println("  7/7  Press the CLUTCH button (or SHIFT-UP again to skip).")
    cl = wait_button(); cl == up && (cl = 0); println("       button $(cl==0 ? "none" : cl)")

    m = JoyMap(Ctrl(s_ax, s_left, s_right), Ctrl(t_ax, rest[t_ax], t_full),
               Ctrl(b_ax, rest[b_ax], b_full), Ctrl(0, 0.0, 1.0), up, dn, cl, 0.06)
    savemap(CONF, m)
    println("\n  Saved → ", CONF)

    println("\n  Verifying for 6 s — move everything; values should track:")
    t0 = time()
    while time() - t0 < 6.0
        js, bs = poll(); s, t, b, c, u, d = apply(m, js, bs)
        print("\r   steer ", lpad(round(s,digits=2),5), "  thr ", lpad(round(t,digits=2),4),
              "  brk ", lpad(round(b,digits=2),4), "  clutch ", c>0.5 ? "ON " : "off",
              "  up ", u ? "▼" : "·", "  dn ", d ? "▼" : "·", "   ")
        sleep(0.05)
    end
    println("\n\n  Done.  Launch the app and your stick is mapped.\n")
    GLFW.Terminate()
end
main()
