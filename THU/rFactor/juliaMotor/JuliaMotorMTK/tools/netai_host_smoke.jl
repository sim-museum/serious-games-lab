# GATE: MP-5 -- host-authoritative AI over the wire.
#
# The host sends each AI car as a pose packet with an id from AI_ID0 up; the client must receive
# them as remote cars, distinct from the host's own car, and map each id to the chassis slot the
# draw uses. Two real NetLinks (two UDP sockets each) in one process, so the packets cross the
# kernel; no sim, because the sim needs ~2 min and 3 GB and the question here is the wire and the
# id/chassis contract, not the render loop (netai_smoke.jl covers the sim-side guard).
#
# Stated before the first run:
#   - after the host sends 1 human + 3 AI poses, the client knows exactly ids {1,10,11,12}
#   - each AI pose comes back with the x/z/yaw/v it was sent with (Float32 wire, 1e-3 tolerance)
#   - chassis_slot: 10->1, 12->3, a human id ->1, an AI id past the loaded models -> the last model,
#     and 0 models -> 0 (the draw must skip)
#   - NEGATIVE CONTROL: a client that never received the AI ids has none of them (the assertion
#     can report zero), and a human id never maps to an AI slot other than 1.
include(joinpath(@__DIR__, "..", "..", "demo", "native", "netplay.jl"))
using .NetPlay

fails = Ref(0)
chk(name, ok, detail="") = (println("  ", rpad(name, 58), ok ? "PASS" : "FAIL", "   ", detail);
                            ok || (fails[] += 1); ok)
pump(n, secs) = (t0 = time(); while time() - t0 < secs; NetPlay.poll!(n); sleep(0.01); end)

const HP = 47771; const CP = 47772
host   = NetPlay.netopen(port = HP)                        # learns the peer from its first packet
client = NetPlay.netopen(port = CP, peer = ("127.0.0.1", HP))

# control first: nothing has been sent, the client must know NO ids
pump(client, 0.2)
chk("control: client knows no cars before any packet", isempty(client.remote), "$(length(client.remote)) known")

NetPlay.send_pose!(client, 2, 0, 1.0, 0.0, 2.0, 0.1, 5.0, 0.0)   # client announces itself
pump(host, 0.5)
chk("host learned the client as a peer", length(host.peers) == 1, "peers=$(length(host.peers))")

# the host's frame: its own car (id 1) then its 3-car AI field (ids AI_ID0 ..)
ai = [(100.0, 3.5, 200.0, 0.30, 41.0), (110.0, 3.6, 210.0, 0.35, 42.0), (120.0, 3.7, 220.0, 0.40, 43.0)]
NetPlay.send_pose!(host, 1, 1000, 90.0, 3.4, 190.0, 0.25, 40.0, 0.0)
for (k, p) in enumerate(ai)
    NetPlay.send_pose!(host, NetPlay.AI_ID0 + (k - 1), 1000, p[1], p[2], p[3], p[4], p[5], 0.0)
end
pump(client, 0.7)
ids = sort(Int.(collect(keys(client.remote))))
chk("client received exactly the host car + 3 AI ids", ids == [1, 10, 11, 12], "ids=$(ids)")
chk("no packet was dropped as malformed", client.dropped == 0, "dropped=$(client.dropped)")
ok = true
for (k, p) in enumerate(ai)
    q = get(client.remote, NetPlay.AI_ID0 + (k - 1), nothing)
    q === nothing && (global ok = false; continue)
    global ok &= abs(q.x - p[1]) < 1e-3 && abs(q.z - p[3]) < 1e-3 && abs(q.yaw - p[4]) < 1e-3 && abs(q.v - p[5]) < 1e-3
end
chk("each AI pose arrives with its x/z/yaw/v intact", ok)
rp = NetPlay.remote_poses_at(client, time())
chk("remote_poses_at returns all four (none stale)", length(rp) == 4, "n=$(length(rp))")

chk("chassis_slot: first AI id -> slot 1",        NetPlay.chassis_slot(10, 5) == 1)
chk("chassis_slot: third AI id -> slot 3",        NetPlay.chassis_slot(12, 5) == 3)
chk("chassis_slot: AI id past the loaded models -> last", NetPlay.chassis_slot(14, 2) == 2)
chk("chassis_slot: human ids draw with slot 1",   NetPlay.chassis_slot(1, 5) == 1 && NetPlay.chassis_slot(2, 5) == 1)
chk("chassis_slot: no models -> 0 (draw skips)",  NetPlay.chassis_slot(11, 0) == 0)

NetPlay.netclose(host); NetPlay.netclose(client)
println(fails[] == 0 ? "ALL PASS" : "FAILURES: $(fails[])")
exit(fails[] == 0 ? 0 : 1)
