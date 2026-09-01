# netplay.jl — E85 sprint 1: per-car poses on the wire, GPL-style.
#
# GPL's multiplayer is peer-to-peer and deliberately thin: every client simulates ONLY its own car
# and broadcasts that car's state; remote cars are received poses, dead-reckoned between packets.
# Nobody simulates anybody else's physics. That is what makes it survive a modem, and it is what
# this module implements — the transport only. No session logic, no lobby, no racing.
#
# 🔒 THE PHYSICS DIRECTIVE IS NOT WEAKENED BY THIS FILE, and that is enforced by what it does NOT
# import. A remote car is a RECEIVED POSE: never re-simulated, never given a knob. Nothing here
# reaches Car3D, vehicle_3d.jl or powertrain.jl, and nothing here may ever be allowed to. Dead
# reckoning (sprint 2) is interpolation of a received trajectory, not a physics model.
#
# Pure Julia stdlib `Sockets`, matching demo/drive_server.jl's dependency budget.
module NetPlay

using Sockets
export NetLink, netopen, netclose, send_pose!, poll!, remote_poses, predict, remote_poses_at,
       EXTRAP_MAX, STALE_S, is_stale

const MAGIC   = UInt32(0x4A4D5231)      # "JMR1" — a stray packet on a shared port must not parse
const PKTSIZE = 4 + 1 + 4 + 2 + 6*4      # magic + car id + tick + listen port + 6 Float32
const DEFAULT_PORT = 47700

"""One peer's view of the session. `remote` maps car id -> the last pose received for it."""
# TWO SOCKETS PER PEER, and this is not tidiness — it is the whole reason this module works.
#
# In Julia/libuv, calling `send` on a UDPSocket that has an OUTSTANDING `recvfrom` cancels that
# pending receive. A peer that sends first therefore kills its own reader and never hears anything
# again. That is exactly what happened here: the host (which receives before it ever sends) worked
# perfectly and got all 20 packets, while the client (which sends first) reported rx=0 with a live
# reader task and no error — a one-way transport that was really a self-inflicted deafness.
# Reproduced with raw sockets, and confirmed by inverting the order: start the reader AFTER the
# first send and the same code receives fine.
#
# So: `rsock` is bound to our listen port and ONLY ever receives; `ssock` is unbound and ONLY ever
# sends. Because `ssock`'s source port is then ephemeral and meaningless, every packet carries the
# sender's LISTEN port, and that is what a host learns a peer by.
mutable struct NetLink
    rsock::UDPSocket
    ssock::UDPSocket
    port::Int
    peers::Vector{Tuple{IPAddr,Int}}          # who we send to
    remote::Dict{UInt8,NamedTuple}
    rxtime::Dict{UInt8,Float64}                # when each id's newest packet ARRIVED (dead reckoning)
    inbox::Channel{Tuple{IPAddr,Int,Vector{UInt8}}}
    task::Union{Task,Nothing}
    rx::Int                                    # packets accepted
    dropped::Int                               # packets rejected (bad magic / wrong size)
    open::Bool
    readererr::String                          # non-empty if the reader task died (see poll!)
end

"""    netopen(; port, peer) -> NetLink

`peer = nothing` hosts: bind and learn each peer's address from its first packet (so a client
needs no configuration, which is how GPL behaved). `peer = (host, port)` joins.

A background task owns the socket and pushes datagrams into a channel. That is not decoration:
`recvfrom` BLOCKS, so calling it from the render loop would stall the frame whenever no packet had
arrived — and the obvious workaround (spawn a task per poll and abandon it on timeout) leaves a
dangling reader that eats the NEXT packet. One long-lived reader, one channel, and `poll!` never
blocks.
"""
function netopen(; port::Int = DEFAULT_PORT, peer = nothing)
    r = UDPSocket()
    bind(r, ip"0.0.0.0", port) || error("netopen: cannot bind UDP port $port")
    sk = UDPSocket()
    peers = Tuple{IPAddr,Int}[]
    peer === nothing || push!(peers, (getaddrinfo(String(peer[1])), Int(peer[2])))
    n = NetLink(r, sk, port, peers, Dict{UInt8,NamedTuple}(), Dict{UInt8,Float64}(),
                Channel{Tuple{IPAddr,Int,Vector{UInt8}}}(256), nothing, 0, 0, true, "")
    n.task = @async begin
        while n.open
            try
                # recvfrom returns (Sockets.InetAddr, Vector{UInt8}) -- a STRUCT, not a tuple.
                # The first cut wrote `(from, buf) = recvfrom(...)` then indexed `from[1]`/`from[2]`,
                # which throws; the bare `catch ... break` below swallowed it and killed this reader
                # on the first packet. Both probes then reported rx=0 dropped=0 -- no packets AND no
                # rejects, which is the signature of a reader that is not running at all. Hence the
                # error is now REPORTED, not just survived.
                (from, buf) = recvfrom(n.rsock)
                isopen(n.inbox) && put!(n.inbox, (from.host, Int(from.port), buf))
            catch e
                n.open || break                      # normal shutdown: netclose closed the socket
                if get(ENV, "JM_NET_TRACE", "0") != "0"
                    @warn "netplay reader stopped" exception=(e, catch_backtrace())
                end
                n.readererr = string(typeof(e))
                break
            end
        end
    end
    n
end

function netclose(n::NetLink)
    n.open = false
    try; close(n.rsock); catch; end
    try; close(n.ssock); catch; end
    try; close(n.inbox); catch; end
    nothing
end

"""Broadcast one car's pose to every known peer. Six Float32: x, y, z, yaw, speed, steer."""
function send_pose!(n::NetLink, id::Integer, tick::Integer, x, y, z, yaw, v = 0.0, steer = 0.0)
    io = IOBuffer()
    write(io, MAGIC); write(io, UInt8(id)); write(io, UInt32(tick))
    write(io, UInt16(n.port))                 # our LISTEN port — ssock's source port is ephemeral
    for f in (x, y, z, yaw, v, steer); write(io, Float32(f)); end
    buf = take!(io)
    for (h, p) in n.peers
        send(n.ssock, h, p, buf)
    end
    length(n.peers)
end

"""Drain whatever has arrived. NEVER blocks — it takes only what the reader task has already queued.

A host learns a peer here, on that peer's first packet. Anything without the magic is counted as
dropped rather than discarded silently: "no remote cars" and "the packets are being thrown away"
look identical from outside and need different fixes.
"""
function poll!(n::NetLink; maxpkts::Int = 64)
    got = 0
    while got < maxpkts && isready(n.inbox)
        (host, port, buf) = take!(n.inbox)
        if length(buf) != PKTSIZE
            n.dropped += 1; continue
        end
        io = IOBuffer(buf)
        if read(io, UInt32) != MAGIC
            n.dropped += 1; continue
        end
        id = read(io, UInt8); tick = read(io, UInt32)
        lport = Int(read(io, UInt16))          # reply here, NOT to the ephemeral source port
        x = read(io, Float32); y = read(io, Float32); z = read(io, Float32)
        yaw = read(io, Float32); v = read(io, Float32); st = read(io, Float32)
        n.remote[id] = (tick = Int(tick), x = Float64(x), y = Float64(y), z = Float64(z),
                        yaw = Float64(yaw), v = Float64(v), steer = Float64(st))
        n.rxtime[id] = time()
        n.rx += 1; got += 1
        any(p -> p[1] == host && p[2] == lport, n.peers) || push!(n.peers, (host, lport))
    end
    got
end

"""The remote cars, as an id-ordered vector — the shape the AI field already draws."""
remote_poses(n::NetLink) = [(id, n.remote[id]) for id in sort(collect(keys(n.remote)))]

# ── E85-S2: DEAD RECKONING ──────────────────────────────────────────────────────────────────────
# A remote car's pose arrives at the packet rate, not the frame rate. At 10 Hz the newest packet is
# between 0 and 100 ms old, so simply HOLDING it puts the car `v * age` behind where it is — 3 m on
# average at 60 m/s, 6 m at worst. At racing speeds that is not a stutter, it is a car in the wrong
# place, and it is worst exactly when it matters (side by side at speed).
#
# `predict` advances the last known pose along its own heading at its own speed. What it CANNOT
# follow is curvature: the residual is the second-order term, about ½·a_lat·Δt², which at 1.5 g and
# 100 ms is ~7 cm. So this trades a first-order error for a second-order one and nothing else —
# no smoothing, no history, no filter. Deliberately: a filter would need tuning and would hide the
# transport's real behaviour behind it, and the gate could no longer state a closed-form
# expectation to check against.
#
# ⚠️ It is a PURE function of (pose, Δt) so the gate can drive it with a synthetic trajectory whose
# true position is known in closed form, instead of needing two live processes and a stopwatch.

"""    predict(p, dt) -> NamedTuple

`p` as delivered by `poll!`, advanced `dt` seconds along its own heading at its own speed.
`dt <= 0` returns `p` unchanged. `y` is NOT extrapolated: height comes from the terrain under the
car, and guessing it is how a remote car ends up flying (see E104(a) — a car's drawn height must be
the ground beneath it, never a value carried from somewhere else).
"""
function predict(p, dt::Real)
    dt <= 0 && return p
    (; x = p.x + p.v*cos(p.yaw)*dt, y = p.y, z = p.z + p.v*sin(p.yaw)*dt,
       yaw = p.yaw, v = p.v, steer = p.steer, tick = p.tick)
end

# ── E85-S3: JITTER, LOSS AND SILENCE ────────────────────────────────────────────────────────────
# S2 measured dead reckoning against a PERFECT 10 Hz stream. Real links drop and delay packets, and
# the two failure modes are different in kind:
#
#   LOSS/JITTER — the newest pose is simply older. The error is still ½·a·Δt², so it grows with the
#     SQUARE of the gap: one dropped packet at 10 Hz doubles Δt and quadruples the error (0.075 m ->
#     0.30 m). That is a graceful degradation and needs no special handling.
#
#   SILENCE — a peer that stops sending is NOT a peer moving predictably. Extrapolating it forever
#     produces a ghost: a car that drives on smoothly, through corners it cannot take, into
#     scenery, for as long as the session lasts. That is worse than showing nothing, because it is
#     indistinguishable from a real car right up to the moment you crash into it.
#
# So extrapolation is CAPPED at EXTRAP_MAX, and past STALE_S the car is dropped from the field
# entirely. Between the two the car freezes in place -- honest about being out of date rather than
# inventing motion.

"""How far ahead dead reckoning may extrapolate (s). Past this the pose FREEZES: beyond a couple of
packet intervals a straight-line guess is not evidence about where a car is, and a frozen car is a
smaller lie than a confidently wrong one."""
const EXTRAP_MAX = 0.25

"""After this long with no packet (s) a peer is GONE and is removed from the field, rather than
left driving as a ghost."""
const STALE_S = 2.0

"""True when `age` seconds have passed with no packet from a peer."""
is_stale(age::Real) = age >= STALE_S

"""    remote_poses_at(n, now) -> [(id, pose)]

`remote_poses`, dead-reckoned to `now` using each packet's own arrival time, with the staleness
policy applied: extrapolation capped at `EXTRAP_MAX`, and peers silent for `STALE_S` OMITTED.
`now` is passed in rather than read here so a caller can use the frame's timestamp and a test can
use a fixed clock.
"""
function remote_poses_at(n::NetLink, now::Real)
    out = Tuple{UInt8,NamedTuple}[]
    for id in sort(collect(keys(n.remote)))
        age = now - get(n.rxtime, id, now)
        is_stale(age) && continue                       # gone, not guessed at
        push!(out, (id, predict(n.remote[id], min(age, EXTRAP_MAX))))
    end
    out
end

end # module
