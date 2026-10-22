# GATE: FALSEWRECK-1 -- a backdrop bank is not a wall.
#
# PO 2026-10-21: "car starts fishtailing, then comes to stop on hill, but no crash, yet message says it's a wreck"
# (video 261021_fishtail.mp4 at 256 s; log monza 2026-10-21 16-18-14): off the road at Serraglio at 198 km/h onto open
# grass, the car stopped dead in one frame -- `[WRECK] CLOSING speed 53.8 m/s into a solid`, 24 obstacle hits at
# (-472.7, 72.7). The obstacle was `brbk2`, a Monza backdrop bank (GPL's `bk` tail: thin painted panels), whose faces the
# per-face obstacle builder made solid. Here JM_OBSAT lists the drawn obstacles at that point: none now; the control
# (JM_OBS_BACKDROP=1, the old rule) must still list the bank, so the probe is known to see it.
const D = normpath(joinpath(@__DIR__, "..", "..", "demo", "native"))
fails = Ref(0)
check(name, ok, d = "") = (ok || (fails[] += 1); println("  ", ok ? "PASS" : "FAIL", "  ", rpad(name, 64), d))
function obsat(extra)
    env = merge(Dict(ENV), Dict("TRACK" => "monza", "JM_SMOKE" => "1", "JM_OBSAT" => "-472.7,72.7,-62"), extra)
    log = tempname()
    run(pipeline(ignorestatus(setenv(`julia -t 2 --project=$D $(joinpath(D, "drive_native_mtk.jl"))`, env)); stdout = log, stderr = log))
    t = read(log, String); rm(log; force = true); t
end
println("FALSEWRECK gate: Monza's backdrop banks are not solid")
c = obsat(Dict("JM_OBS_BACKDROP" => "1"))
check("control (old rule): the probe ran", occursin("[obsat] obstacles near", c))
check("control (old rule): the bank brbk2 is a wall at the PO's spot", occursin(r"brbkt1\s+wall", c))
t = obsat(Dict{String,String}())
check("the probe ran", occursin("[obsat] obstacles near", t))
m = match(r"\[obsat\] obstacles near \(-472\.7, 72\.7\):\n((?:     .*\n)*)", t)
check("no obstacle at the PO's spot (Serraglio grass, 3248 m)", m !== nothing && isempty(strip(m[1])), m === nothing ? "" : strip(m[1]))
b = match(r":backdrop => (\d+)", t)
check("the builder skipped the backdrop faces", b !== nothing && parse(Int, b[1]) > 0, b === nothing ? "" : "$(b[1]) faces")
check("no error", !occursin(r"ERROR|Stacktrace"i, t))
println(fails[] == 0 ? "FALSEWRECK: PASS" : "FALSEWRECK: FAIL ($(fails[]))")
exit(fails[] == 0 ? 0 : 1)
