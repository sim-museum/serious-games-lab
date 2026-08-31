include("gpldat.jl"); using .GPLDat; include("gpltrack.jl"); using .GPLTrack; include("ai.jl"); using .RaceAI; include("gpl_lp.jl"); using .GPLLP
using Statistics
T = "/home/admin/sgl-julia-racer/THU/WP/drive_c/Sierra/GPL/tracks/monza"
d = GPLDat.parse_dat(joinpath(T, "monza.DAT")); tmp = tempname()*".trk"; write(tmp, d["monza.trk"])
cl = GPLTrack.trk_centreline(tmp); line = RaceAI.build_line(cl, (x,z) -> 0.0)
gpl = min.(lp_speed_mps(read_lp(joinpath(T, "race.lp"))) .* 1.016, 2.41*36)
# 1. geometry at the divergences: our κ (radius) vs GPL speed; and the raw .trk section radius there
b = read(tmp); u32(o) = UInt32(b[o+1]) | UInt32(b[o+2])<<8 | UInt32(b[o+3])<<16 | UInt32(b[o+4])<<24; i32(o) = reinterpret(Int32, u32(o)); TRK = 19685.03937
traces = Int(u32(12)); sections = Int(u32(16)); wallsize = Int(u32(20)); secbase = 28 + 64 + sections*4 + 32*traces*sections + wallsize
ang(s) = i32(secbase + s*52 + 12) * 2pi / 2.0^32; wrap(x) = x > pi ? x-2pi : x < -pi ? x+2pi : x
secL = [i32(secbase + s*52 + 8)/TRK for s in 0:sections-1]; secR = [ (dth = wrap(ang(mod(s+1,sections)) - ang(s)); abs(dth) < 1e-6 ? Inf : secL[s+1]/abs(dth)) for s in 0:sections-1]
cum = cumsum(vcat(0.0, secL))
println("our line κ/radius vs GPL speed vs .trk section radius, s = 880..1080 step 12:")
for s in 880:12:1080
    i = clamp(round(Int, s/3)+1, 1, length(line.κ)); k = line.κ[i]; sec = searchsortedlast(cum, s)
    println("  s=", s, "  ours R=", round(1/max(k,1e-6), digits=0), " m  v_ours=", round(sqrt(8.0/max(k,1e-4)), digits=1), "  GPL v=", round(gpl[min(i,end)], digits=1), "   .trk section ", sec, " R=", isfinite(secR[sec]) ? round(secR[sec], digits=0) : "straight", " L=", round(secL[sec], digits=1))
end
# 2. how much is the grip cap alone? free profile at amax=8 vs 14 (vmax lifted to GPL's 86.8)
for (am, vm) in ((8.0, 74.0), (11.0, 74.0), (14.0, 86.8))
    (fs, fv) = RaceAI.free_speed_profile(line; amax = am, vmax = vm, ds = 3.0); n = min(length(fv), length(gpl))
    println("  amax=", am, " vmax=", vm, ": lap ", round(sum(3.0 ./ fv), digits=1), " s   mean|diff| vs GPL ", round(mean(abs.(fv[1:n] .- gpl[1:n])), digits=2), "   min speed ", round(minimum(fv), digits=1))
end
println("  GPL lap ", round(sum(3.0 ./ gpl), digits=1), " s")
# implied lateral accel GPL carries: v^2 * κ_ours where our κ is trusted (straight-ish sections) -- report the max of v_gpl^2*κ_trk using .trk radius per section
lat = Float64[]; for s in 0:3:Int(floor(cum[end]))-3; sec = searchsortedlast(cum, s); isfinite(secR[sec]) || continue; i = clamp(round(Int, s/3)+1,1,length(gpl)); push!(lat, gpl[i]^2/secR[sec]); end
println("  GPL lateral accel from .trk section radii: p50 ", round(quantile(lat,.5), digits=1), " p90 ", round(quantile(lat,.9), digits=1), " max ", round(maximum(lat), digits=1), " m/s^2")
