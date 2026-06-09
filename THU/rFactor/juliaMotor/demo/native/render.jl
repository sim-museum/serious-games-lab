# Native OpenGL renderer for juliaMotor — the rF1-fidelity foundation (no
# browser).  Reuses the JuliaMotor physics + RFactorData geometry; renders with
# GLSL shaders through GLFW/ModernGL, now with DDS textures decoded straight
# from the .mas archives (S3TC/DXT uploaded compressed to the GPU).
#
# World frame = (x, y, -z_rFactor), right-handed Y up (un-mirrored like the
# browser).  Car rig-local: +X forward, +Y up, +Z left.  Vertex format is
# 11 floats: position(3) normal(3) colour(3) uv(2).
module Render
using GLFW, ModernGL, LinearAlgebra
using JuliaMotor, RFactorData

const CATCOL = Dict(
    "road"=>(0.27f0,0.27f0,0.29f0), "curb"=>(0.76f0,0.29f0,0.24f0), "grass"=>(0.25f0,0.48f0,0.21f0),
    "sand"=>(0.80f0,0.73f0,0.53f0), "foliage"=>(0.18f0,0.36f0,0.16f0), "dark"=>(0.60f0,0.63f0,0.66f0),
    "structure"=>(0.72f0,0.69f0,0.64f0))
scene_category(n) =
    (startswith(n,"asphalt")||n=="pitline.gmt"||startswith(n,"tarmac")) ? "road" :
    startswith(n,"curb") ? "curb" : startswith(n,"grass") ? "grass" :
    (startswith(n,"sand")||startswith(n,"hayba")||startswith(n,"gravel")) ? "sand" :
    (occursin("tree",n)||occursin("hedge",n)||occursin("bush",n)||occursin("foli",n)||occursin("forest",n)) ? "foliage" :
    (occursin("tire",n)||occursin("tyre",n)||occursin("barrier",n)||occursin("armco",n)||occursin("guard",n)||occursin("fence",n)||occursin("wall",n)) ? "dark" :
    "structure"

okp(p) = all(isfinite,p) && abs(p[1])<2e4 && abs(p[2])<2e4 && abs(p[3])<2e4

"""One renderable track mesh: interleaved 11-float verts, its diffuse texture
name (`""` if none), and a fallback colour (used untextured)."""
struct TrackPart; verts::Vector{Float32}; tex::String; col::NTuple{3,Float32}; end

"""Per-mesh track geometry with UVs + diffuse texture name (one TrackPart per
GMT, so each can bind its own texture)."""
function extract_track(dir)
    scn = read_gen(only(filter(p->endswith(lowercase(p),".scn"), readdir(dir; join=true))))
    want = Set{String}()
    for st in gen_statements(scn, "MeshFile")
        nm = lowercase(string(RFactorData.value(st)))
        (startswith(nm,"x")||startswith(nm,"sky")) && continue
        push!(want, nm)
    end
    parts = TrackPart[]
    for maspath in filter(p->endswith(lowercase(p),".mas"), readdir(dir; join=true))
        m = read_mas(maspath)
        for e in m.entries
            lowercase(e.name) in want || continue
            P,N,UV,T,tex = parse_gmt_uv(extract(m, e))
            isempty(T) && continue
            col = get(CATCOL, scene_category(lowercase(e.name)), (0.5f0,0.5f0,0.5f0))
            v = Float32[]
            for t in T
                (okp(P[t[1]+1]) && okp(P[t[2]+1]) && okp(P[t[3]+1])) || continue
                for vi in t
                    p=P[vi+1]; nn = vi+1<=length(N) ? N[vi+1] : (0f0,1f0,0f0)
                    all(isfinite,nn) || (nn=(0f0,1f0,0f0))
                    uv = vi+1<=length(UV) ? UV[vi+1] : (0f0,0f0)
                    append!(v, Float32[p[1],p[2],-p[3], nn[1],nn[2],-nn[3], 1f0,1f0,1f0, uv[1],-uv[2]])
                end
            end
            isempty(v) || push!(parts, TrackPart(v, tex, col))
        end
    end
    parts
end

"""Car body/cockpit/driver as interleaved 11-float verts (untextured — uv=0,
per-part colour) in the rig-local frame."""
function extract_car(gd)
    mas = read_mas(joinpath(gd,"Vehicles","F158","Vanwall","Vanwall VW58.mas"))
    parts = (("vanwall_body.gmt",(0.11f0,0.35f0,0.20f0)), ("vanwall_cockpit.gmt",(0.08f0,0.14f0,0.11f0)),
             ("ca_driver.gmt",(0.42f0,0.35f0,0.27f0)))
    out = Float32[]
    ok(p)=all(isfinite,p)&&all(c->abs(c)<50,p)
    for (gmt,col) in parts
        i=findfirst(e->lowercase(e.name)==gmt, mas.entries); i===nothing && continue
        g=parse_gmt_indexed(extract(mas, mas.entries[i])); P=g.positions; N=g.normals
        for t in g.triangles
            (ok(P[t[1]+1])&&ok(P[t[2]+1])&&ok(P[t[3]+1])) || continue
            for vi in t
                p=P[vi+1]; nn=vi+1<=length(N) ? N[vi+1] : (0f0,1f0,0f0); all(isfinite,nn)||(nn=(0f0,1f0,0f0))
                append!(out, Float32[-p[3],p[2],p[1], -nn[3],nn[2],nn[1], col[1],col[2],col[3], 0f0,0f0])
            end
        end
    end
    out
end

# ---- textured car: indexed meshes whose UV stride varies per mesh, so detect
# it by which stride makes each triangle's three UVs locally coherent (small
# UV-space triangles).  Body → per-team livery; cockpit/driver → their own .dds.
f32at(b,o) = reinterpret(Float32, view(b, o+1:o+4))[1]
u16at(b,o) = Int(reinterpret(UInt16, view(b, o+1:o+2))[1])

"""Looser index-run recovery than `parse_gmt_indexed` (len ≥ 150, wider band) so
the FULL body is recovered (the tight threshold drops ~60 % of the triangles,
leaving a holey shell); the caller's edge-length filter removes the false
slivers this admits."""
function indexed_tris_loose(b, nv)
    N=length(b); vptr=Int(reinterpret(UInt32, view(b, 0x191:0x194))[1])
    band(o,w=96)= o+2w>N ? 1.0 : count(j->16000<=u16at(b,o+2j)<=16500, 0:w-1)/w
    tris=NTuple{3,Int}[]; o=vptr+32nv
    while o+2<=N
        if u16at(b,o)<nv && band(o)<0.05
            s=o; len=0
            while o+2<=N && u16at(b,o)<nv && band(o)<0.13; len+=1; o+=2; end
            if len>=150
                for t in 0:(len÷3)-1
                    a=u16at(b,s+6t); c=u16at(b,s+6t+2); d=u16at(b,s+6t+4)
                    (a!=c&&c!=d&&a!=d) && push!(tris,(a,c,d))
                end
            end
        else; o+=2; end
    end
    tris
end
function detect_uv_stride(b, attr, nv, T)
    best = (32, Inf)
    for st in (8,12,16,20,24,28,32,40,48)
        uv(k) = (k < nv && attr+st*k+8 <= length(b)) ? (f32at(b,attr+st*k), f32at(b,attr+st*k+4)) : (9f0,9f0)
        s = 0.0; c = 0
        for t in @view T[1:min(end,3000)]
            a=uv(t[1]); x=uv(t[2]); y=uv(t[3])
            (all(isfinite,a)&&all(isfinite,x)&&all(isfinite,y)) || continue
            s += max(hypot(a[1]-x[1],a[2]-x[2]), hypot(x[1]-y[1],x[2]-y[2]), hypot(y[1]-a[1],y[2]-a[2])); c += 1
        end
        m = c>0 ? s/c : Inf
        m < best[2] && (best = (st, m))
    end
    best[1]
end
function first_dds(b)
    run = IOBuffer()
    for c in b
        if 0x20 <= c <= 0x7e; write(run, Char(c))
        else
            s = String(take!(run)); endswith(lowercase(s), ".dds") && return s
        end
    end
    ""
end
"""Index every .dds available to the car: the car .mas plus the team folder
(per-team livery skins are loose files there)."""
function car_texture_index(gd)
    idx = Dict{String,Vector{UInt8}}()
    mas = read_mas(joinpath(gd,"Vehicles","F158","Vanwall","Vanwall VW58.mas"))
    for e in mas.entries; nm=lowercase(e.name); endswith(nm,".dds") && !haskey(idx,nm) && (idx[nm]=extract(mas,e)); end
    team = joinpath(gd,"Vehicles","F158","Vanwall","Teams","LewisEvans")
    isdir(team) && for f in readdir(team; join=true)
        endswith(lowercase(f),".dds") && (idx[lowercase(basename(f))] = read(f))
    end
    idx
end
"""Car body/cockpit/driver as textured TrackParts in the rig-local frame, UVs
auto-strided; the body uses the LewisEvans team livery."""
function extract_car_parts(gd)
    mas = read_mas(joinpath(gd,"Vehicles","F158","Vanwall","Vanwall VW58.mas"))
    specs = (("vanwall_body.gmt", "LewisEvans.dds", (0.11f0,0.35f0,0.20f0)),
             ("vanwall_cockpit.gmt", "", (0.08f0,0.14f0,0.11f0)),
             ("ca_driver.gmt", "", (0.42f0,0.35f0,0.27f0)))
    ok(p)=all(isfinite,p)&&all(c->abs(c)<50,p)
    parts = TrackPart[]
    for (gmt, texoverride, col) in specs
        i=findfirst(e->lowercase(e.name)==gmt, mas.entries); i===nothing && continue
        bb=extract(mas, mas.entries[i]); g=parse_gmt_indexed(bb); P=g.positions; N=g.normals
        nv=Int(reinterpret(UInt32,view(bb,0x17d:0x180))[1]); vptr=Int(reinterpret(UInt32,view(bb,0x191:0x194))[1])
        T = indexed_tris_loose(bb, nv); isempty(T) && continue
        attr=vptr+32nv; st=detect_uv_stride(bb, attr, nv, T)
        uv(k)= (k<nv && attr+st*k+8<=length(bb)) ? (f32at(bb,attr+st*k), f32at(bb,attr+st*k+4)) : (0f0,0f0)
        tex = texoverride=="" ? first_dds(bb) : texoverride
        v=Float32[]
        for t in T
            a=P[t[1]+1]; b2=P[t[2]+1]; c=P[t[3]+1]
            (ok(a)&&ok(b2)&&ok(c)) || continue
            # drop stray slivers from the indexed decode: real car triangles are
            # small, so any edge > 0.4 m is a false index connecting distant verts
            max(hypot((a.-b2)...), hypot((b2.-c)...), hypot((c.-a)...)) > 0.4 && continue
            for vi in t
                p=P[vi+1]; n=vi+1<=length(N) ? N[vi+1] : (0f0,1f0,0f0); all(isfinite,n)||(n=(0f0,1f0,0f0))
                u=uv(vi)
                append!(v, Float32[-p[3],p[2],p[1], -n[3],n[2],n[1], col[1],col[2],col[3], u[1],-u[2]])
            end
        end
        push!(parts, TrackPart(v, tex, col))
    end
    parts
end

"""Procedural wire-spoke wheel (untextured), axis along Z, 11-float verts."""
function wheel_mesh(r, hw; seg=28)
    out=Float32[]; tyre=(0.06f0,0.06f0,0.07f0); rim=(0.20f0,0.21f0,0.24f0)
    push3(p,n,c)=append!(out, Float32[p[1],p[2],p[3], n[1],n[2],n[3], c[1],c[2],c[3], 0f0,0f0])
    for i in 0:seg-1
        a0=2π*i/seg; a1=2π*(i+1)/seg
        for (rr,col) in ((r,tyre),(r*0.55f0,rim))
            x0,y0=rr*cos(a0),rr*sin(a0); x1,y1=rr*cos(a1),rr*sin(a1)
            n0=(cos(a0),sin(a0),0f0); n1=(cos(a1),sin(a1),0f0)
            push3((x0,y0,-hw),n0,col); push3((x1,y1,-hw),n1,col); push3((x1,y1,hw),n1,col)
            push3((x0,y0,-hw),n0,col); push3((x1,y1,hw),n1,col); push3((x0,y0,hw),n0,col)
            for z in (hw,-hw)
                push3((0f0,0f0,z),(0f0,0f0,Float32(sign(z))),col)
                push3((x0,y0,z),(0f0,0f0,Float32(sign(z))),col); push3((x1,y1,z),(0f0,0f0,Float32(sign(z))),col)
            end
        end
    end
    out
end

# ---- mat4 helpers (standard form; Julia column-major == GL column-major) ----
ident() = Matrix{Float32}(I,4,4)
function translate(t)
    M=ident(); M[1,4]=t[1]; M[2,4]=t[2]; M[3,4]=t[3]; M
end
function roty(a)
    c,s = cos(a),sin(a); M=ident(); M[1,1]=c; M[1,3]=s; M[3,1]=-s; M[3,3]=c; Float32.(M)
end
function rotz(a)
    c,s = cos(a),sin(a); M=ident(); M[1,1]=c; M[1,2]=-s; M[2,1]=s; M[2,2]=c; Float32.(M)
end
function perspective(fovy,aspect,near,far)
    f=1/tan(fovy/2); M=zeros(Float32,4,4)
    M[1,1]=f/aspect;M[2,2]=f;M[3,3]=(far+near)/(near-far);M[3,4]=2*far*near/(near-far);M[4,3]=-1; M
end
function lookat(eye,ctr,up)
    f=normalize(ctr.-eye); s=normalize(cross(f,up)); u=cross(s,f)
    Float32[ s[1] s[2] s[3] -dot(s,eye); u[1] u[2] u[3] -dot(u,eye); -f[1] -f[2] -f[3] dot(f,eye); 0 0 0 1 ]
end

# ---- shaders (textured diffuse × two-sided Lambert + hemispheric ambient) ----
const HORIZON = (0.66f0, 0.72f0, 0.78f0)      # pale haze — fog + sky horizon share it
const ZENITH  = (0.28f0, 0.46f0, 0.72f0)
const VSRC = """
#version 330 core
layout(location=0) in vec3 pos; layout(location=1) in vec3 nrm;
layout(location=2) in vec3 col; layout(location=3) in vec2 uv;
uniform mat4 uVP; uniform mat4 uModel; uniform mat4 uLightVP;
out vec3 vN; out vec3 vC; out vec2 vUV; out vec3 vWorld; out vec4 vLS;
void main(){ vN=mat3(uModel)*nrm; vC=col; vUV=uv;
  vWorld=(uModel*vec4(pos,1.0)).xyz; vLS=uLightVP*vec4(vWorld,1.0);
  gl_Position=uVP*uModel*vec4(pos,1.0); }"""
const FSRC = """
#version 330 core
in vec3 vN; in vec3 vC; in vec2 vUV; in vec3 vWorld; in vec4 vLS; out vec4 o;
uniform vec3 uLightDir; uniform sampler2D uTex; uniform int uHasTex; uniform float uBright;
uniform vec3 uCamPos; uniform vec3 uFogCol; uniform float uFogNear; uniform float uFogFar;
uniform sampler2D uShadow; uniform float uShadowTexel;
float shadow(vec3 N){
  vec3 lp = vLS.xyz/vLS.w*0.5+0.5;
  if(lp.z>1.0 || lp.x<0.0||lp.x>1.0||lp.y<0.0||lp.y>1.0) return 1.0;
  float bias = max(0.0025*(1.0-dot(N,normalize(uLightDir))), 0.0006);
  float s=0.0;
  for(int x=-1;x<=1;x++) for(int y=-1;y<=1;y++)
    s += (lp.z-bias > texture(uShadow, lp.xy+vec2(x,y)*uShadowTexel).r) ? 0.0 : 1.0;
  return s/9.0;
}
void main(){
  vec3 N=normalize(vN); if(!gl_FrontFacing) N=-N;
  float diff=max(dot(N,normalize(uLightDir)),0.0)*shadow(N);
  vec3 sky=vec3(0.81,0.89,0.97), grd=vec3(0.33,0.38,0.25);
  vec3 amb=mix(grd,sky,0.5+0.5*N.y)*0.6;
  vec3 base = uHasTex==1 ? texture(uTex,vUV).rgb : vC;
  vec3 lit = pow(base*(amb+diff*0.95)*uBright, vec3(0.85));
  float fog = clamp((length(vWorld-uCamPos)-uFogNear)/(uFogFar-uFogNear), 0.0, 1.0);
  o=vec4(mix(lit, uFogCol, fog*fog), 1.0);
}"""
# depth-only program for the shadow pass (render the scene from the sun's POV)
const DEPTH_VS = """
#version 330 core
layout(location=0) in vec3 pos; uniform mat4 uLightVP; uniform mat4 uModel;
void main(){ gl_Position=uLightVP*uModel*vec4(pos,1.0); }"""
const DEPTH_FS = "#version 330 core\nvoid main(){}"
# Sky: a fullscreen triangle whose fragments reconstruct the world view ray and
# shade a horizon→zenith gradient.  Drawn first, depth-test off.
const SKY_VS = """
#version 330 core
const vec2 P[3]=vec2[3](vec2(-1,-1),vec2(3,-1),vec2(-1,3));
out vec2 ndc; void main(){ ndc=P[gl_VertexID]; gl_Position=vec4(P[gl_VertexID],0,1); }"""
const SKY_FS = """
#version 330 core
in vec2 ndc; out vec4 o;
uniform mat4 uInvVP; uniform vec3 uCamPos; uniform vec3 uHorizon; uniform vec3 uZenith; uniform vec3 uLightDir;
void main(){
  vec4 wp=uInvVP*vec4(ndc,1.0,1.0); vec3 dir=normalize(wp.xyz/wp.w - uCamPos);
  float t=clamp(dir.y,0.0,1.0);
  vec3 col=mix(uHorizon, uZenith, sqrt(t));
  float sun=pow(max(dot(dir,normalize(uLightDir)),0.0), 200.0);   // soft sun disc
  o=vec4(col + vec3(1.0,0.95,0.8)*sun, 1.0);
}"""
compileok(s)=(r=Ref{GLint}(); glGetShaderiv(s,GL_COMPILE_STATUS,r); r[]!=0)
function compile(src,kind)
    s=glCreateShader(kind); glShaderSource(s,1,Ptr{GLchar}[pointer(src)],C_NULL); glCompileShader(s)
    compileok(s) || (buf=Vector{UInt8}(undef,2048); glGetShaderInfoLog(s,2048,C_NULL,buf); error("shader: ",String(buf)))
    s
end
function program()
    p=glCreateProgram(); glAttachShader(p,compile(VSRC,GL_VERTEX_SHADER)); glAttachShader(p,compile(FSRC,GL_FRAGMENT_SHADER)); glLinkProgram(p); p
end
function skyprogram()
    p=glCreateProgram(); glAttachShader(p,compile(SKY_VS,GL_VERTEX_SHADER)); glAttachShader(p,compile(SKY_FS,GL_FRAGMENT_SHADER)); glLinkProgram(p); p
end
function empty_vao(); v=Ref{GLuint}(); glGenVertexArrays(1,v); v[]; end
u3(prog,name,t)=glUniform3f(glGetUniformLocation(prog,name), Float32(t[1]),Float32(t[2]),Float32(t[3]))
"""Draw the gradient sky behind everything (depth test off, no depth write)."""
function draw_sky(skyprog, vao, invVP, campos, lightdir)
    glDisable(GL_DEPTH_TEST); glDepthMask(GL_FALSE)
    glUseProgram(skyprog)
    glUniformMatrix4fv(glGetUniformLocation(skyprog,"uInvVP"),1,GL_FALSE,Matrix{Float32}(invVP))
    u3(skyprog,"uCamPos",campos); u3(skyprog,"uHorizon",HORIZON); u3(skyprog,"uZenith",ZENITH); u3(skyprog,"uLightDir",lightdir)
    glBindVertexArray(vao); glDrawArrays(GL_TRIANGLES,0,3)
    glDepthMask(GL_TRUE); glEnable(GL_DEPTH_TEST)
end
# ---- shadow mapping: render scene depth from the sun's POV into a depth
# texture, then compare in the main pass (PCF-softened) to darken what the sun
# can't see.  The light box follows the car.
function depthprogram()
    p=glCreateProgram(); glAttachShader(p,compile(DEPTH_VS,GL_VERTEX_SHADER)); glAttachShader(p,compile(DEPTH_FS,GL_FRAGMENT_SHADER)); glLinkProgram(p); p
end
function ortho(l,r,b,t,n,f)
    M=zeros(Float32,4,4)
    M[1,1]=2/(r-l); M[2,2]=2/(t-b); M[3,3]=-2/(f-n)
    M[1,4]=-(r+l)/(r-l); M[2,4]=-(t+b)/(t-b); M[3,4]=-(f+n)/(f-n); M[4,4]=1; M
end
const SHADOW_SIZE = 2048
function make_shadow_fbo(size=SHADOW_SIZE)
    fbo=Ref{GLuint}(); glGenFramebuffers(1,fbo)
    tex=Ref{GLuint}(); glGenTextures(1,tex); glBindTexture(GL_TEXTURE_2D,tex[])
    glTexImage2D(GL_TEXTURE_2D,0,GL_DEPTH_COMPONENT24,size,size,0,GL_DEPTH_COMPONENT,GL_FLOAT,C_NULL)
    glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_NEAREST); glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_NEAREST)
    glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_S,GL_CLAMP_TO_BORDER); glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_T,GL_CLAMP_TO_BORDER)
    glTexParameterfv(GL_TEXTURE_2D,GL_TEXTURE_BORDER_COLOR,Float32[1,1,1,1])   # outside map = fully lit
    glBindFramebuffer(GL_FRAMEBUFFER,fbo[]); glFramebufferTexture2D(GL_FRAMEBUFFER,GL_DEPTH_ATTACHMENT,GL_TEXTURE_2D,tex[],0)
    glDrawBuffer(GL_NONE); glReadBuffer(GL_NONE); glBindFramebuffer(GL_FRAMEBUFFER,0)
    (fbo[], tex[])
end
"""Light view-projection: an orthographic box from the sun direction, centred on
`center` (the car), so the shadow map tracks the action."""
function light_vp(center, lightdir; R=70.0, depth=400.0)
    L=normalize(Float64.(lightdir)); eye=Float64.(center) .+ L.*(depth/2)
    up = abs(L[2])>0.99 ? [0.0,0.0,1.0] : [0.0,1.0,0.0]
    ortho(-R,R,-R,R,1.0,depth) * lookat(eye, Float64.(center), up)
end
function shadow_pass(drawfn, depthprog, fbo, lightVP; size=SHADOW_SIZE)
    glBindFramebuffer(GL_FRAMEBUFFER,fbo); glViewport(0,0,size,size); glClear(GL_DEPTH_BUFFER_BIT)
    glUseProgram(depthprog); glUniformMatrix4fv(glGetUniformLocation(depthprog,"uLightVP"),1,GL_FALSE,Matrix{Float32}(lightVP))
    glEnable(GL_POLYGON_OFFSET_FILL); glPolygonOffset(2.5f0, 4.0f0)
    drawfn(depthprog)
    glDisable(GL_POLYGON_OFFSET_FILL); glBindFramebuffer(GL_FRAMEBUFFER,0)
end
function draw_depth(depthprog, item, model)
    glUniformMatrix4fv(glGetUniformLocation(depthprog,"uModel"),1,GL_FALSE,Matrix{Float32}(model))
    glBindVertexArray(item.vao); glDrawArrays(GL_TRIANGLES,0,item.n)
end
"""Bind the shadow map + light matrix for the main pass (shadow on texture unit 1)."""
function bind_shadow(prog, shadowtex, lightVP; unit=1, size=SHADOW_SIZE)
    glUseProgram(prog)
    glUniformMatrix4fv(glGetUniformLocation(prog,"uLightVP"),1,GL_FALSE,Matrix{Float32}(lightVP))
    glActiveTexture(GL_TEXTURE0+unit); glBindTexture(GL_TEXTURE_2D,shadowtex)
    glUniform1i(glGetUniformLocation(prog,"uShadow"),Int32(unit))
    glUniform1f(glGetUniformLocation(prog,"uShadowTexel"),Float32(1/size))
end

"""Per-frame scene uniforms (camera position + distance fog into the haze)."""
function set_scene_uniforms(prog, campos; fognear=300f0, fogfar=2400f0)
    glUseProgram(prog)
    u3(prog,"uCamPos",campos); u3(prog,"uFogCol",HORIZON)
    glUniform1f(glGetUniformLocation(prog,"uFogNear"),Float32(fognear))
    glUniform1f(glGetUniformLocation(prog,"uFogFar"),Float32(fogfar))
end

# ---- 2D HUD: flat-coloured quads in pixel space (7-segment digits + bars), no
# font atlas needed.  Build a vertex list each frame, upload, draw on top.
const HUD_VS = """
#version 330 core
layout(location=0) in vec2 p; layout(location=1) in vec3 c; uniform vec2 uRes; out vec3 col;
void main(){ col=c; gl_Position=vec4(p.x/uRes.x*2.0-1.0, 1.0-p.y/uRes.y*2.0, 0.0, 1.0); }"""
const HUD_FS = "#version 330 core\nin vec3 col; out vec4 o; void main(){ o=vec4(col,1.0); }"
function hud_program()
    p=glCreateProgram(); glAttachShader(p,compile(HUD_VS,GL_VERTEX_SHADER)); glAttachShader(p,compile(HUD_FS,GL_FRAGMENT_SHADER)); glLinkProgram(p); p
end
function hud_buffers(); vao=Ref{GLuint}();glGenVertexArrays(1,vao); vbo=Ref{GLuint}();glGenBuffers(1,vbo); (vao[],vbo[]); end
function hquad!(v,x,y,w,h,c)
    for (px,py) in ((x,y),(x+w,y),(x+w,y+h),(x,y),(x+w,y+h),(x,y+h)); append!(v,Float32[px,py,c[1],c[2],c[3]]); end
end
const SEG7 = (63,6,91,79,102,109,125,7,127,111)     # digit → lit-segment bitmask (a..g)
function hdigit!(v,x,y,W,H,T,d,c)
    (0<=d<=9) || return
    m=SEG7[d+1]; vl=(H-3T)/2
    (m&1)!=0  && hquad!(v,x+T,y,W-2T,T,c)            # a top
    (m&32)!=0 && hquad!(v,x,y+T,T,vl,c)              # f upper-left
    (m&2)!=0  && hquad!(v,x+W-T,y+T,T,vl,c)          # b upper-right
    (m&64)!=0 && hquad!(v,x+T,y+T+vl,W-2T,T,c)       # g middle
    (m&16)!=0 && hquad!(v,x,y+2T+vl,T,vl,c)          # e lower-left
    (m&4)!=0  && hquad!(v,x+W-T,y+2T+vl,T,vl,c)      # c lower-right
    (m&8)!=0  && hquad!(v,x+T,y+H-T,W-2T,T,c)        # d bottom
end
function hnumber!(v,x,y,W,H,T,n,c)
    s=string(max(0,Int(round(n))))
    for (i,ch) in enumerate(s); hdigit!(v,x+(i-1)*(W+2T),y,W,H,T,Int(ch)-48,c); end
end
"""Compose the instrument readout: big 7-seg speed, gear, and throttle/brake/rpm
bars.  Returns the HUD vertex list for `hud_draw`."""
function compose_hud(W,H,kmh,gear,rpm,revlim,thr,brk)
    v=Float32[]
    white=(0.90,0.95,1.0); amber=(1.0,0.82,0.35); green=(0.42,0.82,0.42); red=(0.95,0.35,0.30); dim=(0.16,0.18,0.22)
    hnumber!(v, 40, H-104, 40, 76, 11, kmh, white)             # speed (big)
    hdigit!(v, 250, H-98, 38, 66, 10, clamp(round(Int,gear),0,9), amber)  # gear
    function bar(x,frac,col)
        bw=22; bh=78; by=H-104; hquad!(v,x,by,bw,bh,dim)
        f=clamp(frac,0,1); f>0 && hquad!(v,x,by+bh*(1-f),bw,bh*f,col)
    end
    bar(320, thr, green); bar(350, brk, red)
    rf = rpm/max(revlim,1f0); bar(380, rf, rf>0.9 ? red : amber)
    v
end
function hud_draw(prog,vao,vbo,v,W,H)
    isempty(v) && return
    glDisable(GL_DEPTH_TEST); glUseProgram(prog)
    glUniform2f(glGetUniformLocation(prog,"uRes"),Float32(W),Float32(H))
    glBindVertexArray(vao); glBindBuffer(GL_ARRAY_BUFFER,vbo)
    glBufferData(GL_ARRAY_BUFFER,sizeof(v),v,GL_DYNAMIC_DRAW)
    glVertexAttribPointer(0,2,GL_FLOAT,false,5*4,Ptr{Cvoid}(0)); glEnableVertexAttribArray(0)
    glVertexAttribPointer(1,3,GL_FLOAT,false,5*4,Ptr{Cvoid}(2*4)); glEnableVertexAttribArray(1)
    glDrawArrays(GL_TRIANGLES,0,length(v)÷5); glEnable(GL_DEPTH_TEST)
end

# ---- DDS → GL texture (S3TC/DXT uploaded compressed) ----
const DXT1 = GLenum(0x83F1); const DXT3 = GLenum(0x83F2); const DXT5 = GLenum(0x83F3)
u32le(b,o)=reinterpret(UInt32,view(b,o+1:o+4))[1]
function load_dds(b)
    (length(b)>=128 && String(copy(b[1:4]))=="DDS ") || return GLuint(0)
    height=Int(u32le(b,12)); width=Int(u32le(b,16)); mip=max(1,Int(u32le(b,28)))
    fourcc=String(copy(b[85:88]))
    fmt = fourcc=="DXT1" ? DXT1 : fourcc=="DXT3" ? DXT3 : fourcc=="DXT5" ? DXT5 : return GLuint(0)
    bb = fourcc=="DXT1" ? 8 : 16
    tex=Ref{GLuint}(); glGenTextures(1,tex); glBindTexture(GL_TEXTURE_2D,tex[])
    off=128; w=width; h=height
    for lvl in 0:mip-1
        w=max(w,1); h=max(h,1)
        sz=max(1,(w+3)÷4)*max(1,(h+3)÷4)*bb
        off+sz>length(b) && break
        glCompressedTexImage2D(GL_TEXTURE_2D, lvl, fmt, w, h, 0, sz, b[off+1:off+sz])
        off+=sz; w÷=2; h÷=2
    end
    glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_S,GL_REPEAT); glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_T,GL_REPEAT)
    glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_LINEAR_MIPMAP_LINEAR); glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_LINEAR)
    tex[]
end

"""Index every .dds in the track's .mas archives (name → bytes), so textures
referenced by the meshes can be found and uploaded on demand."""
function texture_index(dir)
    idx = Dict{String,Vector{UInt8}}()
    for masp in filter(p->endswith(lowercase(p),".mas"), readdir(dir; join=true))
        m = read_mas(masp)
        for e in m.entries
            nm=lowercase(e.name)
            endswith(nm,".dds") && !haskey(idx,nm) && (idx[nm]=extract(m,e))
        end
    end
    idx
end

# ---- mesh upload / draw ----
struct Item; vao::GLuint; n::GLsizei; tex::GLuint; col::NTuple{3,Float32}; end
function upload(interleaved)
    vao=Ref{GLuint}(); glGenVertexArrays(1,vao); glBindVertexArray(vao[])
    vbo=Ref{GLuint}(); glGenBuffers(1,vbo); glBindBuffer(GL_ARRAY_BUFFER,vbo[])
    glBufferData(GL_ARRAY_BUFFER,sizeof(interleaved),interleaved,GL_STATIC_DRAW)
    st=11*4
    for (loc,off) in ((0,0),(1,3*4),(2,6*4),(3,9*4))
        glVertexAttribPointer(loc,(loc==3 ? 2 : 3),GL_FLOAT,false,st,Ptr{Cvoid}(off)); glEnableVertexAttribArray(loc)
    end
    Ref{GLuint}(vao[])[], GLsizei(length(interleaved)÷11)
end
"""Upload track parts; resolve each part's diffuse texture from the index."""
function build_track(parts, texidx)
    cache=Dict{String,GLuint}(); items=Item[]
    for p in parts
        vao,n = upload(p.verts)
        tid=GLuint(0)
        if p.tex != ""
            key=lowercase(p.tex)
            tid = get!(cache,key) do
                haskey(texidx,key) ? load_dds(texidx[key]) : GLuint(0)
            end
        end
        push!(items, Item(vao,n,tid,p.col))
    end
    items
end
setmat(prog,name,M)=glUniformMatrix4fv(glGetUniformLocation(prog,name),1,GL_FALSE,M)
function draw(prog, item::Item, vp, model; bright::Real=1.0)
    setmat(prog,"uVP",vp); setmat(prog,"uModel",model)
    glUniform1f(glGetUniformLocation(prog,"uBright"), Float32(bright))
    if item.tex != 0
        glUniform1i(glGetUniformLocation(prog,"uHasTex"),1)
        glActiveTexture(GL_TEXTURE0); glBindTexture(GL_TEXTURE_2D,item.tex)
        glUniform1i(glGetUniformLocation(prog,"uTex"),0)
    else
        glUniform1i(glGetUniformLocation(prog,"uHasTex"),0)
    end
    glBindVertexArray(item.vao); glDrawArrays(GL_TRIANGLES,0,item.n)
end
"""Upload a bare interleaved blob as an untextured Item (car, wheels)."""
function item(interleaved)
    vao,n = upload(interleaved); Item(vao,n,GLuint(0),(1f0,1f0,1f0))
end

end # module
