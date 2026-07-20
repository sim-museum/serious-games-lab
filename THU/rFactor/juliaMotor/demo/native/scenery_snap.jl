# scenery_snap.jl — FAST offscreen scenery/atmosphere QA harness.
# Loads a GPL track's MESH + horizon ring + sky (NO physics, NO MTK, NO car/objects)
# and renders it from camera poses along the .trk centreline.  Purpose: iterate the
# per-track colour GRADE / sky / horizon / fog against the GPL gold-standard shots
# WITHOUT paying the ~5-min MTK model-build every launch.
#
#   TRACK=watglen JM_GRADE=WATK JM_S=0,300,800 julia --project=. scenery_snap.jl
#
# Env:
#   TRACK    zandvoort|watglen|monza|spa|nurburgring   (default zandvoort)
#   JM_GRADE OVERCAST|SUNNY|WATK|SPA|MONZA|NURB|ZAND|GPL   (default: per-track like the game)
#   JM_S     comma list of centreline distances [m]        (default 0,400,900,1500)
#   JM_EYE   camera eye height above the road [m]           (default 1.1)
#   JM_OUT   output dir                                     (default /tmp/scn)
using GLFW, ModernGL, LinearAlgebra
using JuliaMotor
include("render.jl"); using .Render
include("gpltrack.jl"); using .GPLTrack

const TRACKSEL = lowercase(get(ENV, "TRACK", "zandvoort"))
const GPLBASE  = normpath(joinpath(@__DIR__,"..","..","..","..","WP","drive_c","Sierra","GPL","tracks"))
const GPLNAME  = get(Dict("nurburgring"=>"nurburg","zandvoort"=>"zandvort",
                          "watglen"=>"watglen","monza"=>"monza","spa"=>"spa67"), TRACKSEL, "zandvort")
const ZD   = joinpath(GPLBASE, GPLNAME)
const OUT  = get(ENV, "JM_OUT", "/tmp/scn"); mkpath(OUT)
find_ci(dir,name) = (m=filter(f->lowercase(f)==lowercase(name), readdir(dir)); isempty(m) ? joinpath(dir,name) : joinpath(dir,m[1]))
const DAT = (p=find_ci(ZD, GPLNAME*".dat"); isfile(p) ? Render.GPLDat.parse_dat(p) : Dict{String,Vector{UInt8}}())
const TMP = mktempdir()
function track_file(base, ext)
    p = find_ci(ZD, base*ext); isfile(p) && return p
    v = get(DAT, lowercase(base*ext), nothing); v===nothing && return p
    q = joinpath(TMP, base*ext); write(q, v); q
end
const ZTRK = track_file(GPLNAME, ".3do")

# ---- colour grade (copied verbatim from drive_native_mtk.jl so it is faithful) ----
struct ColourGrade
    zenith::NTuple{3,Float32}; horizon::NTuple{3,Float32}; cloud::Float32
    suncol::NTuple{3,Float32}; ambsky::NTuple{3,Float32}; sat::Float32; ringtint::NTuple{3,Float32}
end
const GRADES = Dict(
 "GPL"      => ColourGrade((0.40,0.56,0.78),(0.78,0.78,0.75),1.0,(1,1,1),(0.95,0.93,0.86),1.0,(1,1,1)),
 "SUNNY"    => ColourGrade((0.20,0.47,0.85),(0.80,0.88,0.97),1.0,(1.07,1.0,0.85),(0.72,0.82,0.99),1.18,(1.28,1.27,1.30)),
 "ZAND"     => ColourGrade((0.24,0.46,0.80),(0.74,0.83,0.92),0.45,(1.07,1.0,0.85),(0.70,0.80,0.98),1.30,(1.12,1.10,1.06)),
 "SPA"      => ColourGrade((0.22,0.45,0.82),(0.72,0.82,0.93),0.50,(1.07,1.0,0.85),(0.70,0.80,0.98),1.34,(1.10,1.13,1.05)),
 "MONZA"    => ColourGrade((0.31,0.51,0.80),(0.85,0.90,0.96),0.34,(1.07,1.02,0.90),(0.74,0.83,0.97),1.18,(1.17,1.15,1.11)),
 "WATK"     => ColourGrade((0.28,0.48,0.80),(0.82,0.87,0.93),0.40,(1.10,1.02,0.86),(0.74,0.82,0.96),1.26,(1.21,1.16,1.06)),
 "NURB"     => ColourGrade((0.42,0.48,0.56),(0.66,0.68,0.70),1.0,(0.92,0.92,0.95),(0.72,0.74,0.80),0.88,(0.90,0.91,0.96)),
 "OVERCAST" => ColourGrade((0.66,0.67,0.69),(0.76,0.765,0.77),1.0,(1.0,1.0,0.98),(0.88,0.89,0.92),1.12,(1.10,1.10,1.10)),
)
# mirror drive_native_mtk.jl's per-track grade selection (E58)
default_grade() = get(Dict("nurburgring"=>"NURB","monza"=>"MONZA","spa"=>"SPA",
                           "watglen"=>"WATK","zandvoort"=>"ZAND"), TRACKSEL, "OVERCAST")
const GRADE = GRADES[uppercase(get(ENV, "JM_GRADE", default_grade()))]

# ---- geometry ----
print("loading GPL ", GPLNAME, "… "); flush(stdout)
const MESH    = Render.GPL3DO.parse_3do(ZTRK)
const TERRAIN = GPLTrack.build_hat(MESH)
const CLINE   = GPLTrack.trk_centreline(track_file(GPLNAME, ".trk"))
const TRACK   = Render.extract_gpl_car(ZTRK; track=true, mirror=true, exclude=("ltraymap","lshad","wiref_s"))
println(length(TRACK), " track parts, ", length(CLINE), " centreline pts")

# arc-length table along the centreline
const SEGLEN = [hypot(CLINE[i%length(CLINE)+1][1]-CLINE[i][1], CLINE[i%length(CLINE)+1][2]-CLINE[i][2]) for i in 1:length(CLINE)]
const ARC = cumsum(SEGLEN); const TOTAL = ARC[end]
gz(x,y) = (h=JuliaMotor.hat3d(TERRAIN, Float64(x), Float64(y); ref=Inf); h[3] ? Float32(h[1]) : 0f0)
idx_at(s) = (t=mod(s, TOTAL); findfirst(a->a>=t, ARC) |> x-> x===nothing ? length(CLINE) : x)

# ---- GL ----
const W,H = 1440, 810
GLFW.Init(); GLFW.WindowHint(GLFW.VISIBLE,false)
GLFW.WindowHint(GLFW.CONTEXT_VERSION_MAJOR,4); GLFW.WindowHint(GLFW.CONTEXT_VERSION_MINOR,5)
GLFW.WindowHint(GLFW.OPENGL_PROFILE,GLFW.OPENGL_CORE_PROFILE); GLFW.WindowHint(GLFW.OPENGL_FORWARD_COMPAT,true)
GLFW.WindowHint(GLFW.SAMPLES,8)
win=GLFW.CreateWindow(W,H,"scn"); GLFW.MakeContextCurrent(win)
glEnable(GL_DEPTH_TEST); glEnable(GL_MULTISAMPLE); glEnable(GL_SAMPLE_ALPHA_TO_COVERAGE)
glEnable(GL_BLEND); glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
const LIGHTDIR = Float32[0.4,1.0,0.25]
prog=Render.program(); glUseProgram(prog); glUniform3f(glGetUniformLocation(prog,"uLightDir"),LIGHTDIR...)
skyprog=Render.skyprogram(); skyvao=Render.empty_vao()
depthprog=Render.depthprogram(); (shadowfbo,shadowtex)=Render.make_shadow_fbo()
print("textures… "); flush(stdout)
const TEXIDX = Render.gpl_texture_index(ZD)
trackItems = Render.build_gpl(TRACK, TEXIDX)
const RING = Render.build_horizon(TEXIDX)
println(count(it->it.tex!=0,trackItems),"/",length(trackItems)," textured")
const PROJ = Render.perspective_revz(deg2rad(62f0), Float32(W/H), 0.35f0, 3000f0)
const EYEUP = parse(Float32, get(ENV,"JM_EYE","1.1"))

function snap(fname, s)
    i = idx_at(s); j = idx_at(s + 15.0)                       # look 15 m ahead
    x,y = CLINE[i]; xa,ya = CLINE[j]
    eye = Float32[x, gz(x,y)+EYEUP, -y]
    ctr = Float32[xa, gz(xa,ya)+EYEUP*0.6f0, -ya]
    vp = PROJ * Render.lookat(eye, ctr, Float32[0,1,0])
    lightVP = Render.light_vp(eye, LIGHTDIR)
    Render.shadow_pass(depthprog, shadowfbo, lightVP) do dp
        for it in trackItems; Render.draw_depth(dp, it, Render.ident()); end
    end
    glViewport(0,0,W,H)
    glClipControl(GL_LOWER_LEFT, GL_ZERO_TO_ONE); glDepthFunc(GL_GEQUAL); glClearDepth(0.0)
    glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
    Render.draw_sky(skyprog, skyvao, inv(vp), eye, LIGHTDIR; cloud=GRADE.cloud, zenith=GRADE.zenith, horizon=GRADE.horizon)
    Render.set_scene_uniforms(prog, eye; fognear=400f0, fogfar=2800f0, fogcol=GRADE.horizon, suncol=GRADE.suncol, ambsky=GRADE.ambsky, sat=GRADE.sat)
    Render.bind_shadow(prog, shadowtex, lightVP)
    Render.draw_horizon(prog, RING, vp, eye; tint=GRADE.ringtint)
    for it in trackItems; Render.draw(prog, it, vp, Render.ident(); bright=0.72, ambfill=0.34); end
    glFinish()
    buf=Vector{UInt8}(undef,W*H*3); glReadPixels(0,0,W,H,GL_RGB,GL_UNSIGNED_BYTE,buf)
    open(fname,"w") do io; write(io,"P6\n$W $H\n255\n")
        for yy in H:-1:1, xx in 1:W; o=((yy-1)*W+(xx-1))*3; write(io,buf[o+1],buf[o+2],buf[o+3]); end; end
    println("wrote ", fname, "  (s=", round(Int,s), " of ", round(Int,TOTAL), " m)")
end

const SLIST = [parse(Float64,strip(x)) for x in split(get(ENV,"JM_S","0,400,900,1500"), ",")]
gtag = uppercase(get(ENV,"JM_GRADE", default_grade()))
for s in SLIST
    snap(joinpath(OUT, "$(TRACKSEL)_s$(round(Int,s))_$(gtag).ppm"), s)
end
GLFW.Terminate()
println("done.")
