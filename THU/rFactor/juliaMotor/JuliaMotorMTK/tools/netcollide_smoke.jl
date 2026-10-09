# netcollide_smoke.jl — MP-COLLIDE-1 (PO 2026-09-19, the first two-PC race: "cars can see each other but drive through
# each other"). Two REAL sims over UDP loopback at Watkins Glen: the HOST's car stands at s=150 m (on the racing line), the CLIENT's car
# autodrives into it from s=50 m at 25 m/s. The client must register a closing contact with the remote car and must
# never get closer than 2.0 m centre to centre (the cars are ~1.8 m wide alongside, ~4 m nose to tail).
#
# Control (run once by hand, recorded in PRODUCT_BACKLOG.md MP-COLLIDE-1 S1): the same run with JM_NET_COLLIDE=0 passes
# straight through -- that is what makes a PASS here mean the contact, not a lucky miss.
#
# LOADHANG-1 S4 (2026-10-08): the gate went red with no code change. Two faults in the HARNESS, both fixed: (1) both sims
# read the PO's TX wheel (the parked host took its throttle/clutch from it; the client copied the live clutch) -- smoke
# runs now ignore physical controllers (SMOKE_NOJOY); (2) the host was parked on the CENTRELINE while the autodrive
# tracks the AI's RACING line, 1.7 m aside in the original measurement and 2.66 m now, so the client brushed past
# alongside (dmin 2.4-2.7 m, no contact) -- the host now parks ON the racing line (JM_START_LANE=race), on the
# start/finish straight (host s=150, client from s=50), so the approach is head-on whatever line the AI uses.
# Each sim's stdout+stderr share ONE handle (two handles on one file overwrote each other -- garbled logs).
using Printf
const D = normpath(joinpath(@__DIR__, "..", "..", "demo", "native"))
fails = Ref(0)
chk(name, ok, detail) = (@printf("  %-58s %s   %s\n", name, ok ? "PASS" : "FAIL", detail); ok || (fails[] += 1))
println("\n  MP-COLLIDE-1 — remote cars collide (two sims, UDP loopback, Watkins Glen)\n")

hostlog = tempname(); clientlog = tempname()
henv = Dict("TRACK" => "watglen", "JM_SMOKE" => "1", "JM_SMOKE_FRAMES" => "40000", "JM_NET" => "host",
            "JM_START_S" => "150", "JM_START_LANE" => "race", "JM_NET_DIAG" => "60", "JM_AI" => "0")
hio = open(hostlog, "w")
hp = run(pipeline(setenv(`julia --project=$D $(joinpath(D, "drive_native_mtk.jl"))`, merge(copy(ENV), henv));
                  stdout = hio, stderr = hio); wait = false)
t0 = time()
while time() - t0 < 600 && !occursin("JM_START_S", read(hostlog, String)); sleep(5); end
sleep(10)
cenv = Dict("TRACK" => "watglen", "JM_SMOKE" => "1", "JM_SMOKE_FRAMES" => "1200", "JM_NET" => "join",
            "JM_NET_HOST" => "127.0.0.1", "JM_START_S" => "50", "JM_AUTODRIVE" => "1", "JM_AUTODRIVE_V" => "25",
            "JM_NET_DIAG" => "30", "JM_AI" => "0")
try
    open(clientlog, "w") do cio
        run(pipeline(setenv(`julia --project=$D $(joinpath(D, "drive_native_mtk.jl"))`, merge(copy(ENV), cenv));
                     stdout = cio, stderr = cio))
    end
catch
end
# 2026-10-08: the host once printed its SIGTERM stack trace and then deadlocked on exit (futex wait, 15 min) with the
# checks already passed -- `wait(hp)` would have run the gate into its 1800 s timeout. Grace period, then SIGKILL.
try
    kill(hp); tk = time()
    while process_running(hp) && time() - tk < 20; sleep(0.5); end
    process_running(hp) && (println("    (host did not exit on SIGTERM within 20 s -- SIGKILL)"); kill(hp, Base.SIGKILL))
    wait(hp)
catch
end
close(hio)

ct = read(clientlog, String)
nets = [m for m in eachmatch(r"\[net\] t=[0-9.]+ rx=(\d+) .* hits=(\d+) dmin=([0-9.Inf]+)", ct)]
rx = isempty(nets) ? 0 : parse(Int, nets[end][1])
hits = isempty(nets) ? 0 : parse(Int, nets[end][2])
dmin = isempty(nets) ? Inf : parse(Float64, nets[end][3])
for m in eachmatch(r"\[netcollide\][^\n]*", ct); println("    ", m.match); end
chk("the client received the host's car", rx > 0, "rx=$rx")
chk("the client closed on it (it was reachable)", dmin < 6.0, "dmin=$(round(dmin, digits = 2)) m")
chk("a closing contact with the remote car registered", hits >= 1, "hits=$hits")
chk("no pass-through: closest approach >= 2.0 m", dmin >= 2.0, "dmin=$(round(dmin, digits = 2)) m")
println(fails[] == 0 ? "\n  NETCOLLIDE GATE: PASS ✓" : "\n  NETCOLLIDE GATE: FAIL ✗")
exit(fails[] == 0 ? 0 : 1)
