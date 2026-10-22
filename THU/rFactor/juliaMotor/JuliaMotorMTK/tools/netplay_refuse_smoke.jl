# GATE: JR-REFUSE-1 (PO 2026-10-22) -- a refused racer is TOLD why, and a racer that hears nothing says so.
#
# Real sockets on 127.0.0.1, no sim. Stated before the first run:
#   host "abc" / racer "x"  -> racer.refused says "Wrong password"; the racer then stops sending (send_pose! -> 0)
#   host "abc" / racer ""   -> racer.refused says "needs a password"
#   host ""    / racer "x"  -> joined, racer.refused == "" (NEGATIVE CONTROL: an open race refuses no one)
#   a packet with another build tag     -> host skew=1, racer.refused says "Different version"
#   a packet in the pre-password layout -> the same (old builds are named, not dropped as malformed)
#   6 junk bytes                        -> dropped, racer.refused stays "" (only REFMAGIC refuses)
#   racer joined to a dead port         -> status_text "" at 1 s, "No reply from the host" past NOREPLY_S
include(joinpath(@__DIR__, "..", "..", "demo", "native", "netplay.jl"))
using .NetPlay, Sockets

fails = Ref(0)
chk(name, ok, detail="") = (println("  ", rpad(name, 58), ok ? "PASS" : "FAIL", "   ", detail);
                            ok || (fails[] += 1); ok)
pump(n, secs) = (t0 = time(); while time() - t0 < secs; NetPlay.poll!(n); sleep(0.01); end)

function pwcase(hpw, cpw, want, hp)
    host = NetPlay.netopen(port = hp, password = hpw)
    racer = NetPlay.netopen(port = hp + 1, peer = ("127.0.0.1", hp), password = cpw)
    try
        for k in 1:5; NetPlay.send_pose!(racer, 2, k, 1.0, 0.0, 2.0, 0.1); sleep(0.01); end
        pump(host, 0.3); pump(racer, 0.3)
        chk("host \"$hpw\" / racer \"$cpw\" -> " * (isempty(want) ? "not refused" : "\"$want\""),
            isempty(want) ? isempty(racer.refused) : occursin(want, racer.refused), repr(racer.refused))
        isempty(want) || chk("  refused racer stops sending", NetPlay.send_pose!(racer, 2, 9, 1.0, 0.0, 2.0, 0.1) == 0)
        isempty(want) || chk("  on screen: status_text is the reason", NetPlay.status_text(racer) == racer.refused)
    finally
        NetPlay.netclose(host); NetPlay.netclose(racer)
    end
end

# A racer from another build, faked byte by byte: the new layout with another build tag, or the old layout (no
# password tag). The NetLink racer only listens; the fake packet names its port as the listen port.
function vercase(name, old, hp)
    host = NetPlay.netopen(port = hp)
    racer = NetPlay.netopen(port = hp + 1, peer = ("127.0.0.1", hp))
    raw = UDPSocket()
    try
        io = IOBuffer(); write(io, NetPlay.MAGIC); write(io, NetPlay.BUILDTAG + UInt32(1))
        old || write(io, UInt32(0))
        write(io, UInt8(2)); write(io, UInt32(1)); write(io, UInt16(hp + 1))
        for f in 1:6; write(io, Float32(0)); end
        pkt = take!(io)
        for k in 1:3; send(raw, ip"127.0.0.1", hp, pkt); sleep(0.01); end
        pump(host, 0.3); pump(racer, 0.3)
        chk(name * " -> \"Different version\"", occursin("Different version", racer.refused),
            "len=$(length(pkt)) host skew=$(host.skew) dropped=$(host.dropped) refused=$(repr(racer.refused))")
    finally
        close(raw); NetPlay.netclose(host); NetPlay.netclose(racer)
    end
end

println("netplay refusal gate")
pwcase("abc", "x",  "Wrong password",   47801)
pwcase("abc", "",   "needs a password", 47803)
pwcase("",    "x",  "",                 47805)
vercase("racer with another build tag", false, 47807)
vercase("racer in the pre-password layout", true, 47809)
let r = NetPlay.netopen(port = 47812, peer = ("127.0.0.1", 47811)), raw = UDPSocket()
    send(raw, ip"127.0.0.1", 47812, UInt8[1, 2, 3, 4, 5, 6]); sleep(0.05); pump(r, 0.2)
    chk("6 junk bytes -> dropped, not a refusal", r.dropped == 1 && isempty(r.refused), "dropped=$(r.dropped)")
    chk("no host: silent at 1 s", NetPlay.status_text(r, r.t0 + 1.0) == "")
    chk("no host: \"No reply from the host\" past $(NetPlay.NOREPLY_S) s",
        startswith(NetPlay.status_text(r, r.t0 + NetPlay.NOREPLY_S + 1), "No reply from the host"),
        NetPlay.status_text(r, r.t0 + NetPlay.NOREPLY_S + 1))
    close(raw); NetPlay.netclose(r)
end
println(fails[] == 0 ? "ALL PASS" : "$(fails[]) FAIL")
exit(fails[] == 0 ? 0 : 1)
