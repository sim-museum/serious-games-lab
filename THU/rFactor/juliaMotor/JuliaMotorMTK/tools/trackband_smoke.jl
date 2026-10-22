# GATE: TRACKBAND-1 -- each GPL segment tree is drawn in ONE band (near / mid / far) by its lap distance from the eye.
#
# MONZAWALL-1 found every segment tree's near (slots 1-4), mid (5-6) and far (7) versions of the track drawn at once:
# ~40 % of Monza's track mesh a second or third copy of the same surfaces, fighting wherever the copies differ. gpl.exe
# (FUN_00485ff0) draws near within 117 m along the lap of the camera, mid to 312 m, far beyond. Checks:
#   * bandranges! (lifted from the sim, synthetic lap of one triangle per bin and band): every window bin is drawn by
#     exactly one band, untagged geometry over the window (or the whole lap for Monza's graded draw);
#   * both track draw branches use it for banded parts;
#   * Monza: the parser tags the trees' triangles and the eye at three lap positions draws markedly fewer triangles than
#     with every band (JM_TRACKBAND_DIAG); the control JM_TRACKBAND=0 prints no band line and draws them all.
const D = normpath(joinpath(@__DIR__, "..", "..", "demo", "native"))
src = read(joinpath(D, "drive_native_mtk.jl"), String); ml = read(joinpath(D, "main_loop.jl"), String)
fails = Ref(0)
check(name, ok, d = "") = (ok || (fails[] += 1); println("  ", ok ? "PASS" : "FAIL", "  ", rpad(name, 72), d))
println("TRACKBAND gate: one band per segment tree")
fr = match(r"\nfunction bandranges!\(r, off, c, whole = false\)\n.*?\n    r\nend\n"s, src)
check("bandranges! is in the sim", fr !== nothing)
if fr !== nothing
    M = Module(:TB)
    Core.eval(M, :(const LAPBIN = 100.0; const LAPWIN = 914.0; const TRACKBAND_NEAR = 117.0; const TRACKBAND_MID = 312.0;
                   const _LW = (L = 5762.2,); const LAPNB = 58))
    Base.include_string(M, fr.match)
    N = 58; off = Int32.(0:3:3*4N); r = Tuple{Int,Int}[]
    inw(b, c) = abs(mod(b*100.0 + 50 - c + 5762.2/2, 5762.2) - 5762.2/2) <= 914 + 100   # generous: the window's bins
    bad, nearok = let bad = 0, nearok = true        # (a let: top-level loops would make these soft-scope locals)
    for whole in (false, true), c in 0.0:7.3:5762.2
        M.bandranges!(r, off, c, whole)
        cnt = zeros(Int, 4N); for (f, n) in r, k in f÷3+1:(f+n)÷3; cnt[k] += 1; end
        maximum(cnt) > 1 && (bad += 1; continue)
        for b in 0:N-1
            t = cnt[b+N+1] + cnt[b+2N+1] + cnt[b+3N+1]; u = cnt[b+1]
            (whole ? (t == 1 && u == 1) : (t == u && (u == 0 || inw(b, c)))) || (bad += 1; break)
        end
        cb = clamp(floor(Int, mod(c, 5762.2)/100), 0, N-1); nearok &= cnt[cb+N+1] == 1   # the eye's own bin: near
    end
    bad, nearok
    end
    check("every bin drawn by exactly one band, untagged with it (window / whole lap)", bad == 0, "$bad bad eye positions")
    check("the eye's own bin draws the near band", nearok)
end
check("the lap-window draw uses it for banded parts", occursin("for (f0, n0) in bandranges!(BANDR, TRACKLAPOFF[ti], _clap)\n", ml))
check("Monza's graded draw uses it over the whole lap", occursin("for (f0, n0) in bandranges!(BANDR, TRACKLAPOFF[ti], _clap, true)", ml))
function diag(extra)
    env = merge(Dict(ENV), Dict("TRACK" => "monza", "JM_SMOKE" => "1", "JM_TRACKBAND_DIAG" => "300,2500,4600"), extra)
    log = tempname()
    run(pipeline(ignorestatus(setenv(`julia -t 2 --project=$D $(joinpath(D, "drive_native_mtk.jl"))`, env)); stdout = log, stderr = log))
    t = read(log, String); rm(log; force = true); t
end
t = diag(Dict{String,String}())
m = match(r"\[trackband\] (\d+) track triangles in (\d+) segment trees", t)
check("Monza: the trees' triangles are tagged", m !== nothing && parse(Int, m[1]) >= 50_000 && parse(Int, m[2]) >= 60,   # 56,342 in 67 of 89 (2026-10-21): copies shared by bands stay untagged
      m === nothing ? "no [trackband] line" : "$(m[1]) in $(m[2]) trees")
rows = [parse.(Int, (x[1], x[2], x[3], x[4])) for x in eachmatch(r"\[trackband diag\] eye at s \d+: (\d+) of (\d+) triangles drawn \((\d+) of (\d+) whole lap\)", t)]
check("three eye positions measured", length(rows) == 3)
for (k, (n1, n0, w1, w0)) in enumerate(rows)
    # 2026-10-21: 75 / 61 / 59 % of the window (s 300 has the most untagged ground), 65-68 % of the whole lap
    check("  eye $k: one band draws <= 85 % of the window, <= 75 % of the whole lap", n1 <= 0.85n0 && w1 <= 0.75w0,
          "$n1 / $n0, $w1 / $w0")
end
check("no error", !occursin(r"ERROR|Stacktrace"i, t))
c = diag(Dict("JM_TRACKBAND" => "0"))
cr = [parse.(Int, (x[1], x[2])) for x in eachmatch(r"\[trackband diag\] eye at s \d+: (\d+) of (\d+) triangles drawn", c)]
check("control JM_TRACKBAND=0: no band line, every band drawn", !occursin("[trackband] ", c) && length(cr) == 3 && all(x -> x[1] == x[2], cr))
println(fails[] == 0 ? "TRACKBAND: PASS" : "TRACKBAND: FAIL ($(fails[]))")
exit(fails[] == 0 ? 0 : 1)
