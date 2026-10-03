# Joystick mapping + calibration config for the native driving app.  A JoyMap
# assigns each control (steer / throttle / brake / clutch) to a joystick AXIS with
# two captured endpoints (a→0, b→1 output) and each shift/clutch to a BUTTON, so
# any stick or wheel+pedals can be made to work.  `calibrate.jl` writes the config;
# the app loads it (falling back to a default that reproduces the old hardcoded
# Logitech-Extreme-3D-Pro mapping when no config file is present).
module JoyCfg

export Ctrl, JoyMap, defaultmap, loadmap, savemap, apply, x3dmap, txmap, profile_for, resolve

struct Ctrl
    axis::Int          # 1-based index into the GLFW axes array; 0 = unused
    a::Float64         # raw value that maps to output 0  (off / full-left)
    b::Float64         # raw value that maps to output 1  (full / full-right)
end

struct JoyMap
    steer::Ctrl
    throttle::Ctrl
    brake::Ctrl
    clutch::Ctrl       # axis 0 → use clutch_btn instead
    up_btn::Int        # 1-based button indices; 0 = unused
    dn_btn::Int
    clutch_btn::Int
    deadzone::Float64
end

"Default = the original hardcoded mapping: steer=axis1, throttle/brake=axis2 (push/
pull), buttons 1/2/3 = up/down/clutch.  `apply` then reduces to the old formulas."
defaultmap() = JoyMap(Ctrl(1, -1.0, 1.0), Ctrl(2, 0.0, -1.0), Ctrl(2, 0.0, 1.0),
                      Ctrl(0, 0.0, 1.0), 1, 2, 3, 0.06)

# ---- AUTODETECT (PO 2026-10-03: "the code should autodetect the controller type") ----------------
# Without a joystick.conf the sim used to assume a Logitech Extreme 3D for EVERY controller. On a
# Thrustmaster TX that is dangerous, not just wrong: X3D reads axis 2 as throttle(push)/brake(pull),
# and the TX throttle PEDAL rests at +1.0 -- so a released throttle read as FULL BRAKE (1.4-1.5 g to a
# standstill from 200 km/h, measured from the PO's 2026-10-03 Watkins replay), part throttle mixed
# brake in, and the X3D clutch slider (axis 4) is the TX BRAKE pedal resting at +1.0 = clutch held in.
# An AppImage update had deleted the PO's joystick.conf, which is how the fallback was reached.
# Precedence: joystick.conf (the driver's own calibration) > a profile matched by device NAME > X3D.

"The Logitech Extreme 3D Pro: steer = roll, throttle/brake = push/pull on axis 2, clutch = slider."
x3dmap() = (m = defaultmap(); JoyMap(m.steer, m.throttle, m.brake, Ctrl(4, -1.0, 1.0),
                                     m.up_btn, m.dn_btn, m.clutch_btn, m.deadzone))

"""The Thrustmaster TX (hid-tmff2): wheel axis 1, throttle 2, clutch 3, brake 4 -- each pedal rests
at +1.0 and falls when pressed; paddles: right (button 2) = up, left (button 1) = down. Values are the
PO's own calibration of this wheel (juliaRacer.py, 2026-06-29)."""
txmap() = JoyMap(Ctrl(1, -0.99701, 0.99637), Ctrl(2, 1.0, -0.99804), Ctrl(4, 1.0, 0.29814),
                 Ctrl(3, 0.99609, -0.99609), 2, 1, 0, 0.06)

"""Built-in profile for a GLFW joystick NAME: (label, JoyMap), or nothing if the device is unknown."""
function profile_for(name::AbstractString)
    n = lowercase(name)
    occursin("thrustmaster", n) && occursin("tx", n) && return ("Thrustmaster TX", txmap())
    occursin("extreme 3d", n) && return ("Logitech Extreme 3D", x3dmap())
    nothing
end

"""Resolve the live map: (JoyMap, source) from the config path and the connected device's name."""
function resolve(conf::AbstractString, name::AbstractString)
    isfile(conf) && return (loadmap(conf), "joystick.conf")
    pr = profile_for(name)
    pr === nothing || return (pr[2], "autodetected " * pr[1] * " (\"" * name * "\")")
    (x3dmap(), isempty(name) ? "X3D default (no controller found)" :
               "X3D default -- UNKNOWN controller \"" * name * "\": calibrate it in the launcher")
end

@inline function _norm(c::Ctrl, js)
    (c.axis < 1 || js === nothing || c.axis > length(js)) && return 0.0
    d = c.b - c.a
    abs(d) < 1e-6 ? 0.0 : (Float64(js[c.axis]) - c.a) / d
end

"""Map raw GLFW axes/buttons → (steer∈[-1,1], throttle∈[0,1], brake∈[0,1],
clutch∈[0,1], up::Bool, dn::Bool) per a JoyMap."""
function apply(m::JoyMap, js, bs)
    s = clamp(1.0 - 2.0 * _norm(m.steer, js), -1.0, 1.0)   # a=full-left→+1, b=full-right→-1
    # NO steering deadzone — the wheel must be continuous right through center (a dead
    # band makes it unresponsive near center). Throttle/brake keep theirs (creep).
    # PO 2026-08-27: "let off the throttle and the car stops very quickly, even if I don't use
    # brakes". The trace shows brk=0.07–0.11 throughout those coasts: throttle and brake share axis 2
    # (push/pull) and the configured deadzone is only 0.06, so a stick resting slightly back applies a
    # continuous light brake. JM_DEADZONE overrides the configured value.
    dz = (v = tryparse(Float64, get(ENV,"JM_DEADZONE","")); v === nothing ? m.deadzone : v)
    thr = clamp(_norm(m.throttle, js), 0.0, 1.0); thr < dz && (thr = 0.0)
    brk = clamp(_norm(m.brake,    js), 0.0, 1.0); brk < dz && (brk = 0.0)
    btn(i) = (bs !== nothing && i >= 1 && length(bs) >= i && bs[i] != 0)
    clu = m.clutch.axis >= 1 ? clamp(_norm(m.clutch, js), 0.0, 1.0) : (btn(m.clutch_btn) ? 1.0 : 0.0)
    (s, thr, brk, clu, btn(m.up_btn), btn(m.dn_btn))
end

# ---- file format: plain `key value` lines (a "# comment" first line is fine) ----
function savemap(path, m::JoyMap)
    open(path, "w") do io
        println(io, "# zand_racer joystick config — generated by calibrate.jl")
        for (nm, c) in (("steer",m.steer),("throttle",m.throttle),("brake",m.brake),("clutch",m.clutch))
            println(io, "$nm.axis $(c.axis)"); println(io, "$nm.a $(c.a)"); println(io, "$nm.b $(c.b)")
        end
        println(io, "up_btn $(m.up_btn)"); println(io, "dn_btn $(m.dn_btn)")
        println(io, "clutch_btn $(m.clutch_btn)"); println(io, "deadzone $(m.deadzone)")
    end
end

"""Load a JoyMap from `path`; any missing key falls back to the default."""
function loadmap(path)
    isfile(path) || return defaultmap()
    d = Dict{String,Float64}()
    for ln in eachline(path)
        s = strip(ln); (isempty(s) || startswith(s, "#")) && continue
        parts = split(s); length(parts) >= 2 || continue
        v = tryparse(Float64, parts[2]); v !== nothing && (d[parts[1]] = v)
    end
    dm = defaultmap()
    ctrl(nm, def) = Ctrl(round(Int, get(d, "$nm.axis", def.axis)),
                         get(d, "$nm.a", def.a), get(d, "$nm.b", def.b))
    JoyMap(ctrl("steer",dm.steer), ctrl("throttle",dm.throttle), ctrl("brake",dm.brake),
           ctrl("clutch",dm.clutch),
           round(Int, get(d,"up_btn",dm.up_btn)), round(Int, get(d,"dn_btn",dm.dn_btn)),
           round(Int, get(d,"clutch_btn",dm.clutch_btn)), get(d,"deadzone",dm.deadzone))
end

end # module
