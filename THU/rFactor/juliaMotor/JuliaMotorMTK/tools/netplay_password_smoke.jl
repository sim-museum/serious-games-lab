# GATE: backlog 55 -- the race password, the same rules as the other Serious Games Week games (blank host = open race).
#
# Two real NetLinks per case (host learns the racer from its first packet, the racer joins by address), so the
# packets cross the kernel; no sim. Each case: the racer sends, the host polls, the host sends back, the racer polls.
#
# Stated before the first run (host password / racer password -> joined?):
#   ""    / "x"   -> joined both ways (open race)
#   "abc" / "x"   -> refused: the host never learns the racer, pwbad counts it; the racer hears nothing
#   "abc" / "abc" -> joined both ways
#   "abc" / ""    -> refused both ways (the racer says "that race needs a password")
#   ""    / ""    -> joined (the old behaviour)
#   NEGATIVE CONTROL: a refused case leaves the host's peer list empty, so the host has no one to send to.
include(joinpath(@__DIR__, "..", "..", "demo", "native", "netplay.jl"))
using .NetPlay

fails = Ref(0)
chk(name, ok, detail="") = (println("  ", rpad(name, 58), ok ? "PASS" : "FAIL", "   ", detail);
                            ok || (fails[] += 1); ok)
pump(n, secs) = (t0 = time(); while time() - t0 < secs; NetPlay.poll!(n); sleep(0.01); end)

function case(hpw, cpw, expect, hp)
    host = NetPlay.netopen(port = hp, password = hpw)
    racer = NetPlay.netopen(port = hp + 1, peer = ("127.0.0.1", hp), password = cpw)
    try
        for k in 1:5; NetPlay.send_pose!(racer, 2, k, 1.0, 0.0, 2.0, 0.1); sleep(0.01); end
        pump(host, 0.3)
        sent = NetPlay.send_pose!(host, 1, 1, 5.0, 0.0, 6.0, 0.2)
        pump(racer, 0.3)
        joined = haskey(host.remote, UInt8(2)) && haskey(racer.remote, UInt8(1))
        refused = !haskey(host.remote, UInt8(2)) && !haskey(racer.remote, UInt8(1))
        chk("host \"$hpw\" / racer \"$cpw\" -> " * (expect ? "joined" : "refused"), expect ? joined : refused,
            "host peers=$(length(host.peers)) sent=$sent host pwbad=$(host.pwbad) racer pwbad=$(racer.pwbad)")
        expect || chk("  refused: host has no one to send to", sent == 0)
    finally
        NetPlay.netclose(host); NetPlay.netclose(racer)
    end
end

println("netplay password gate")
case("",    "x",   true,  47781)
case("abc", "x",   false, 47783)
case("abc", "abc", true,  47785)
case("abc", "",    false, 47787)
case("",    "",    true,  47789)
println(fails[] == 0 ? "ALL PASS" : "$(fails[]) FAIL")
exit(fails[] == 0 ? 0 : 1)
