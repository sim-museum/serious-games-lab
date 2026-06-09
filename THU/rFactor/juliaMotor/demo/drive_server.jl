#!/usr/bin/env julia
# drive_server.jl — drive the JuliaMotor Vanwall around Zandvoort, live, from a
# browser.  A human supplies throttle/brake/steer/shift; the car's motion is
# governed entirely by the JuliaMotor physics (the validated bicycle model +
# calibrated TBC tires + engine/drivetrain/brakes, over the real GMT track
# surface).  This is the Phase 4.3 "drivable standalone" end-state.
#
# Pure Julia stdlib (Sockets) — no web framework.  The browser polls /step at
# its frame rate sending the current key state; the server advances the physics
# by the elapsed wall-clock time and returns the car pose + HUD.  Static track
# geometry is served once from /track.json; the page itself from /.
#
#   julia --project=../JuliaMotor drive_server.jl [port]
#   then open  http://127.0.0.1:8080/

using Pkg
Pkg.activate(; temp=true, io=devnull)
Pkg.develop([PackageSpec(path=joinpath(@__DIR__, "..", "JuliaMotor")),
             PackageSpec(path=joinpath(@__DIR__, "..", "RFactorData")),
             PackageSpec(path=joinpath(@__DIR__, "..", "RFactorTelemetry"))]; io=devnull)

using JuliaMotor, RFactorData
using Sockets
using Printf

const PORT = length(ARGS) >= 1 ? parse(Int, ARGS[1]) : 8080

# ---------------------------------------------------------------------------
# Load the car + track once.
# ---------------------------------------------------------------------------
println("Loading Vanwall + Zandvoort…")
const GD  = default_gamedata()
const DIR = joinpath(GD, "Locations", "Zandvoort67")
const VEH = load_vehicle(joinpath(GD, "Vehicles", "F158", "Vanwall", "Teams",
                                  "LewisEvans", "LewisEvans.veh"))
const MODEL = VehicleModel(VEH)
const AIW = read_aiw(joinpath(DIR, "zandvoort67.AIW"))
print("  building collision surface… "); flush(stdout)
const TERRAIN = TriangleHAT(DIR)
println(TERRAIN)
const CAR = DriveCar(MODEL, AIW; terrain=TERRAIN)
println("  ", MODEL, "  ", CAR.ts)

# live state, guarded by a lock (handlers run as async tasks)
const STATE = spawn(CAR; v0=0.0)
const LOCK = ReentrantLock()
const LAST_T = Ref(0.0)          # wall clock of the previous /step (0 = not yet)

# ---------------------------------------------------------------------------
# Track geometry JSON (built once): classified surface triangles + racing line.
# ---------------------------------------------------------------------------
function build_track_json()
    cls(n) = startswith(n, "asphalt") || n == "pitline.gmt" || startswith(n, "curb") ? "road" :
             startswith(n, "grass") ? "grass" :
             (startswith(n, "sand") || startswith(n, "hayba")) ? "sand" : "skip"
    mas = read_mas(joinpath(DIR, "Zand67.mas"))
    tris = Dict("road" => Float64[], "grass" => Float64[], "sand" => Float64[])
    for nm in JuliaMotor.hat_meshes(DIR)
        c = cls(nm); c == "skip" && continue
        e = findfirst(x -> lowercase(x.name) == nm, mas.entries); e === nothing && continue
        g = parse_gmt(extract(mas, mas.entries[e])); P = g.positions
        buf = tris[c]
        for t in g.triangles
            for vi in (t[1], t[2], t[3])
                p = P[vi + 1]
                push!(buf, p[1], -p[3])     # X, Z (top-down, display frame)
            end
        end
    end
    # racing line (centerline) + start pose — display frame (Z negated)
    ts = CAR.ts
    line = Float64[]
    for p in ts.pos; push!(line, p[1], -p[3]); end
    io = IOBuffer()
    print(io, "{")
    for (k, key) in enumerate(("road", "grass", "sand"))
        k > 1 && print(io, ",")
        print(io, "\"", key, "\":[")
        b = tris[key]
        for (i, x) in enumerate(b); i > 1 && print(io, ","); print(io, @sprintf("%.1f", x)); end
        print(io, "]")
    end
    print(io, ",\"line\":[")
    for (i, x) in enumerate(line); i > 1 && print(io, ","); print(io, @sprintf("%.1f", x)); end
    print(io, "]")
    print(io, ",\"start\":[", @sprintf("%.1f,%.1f", STATE.x, -STATE.z), "]")
    print(io, ",\"laplen\":", @sprintf("%.1f", ts.lap_length))
    print(io, "}")
    String(take!(io))
end
print("Building track geometry… "); flush(stdout)
const TRACK_JSON = build_track_json()
println(round(length(TRACK_JSON) / 1024, digits=0), " KB"); flush(stdout)

# ---------------------------------------------------------------------------
# Full 3D scene: every visible mesh from the track's .mas archives, in world
# coordinates (Zandvoort's .scn carries no per-instance transform — meshes are
# pre-baked world-space), as per-category triangle soup (position + normal) for
# WebGL.  Skips the invisible timing planes (x*) and the (textureless) skybox.
# ---------------------------------------------------------------------------
function scene_meshes(scn_dir)
    scn = read_gen(only(filter(p -> endswith(lowercase(p), ".scn"),
                               readdir(scn_dir; join=true))))
    names = String[]
    for st in gen_statements(scn, "MeshFile")
        nm = lowercase(string(RFactorData.value(st)))
        (startswith(nm, "x") || startswith(nm, "sky")) && continue   # timing / skybox
        push!(names, nm)
    end
    unique(names)
end

function scene_category(n)
    startswith(n, "asphalt") || n == "pitline.gmt" || startswith(n, "tarmac") ? "road" :
    startswith(n, "curb") ? "curb" :
    startswith(n, "grass") ? "grass" :
    (startswith(n, "sand") || startswith(n, "hayba") || startswith(n, "gravel")) ? "sand" :
    (occursin("tree", n) || occursin("hedge", n) || occursin("bush", n) ||
        occursin("foli", n) || occursin("forest", n)) ? "foliage" :
    (occursin("tire", n) || occursin("tyre", n) || occursin("barrier", n) ||
        occursin("armco", n) || occursin("guard", n) || occursin("fence", n) ||
        occursin("wall", n)) ? "dark" :
    "structure"
end

const SCENE_CATS = ("road", "curb", "grass", "sand", "foliage", "dark", "structure")

function build_scene_json()
    want = Set(scene_meshes(DIR))
    pos = Dict(c => Float64[] for c in SCENE_CATS)
    nrm = Dict(c => Float64[] for c in SCENE_CATS)
    ntri = 0
    for maspath in filter(p -> endswith(lowercase(p), ".mas"), readdir(DIR; join=true))
        m = read_mas(maspath)
        for e in m.entries
            lowercase(e.name) in want || continue
            g = parse_gmt(extract(m, e)); P = g.positions; N = g.normals
            c = scene_category(lowercase(e.name))
            bp = pos[c]; bn = nrm[c]
            ok(p) = all(isfinite, p) && abs(p[1]) < 2e4 && abs(p[2]) < 2e4 && abs(p[3]) < 2e4
            for t in g.triangles
                v1 = P[t[1]+1]; v2 = P[t[2]+1]; v3 = P[t[3]+1]
                (ok(v1) && ok(v2) && ok(v3)) || continue   # drop mis-parsed triangles
                for vi in (t[1], t[2], t[3])
                    p = P[vi + 1]
                    nn = vi + 1 <= length(N) ? N[vi + 1] : (0.0f0, 1.0f0, 0.0f0)
                    all(isfinite, nn) || (nn = (0.0f0, 1.0f0, 0.0f0))  # guard NaN/Inf → valid JSON
                    # display frame: negate Z to convert rFactor's left-handed
                    # world to three.js' right-handed frame (un-mirrors the
                    # track — Tarzan reads as the right-hander it is — and makes
                    # steering intuitive).  Flip normal.z to match the reflection.
                    push!(bp, p[1], p[2], -p[3]); push!(bn, nn[1], nn[2], -nn[3])
                end
                ntri += 1
            end
        end
    end
    io = IOBuffer()
    print(io, "{\"cats\":{")
    for (k, c) in enumerate(SCENE_CATS)
        k > 1 && print(io, ",")
        print(io, "\"", c, "\":{\"pos\":[")
        bp = pos[c]; for (i, x) in enumerate(bp); i > 1 && print(io, ","); print(io, @sprintf("%.2f", x)); end
        print(io, "],\"nrm\":[")
        bn = nrm[c]; for (i, x) in enumerate(bn); i > 1 && print(io, ","); print(io, @sprintf("%.3f", x)); end
        print(io, "]}")
    end
    print(io, "}")
    print(io, ",\"start\":[", @sprintf("%.2f,%.2f,%.2f,%.4f", STATE.x, STATE.y, -STATE.z, -STATE.θ), "]")
    print(io, ",\"ntri\":", ntri, "}")
    String(take!(io)), ntri
end
print("Building 3D scene… "); flush(stdout)
const SCENE_JSON, SCENE_NTRI = build_scene_json()
println(SCENE_NTRI, " triangles, ", round(length(SCENE_JSON) / 1024 / 1024, digits=1), " MB"); flush(stdout)

# ---------------------------------------------------------------------------
# The real car: the actual Vanwall GMT meshes (parse_gmt_indexed — the
# multi-group/indexed decoder) in the rig's local frame (+X forward, +Y up,
# +Z left).  GMT local axes are comp1 = lateral, comp2 = vertical, comp3 =
# longitudinal (+ = rear), so map X = -comp3, Y = comp2, Z = comp1.  Served as
# named, flat-coloured triangle-soup parts the client adds to the car rig.
# ---------------------------------------------------------------------------
const CAR_MAS = joinpath(GD, "Vehicles", "F158", "Vanwall", "Vanwall VW58.mas")
const CAR_PARTS = (("body", "vanwall_body.gmt", 0x1d5a34),       # racing green
                   ("cockpit", "vanwall_cockpit.gmt", 0x15251c), # dark interior
                   ("driver", "ca_driver.gmt", 0x6b5a44))        # overalls
function build_car_json()
    mas = read_mas(CAR_MAS)
    io = IOBuffer(); print(io, "{\"parts\":[")
    nfirst = true; ntri = 0
    for (label, gmt, col) in CAR_PARTS
        i = findfirst(e -> lowercase(e.name) == gmt, mas.entries); i === nothing && continue
        g = parse_gmt_indexed(extract(mas, mas.entries[i])); isempty(g.triangles) && continue
        P = g.positions; Nn = g.normals; bp = Float64[]; bn = Float64[]
        ok(p) = all(isfinite, p) && all(c -> abs(c) < 50, p)
        for t in g.triangles
            (ok(P[t[1]+1]) && ok(P[t[2]+1]) && ok(P[t[3]+1])) || continue
            for vi in t
                p = P[vi+1]; nn = vi + 1 <= length(Nn) ? Nn[vi+1] : (0.0f0, 1.0f0, 0.0f0)
                all(isfinite, nn) || (nn = (0.0f0, 1.0f0, 0.0f0))
                push!(bp, -p[3], p[2], p[1])      # X=-lon (nose +X), Y=up, Z=lat
                push!(bn, -nn[3], nn[2], nn[1])
            end
            ntri += 1
        end
        nfirst || print(io, ","); nfirst = false
        print(io, "{\"name\":\"", label, "\",\"color\":", Int(col), ",\"pos\":[")
        for (k, x) in enumerate(bp); k > 1 && print(io, ","); print(io, @sprintf("%.3f", x)); end
        print(io, "],\"nrm\":[")
        for (k, x) in enumerate(bn); k > 1 && print(io, ","); print(io, @sprintf("%.3f", x)); end
        print(io, "]}")
    end
    print(io, "]}")
    String(take!(io)), ntri
end
print("Building car meshes… "); flush(stdout)
const CAR_JSON, CAR_NTRI = build_car_json()
println(CAR_NTRI, " triangles, ", round(length(CAR_JSON) / 1024, digits=0), " KB"); flush(stdout)

# ---------------------------------------------------------------------------
# The car's REAL onboard engine samples (the rFactor .sfx onboard set: idle +
# four power samples spanning idle→redline).  Loaded once and served as binary
# WAV; the browser crossfades them by RPM the way the sim does.
# ---------------------------------------------------------------------------
const SOUND_DIR = joinpath(GD, "Sounds", "F158", "Vanwall_V254", "IN")
const SOUND_FILES = ("idle1e.WAV", "v4g.wav", "l4f.wav", "l2e.wav", "h1g.wav")
const SOUNDS = Dict{String,Vector{UInt8}}()
let total = 0
    for f in SOUND_FILES
        p = joinpath(SOUND_DIR, f)
        if isfile(p); b = read(p); SOUNDS[lowercase(f)] = b; total += length(b); end
    end
    println("Loaded ", length(SOUNDS), " engine samples, ", round(total / 1024 / 1024, digits=1), " MB")
end

# ---------------------------------------------------------------------------
# Physics step driven by wall-clock time.
# ---------------------------------------------------------------------------
function advance!(inp::DriveInput, reset::Bool)
    lock(LOCK) do
        if reset
            s = spawn(CAR; v0=0.0)
            for f in fieldnames(CarState); setfield!(STATE, f, getfield(s, f)); end
            LAST_T[] = 0.0
        else
            now = time()
            dt = LAST_T[] == 0.0 ? 1 / 60 : clamp(now - LAST_T[], 0.0, 0.1)
            LAST_T[] = now
            dt > 1e-4 && step!(STATE, CAR, inp; dt=dt)
        end
        s = STATE
        tc = s.tc   # ((long,lat,radius)×4) for FL,FR,RL,RR — common mg/4 scale
        @sprintf("{\"x\":%.2f,\"y\":%.2f,\"z\":%.2f,\"h\":%.4f,\"v\":%.2f,\"kmh\":%.1f,\"gear\":%d,\"rpm\":%.0f,\"thr\":%.2f,\"brk\":%.2f,\"clutch\":%.2f,\"steer\":%.3f,\"g\":%.2f,\"beta\":%.3f,\"yaw\":%.3f,\"ontrack\":%s,\"lat\":%.2f,\"lapdist\":%.1f,\"laps\":%d,\"t\":%.1f,\"tc\":[[%.3f,%.3f,%.3f],[%.3f,%.3f,%.3f],[%.3f,%.3f,%.3f],[%.3f,%.3f,%.3f]],\"revlim\":%.0f}",
                 s.x, s.y, -s.z, -s.θ, s.v, s.v * 3.6, s.gear, s.rpm, inp.throttle, inp.brake,
                 inp.clutch, inp.steer, s.along / 9.81, s.β, s.r, s.ontrack ? "true" : "false",
                 s.lateral, s.lapdist, s.laps, s.t,
                 tc[1][1], tc[1][2], tc[1][3], tc[2][1], tc[2][2], tc[2][3],
                 tc[3][1], tc[3][2], tc[3][3], tc[4][1], tc[4][2], tc[4][3],
                 MODEL.eng.rev_limit)
    end
end

# ---------------------------------------------------------------------------
# Minimal HTTP/1.1 over Sockets.
# ---------------------------------------------------------------------------
function parse_query(q)
    d = Dict{String,String}()
    for kv in split(q, '&'; keepempty=false)
        p = split(kv, '='; limit=2)
        d[p[1]] = length(p) == 2 ? p[2] : ""
    end
    d
end
qf(d, k, default=0.0) = (v = get(d, k, ""); v == "" ? default : something(tryparse(Float64, v), default))

function respond(sock, status, ctype, body; nocache=true)
    hdr = "HTTP/1.1 $status\r\nContent-Type: $ctype\r\nContent-Length: $(sizeof(body))\r\n" *
          (nocache ? "Cache-Control: no-store\r\n" : "") *
          "Connection: close\r\n\r\n"
    write(sock, hdr); write(sock, body)
end

# Build identity for the on-screen version badge — a short content hash over
# the UI + engine source, so the badge CHANGES whenever the code the server
# loaded changes (catches version skew when judging subjective feel).  Paired
# with the live tyre calibration the engine actually loaded, and the wall-clock
# start time of this server instance.
function build_id()
    srcs = String[joinpath(@__DIR__, "drive.html"), joinpath(@__DIR__, "drive_server.jl")]
    sdir = normpath(joinpath(@__DIR__, "..", "JuliaMotor", "src"))
    isdir(sdir) && append!(srcs, sort(filter(f -> endswith(f, ".jl"), readdir(sdir; join=true))))
    h = zero(UInt)
    for f in srcs
        isfile(f) && (h = hash(read(f, String), h))
    end
    string(h; base=16, pad=16)[1:8]
end
const BUILD = build_id()
const STARTED = Libc.strftime("%H:%M", time())
const VERSTR = string("build <b>", BUILD, "</b> · tyre scale ", LATERAL_CAL.peak_scale,
                      " (", LATERAL_CAL.peak_scale <= 1.0 ? "realistic" : "soft",
                      ") · up ", STARTED)

const PAGE = replace(read(joinpath(@__DIR__, "drive.html"), String), "__BUILD__" => VERSTR)
const THREE_JS = read(joinpath(@__DIR__, "three.min.js"), String)

function handle(sock)
    try
        reqline = readline(sock)
        isempty(reqline) && return
        parts = split(reqline, ' ')
        length(parts) >= 2 || return
        target = parts[2]
        while true                      # drain headers
            l = readline(sock); (isempty(l) || l == "\r") && break
        end
        path, _, query = partition3(target, '?')
        if path == "/" || path == "/index.html"
            respond(sock, "200 OK", "text/html; charset=utf-8", PAGE)
        elseif path == "/track.json"
            respond(sock, "200 OK", "application/json", TRACK_JSON; nocache=false)
        elseif path == "/scene.json"
            respond(sock, "200 OK", "application/json", SCENE_JSON; nocache=false)
        elseif path == "/car.json"
            respond(sock, "200 OK", "application/json", CAR_JSON; nocache=false)
        elseif startswith(path, "/sound/")
            nm = lowercase(path[length("/sound/")+1:end])
            haskey(SOUNDS, nm) ?
                respond(sock, "200 OK", "audio/wav", SOUNDS[nm]; nocache=false) :
                respond(sock, "404 Not Found", "text/plain", "no sound")
        elseif path == "/three.min.js"
            respond(sock, "200 OK", "application/javascript", THREE_JS; nocache=false)
        elseif path == "/step"
            d = parse_query(query)
            inp = DriveInput(throttle=clamp(qf(d, "thr"), 0, 1),
                             brake=clamp(qf(d, "brk"), 0, 1),
                             steer=clamp(qf(d, "steer"), -1, 1),
                             clutch=clamp(qf(d, "clutch"), 0, 1),
                             shift_up=qf(d, "up") != 0,
                             shift_down=qf(d, "down") != 0,
                             autoshift=qf(d, "auto", 1.0) != 0)
            body = advance!(inp, qf(d, "reset") != 0)
            respond(sock, "200 OK", "application/json", body)
        else
            respond(sock, "404 Not Found", "text/plain", "not found")
        end
    catch
    finally
        close(sock)
    end
end

# split "a?b" into (a, '?', b); query empty if no '?'
function partition3(s, c)
    i = findfirst(==(c), s)
    i === nothing ? (s, "", "") : (s[1:i-1], c, s[i+1:end])
end

function serve()
    server = listen(IPv4("127.0.0.1"), PORT)
    println("\n  Drive it:  http://127.0.0.1:$PORT/\n  (W/↑ throttle, S/↓ brake, A/D or ←/→ steer, R respawn, Shift/Ctrl manual shift)\n  Ctrl-C to stop.\n")
    flush(stdout)
    while true
        sock = accept(server)
        @async handle(sock)
    end
end

serve()
