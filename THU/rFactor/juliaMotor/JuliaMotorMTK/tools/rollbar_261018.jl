# IRPLAN-3 E3: body roll per bar setting, from the gold alone.  Per file: the slope (least squares, 0.4-1.1 g, steady)
# of the left-right shock-deflection difference per g at each axle, and the roll angle per g from the ride heights.
#   julia --project=JuliaMotorMTK JuliaMotorMTK/tools/rollbar_261018.jl <file.ibt> ...
include(joinpath(@__DIR__, "..", "src", "ibt.jl")); using .IBT
using Printf, Statistics
sm(x, n) = (h = n ÷ 2; [mean(@view x[max(1, k-h):min(length(x), k+h)]) for k in eachindex(x)])
slope(x, y) = (mx = mean(x); sum((x .- mx) .* (y .- mean(y))) / sum((x .- mx) .^ 2))
@printf("%-26s %-22s %-22s %8s %8s %8s %8s %6s\n", "file", "front bar", "rear bar", "dF mm/g", "dR mm/g", "roll°/g", "F share", "n")
for fn in ARGS
    f = IBT.ibt_open(fn); ch(n) = Float64.(IBT.channel(f, n)); y = IBT.session_yaml(f)
    bar(sec) = (s = split(split(y, "  " * sec * ":\n")[end], "\n  LeftFront")[1];
                strip(match(r"ArbDiameter: ([^\n]*)", s).captures[1]) * " " * strip(match(r"ArbArms: ([^\n]*)", s).captures[1]))
    cs = split(y, "CarSetup:")[2]
    fb = bar_front = (m = match(r"Front:\n\s+ArbArms: ([^\n]*)\n\s+ArbDiameter: ([^\n]*)", cs); m === nothing ? "?" : m.captures[2] * " " * m.captures[1])
    rb = (m = match(r"Rear:\n\s+FuelLevel: [^\n]*\n\s+ArbDiameter: ([^\n]*)\n\s+ArbArms: ([^\n]*)", cs); m === nothing ? "?" : m.captures[1] * " " * m.captures[2])
    ay = sm(ch("LatAccel"), 61) ./ 9.80665; v = ch("Speed")
    dF = sm(ch("LFshockDefl") .- ch("RFshockDefl"), 61) .* 1000
    dR = sm(ch("LRshockDefl") .- ch("RRshockDefl"), 61) .* 1000
    roll = sm(ch("Roll"), 61) .* (180 / pi)
    ok = (v .> 10) .& (0.4 .< abs.(ay) .< 1.1)
    n = count(ok); n < 200 && (println(basename(fn), ": too few steady samples"); continue)
    sF = slope(ay[ok], dF[ok]); sR = slope(ay[ok], dR[ok]); sr = slope(ay[ok], roll[ok])
    @printf("%-26s %-22s %-22s %8.2f %8.2f %8.3f %8.3f %6d\n", basename(fn)[9:min(end, 34)], fb, rb, sF, sR, sr, sF / (sF + sR), n)
end
