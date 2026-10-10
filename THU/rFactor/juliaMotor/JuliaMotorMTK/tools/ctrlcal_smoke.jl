# CTRLCAL-1 gate (PO 2026-10-10): "controller calibration should have two options - autodetect or saved profile. Saved
# profile includes Thrustmaster TX and Logitech 3Dx Pro."
#
# 1. The built-in profiles are files (controller_profiles/) read by BOTH the sim (JoyCfg) and the launcher, and hold the
#    documented maps (the launcher's own TX preset had drifted: pedals unmapped, paddles swapped).
# 2. JoyCfg.resolve honours the choice: `mode profile` = that profile whatever device; `mode autodetect` = the device's
#    own calibration (this conf if made on it, else joystick_profiles/<device>.conf), else a built-in by name, else X3D
#    with a warning; no mode line = the old precedence.
# 3. The launcher's resolve() (what its "The game will use:" line says) agrees with JoyCfg's on every case.
# 4. AppImage updates keep the per-device calibrations.
# Headless, temp files only: the real joystick.conf and joystick_profiles/ are never read or written.
include(joinpath(@__DIR__, "..", "..", "demo", "native", "joycfg.jl")); using .JoyCfg
const NATIVE = normpath(joinpath(@__DIR__, "..", "..", "demo", "native"))
fails = Ref(0)
check(name, cond, msg = "") = (cond || (fails[] += 1); println("  ", cond ? "PASS" : "FAIL", "  ", rpad(name, 62), msg))
println("CTRLCAL-1 gate: autodetect or saved profile")

# 1. built-ins
bp = JoyCfg.builtin_profiles()
check("built-ins: Logitech Extreme 3D Pro + Thrustmaster TX", [b[1] for b in bp] == ["Logitech Extreme 3D Pro", "Thrustmaster TX"],
      string([b[1] for b in bp]))
same(a, b) = a.steer == b.steer && a.throttle == b.throttle && a.brake == b.brake && a.clutch == b.clutch &&
             (a.up_btn, a.dn_btn, a.clutch_btn, a.deadzone) == (b.up_btn, b.dn_btn, b.clutch_btn, b.deadzone)
TXDOC  = JoyMap(Ctrl(1, -0.99701, 0.99637), Ctrl(2, 1.0, -0.99804), Ctrl(4, 1.0, 0.29814), Ctrl(3, 0.99609, -0.99609), 2, 1, 0, 0.06)
X3DDOC = JoyMap(Ctrl(1, -1.0, 1.0), Ctrl(2, 0.0, -1.0), Ctrl(2, 0.0, 1.0), Ctrl(4, -1.0, 1.0), 1, 2, 3, 0.06)
check("TX file = the PO's June calibration (right paddle up, pedals 2/4/3)", same(JoyCfg.txmap(), TXDOC))
check("X3D file = the historical map (clutch on the slider, axis 4)", same(JoyCfg.x3dmap(), X3DDOC))

# 2. resolve, every path
TX = "Thrustmaster Thrustmaster TX Racing Wheel"; X3D = "Logitech Logitech Extreme 3D pro"; PAD = "Some Gamepad"
dir = mktempdir(); ud = joinpath(dir, "joystick_profiles"); mkdir(ud); conf = joinpath(dir, "joystick.conf")
writeconf(meta, m) = (savemap(conf, m); open(conf, "a") do io; for (k, v) in meta; println(io, k, " ", v); end; end)
LEGACY = JoyMap(Ctrl(1, -0.21459, 0.22359), Ctrl(2, 0.99609, -0.18084), Ctrl(4, 0.99609, 0.86315), Ctrl(3, 0.99804, -0.1828), 2, 1, 0, 0.06)
CUSTOM = JoyMap(Ctrl(3, -0.5, 0.5), Ctrl(1, 0.0, 1.0), Ctrl(2, 0.0, 1.0), Ctrl(5, 0.0, 1.0), 4, 5, 0, 0.05)
cases = Tuple{String,Any,String,String,Any,String}[]       # (label, meta-or-nothing, device, want-source-prefix, want-map, conf map tag)
function case(label, meta, confmap, dev, wantsrc, wantmap)
    rm(conf; force = true)
    meta === :none || writeconf(meta, confmap)
    m, src = JoyCfg.resolve(conf, dev; userdir = ud)
    check(label, startswith(src, wantsrc) && same(m, wantmap), src)
    push!(cases, (label, meta, dev, wantsrc, wantmap, confmap === CUSTOM ? "custom" : confmap === TXDOC ? "tx" :
                  confmap === LEGACY ? "legacy" : "x3d"))
end
case("old conf (no mode line) wins, as before", Pair{String,String}[], CUSTOM, TX, "joystick.conf", CUSTOM)
case("saved profile X3D used on a TX (the driver's choice)", ["mode" => "profile", "label" => "Logitech Extreme 3D Pro"], X3DDOC, TX,
     "saved profile \"Logitech Extreme 3D Pro\"", X3DDOC)
case("autodetect: conf made on this TX -> conf", ["mode" => "autodetect", "device" => TX], CUSTOM, TX, "autodetect: calibration of", CUSTOM)
case("autodetect: conf made on the TX, X3D plugged -> built-in X3D", ["mode" => "autodetect", "device" => TX], CUSTOM, X3D,
     "autodetected Logitech Extreme 3D Pro", X3DDOC)
case("autodetect: no calibration, TX plugged -> built-in TX", ["mode" => "autodetect"], X3DDOC, TX, "autodetected Thrustmaster TX", TXDOC)
case("autodetect: unknown pad, no calibration -> X3D + warning", ["mode" => "autodetect"], X3DDOC, PAD, "X3D default -- UNKNOWN", X3DDOC)
savemap(JoyCfg.device_file(PAD, ud), CUSTOM)
case("autodetect: unknown pad with its own saved calibration -> it", ["mode" => "autodetect"], X3DDOC, PAD,
     "autodetect: saved calibration of \"Some Gamepad\"", CUSTOM)
# S3: a pre-CTRLCAL-1 conf is attributed to the device whose saved file is identical (the PO's own case)
savemap(JoyCfg.device_file(TX, ud), LEGACY)
case("old conf made on the TX, TX plugged -> it, as before", Pair{String,String}[], LEGACY, TX, "joystick.conf", LEGACY)
case("old conf made on the TX, X3D plugged -> built-in X3D, not the TX map", Pair{String,String}[], LEGACY, X3D,
     "autodetected Logitech Extreme 3D Pro", X3DDOC)
case("old conf of unknown origin -> used as before", Pair{String,String}[], TXDOC, X3D, "joystick.conf", TXDOC)
case("old conf identical to the pad's saved file, X3D plugged -> not used", Pair{String,String}[], CUSTOM, X3D,
     "autodetected Logitech Extreme 3D Pro", X3DDOC)
rm(JoyCfg.device_file(TX, ud))
case("no conf at all, TX -> built-in TX", :none, X3DDOC, TX, "autodetected Thrustmaster TX", TXDOC)
case("no conf, no controller -> X3D default", :none, X3DDOC, "", "X3D default (no controller found)", X3DDOC)

# 3. the launcher's mirror says the same thing, case by case
py = """
import os, sys, json
sys.path.insert(0, sys.argv[1])
import juliaRacer as jr
jr.PROFILE_DIR = sys.argv[3]
m, src = jr.resolve(sys.argv[2], sys.argv[4])
c = lambda x: [x.axis, x.a, x.b]
print(json.dumps({"src": src, "map": [c(m.steer), c(m.throttle), c(m.brake), c(m.clutch), m.up_btn, m.dn_btn, m.clutch_btn, m.deadzone]}))
"""
pyf = joinpath(dir, "mirror.py"); write(pyf, py)
agree = 0
for (label, meta, dev, wantsrc, wantmap, tag) in cases
    rm(conf; force = true)
    meta === :none || writeconf(meta, tag == "custom" ? CUSTOM : tag == "tx" ? TXDOC : tag == "legacy" ? LEGACY : X3DDOC)
    legacyfile = occursin("made on the TX", label)        # those cases had the TX's saved file present
    legacyfile && savemap(JoyCfg.device_file(TX, ud), LEGACY)
    jm, jsrc = JoyCfg.resolve(conf, dev; userdir = ud)
    out = try
        readchomp(addenv(`python3 -I $pyf $NATIVE $conf $ud $dev`, "QT_QPA_PLATFORM" => "offscreen"))
    catch e
        string(e)
    end
    ok = occursin("\"src\": " * repr(jsrc), out) || occursin("\"src\": \"" * replace(jsrc, "\"" => "\\\"") * "\"", out)
    want = string([[jm.steer.axis, jm.steer.a, jm.steer.b], [jm.throttle.axis, jm.throttle.a, jm.throttle.b],
                   [jm.brake.axis, jm.brake.a, jm.brake.b], [jm.clutch.axis, jm.clutch.a, jm.clutch.b]])
    nums = [parse(Float64, x.match) for x in eachmatch(r"-?\d+(\.\d+)?(e-?\d+)?", split(out, "\"map\"")[end])]
    mapok = length(nums) == 16 && nums[1:12] == Float64[jm.steer.axis, jm.steer.a, jm.steer.b, jm.throttle.axis, jm.throttle.a,
        jm.throttle.b, jm.brake.axis, jm.brake.a, jm.brake.b, jm.clutch.axis, jm.clutch.a, jm.clutch.b] &&
        nums[13:16] == Float64[jm.up_btn, jm.dn_btn, jm.clutch_btn, jm.deadzone]
    ok && mapok ? (global agree += 1) : println("    mirror differs on \"", label, "\": ", out)
    legacyfile && rm(JoyCfg.device_file(TX, ud))
end
check("launcher resolve() == JoyCfg.resolve on all $(length(cases)) cases", agree == length(cases), "$agree/$(length(cases))")

# NEGATIVE CONTROL: the mirror check must see a difference when there is one (a profile conf read as autodetect).
rm(conf; force = true); writeconf(["mode" => "profile", "label" => "x"], CUSTOM)
out = readchomp(addenv(`python3 -I $pyf $NATIVE $conf $ud $TX`, "QT_QPA_PLATFORM" => "offscreen"))
check("NEGATIVE CONTROL: a profile conf is not reported as autodetect", !occursin("autodetect", out), out)

# 5. S2: the wizard's 90° step (iRacing) -> wheel_half_deg, saved and read back; the sim prefers the kernel's range, then
# the measurement, then the TX name default; a joystick (no measurement, unknown name) stays on endpoint steering.
mw = JoyMap(TXDOC.steer, TXDOC.throttle, TXDOC.brake, TXDOC.clutch, 2, 1, 0, 0.06, 450.0)
savemap(joinpath(dir, "w.conf"), mw)
check("wheel range saved and read back", loadmap(joinpath(dir, "w.conf")).wheel_half_deg == 450.0)
check("old 8-field maps still build (wheel range 0)", JoyCfg.txmap().wheel_half_deg == 0.0)
check("unknown wheel with a measured range -> physical steering", JoyCfg.wheel_half_range_deg("Some Wheel"; measured = 270.0) == 270.0)
check("unknown device, no measurement -> endpoint steering", JoyCfg.wheel_half_range_deg("Some Wheel") == 0.0)
check("the sim passes the calibration's range", occursin("wheel_half_range_deg(JOYNAME; measured = JOYMAP.wheel_half_deg)",
      read(joinpath(NATIVE, "drive_native_mtk.jl"), String)))

# 4. AppImage update keeps the autodetect store
sh = read(normpath(joinpath(@__DIR__, "..", "..", "tools", "appimage", "build_julia.sh")), String)
check("AppImage update keeps joystick.conf AND joystick_profiles/", occursin("demo/native/joystick.conf\" \"\$W", sh) &&
      occursin("cp -a \"\$W/THU/rFactor/juliaMotor/demo/native/joystick_profiles\"", sh))
check("the image ships no builder calibration (fresh install = autodetect)",
      occursin("rm -rf \"\$APP/usr/share/julia/juliaMotor/demo/native/joystick.conf\" \"\$APP/usr/share/julia/juliaMotor/demo/native/joystick_profiles\"", sh))

println(fails[] == 0 ? "CTRLCAL GATE: PASS" : "CTRLCAL GATE: FAIL ($(fails[]))")
exit(fails[] == 0 ? 0 : 1)
