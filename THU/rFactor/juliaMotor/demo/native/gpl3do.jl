# Parser for Grand Prix Legends .3do model files (format "3DO4", P.A.Flack spec).
# Walks the PRIM node tree and emits a textured triangle mesh: per-triangle
# positions, vertex normals, UVs, and the texture (mip) name set by the nearest
# ancestor T-005 selector.  This is the GPL analogue of RFactorData's GMT parser —
# the first step of the GPL-asset pivot (Lotus 49 in place of the rFactor Vanwall).
module GPL3DO
using LinearAlgebra

export Mesh3DO, parse_3do, gpl_placements

# E64 S4: walk every LOD child (the pre-fix behaviour) instead of only the highest-detail one
const LOD_ALL = get(ENV,"JM_LOD_ALL","0") != "0"

# positioner local matrix: Translate(d) * Rot(m, GPL Euler about X,Y,Z) * Scale(s).
# Places a sub-object (hands, wheel, mirrors, suspension) relative to its parent.
function posmat(d, m, s)
    cx,sx = cos(m[1]),sin(m[1]); cy,sy = cos(m[2]),sin(m[2]); cz,sz = cos(m[3]),sin(m[3])
    Rx = [1.0 0 0; 0 cx -sx; 0 sx cx]; Ry = [cy 0 sy; 0 1.0 0; -sy 0 cy]; Rz = [cz -sz 0; sz cz 0; 0 0 1.0]
    R = (Rz*Ry*Rx) .* s
    # clamp absurd translations: a real car-part offset is < ~3m; GPL uses huge
    # values (e.g. dy=20) as a hide/LOD marker — ignore those so the body stays put.
    cl(x) = abs(x) > 5.0 ? 0.0 : Float64(x)
    [R[1,1] R[1,2] R[1,3] cl(d[1]); R[2,1] R[2,2] R[2,3] cl(d[2]); R[3,1] R[3,2] R[3,3] cl(d[3]); 0 0 0 1.0]
end

struct Tri
    p::NTuple{3,NTuple{3,Float32}}    # 3 positions
    n::NTuple{3,NTuple{3,Float32}}    # 3 normals
    uv::NTuple{3,NTuple{2,Float32}}   # 3 UVs
    tex::String                       # mip name ("" = untextured)
    col::NTuple{3,Float32}            # flat-shade surface colour (ARGB→RGB), for untextured polys
    # E106-S19: TRUE when GPL authored this poly with NO uv list at all -- the FLAT poly types
    # (0x81B/0x81C/0x81E: "col, count, vert*") as opposed to the textured ones (0x820/0x821/
    # 0x1F/0x20/0x21, which carry a "UV*" block). The parser knows this exactly; downstream code
    # could only INFER it from "all three UVs are equal", which conflates a genuinely flat poly
    # with a textured one whose UVs happen to coincide -- and acting on that inference is what
    # turned the cockpit cowl bright yellow in S10.
    flat::Bool
end

struct Mesh3DO
    tris::Vector{Tri}
    textures::Vector{String}          # distinct texture names used
    groups::Vector{Int}               # parallel to tris: offset of the placing positioner
end

# little-endian readers over a byte vector (1-based indexing; o is a 0-based offset).
# Bounds-safe: out-of-range reads return 0 rather than throwing (the PRIM tree has
# a few nodes whose layout we don't fully model; we'd rather skip than crash).
@inline u32(b, o) = (o < 0 || o+4 > length(b)) ? UInt32(0) :
    UInt32(b[o+1]) | (UInt32(b[o+2])<<8) | (UInt32(b[o+3])<<16) | (UInt32(b[o+4])<<24)
@inline i32(b, o) = reinterpret(Int32, u32(b,o))
@inline f32(b, o) = reinterpret(Float32, u32(b,o))
tag(b, o) = String(b[o+1:o+4])

"""Parse a GPL .3do file into a `Mesh3DO` (triangulated, textured)."""
function parse_3do(path::AbstractString; textable::Union{Nothing,Vector{String}}=nothing, Mroot=nothing, extdepth::Int=0)
    b = read(path)
    String(b[1:4]) == "4OD3" || error("not a 3DO4 file: $path (magic=$(String(b[1:4])))")

    # ---- locate sections ----
    xyz_off = norm_off = strn_off = prim_off = 0
    strn_size = 0; nverts = 0
    o = 12
    while o + 12 <= length(b)
        t = tag(b, o); sz = Int(u32(b, o+8)); data = o + 12
        if     t == "SZYX"; xyz_off  = data; nverts = sz ÷ 16
        elseif t == "MRON"; norm_off = data
        elseif t == "NRTS"; strn_off = data; strn_size = sz
        elseif t == "MIRP"; prim_off = data
        end
        o = data + sz; o += (4 - o % 4) % 4
    end
    prim_off == 0 && error("no PRIM section in $path")

    # ---- string table: 0x00-terminated names, 0xFF ends the table ----
    strings = String[]
    if strn_off != 0
        cur = UInt8[]
        for i in strn_off : strn_off + strn_size - 1
            c = b[i+1]
            if c == 0xFF; break
            elseif c == 0x00; push!(strings, String(copy(cur))); empty!(cur)
            else push!(cur, c); end
        end
        !isempty(cur) && push!(strings, String(copy(cur)))
    end
    # string offset (byte into STRN data) -> name.  Build an offset→name map.
    stroff = Dict{Int,String}()
    let p = 0
        for s in strings
            stroff[p] = s
            p += length(s) + 1
        end
    end

    # vertex/normal accessors: number n -> the 16-byte record at base + n*16,
    # whose useful payload is the last 3 floats (x,y,z); first float is s/w (=0).
    vert(n) = (f32(b, xyz_off + n*16 + 4),  f32(b, xyz_off + n*16 + 8),  f32(b, xyz_off + n*16 + 12))
    nrm(n)  = norm_off == 0 ? (0f0,1f0,0f0) :
              (f32(b, norm_off + n*16 + 4), f32(b, norm_off + n*16 + 8), f32(b, norm_off + n*16 + 12))

    tris = Tri[]
    groups = Int[]
    used_tex = Set{String}()
    # E106-S6 diagnostic: for polys reaching emit with NO selector-set texture, record the raw
    # header words -- the suspected texture-SLOT reference lives in one of them. JM_SLOTDIAG=<file>.
    slotdiag = get(ENV, "JM_SLOTDIAG", "") != "" &&
               occursin(lowercase(ENV["JM_SLOTDIAG"]), lowercase(basename(path)))
    slotrows = NTuple{6,Int}[]        # (tri_first_index, typ, w1, w2, w3, w4)
    selrows  = NTuple{3,Int}[]        # (subtype, word3, word4) of every selector walked
    # count guard (a real polygon has 3..64 verts; bigger = a misparsed node) and
    # count-bounded array readers for vertex#/UV runs
    ok(c) = (0 < c <= 64) ? Int(c) : 0
    rv(base, cnt) = [Int(u32(b, base + (k-1)*4)) for k in 1:cnt]
    ru(base, cnt) = [(f32(b, base + (k-1)*8), f32(b, base + (k-1)*8 + 4)) for k in 1:cnt]

    # emit one polygon (vertex list, optional UVs, optional normals) as a triangle
    # fan, computing a face normal when per-vertex normals are absent.
    rgb(c) = (Float32(((c>>16)&0xff)/255), Float32(((c>>8)&0xff)/255), Float32((c&0xff)/255))  # ARGB→RGB
    function emit(verts, uvs, norms, tex, M, grp, col)
        (length(verts) < 3 || length(verts) > 64) && return   # >64 = a misparsed node
        any(v -> v < 0 || v >= nverts, verts) && return       # vertex# out of range
        push!(used_tex, tex)
        txp(p) = (Float32(M[1,1]*p[1]+M[1,2]*p[2]+M[1,3]*p[3]+M[1,4]),
                  Float32(M[2,1]*p[1]+M[2,2]*p[2]+M[2,3]*p[3]+M[2,4]),
                  Float32(M[3,1]*p[1]+M[3,2]*p[2]+M[3,3]*p[3]+M[3,4]))
        txn(n) = begin
            x=M[1,1]*n[1]+M[1,2]*n[2]+M[1,3]*n[3]; y=M[2,1]*n[1]+M[2,2]*n[2]+M[2,3]*n[3]; z=M[3,1]*n[1]+M[3,2]*n[2]+M[3,3]*n[3]
            l=sqrt(x*x+y*y+z*z); l<1e-9 && (l=1.0); (Float32(x/l),Float32(y/l),Float32(z/l))
        end
        P = [txp(vert(v)) for v in verts]
        # face normal (Newell) as fallback, in the transformed frame
        fn = (0f0,0f0,0f0)
        let nx=0f0,ny=0f0,nz=0f0
            for k in 1:length(P)
                a = P[k]; c = P[k % length(P) + 1]
                nx += (a[2]-c[2])*(a[3]+c[3]); ny += (a[3]-c[3])*(a[1]+c[1]); nz += (a[1]-c[1])*(a[2]+c[2])
            end
            l = sqrt(nx*nx+ny*ny+nz*nz); l < 1f-9 && (l = 1f0)
            fn = (nx/l, ny/l, nz/l)
        end
        N = isempty(norms) ? [fn for _ in P] : [txn(nrm(n)) for n in norms]
        isflat = isempty(uvs)                    # no uv list authored => GPL flat-shaded poly
        UV = isflat ? [(0f0,0f0) for _ in P] : uvs
        for k in 2:length(P)-1                      # fan: (1, k, k+1)
            push!(tris, Tri((P[1],P[k],P[k+1]), (N[1],N[k],N[k+1]), (UV[1],UV[k],UV[k+1]), tex, col, isflat))
            push!(groups, grp)
        end
        push!(ALL_GROUPS, grp); PARKDEPTH[] > 0 && push!(PARKED_GROUPS, grp)
        if get(ENV, "JM_POSDIAG", "") != ""; ps = join(string.(PATH, base=16), ">"); for _ in 2:length(P)-1; push!(TRIPATH, ps); end; end
    end

    # ---- walk the PRIM node tree (offsets are byte offsets into PRIM data) ----
    # `visited` tracks the active path (offset → transform identity) to break cycles
    # while still allowing a node to be reached under different positioner transforms.
    I4 = Matrix{Float64}(I,4,4)
    visited = Set{Int}()
    # E70-S4: when an object parses to ZERO triangles the walker gives no reason — E76-S5 lost a
    # sprint to exactly that silence. Tally every node type reached, so "0 tris" can be answered with
    # "the tree contains only types X and Y, and we handle neither". JM_PRIMDIAG=<name substring>.
    PRIMTALLY = Dict{UInt32,Int}()
    PARKDEPTH = Ref(0); PARKED_GROUPS = Set{Int}(); ALL_GROUPS = Set{Int}()
    PATH = UInt32[]; TRIPATH = String[]          # E82 diag: node-type path per triangle (JM_POSDIAG)
    function walk(off::Int, curtex::String, depth::Int, M, grp::Int)
        n0 = length(PATH); _walk(off, curtex, depth, M, grp); resize!(PATH, n0)   # path bookkeeping (diag)
    end
    function _walk(off::Int, curtex::String, depth::Int, M, grp::Int)
        (off < 0 || off in visited || depth > 220) && return
        push!(visited, off)
        p = prim_off + off
        p + 4 > length(b) && return
        typ = u32(b, p)
        PRIMTALLY[typ] = get(PRIMTALLY, typ, 0) + 1
        push!(PATH, typ)
        if typ == 0x04                              # group: 4, count, child*
            cnt = Int(u32(b, p+4))
            for k in 1:cnt
                walk(Int(i32(b, p + 4 + k*4)), curtex, depth+1, M, grp)
            end
        elseif typ == 0x05                          # selector: 5, child, subtype, ...
            child = Int(i32(b, p+4)); sub = u32(b, p+8)
            tex = curtex
            # subtypes whose 4th word is a string offset (mip name)
            if sub in (0x1, 0x5, 0xD)
                tex = get(stroff, Int(u32(b, p+12)), curtex)
            end
            slotdiag && push!(selrows, (Int(sub), Int(u32(b, p+12)), Int(u32(b, p+16))))
            # E106-S6: THE WRAPPER MECHANISM (measured on llftire0/lotd + lotulf).
            # sub 0x11 = bind a texture-slot TABLE: word4 = count, then count string offsets.
            # sub 0x20 = select a slot: word4 = 0-based index into the bound table. The tyre mesh
            # carries five 0x20 selectors with slots {0,1,1,2,3} against a 4-entry table -- one per
            # surface (outer face, inner x2, tread, spinner).
            if sub == 0x11
                cnt = Int(u32(b, p+12))
                if 0 < cnt <= 64
                    tbl = String[get(stroff, Int(u32(b, p+16+(k-1)*4)), "") for k in 1:cnt]
                    curtable[] = tbl
                end
            elseif sub in (0x20, 0x24, 0x2C)
                # 0x20 in the small wheel meshes, 0x2C (and one 0x24) in lotus.3do -- all carry a
                # 0-based slot index in word4. lotus.3do's 0x2C values run exactly 0..8 against
                # lotd.3DO's 9-entry table.
                slot = Int(u32(b, p+12))
                tt = curtable[]
                if tt !== nothing && 0 <= slot < length(tt) && tt[slot+1] != ""
                    tex = tt[slot+1]
                end
            end
            walk(child, tex, depth+1, M, grp)
        elseif typ == 0x0E                          # external mesh: 0x0E, strofs(file), 0
            # E106-S6: a wrapper's whole point -- re-enter another .3do with THIS file's bound
            # texture table (llftire0 -> lotulf with the tyre set; lotd -> lotus with the cockpit
            # set). Case-insensitive sibling lookup; depth-capped against cycles.
            if extdepth < 2
                nm = get(stroff, Int(u32(b, p+4)), "")
                if nm != ""
                    dir = dirname(path)
                    hit = ""
                    for f in readdir(dir)
                        lowercase(f) == lowercase(nm * ".3do") && (hit = joinpath(dir, f); break)
                    end
                    if hit != ""
                        sub3 = parse_3do(hit; textable=curtable[], Mroot=M, extdepth=extdepth+1)
                        append!(tris, sub3.tris)
                        # keep the SUB-parse's group ids: they are node offsets in the referenced
                        # file, which is where exclude_groups(27288, …) point when the caller loads
                        # a wrapper. Overwriting them with the wrapper's grp would break the
                        # displaced-assembly excludes silently.
                        append!(groups, sub3.groups)
                        for t in sub3.textures; push!(used_tex, t); end
                    end
                end
            end
        elseif typ in (0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B)   # plane node + 1..4 children
            nchild = typ==0x06 ? 1 : typ in (0x07,0x0B) ? 2 : typ==0x08 ? 4 : 3
            for k in 1:nchild                            # word1 = plane#, then children
                walk(Int(i32(b, p + 8 + (k-1)*4)), curtex, depth+1, M, grp)
            end
        elseif typ in (0x0D, 0x13, 0x16)            # positioner: type, dx,dy,dz, rx,ry,rz, scale, child
            d = (f32(b,p+4), f32(b,p+8), f32(b,p+12)); mm = (f32(b,p+16), f32(b,p+20), f32(b,p+24))
            s = f32(b,p+28); s = (s <= 0f0 ? 1.0 : Float64(s))
            # E82 (S1): JM_POSDIAG="3560,6600" prints the positioner at those node offsets with the
            # accumulated parent transform, so a misplaced assembly can be read off its chain.
            if get(ENV, "JM_POSDIAG", "") != "" && (ENV["JM_POSDIAG"] == "all" || string(off) in split(ENV["JM_POSDIAG"], ","))
                sc = sqrt(M[1,1]^2 + M[2,1]^2 + M[3,1]^2)
                println("   [posdiag] node ", off, " type 0x", string(typ, base=16), " depth ", depth, "  d=", d, "  rot=", mm, "  s=", s,
                        "  parent: translation (", round(M[1,4],digits=3), ",", round(M[2,4],digits=3), ",", round(M[3,4],digits=3), ") scale ", round(sc,digits=3))
            end
            # E82 diagnostic: which placing groups sit under a PARKED (|d|>5, hide-marker) positioner?
            # GPL parks geometry it does not draw statically at y=+20; posmat clamps that to 0 and we
            # draw it at the origin. JM_POSDIAG reports the parked group set at the end of the parse.
            parked = any(abs(x) > 5.0 for x in d)
            parked && (PARKDEPTH[] += 1)
            walk(Int(i32(b, p + 8*4)), curtex, depth+1, M * posmat(d, mm, s), off)
            parked && (PARKDEPTH[] -= 1)
        elseif typ == 0x19                          # bounding cuboid: 8 vert#, then child
            walk(Int(i32(b, p + 9*4)), curtex, depth+1, M, grp)
        elseif typ == 0x11                          # LOD/distance list: 11,int,int,int,count,(dist,childoff)*
            # E64 S4 (D12): lotus.3do has 47 of these with DESCENDING range thresholds (4.0/2.5/0.0)
            # — GPL picks ONE child by camera distance.  Walking all of them rendered every LOD at
            # once, and the far-LOD crudes (clamped back by the posmat hide-translation guard) are
            # the chase car's "chrome spider-legs".  Distinct thresholds ⇒ real LOD switch: keep
            # only the min-threshold (closest-range, highest-detail) child.  All-equal thresholds
            # (e.g. six 0.0s) ⇒ a plain list-group: keep walking every child.  JM_LOD_ALL=1 A/Bs.
            cnt = Int(u32(b, p+16))
            if get(ENV,"JM_PRIMDIAG","") != "" && occursin(lowercase(ENV["JM_PRIMDIAG"]), lowercase(basename(path)))
                println("     [LOD node] count = ", cnt, "  (walked only when 0 < count <= 4096)")
                for kk in 1:min(cnt,6)
                    println("        child ", kk, ": dist ", f32(b, p + 20 + (kk-1)*8),
                            " off ", i32(b, p + 20 + (kk-1)*8 + 4))
                end
            end
            if 0 < cnt <= 4096
                ds = [f32(b, p + 20 + (k-1)*8) for k in 1:cnt]
                offs = [Int(i32(b, p + 20 + (k-1)*8 + 4)) for k in 1:cnt]
                # E70-S4: only consider children that EXIST. GPL pads its LOD lists with NULL
                # entries (offset -1) carrying sentinel distances, and argmin over the raw distance
                # array happily selects one of those. ogrnd2 — the Nürburgring's start/finish crowd
                # terrace, and the PO's actual E76 complaint — has
                #     dist 4.0e7 off -1 | dist 7.0e6 off 6384 | dist 0.0 off -1 | dist -6000.0 off -1
                # so argmin picked the -6000.0 sentinel, walked offset -1, and returned 0 triangles
                # from an object that plainly has geometry. Choose the nearest-range child WITH a
                # real offset. JM_LOD_ALL=1 still walks everything.
                live = get(ENV,"JM_LOD_NULLS","0") != "0" ? collect(1:cnt) : [k for k in 1:cnt if offs[k] >= 0]
                # E75-S14: which end of the threshold list is the HIGH-DETAIL child? E64-S4 assumed the
                # smallest threshold is the closest-range/finest one. If GPL's convention is the
                # reverse, we have been drawing the CRUDEST rear end at all times - which would explain
                # gold's slender wishbones against our broad chrome bodies. JM_LOD_PICK=max tests it.
                _lodmax = get(ENV,"JM_LOD_PICK","min") == "max"
                if !LOD_ALL && length(unique(ds)) > 1 && !isempty(live)
                    k = live[_lodmax ? argmax([ds[k] for k in live]) : argmin([ds[k] for k in live])]
                    walk(offs[k], curtex, depth+1, M, grp)
                else
                    for k in 1:cnt
                        walk(Int(i32(b, p + 20 + (k-1)*8 + 4)), curtex, depth+1, M, grp)
                    end
                end
            end
        # ---- polygon leaves ----  (rv/ru read count-bounded vert# / UV arrays)
        elseif typ == 0x81B                         # flat: col, count, vert*
            cnt = ok(u32(b,p+8)); vs = rv(p+12, cnt); emit(vs, [], [], curtex, M, grp, rgb(u32(b,p+4)))
        elseif typ == 0x81C                         # smooth: col, count, vert*, col*
            cnt = ok(u32(b,p+8)); vs = rv(p+12, cnt); emit(vs, [], [], curtex, M, grp, rgb(u32(b,p+4)))
        elseif typ == 0x81D                         # normals: col, count, vert*, norm*
            cnt = ok(u32(b,p+8)); emit(rv(p+12,cnt), [], rv(p+12+cnt*4,cnt), curtex, M, grp, rgb(u32(b,p+4)))
        elseif typ == 0x81E                         # smooth+normals: col, count, vert*, col*, norm*
            cnt = ok(u32(b,p+8)); emit(rv(p+12,cnt), [], rv(p+12+2*cnt*4,cnt), curtex, M, grp, rgb(u32(b,p+4)))
        elseif typ == 0x81F                         # textured: 0, col, count, UV*, vert*
            cnt = ok(u32(b,p+12))
            slotdiag && curtex == "" && push!(slotrows, (length(tris), Int(typ), Int(u32(b,p+4)), Int(u32(b,p+8)), Int(u32(b,p+12)), Int(u32(b,p+16))))
            emit(rv(p+16+cnt*8,cnt), ru(p+16,cnt), [], curtex, M, grp, rgb(u32(b,p+8)))
        elseif typ == 0x820                         # textured+smooth: 0, col, count, UV*, vert*, col*
            cnt = ok(u32(b,p+12)); emit(rv(p+16+cnt*8,cnt), ru(p+16,cnt), [], curtex, M, grp, rgb(u32(b,p+8)))
        elseif typ == 0x821                         # textured+normals: 0, col, count, UV*, vert*, norm*
            cnt = ok(u32(b,p+12))
            slotdiag && curtex == "" && push!(slotrows, (length(tris), Int(typ), Int(u32(b,p+4)), Int(u32(b,p+8)), Int(u32(b,p+12)), Int(u32(b,p+16))))
            emit(rv(p+16+cnt*8,cnt), ru(p+16,cnt), rv(p+16+cnt*12,cnt), curtex, M, grp, rgb(u32(b,p+8)))
        elseif typ == 0x1F                          # car textured: 1F, 0, int, count, UV*, vert*
            cnt = ok(u32(b,p+12))
            slotdiag && curtex == "" && push!(slotrows, (length(tris), Int(typ), Int(u32(b,p+4)), Int(u32(b,p+8)), Int(u32(b,p+12)), Int(u32(b,p+16))))
            emit(rv(p+16+cnt*8,cnt), ru(p+16,cnt), [], curtex, M, grp, rgb(u32(b,p+8)))
        elseif typ == 0x20                          # car textured+smooth: 20,0,0,int,count,UV*,vert*,col*
            cnt = ok(u32(b,p+16)); emit(rv(p+20+cnt*8,cnt), ru(p+20,cnt), [], curtex, M, grp, (1f0,1f0,1f0))
        elseif typ == 0x21                          # car textured+normals: 21,0,int,count,UV*,vert*,norm*
            cnt = ok(u32(b,p+12))
            slotdiag && curtex == "" && push!(slotrows, (length(tris), Int(typ), Int(u32(b,p+4)), Int(u32(b,p+8)), Int(u32(b,p+12)), Int(u32(b,p+16))))
            emit(rv(p+16+cnt*8,cnt), ru(p+16,cnt), rv(p+16+cnt*12,cnt), curtex, M, grp, (1f0,1f0,1f0))
        end
        # unknown types: we don't know their child layout, so that subtree is skipped
    end

    curtable = Ref{Union{Nothing,Vector{String}}}(textable)
    root = Int(u32(b, prim_off))                    # first 4 bytes of PRIM data = root offset
    walk(root, "", 0, Mroot === nothing ? I4 : Mroot, 0)
    if slotdiag && !isempty(selrows)
        tal = Dict{NTuple{3,Int},Int}()
        for r in selrows; tal[r] = get(tal, r, 0) + 1; end
        println("  [slotdiag] selectors walked:")
        for (k,c) in sort(collect(tal))
            println("     sub 0x", string(k[1], base=16), "  w3=", k[2], " w4=", k[3], "  x", c)
        end
    end
    if slotdiag && !isempty(slotrows)
        println("  [slotdiag] ", basename(path), ": ", length(slotrows), " untextured poly headers")
        shown = Dict{NTuple{4,Int},Int}()
        for r in slotrows
            k = (r[2], r[3], r[4], 0)
            shown[k] = get(shown, k, 0) + 1
        end
        for (k, c) in sort(collect(shown))
            println("     typ 0x", string(k[1], base=16), "  w1=", k[2], " w2=", k[3], "  x", c)
        end
        flush(stdout)
    end
    if get(ENV,"JM_PRIMDIAG","") != "" && occursin(lowercase(ENV["JM_PRIMDIAG"]), lowercase(basename(path)))
        handled = Set{UInt32}([0x04,0x05,0x06,0x07,0x08,0x09,0x0A,0x0B,0x0D,0x13,0x16,0x19,0x11,
                               0x81B,0x81C,0x81D,0x81E,0x81F,0x820,0x821,0x822])
        println("  [primdiag] ", basename(path), ": ", length(tris), " tris from ",
                sum(values(PRIMTALLY)), " nodes")
        for (t,c) in sort(collect(PRIMTALLY), by=x->-x[2])
            println("     type 0x", string(t, base=16, pad=3), "  x", rpad(c,6),
                    t in handled ? "handled" : "*** NOT HANDLED ***")
        end
        flush(stdout)
    end
    if get(ENV, "JM_POSDIAG", "") != ""
        println("   [posdiag] placing groups: ", length(ALL_GROUPS), " total, ", length(PARKED_GROUPS), " under a PARK (|d|>5) node")
        for g in sort(collect(PARKED_GROUPS))
            texs = Dict{String,Int}(); for (k,gg) in enumerate(groups); gg == g && (texs[tris[k].tex] = get(texs, tris[k].tex, 0) + 1); end
            println("   [posdiag]   parked group ", g, ": ", join([string(k == "" ? "(untex)" : k, "=", v) for (k,v) in sort(collect(texs))], " "))
        end
    end
    if get(ENV, "JM_POSDIAG", "") != "" && length(TRIPATH) == length(tris)
        # which node-type paths carry the LONG strips (max edge > 1.4 m) vs the rest, per front group
        for g in (3560, 6600)
            long = Dict{String,Int}(); short = Dict{String,Int}()
            for (k,t) in enumerate(tris)
                groups[k] == g || continue
                e(a,b) = sqrt(sum((a[i]-b[i])^2 for i in 1:3)); L = max(e(t.p[1],t.p[2]), e(t.p[2],t.p[3]), e(t.p[1],t.p[3]))
                d = L > 1.4 ? long : short; d[TRIPATH[k]] = get(d, TRIPATH[k], 0) + 1
            end
            println("   [posdiag] group $g LONG-strip paths: ", join(["$v x [$k]" for (k,v) in sort(collect(long), by=x->-x[2])], "  "))
            println("   [posdiag] group $g short paths:      ", join(["$v x [$k]" for (k,v) in sort(collect(short), by=x->-x[2])][1:min(end,3)], "  "))
        end
    end
    Mesh3DO(tris, sort(collect(used_tex)), groups)
end

"""
    gpl_placements(path) -> Vector{Tuple{String, NTuple{7,Float64}}}

GPL places `.dat` scenery meshes (corner terrain sections, trees, signs, buildings)
into a track via PRIM node type 0x0E — a "named external sub-object reference":
`[14, string-offset, 0,  19, dx,dy,dz, rx,ry,rz, scale, child]` (an inline 0x13
positioner).  The geometry lives in a separate `.dat` mesh named by the string; the
positioner gives its WORLD transform.  These nodes hang under unhandled parents (so the
main walk never reaches them) and their translations are huge (the regular positioner
clamp would zero them), so we recover them by scanning PRIM for the fixed signature.
Returns (sub-object name, (dx,dy,dz, rx,ry,rz, scale)) per placement.
"""
function gpl_placements(path::AbstractString)
    b = read(path)
    String(b[1:4]) == "4OD3" || error("not a 3DO4 file: $path")
    strn_off = strn_sz = prim_off = prim_sz = 0
    o = 12
    while o + 12 <= length(b)
        t = tag(b, o); sz = Int(u32(b, o+8)); data = o + 12
        t == "NRTS" && (strn_off = data; strn_sz = sz)
        t == "MIRP" && (prim_off = data; prim_sz = sz)
        o = data + sz; o += (4 - o % 4) % 4
    end
    # string offset (byte into STRN data) → name
    strings = String[]; cur = UInt8[]
    for i in strn_off : strn_off + strn_sz - 1
        c = b[i+1]
        if c == 0xFF; break
        elseif c == 0x00; push!(strings, String(copy(cur))); empty!(cur)
        else push!(cur, c); end
    end
    stroff = Dict{Int,String}(); let q = 0
        for s in strings; stroff[q] = s; q += length(s) + 1; end
    end
    res = Tuple{String,NTuple{7,Float64}}[]
    for N in prim_off : 4 : prim_off + prim_sz - 44
        (u32(b,N) == 14 && u32(b,N+8) == 0 && u32(b,N+12) == 19) || continue
        nm = get(stroff, Int(u32(b,N+4)), ""); nm == "" && continue
        res = push!(res, (nm, (Float64(f32(b,N+16)), Float64(f32(b,N+20)), Float64(f32(b,N+24)),
                               Float64(f32(b,N+28)), Float64(f32(b,N+32)), Float64(f32(b,N+36)),
                               Float64(f32(b,N+40)))))
    end
    res
end

end # module
