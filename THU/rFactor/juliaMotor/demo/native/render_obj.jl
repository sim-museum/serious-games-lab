# render_obj.jl — render a single GPL object .3do in isolation from 3 angles, with
# each PART tinted a distinct colour so we can see which part is which (identify the
# 2nd lambda / stray hay bale to remove).  OBJ=startbox julia --project=. render_obj.jl
using GLFW, ModernGL, LinearAlgebra
using JuliaMotor
include("render.jl"); using .Render
const GPLBASE="/home/g/sgl/THU/WP/drive_c/Sierra/GPL/tracks"
const TRACKSEL=lowercase(get(ENV,"TRACK","watglen"))
const GPLNAME=get(Dict("nurburgring"=>"nurburg","zandvoort"=>"zandvort","watglen"=>"watglen","monza"=>"monza","spa"=>"spa67"),TRACKSEL,"zandvort")
const ZD=joinpath(GPLBASE,GPLNAME)
find_ci(d,n)=(m=filter(f->lowercase(f)==lowercase(n),readdir(d)); isempty(m) ? joinpath(d,n) : joinpath(d,m[1]))
const DAT=(p=find_ci(ZD,GPLNAME*".dat"); isfile(p) ? Render.GPLDat.parse_dat(p) : Dict{String,Vector{UInt8}}())
const TMP=mktempdir(); const OBJ=get(ENV,"OBJ","startbox")
p=find_ci(ZD,OBJ*".3do"); isfile(p)||(v=get(DAT,lowercase(OBJ*".3do"),nothing); v!==nothing&&(p=joinpath(TMP,OBJ*".3do");write(p,v)))
const EXCL = Tuple(split(get(ENV,"JM_EXCL",""), ',', keepempty=false))
parts=Render.extract_gpl_car(p; track=true, mirror=true, exclude=EXCL)
println(OBJ," parts=",length(parts))
# tint each part a distinct bright colour by overwriting its vertex colours (cols at offset 7..9 of 11)
palette=[(1.0,0.2,0.2),(0.2,1.0,0.2),(0.2,0.4,1.0),(1.0,1.0,0.2),(1.0,0.2,1.0),(0.2,1.0,1.0),(1.0,0.6,0.1),(0.6,0.2,1.0),(0.9,0.9,0.9),(0.4,0.8,0.4)]
for (k,pp) in enumerate(parts)
    c=palette[(k-1)%length(palette)+1]; n=length(pp.verts)÷11
    for i in 1:n; o=(i-1)*11; pp.verts[o+7]=Float32(c[1]); pp.verts[o+8]=Float32(c[2]); pp.verts[o+9]=Float32(c[3]); end
end
const W,H=900,900
GLFW.Init(); GLFW.WindowHint(GLFW.VISIBLE,false); GLFW.WindowHint(GLFW.SAMPLES,4)
GLFW.WindowHint(GLFW.CONTEXT_VERSION_MAJOR,3); GLFW.WindowHint(GLFW.CONTEXT_VERSION_MINOR,3)
GLFW.WindowHint(GLFW.OPENGL_PROFILE,GLFW.OPENGL_CORE_PROFILE); GLFW.WindowHint(GLFW.OPENGL_FORWARD_COMPAT,true)
win=GLFW.CreateWindow(W,H,"o"); GLFW.MakeContextCurrent(win)
glEnable(GL_DEPTH_TEST); glEnable(GL_MULTISAMPLE)
prog=Render.program(); glUseProgram(prog); glUniform3f(glGetUniformLocation(prog,"uLightDir"),0.4f0,1.0f0,0.25f0)
const TINT = get(ENV,"JM_TINT","")!=""
items=Render.build_gpl(parts, TINT ? Render.GPLTex(Dict{String,String}(), Dict{String,Vector{UInt8}}()) : Render.gpl_texture_index(ZD))
for (k,pp) in enumerate(parts); println("  part $k  tex=$(pp.tex)"); end
# bounding box / centre
allx=Float32[];ally=Float32[];allz=Float32[]
for pp in parts, i in 1:(length(pp.verts)÷11); o=(i-1)*11; push!(allx,pp.verts[o+1]);push!(ally,pp.verts[o+2]);push!(allz,pp.verts[o+3]); end
cx=(minimum(allx)+maximum(allx))/2; cy=(minimum(ally)+maximum(ally))/2; cz=(minimum(allz)+maximum(allz))/2
R=Float32(1.6*max(maximum(allx)-minimum(allx),maximum(ally)-minimum(ally),maximum(allz)-minimum(allz)))
PROJ=Render.perspective(deg2rad(45f0),1f0,0.1f0,500f0)
function snap(fn,ex,ey,ez)
    eye=Float32[cx+ex,cy+ey,cz+ez]; vp=PROJ*Render.lookat(eye,Float32[cx,cy,cz],Float32[0,1,0])
    glViewport(0,0,W,H); glClearColor(0.1f0,0.1f0,0.12f0,1f0); glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
    Render.set_scene_uniforms(prog,eye)
    for it in items; Render.draw(prog,it,vp,Render.ident();bright=1.2,ambfill=0.7); end
    glFinish(); buf=Vector{UInt8}(undef,W*H*3); glReadPixels(0,0,W,H,GL_RGB,GL_UNSIGNED_BYTE,buf)
    open(fn,"w") do io; write(io,"P6\n$W $H\n255\n"); for y in H:-1:1,x in 1:W; o=((y-1)*W+(x-1))*3; write(io,buf[o+1],buf[o+2],buf[o+3]); end; end
    println("wrote ",fn)
end
snap("/tmp/shot/obj_$(OBJ)_front.ppm", 0f0, R*0.3f0, R)      # front (along +z)
snap("/tmp/shot/obj_$(OBJ)_side.ppm",  R, R*0.3f0, 0f0)      # side (along +x)
snap("/tmp/shot/obj_$(OBJ)_top.ppm",   0.01f0, R, 0.01f0)    # top-down
GLFW.Terminate(); println("done")
