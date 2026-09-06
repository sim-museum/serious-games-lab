# TRACKGOLD-1 S1: what does the Ring's .trk PLACE (0x0E nodes) that the sim never loads?
const J = "/home/admin/sgl-julia-racer/THU/rFactor/juliaMotor/demo/native"
include(joinpath(J, "gpltrack.jl")); using .GPLTrack
base = "/home/admin/sgl-julia-racer/THU/WP/drive_c/Sierra/GPL/tracks/nurburg"
ztrk = joinpath(base, "nurburg.3do")
names = Set{String}()
for f in readdir(base); endswith(lowercase(f), ".3do") && push!(names, lowercase(replace(f, r"\.3do$"i => ""))); end
println("loose .3do files in the Ring dir: ", length(names))
insts_all = GPLTrack.trackside_objects(ztrk; objnames = Set{String}())   # nothing matches: 0 by construction
insts = GPLTrack.trackside_objects(ztrk; objnames = names)
println("placements matching a loose .3do: ", length(insts))
cnt = Dict{String,Int}(); for i in insts; cnt[i.name] = get(cnt, i.name, 0) + 1; end
for (n, c) in sort(collect(cnt); by = x -> -x[2])[1:min(end, 40)]; println("  ", rpad(n, 14), c); end
# and the names the .trk references that have NO loose file (they may live in nurburg.dat)
b = read(ztrk); u32(o) = UInt32(b[o+1]) | (UInt32(b[o+2]) << 8) | (UInt32(b[o+3]) << 16) | (UInt32(b[o+4]) << 24)
strn = prim = 0; strnsz = 0; o = 12
while o + 12 <= length(b)
    t = String(b[o+1:o+4]); sz = Int(u32(o+8)); data = o + 12
    t == "NRTS" && (global strn = data; global strnsz = sz); t == "MIRP" && (global prim = data)
    global o = data + sz; global o += (4 - o % 4) % 4
end
off2name = Dict{Int,String}(); let cur = UInt8[], p = 0
    for i in strn:strn+strnsz-1
        c = b[i+1]; if c == 0xFF; break; elseif c == 0x00; off2name[p] = String(copy(cur)); p += length(cur) + 1; empty!(cur); else push!(cur, c); end
    end
end
refd = Dict{String,Int}(); k = 0; primlen = length(b) - prim
while k + 44 <= primlen
    if u32(prim+k) == 14 && u32(prim+k+8) == 0 && u32(prim+k+12) == 19
        wn = Int(u32(prim+k+4)); haskey(off2name, wn) && (refd[lowercase(off2name[wn])] = get(refd, lowercase(off2name[wn]), 0) + 1)
    end
    global k += 4
end
println("distinct names referenced by 0x0E placements: ", length(refd), "  total placements: ", sum(values(refd)))
missing = [(n, c) for (n, c) in refd if !(n in names)]
println("referenced but NO loose .3do (in nurburg.dat?): ", length(missing), " names, ", sum(c for (_, c) in missing; init = 0), " placements")
for (n, c) in sort(missing; by = x -> -x[2])[1:min(end, 40)]; println("  ", rpad(n, 14), c); end
