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
export NetLink, netopen, netclose, send_pose!, poll!, remote_poses

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
    n = NetLink(r, sk, port, peers, Dict{UInt8,NamedTuple}(),
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
        n.rx += 1; got += 1
        any(p -> p[1] == host && p[2] == lport, n.peers) || push!(n.peers, (host, lport))
    end
    got
end

"""The remote cars, as an id-ordered vector — the shape the AI field already draws."""
remote_poses(n::NetLink) = [(id, n.remote[id]) for id in sort(collect(keys(n.remote)))]

end # module
