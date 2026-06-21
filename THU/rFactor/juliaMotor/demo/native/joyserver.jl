# joyserver.jl — a tiny GLFW joystick streamer for the PyQt calibration GUI.
#
# WHY THIS EXISTS: the game (`drive_native*.jl`) reads the controller through GLFW
# (`GLFW.GetJoystickAxes/Buttons`), and `joystick.conf` stores axis indices in GLFW's
# ordering.  A Python reader (pygame/SDL2 or evdev) numbers axes differently, so a
# config calibrated there would map the wrong axes in the game.  This script polls the
# SAME GLFW backend and streams the live state as JSON lines on stdout, one per poll —
# so the GUI calibrates against exactly the indices the game will use.
#
#   julia --project=. joyserver.jl [slot]      # slot defaults to 1 (GLFW.JOYSTICK_1)
#
# Output (one compact JSON object per line, ~60 Hz, flushed):
#   {"present":true,"slot":1,"name":"...","axes":[..],"buttons":[0,1,..]}
#   {"present":false,"slot":1}
using GLFW

const SLOT = let a = length(ARGS) >= 1 ? tryparse(Int, ARGS[1]) : nothing
    GLFW.Joystick(clamp((a === nothing ? 1 : a) - 1, 0, 15))   # 1-based arg → 0-based enum
end

jstr(s) = '"' * replace(string(s), '\\' => "\\\\", '"' => "\\\"") * '"'
farr(v) = '[' * join((string(round(Float64(x); digits=5)) for x in v), ',') * ']'
iarr(v) = '[' * join((string(Int(x)) for x in v), ',') * ']'

function main()
    GLFW.Init()
    GLFW.WindowHint(GLFW.VISIBLE, false)
    win = GLFW.CreateWindow(64, 64, "joyserver")
    GLFW.MakeContextCurrent(win)
    while !GLFW.WindowShouldClose(win)
        GLFW.PollEvents()
        if GLFW.JoystickPresent(SLOT)
            nm = GLFW.GetJoystickName(SLOT)
            ax = GLFW.GetJoystickAxes(SLOT)
            bs = GLFW.GetJoystickButtons(SLOT)
            print("{\"present\":true,\"slot\":", Int(SLOT) + 1,
                  ",\"name\":", jstr(nm === nothing ? "" : nm),
                  ",\"axes\":", farr(ax === nothing ? Float32[] : ax),
                  ",\"buttons\":", iarr(bs === nothing ? UInt8[] : bs), "}\n")
        else
            print("{\"present\":false,\"slot\":", Int(SLOT) + 1, "}\n")
        end
        flush(stdout)
        sleep(1 / 60)
    end
    GLFW.Terminate()
end

main()
