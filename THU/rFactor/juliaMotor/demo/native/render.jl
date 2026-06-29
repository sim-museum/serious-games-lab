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
include("gpl3do.jl"); using .GPL3DO        # Grand Prix Legends model parser (Lotus 49)
include("gplmip.jl"); using .GPLMip        # GPL .mip texture decoder
include("gpldat.jl"); using .GPLDat        # GPL track .dat archive (packed objects/textures)

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

"""The cockpit steering wheel (`volante`) as a textured TrackPart, CENTRED at its
own origin (rig frame) so the caller can position it on the column and spin it
about X with the steering input."""
function extract_steering_wheel(gd)
    mas = read_mas(joinpath(gd,"Vehicles","F158","Vanwall","Vanwall VW58.mas"))
    i=findfirst(e->lowercase(e.name)=="volante.gmt", mas.entries); i===nothing && return nothing
    bb=extract(mas, mas.entries[i]); g=parse_gmt_indexed(bb); P=g.positions; N=g.normals
    nv=Int(reinterpret(UInt32,view(bb,0x17d:0x180))[1]); vptr=Int(reinterpret(UInt32,view(bb,0x191:0x194))[1])
    attr=vptr+32nv; T=g.triangles; isempty(T) && return nothing   # tight decode (fewer slivers)
    st=detect_uv_stride(bb,attr,nv,T)
    uv(k)= (k<nv && attr+st*k+8<=length(bb)) ? (f32at(bb,attr+st*k), f32at(bb,attr+st*k+4)) : (0f0,0f0)
    ok(p)=all(isfinite,p)&&all(c->abs(c)<50,p); v=Float32[]
    for t in T
        a=P[t[1]+1]; b2=P[t[2]+1]; c=P[t[3]+1]; (ok(a)&&ok(b2)&&ok(c)) || continue
        max(hypot((a.-b2)...),hypot((b2.-c)...),hypot((c.-a)...))>0.28 && continue   # wheel is small
        for vi in t
            p=P[vi+1]; n=vi+1<=length(N) ? N[vi+1] : (0f0,1f0,0f0); all(isfinite,n)||(n=(0f0,1f0,0f0))
            u=uv(vi); append!(v, Float32[-p[3],p[2],p[1], -n[3],n[2],n[1], 1f0,1f0,1f0, u[1],-u[2]])
        end
    end
    TrackPart(v, "VANWALL_STEERING_WHEEL.DDS", (0.35f0,0.26f0,0.18f0))
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
function rotx(a)
    c,s = cos(a),sin(a); M=ident(); M[2,2]=c; M[2,3]=-s; M[3,2]=s; M[3,3]=c; Float32.(M)
end
scalexyz(x,y,z) = Float32[x 0 0 0; 0 y 0 0; 0 0 z 0; 0 0 0 1]
# average vertex normal of a mesh part (11-float stride) — the steering wheel's
# disc normal, i.e. its column axis (already raked toward the front axle in the mesh)
function disc_normal(v)
    n=length(v)÷11; nx=ny=nz=0.0
    for k in 0:n-1; nx+=v[k*11+4]; ny+=v[k*11+5]; nz+=v[k*11+6]; end
    Float32.(normalize([nx,ny,nz]))
end
# rotation about an arbitrary unit axis (Rodrigues) — used to spin the steering
# wheel about its own column axis (the disc normal) without re-orienting it
function rotaxis(axis, θ)
    x,y,z = normalize(Float64.(collect(axis))); c=cos(θ); s=sin(θ); t=1-c; M=ident()
    M[1,1]=t*x*x+c;   M[1,2]=t*x*y-s*z; M[1,3]=t*x*z+s*y
    M[2,1]=t*x*y+s*z; M[2,2]=t*y*y+c;   M[2,3]=t*y*z-s*x
    M[3,1]=t*x*z-s*y; M[3,2]=t*y*z+s*x; M[3,3]=t*z*z+c; Float32.(M)
end
function perspective(fovy,aspect,near,far)
    f=1/tan(fovy/2); M=zeros(Float32,4,4)
    M[1,1]=f/aspect;M[2,2]=f;M[3,3]=(far+near)/(near-far);M[3,4]=2*far*near/(near-far);M[4,3]=-1; M
end
# Reversed-Z perspective: maps near→1, far→0 into a [0,1] clip-depth range.  Needs the
# main pass set up with glClipControl(ZERO_TO_ONE) + glDepthFunc(GEQUAL) + glClearDepth(0).
# Combined with a float depth buffer this spreads depth precision near-UNIFORMLY with
# distance (the float exponent near 0 cancels the 1/z crunch), so coplanar surfaces at
# 150 m+ (advertising signs on fences) stop z-fighting — the strobe a standard [−1,1]
# 24-bit buffer can't avoid.
function perspective_revz(fovy,aspect,near,far)
    f=1/tan(fovy/2); M=zeros(Float32,4,4)
    M[1,1]=f/aspect; M[2,2]=f
    M[3,3]=near/(far-near); M[3,4]=far*near/(far-near); M[4,3]=-1; M
end
function lookat(eye,ctr,up)
    f=normalize(ctr.-eye); s=normalize(cross(f,up)); u=cross(s,f)
    Float32[ s[1] s[2] s[3] -dot(s,eye); u[1] u[2] u[3] -dot(u,eye); -f[1] -f[2] -f[3] dot(f,eye); 0 0 0 1 ]
end

# ---- shaders (textured diffuse × two-sided Lambert + hemispheric ambient) ----
const HORIZON = (0.78f0, 0.78f0, 0.75f0)      # warm pale haze (was cold blue 0.66,0.72,0.78) — fog + sky horizon share it
const ZENITH  = (0.40f0, 0.56f0, 0.78f0)      # paler/hazier blue (was deep 0.28,0.46,0.72) — GPL's overcast-ish sky
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
uniform sampler2D uShadow; uniform float uShadowTexel; uniform float uSpec; uniform int uBackFlip;
uniform float uAmbFill;   // flat fill light (GPL pre-lit cockpit interior — lifts self-shadowed faces)
uniform float uAlpha;     // per-draw opacity multiplier (1 = opaque; <1 = glass, e.g. the windscreen)
uniform int uCutout;      // 1 for chain-link/foliage cutouts → sharpen alpha edge (kill shimmer)
uniform int uGraze;       // 1 for GPL tree-LINE meshes → fade faces viewed edge-on (kills the end-on "smear")
uniform int uSky;
uniform vec3 uSunCol;     // directional-sun tint (warm white on the sunny grade; white = neutral GPL)
uniform vec3 uAmbSky;     // up-facing sky-fill colour (cool blue on the sunny grade → cooler shadows)
uniform float uSat;       // output saturation multiplier (>1 = punchier sunny colours; 1 = neutral)
uniform vec3 uSkyTint;    // GPL horizon-ring multiply (warm/brighten the overcast band toward sunny)
uniform vec3 uTint;       // per-draw colour multiply (default white = no-op; e.g. de-blue the crowd MIP)
float shadow(vec3 N){
  vec3 lp = vLS.xyz/vLS.w*0.5+0.5;
  if(lp.z>1.0 || lp.x<0.0||lp.x>1.0||lp.y<0.0||lp.y>1.0) return 1.0;
  float bias = max(0.0035*(1.0-dot(N,normalize(uLightDir))), 0.0018);   // larger → kill flat-ground acne
  float s=0.0;
  for(int x=-1;x<=1;x++) for(int y=-1;y<=1;y++)
    s += (lp.z-bias > texture(uShadow, lp.xy+vec2(x,y)*uShadowTexel).r) ? 0.0 : 1.0;
  s /= 9.0;
  // fade shadowing to fully-lit before the shadow-map box edge, so the box boundary
  // (which tracks the car) isn't a visible "light carpet" sweeping the ground
  vec2 e = abs(lp.xy - 0.5);
  return mix(s, 1.0, smoothstep(0.40, 0.5, max(e.x, e.y)));
}
void main(){
  vec2 uv = (uBackFlip==1 && !gl_FrontFacing) ? vec2(1.0-vUV.x, vUV.y) : vUV;  // un-mirror back-facing sign text
  vec4 t = uHasTex==1 ? texture(uTex,uv) : vec4(vC,1.0);
  if(uHasTex==1){
    if(uCutout==1){
      if(t.a < 0.02) discard;
      // CUTOUTS ONLY (chain-link/foliage): sharpen the alpha to a ~1px screen-space edge.
      // Distant cutouts shimmer because mipmapping softens their alpha to mid-grey and
      // alpha-to-coverage then dithers it per pixel; rescaling by the derivative keeps the
      // edge ~1px (smooth + stable) at any distance.  Gated to cutouts so blended overlays
      // (the racing groove) keep their soft alpha and don't harden into a black strip.
      t.a = clamp((t.a - 0.5) / max(fwidth(t.a), 1e-4) + 0.5, 0.0, 1.0);
      // Far away the wires are sub-pixel (fwidth huge → alpha stuck ~0.5, keeps crawling):
      // fade that UNRESOLVED partial alpha toward transparent with distance so it drops out
      // cleanly.  Solid alpha (signs) → pow(1.0,·)=1 stays; only the flickery mid-alpha goes.
      t.a = pow(t.a, 1.0 + smoothstep(140.0, 460.0, length(vWorld-uCamPos))*4.0);
    } else if(t.a < 0.04) discard;              // blended/opaque: plain soft alpha-to-coverage
  }
  if(uSky==1){ o=vec4(t.rgb*uSkyTint, 1.0); return; }     // horizon ring: unlit, unfogged backdrop (tinted/brightened per grade)
  vec3 N = dot(vN,vN) > 1e-6 ? normalize(vN) : vec3(0.0,1.0,0.0);  // guard zero/degenerate normals
  if(!gl_FrontFacing) N=-N;
  float diff=max(dot(N,normalize(uLightDir)),0.0)*shadow(N);
  vec3 grd=vec3(0.34,0.36,0.26);                             // ground-bounce fill (warm)
  vec3 amb=mix(grd,uAmbSky,0.5+0.5*N.y)*0.46;                // sky-fill: uAmbSky tints the up-facing fill (cool=sunny shadows)
  vec3 base = t.rgb * uTint;                                 // per-draw colour multiply (default white)
  if(uHasTex==1 && max(abs(vUV.x),abs(vUV.y)) > 3.0)   // tiling surface: gently break up the repeat
    base *= mix(vec3(1.0), texture(uTex, vUV*0.07).rgb * 1.7, 0.45);   // softer → no harsh light/dark patches
  vec3 lit = pow(base*(amb+0.5*uAmbFill+diff*1.15*uSunCol)*uBright, vec3(0.94));   // stronger sun (0.95→1.15), tinted by uSunCol; gamma→neutral (0.85→0.94) ⇒ GPL contrast
  lit += uAmbFill*vec3(0.13,0.135,0.125);   // ADDITIVE fill: lifts pure-black cockpit parts
                                            // (tub/dash) to a visible dark grey, as GPL pre-lights them
  if(uSpec > 0.0){                               // Blinn-Phong sheen (painted/chrome bodywork)
    vec3 V = normalize(uCamPos - vWorld);
    float s = pow(max(dot(N, normalize(normalize(uLightDir)+V)), 0.0), 28.0) * uSpec * step(0.01, diff);
    lit += s * vec3(1.0, 0.97, 0.9);
  }
  lit = mix(vec3(dot(lit, vec3(0.299,0.587,0.114))), lit, uSat);   // grade: punch up colour for the sunny look (uSat=1 → no-op)
  float fog = clamp((length(vWorld-uCamPos)-uFogNear)/(uFogFar-uFogNear), 0.0, 1.0);
  float alpha = uHasTex==1 ? t.a : 1.0;
  if(uGraze==1){                                  // tree-line mesh: fade quads seen edge-on (no streaky end-on smear)
    float g = abs(dot(N, normalize(uCamPos - vWorld)));   // 0 = edge-on, 1 = face-on
    alpha *= smoothstep(0.05, 0.32, g);
  }
  o=vec4(mix(lit, uFogCol, fog*fog), alpha*uAlpha);     // alpha → MSAA coverage (smooth cutout edges); uAlpha = glass
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
uniform mat4 uInvVP; uniform vec3 uCamPos; uniform vec3 uHorizon; uniform vec3 uZenith; uniform vec3 uLightDir; uniform float uCloud;
float hash(vec2 p){ return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453); }
float noise(vec2 p){ vec2 i=floor(p),f=fract(p); f=f*f*(3.0-2.0*f);
  return mix(mix(hash(i),hash(i+vec2(1,0)),f.x), mix(hash(i+vec2(0,1)),hash(i+vec2(1,1)),f.x), f.y); }
float fbm(vec2 p){ float v=0.0,a=0.55; for(int i=0;i<5;i++){ v+=a*noise(p); p=p*2.03+vec2(1.7,9.2); a*=0.5; } return v; }
void main(){
  vec4 wp=uInvVP*vec4(ndc,1.0,1.0); vec3 dir=normalize(wp.xyz/wp.w - uCamPos);
  float t=clamp(dir.y,0.0,1.0);
  vec3 col=mix(uHorizon, uZenith, sqrt(t));
  float sun=pow(max(dot(dir,normalize(uLightDir)),0.0), 200.0);
  if(dir.y > 0.01){                                  // procedural cloud layer
    vec2 cp = (uCamPos.xz + dir.xz/dir.y*1400.0)*0.0011;
    float c = fbm(cp);
    float cov = smoothstep(0.52,0.82,c) * smoothstep(0.015,0.22,dir.y) * uCloud;
    col = mix(col, mix(vec3(0.75,0.78,0.84), vec3(1.0), c), cov*0.9);
    sun *= (1.0 - cov*0.85);
  }
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
function draw_sky(skyprog, vao, invVP, campos, lightdir; cloud::Real=1.0, horizon=HORIZON, zenith=ZENITH)
    glDisable(GL_DEPTH_TEST); glDepthMask(GL_FALSE)
    glUseProgram(skyprog)
    glUniformMatrix4fv(glGetUniformLocation(skyprog,"uInvVP"),1,GL_FALSE,Matrix{Float32}(invVP))
    u3(skyprog,"uCamPos",campos); u3(skyprog,"uHorizon",horizon); u3(skyprog,"uZenith",zenith); u3(skyprog,"uLightDir",lightdir)
    glUniform1f(glGetUniformLocation(skyprog,"uCloud"), Float32(cloud))
    glBindVertexArray(vao); glDrawArrays(GL_TRIANGLES,0,3)
    glDepthMask(GL_TRUE); glEnable(GL_DEPTH_TEST)
end
# ---- post-process anti-aliasing (FXAA) -------------------------------------
# MSAA only smooths geometry silhouettes; the faceted/decoded body shows hard
# *internal* edges that MSAA can't touch.  We render the scene into an offscreen
# (multisampled) FBO, resolve it, then run Lottes' FXAA over the whole image so
# every contrast edge — silhouette and facet alike — is softened.  The HUD is
# drawn afterwards, straight to the screen, so it stays crisp.
const FXAA_VS = """
#version 330 core
const vec2 P[3]=vec2[3](vec2(-1,-1),vec2(3,-1),vec2(-1,3));
out vec2 uv; void main(){ vec2 p=P[gl_VertexID]; uv=p*0.5+0.5; gl_Position=vec4(p,0,1); }"""
const FXAA_FS = """
#version 330 core
in vec2 uv; out vec4 o; uniform sampler2D uTex; uniform vec2 uInv;
float L(vec3 c){ return dot(c, vec3(0.299,0.587,0.114)); }
void main(){
  vec3 mC=texture(uTex,uv).rgb;
  vec3 nw=texture(uTex,uv+vec2(-1,-1)*uInv).rgb, ne=texture(uTex,uv+vec2(1,-1)*uInv).rgb;
  vec3 sw=texture(uTex,uv+vec2(-1, 1)*uInv).rgb, se=texture(uTex,uv+vec2(1, 1)*uInv).rgb;
  float lnw=L(nw),lne=L(ne),lsw=L(sw),lse=L(se),lm=L(mC);
  float lmin=min(lm,min(min(lnw,lne),min(lsw,lse))), lmax=max(lm,max(max(lnw,lne),max(lsw,lse)));
  if(lmax-lmin < 0.045){ o=vec4(mC,1.0); return; }       // no edge here
  vec2 dir=vec2(-((lnw+lne)-(lsw+lse)), ((lnw+lsw)-(lne+lse)));
  float red=max((lnw+lne+lsw+lse)*0.25*(1.0/8.0), 1.0/128.0);
  float rcp=1.0/(min(abs(dir.x),abs(dir.y))+red);
  dir=clamp(dir*rcp, vec2(-8.0), vec2(8.0))*uInv;
  vec3 a=0.5*(texture(uTex,uv+dir*(1.0/3.0-0.5)).rgb + texture(uTex,uv+dir*(2.0/3.0-0.5)).rgb);
  vec3 b=a*0.5 + 0.25*(texture(uTex,uv+dir*-0.5).rgb + texture(uTex,uv+dir*0.5).rgb);
  float lb=L(b);
  o=vec4((lb<lmin||lb>lmax)?a:b, 1.0);
}"""
function fxaa_program()
    p=glCreateProgram(); glAttachShader(p,compile(FXAA_VS,GL_VERTEX_SHADER)); glAttachShader(p,compile(FXAA_FS,GL_FRAGMENT_SHADER)); glLinkProgram(p); p
end
# multisampled scene FBO + single-sample resolve target (sampleable color texture)
function make_scene_fbo(w, h; samples=4)
    ms=Ref{GLuint}(); glGenFramebuffers(1,ms); glBindFramebuffer(GL_FRAMEBUFFER, ms[])
    c=Ref{GLuint}(); glGenRenderbuffers(1,c); glBindRenderbuffer(GL_RENDERBUFFER, c[])
    glRenderbufferStorageMultisample(GL_RENDERBUFFER, samples, GL_RGBA8, w, h)
    glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_RENDERBUFFER, c[])
    d=Ref{GLuint}(); glGenRenderbuffers(1,d); glBindRenderbuffer(GL_RENDERBUFFER, d[])
    glRenderbufferStorageMultisample(GL_RENDERBUFFER, samples, GL_DEPTH_COMPONENT32F, w, h)  # 32F: +8 depth bits → less distant z-fight (signs on fences) without reversed-Z
    glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, d[])
    rf=Ref{GLuint}(); glGenFramebuffers(1,rf); glBindFramebuffer(GL_FRAMEBUFFER, rf[])
    rt=Ref{GLuint}(); glGenTextures(1,rt); glBindTexture(GL_TEXTURE_2D, rt[])
    glTexImage2D(GL_TEXTURE_2D,0,GL_RGBA8,w,h,0,GL_RGBA,GL_UNSIGNED_BYTE,C_NULL)
    glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_LINEAR); glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_S,GL_CLAMP_TO_EDGE); glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_T,GL_CLAMP_TO_EDGE)
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, rt[], 0)
    glBindFramebuffer(GL_FRAMEBUFFER, 0)
    (ms[], rf[], rt[])
end
# resolve the multisampled scene into the single-sample texture, then FXAA to screen
function resolve_and_fxaa(fxaaprog, vao, msfbo, resolvefbo, resolvetex, w, h)
    glBindFramebuffer(GL_READ_FRAMEBUFFER, msfbo); glBindFramebuffer(GL_DRAW_FRAMEBUFFER, resolvefbo)
    glBlitFramebuffer(0,0,w,h, 0,0,w,h, GL_COLOR_BUFFER_BIT, GL_NEAREST)
    glBindFramebuffer(GL_FRAMEBUFFER, 0); glViewport(0,0,w,h)
    glDisable(GL_DEPTH_TEST)
    glUseProgram(fxaaprog); glActiveTexture(GL_TEXTURE0); glBindTexture(GL_TEXTURE_2D, resolvetex)
    glUniform1i(glGetUniformLocation(fxaaprog,"uTex"), 0)
    glUniform2f(glGetUniformLocation(fxaaprog,"uInv"), 1f0/w, 1f0/h)
    glBindVertexArray(vao); glDrawArrays(GL_TRIANGLES,0,3)
    glEnable(GL_DEPTH_TEST)
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
    # the shadow map stays STANDARD depth ([0,1] clip, near→0, LESS) regardless of the
    # reversed-Z main pass — so the shadow map + the sampler logic in the FS are untouched
    glClipControl(GL_LOWER_LEFT, GL_NEGATIVE_ONE_TO_ONE); glDepthFunc(GL_LESS); glClearDepth(1.0)
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
function set_scene_uniforms(prog, campos; fognear=300f0, fogfar=2400f0,
                            fogcol=HORIZON, suncol=(1f0,1f0,1f0),
                            ambsky=(0.95f0,0.93f0,0.86f0), sat=1f0)
    glUseProgram(prog)
    u3(prog,"uCamPos",campos); u3(prog,"uFogCol",fogcol)
    u3(prog,"uSunCol",suncol); u3(prog,"uAmbSky",ambsky)
    glUniform1f(glGetUniformLocation(prog,"uSat"),Float32(sat))
    glUniform1f(glGetUniformLocation(prog,"uFogNear"),Float32(fognear))
    glUniform1f(glGetUniformLocation(prog,"uFogFar"),Float32(fogfar))
    glUniform3f(glGetUniformLocation(prog,"uTint"),1f0,1f0,1f0)   # frame default white (draws that bypass draw(), e.g. the horizon ring)
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
    m = d < 0 ? 84 : (0<=d<=9 ? SEG7[d+1] : return)   # d<0 ⇒ lowercase "n" (segments c+e+g) for NEUTRAL
    vl=(H-3T)/2
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
function hline!(v,x1,y1,x2,y2,t,c)
    dx=x2-x1; dy=y2-y1; len=hypot(dx,dy); len<1e-3 && return
    px=-dy/len*(t/2); py=dx/len*(t/2)
    for (qx,qy) in ((x1+px,y1+py),(x2+px,y2+py),(x2-px,y2-py),(x1+px,y1+py),(x2-px,y2-py),(x1-px,y1-py))
        append!(v,Float32[qx,qy,c[1],c[2],c[3]])
    end
end
function hcircle!(v,cx,cy,r,t,c;seg=22)
    px,py=cx+r,cy
    for i in 1:seg; a=2π*i/seg; qx,qy=cx+r*cos(a),cy+r*sin(a); hline!(v,px,py,qx,qy,t,c); px,py=qx,qy; end
end
"Filled (SOLID) disc — triangle fan emitted as GL_TRIANGLES (center, p_i, p_i+1)."
function hdisc!(v,cx,cy,r,c;seg=26)
    for i in 1:seg
        a0=2π*(i-1)/seg; a1=2π*i/seg
        append!(v, Float32[cx,cy, c[1],c[2],c[3]])
        append!(v, Float32[cx+r*cos(a0),cy+r*sin(a0), c[1],c[2],c[3]])
        append!(v, Float32[cx+r*cos(a1),cy+r*sin(a1), c[1],c[2],c[3]])
    end
end
# nominal static grip μ·Fz [mg/4 units] that maps to the base ring radius — so a tyre
# at static load draws ~baseR, a loaded (outside/squatting) tyre draws BIGGER, a light
# (inside/airborne) tyre draws SMALLER.  (front static ≈1.24, rear ≈1.53 ⇒ ~1.38 avg.)
const GRIP_REF = 1.38
"""One per-wheel traction circle.  `tc` = (Fx_long, Fy_lat, GRIP=μ·Fz), all in mg/4.
The RING RADIUS scales with the grip (μ·Fz) — it GROWS as the tyre loads up under
weight transfer and SHRINKS as it goes light — and the dot is the force at the same
pixels-per-Newton scale, so it sits INSIDE the ring with grip in hand (green), at the
EDGE at the limit, and OUTSIDE when the tyre breaks away and skids (red)."""
function htraction!(v,cx,cy,baseR,tc)
    long,lat,grip = Float64(tc[1]),Float64(tc[2]),max(Float64(tc[3]),1e-3)
    s = baseR / GRIP_REF                           # pixels per (mg/4) — common scale for ring AND force
    R = clamp(grip*s, baseR*0.45, baseR*1.7)       # ring = the grip limit (varies with load)
    util = hypot(long,lat)/grip                    # 1.0 = at the friction limit (skid onset)
    col = util<0.7 ? (0.40,0.80,0.40) : util<0.95 ? (0.92,0.80,0.32) : (0.95,0.32,0.28)
    hdisc!(v,cx,cy,R,(0.09,0.10,0.13))             # SOLID opaque backing (no see-through road)
    hcircle!(v,cx,cy,R,2.5,(0.58,0.64,0.72))       # bright grip ring = the friction limit (size = grip)
    dx=-lat*s; dy=-long*s                          # force at the SAME scale: |dx,dy| reaches R at the limit
    m=hypot(dx,dy); cap=R*1.5; m>cap && (dx*=cap/m; dy*=cap/m)   # cap a big skid so the dot stays on-screen
    hquad!(v,cx+dx-4,cy+dy-4,8,8,col)              # force dot: inside=grip in hand, outside=skidding
end

"""Render a lap time `secs` as 7-segment M:SS.t at (x,y) in colour c."""
function htime!(v,x,y,secs,c; Wd=18,Hd=30,T=4,gap=6)
    secs = max(0.0, Float64(secs)); m = floor(Int, secs/60); s = secs - 60m
    si = floor(Int, s); ti = floor(Int, (s-si)*10); cx = Float64(x)
    hdigit!(v,cx,y,Wd,Hd,T, m%10, c); cx += Wd+gap
    hquad!(v,cx,y+Hd*0.28,T,T,c); hquad!(v,cx,y+Hd*0.60,T,T,c); cx += T+gap   # colon
    hdigit!(v,cx,y,Wd,Hd,T, si÷10, c); cx += Wd+3
    hdigit!(v,cx,y,Wd,Hd,T, si%10, c); cx += Wd+gap
    hquad!(v,cx,y+Hd-T,T,T,c); cx += T+gap                                    # decimal point
    hdigit!(v,cx,y,Wd,Hd,T, ti, c)
end

# Tachometer DIAL: 270° sweep (frac 0→1 maps 225°→−45°, clockwise through the top), tick dots
# (red past `redfrac`), and a needle. Pixel space, y down.
function hdial!(v,cx,cy,R,frac,redfrac,dimc,litc,redc)
    a0=Float32(deg2rad(225.0)); a1=Float32(deg2rad(-45.0))
    arc(f)=a0+(a1-a0)*clamp(Float32(f),0f0,1f0)
    n=30
    for i in 0:n
        f=i/n; θ=arc(f); c = f>=redfrac ? redc : dimc
        hquad!(v, cx+R*cos(θ)-1.6f0, cy-R*sin(θ)-1.6f0, 3.2f0, 3.2f0, c)
    end
    θ=arc(frac); nx=cx+(R-2f0)*cos(θ); ny=cy-(R-2f0)*sin(θ)   # needle
    bx=sin(θ)*2.3f0; by=cos(θ)*2.3f0                           # perpendicular base half-width
    append!(v, Float32[cx+bx,cy+by, litc[1],litc[2],litc[3]])
    append!(v, Float32[cx-bx,cy-by, litc[1],litc[2],litc[3]])
    append!(v, Float32[nx,ny,        litc[1],litc[2],litc[3]])
    hquad!(v, cx-2.5f0, cy-2.5f0, 5f0, 5f0, litc)             # hub
end

"""Compose the instrument readout: big 7-seg speed (bottom-left), gear (bottom-
right), throttle/brake/rpm bars, the four per-wheel traction circles (over the
nose), and last/best lap times (top-left).  `tc`=(FL,FR,RL,RR) (long,lat,radius)
or nothing; `lastlap`/`bestlap` in seconds (0 = none).  Returns the HUD vertex list."""
function compose_hud(W,H,kmh,gear,rpm,revlim,thr,brk,clu=0.0,tc=nothing; lastlap=0.0, bestlap=0.0, manual=false)
    v=Float32[]
    white=(0.90,0.95,1.0); amber=(1.0,0.82,0.35); green=(0.42,0.82,0.42); red=(0.95,0.35,0.30); dim=(0.16,0.18,0.22); blue=(0.35,0.65,1.0)
    hnumber!(v, 40, H-104, 40, 76, 11, kmh, white)             # speed (big, bottom-left)
    hdigit!(v, W-92, H-150, 40, 76, 11, (round(Int,gear) <= 0 ? -1 : clamp(round(Int,gear),1,9)), amber)  # gear (N for neutral), raised so it isn't clipped
    hquad!(v, W-100, H-164, 12, 12, manual ? amber : green)    # shift-mode dot: green=auto amber=manual
    # HUD decluttered (PO, E13): pedal bar charts, the hand-drawn RPM dial, and the per-wheel traction
    # circles are REMOVED so the real GPL dash reads clean.  Keep speed, gear, and the lap times only.
    lastlap > 0 && htime!(v, 40, 28, lastlap, white)           # last lap (white, top-left)
    bestlap > 0 && htime!(v, 40, 74, bestlap, green)           # best lap (green, below)
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
u32le(b,o)=reinterpret(UInt32,view(b,o+1:o+4))[1]
c565(c)=(UInt8(((c>>11)&0x1f)*255÷31), UInt8(((c>>5)&0x3f)*255÷63), UInt8((c&0x1f)*255÷31))
"""Software-decode a DXT1/DXT3/DXT5 (BC1/2/3) DDS to a flat RGBA byte array —
gives correct colour AND alpha (so alpha-cutout crowd/fence/signage textures
work), where the compressed S3TC upload path was dropping DXT3/5 alpha."""
function decode_dds(b)
    (length(b)>=128 && String(copy(b[1:4]))=="DDS ") && return _decode(b)
    (0,0,UInt8[])
end
function _decode(b)
    H=Int(u32le(b,12)); W=Int(u32le(b,16)); fourcc=String(copy(b[85:88]))
    fourcc in ("DXT1","DXT3","DXT5") || return (0,0,UInt8[])
    out=zeros(UInt8, W*H*4); o=128; N=length(b)
    @inbounds for by in 0:4:H-1, bx in 0:4:W-1
        o+16 > N && break
        a = ntuple(_->0xff, 16)
        if fourcc=="DXT3"
            a = ntuple(k->UInt8(((b[o+1+((k-1)÷2)] >> (4*((k-1)%2))) & 0xf)*17), 16); o+=8
        elseif fourcc=="DXT5"
            a0=Int(b[o+1]); a1=Int(b[o+2]); abits=UInt64(0)
            for k in 0:5; abits |= UInt64(b[o+3+k])<<(8k); end
            at = a0>a1 ? ntuple(i-> i<=2 ? UInt8(i==1 ? a0 : a1) : round(UInt8,((8-i)*a0+(i-1)*a1)/7), 8) :
                         ntuple(i-> i<=2 ? UInt8(i==1 ? a0 : a1) : i<=6 ? round(UInt8,((6-i)*a0+(i-1)*a1)/5) : (i==7 ? 0x00 : 0xff), 8)
            a = ntuple(k->at[Int((abits>>(3*(k-1)))&0x7)+1], 16); o+=8
        end
        c0=UInt16(b[o+1])|(UInt16(b[o+2])<<8); c1=UInt16(b[o+3])|(UInt16(b[o+4])<<8)
        r0,g0,b0=c565(c0); r1,g1,b1=c565(c1)
        opaque = c0>c1 || fourcc!="DXT1"
        col(i)= i==0 ? (r0,g0,b0) : i==1 ? (r1,g1,b1) :
                opaque ? (i==2 ? (UInt8((2*Int(r0)+r1)÷3),UInt8((2*Int(g0)+g1)÷3),UInt8((2*Int(b0)+b1)÷3)) :
                                 (UInt8((Int(r0)+2*r1)÷3),UInt8((Int(g0)+2*g1)÷3),UInt8((Int(b0)+2*b1)÷3))) :
                        (i==2 ? (UInt8((Int(r0)+r1)÷2),UInt8((Int(g0)+g1)÷2),UInt8((Int(b0)+b1)÷2)) : (0x00,0x00,0x00))
        bits=UInt32(b[o+5])|(UInt32(b[o+6])<<8)|(UInt32(b[o+7])<<16)|(UInt32(b[o+8])<<24); o+=8
        for k in 0:15
            px=bx+(k%4); py=by+(k÷4); (px<W && py<H) || continue
            ci=Int((bits>>(2k))&0x3); r,g,bl=col(ci)
            al = (!opaque && ci==3) ? 0x00 : a[k+1]
            i=(py*W+px)*4; out[i+1]=r; out[i+2]=g; out[i+3]=bl; out[i+4]=al
        end
    end
    (W,H,out)
end
const DXT1GL = GLenum(0x83F1)   # GL_COMPRESSED_RGBA_S3TC_DXT1 (1-bit alpha, GPU-native)
function load_dds(b)
    (length(b)>=128 && String(copy(b[1:4]))=="DDS ") || return GLuint(0)
    fourcc=String(copy(b[85:88]))
    tex=Ref{GLuint}(); glGenTextures(1,tex); glBindTexture(GL_TEXTURE_2D,tex[])
    if fourcc=="DXT1"            # fast path: upload compressed blocks directly
        H=Int(u32le(b,12)); W=Int(u32le(b,16)); mip=max(1,Int(u32le(b,28)))
        off=128; w=W; h=H
        for lvl in 0:mip-1
            w=max(w,1); h=max(h,1); sz=max(1,(w+3)÷4)*max(1,(h+3)÷4)*8
            off+sz>length(b) && break
            glCompressedTexImage2D(GL_TEXTURE_2D,lvl,DXT1GL,w,h,0,sz,b[off+1:off+sz])
            off+=sz; w÷=2; h÷=2
        end
        CUTOUT_TEX[tex[]] = true   # DXT1 = 1-bit alpha → cutout (chain-link/foliage); no-op if opaque
    else                        # DXT3/5: software-decode to RGBA for reliable 8-bit alpha
        W,H,rgba = decode_dds(b)
        (W==0 || isempty(rgba)) && (glDeleteTextures(1,tex); return GLuint(0))
        glTexImage2D(GL_TEXTURE_2D,0,GL_RGBA8,W,H,0,GL_RGBA,GL_UNSIGNED_BYTE,rgba)
        glGenerateMipmap(GL_TEXTURE_2D)
        CUTOUT_TEX[tex[]] = classify_cutout(rgba)   # 8-bit alpha → groove/blended stays soft
    end
    glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_S,GL_REPEAT); glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_T,GL_REPEAT)
    glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_LINEAR_MIPMAP_LINEAR); glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_LINEAR)
    aniso=Ref{Float32}(0f0); glGetFloatv(GLenum(0x84FF), aniso)
    aniso[]>1 && glTexParameterf(GL_TEXTURE_2D, GLenum(0x84FE), min(aniso[],16f0))
    tex[]
end

# ---- Grand Prix Legends assets (Lotus 49) ---------------------------------
"""Upload decoded RGBA pixels as a GL texture (GL builds the mips)."""
# Per-texture CUTOUT classification: a chain-link / foliage texture has BIMODAL alpha —
# a real fraction of fully-transparent texels (the holes) and the rest opaque, with few
# mid-alpha texels.  A blended overlay (the racing groove) instead has lots of mid-alpha
# (a smooth gradient).  Only cutouts get the FS alpha-edge sharpening, so the groove (and
# opaque surfaces) keep their soft alpha-to-coverage — this is what makes the shimmer fix
# safe (the global sharpening broke the groove).  texid → is-cutout.
const CUTOUT_TEX = Dict{GLuint,Bool}()
function classify_cutout(rgba)
    N = length(rgba) ÷ 4; N == 0 && return false
    nt = 0; nmid = 0
    @inbounds for i in 4:4:length(rgba)
        a = rgba[i]
        a < 26 ? (nt += 1) : (a <= 230 && (nmid += 1))   # <0.1 transparent ; 0.1..0.9 mid
    end
    nt/N > 0.05 && nmid/N < 0.22         # holes present AND sharp edges (not a gradient)
end
function upload_rgba(w, h, rgba)
    tex=Ref{GLuint}(); glGenTextures(1,tex); glBindTexture(GL_TEXTURE_2D,tex[])
    CUTOUT_TEX[tex[]] = classify_cutout(rgba)
    glTexImage2D(GL_TEXTURE_2D,0,GL_RGBA8,w,h,0,GL_RGBA,GL_UNSIGNED_BYTE,rgba)
    glGenerateMipmap(GL_TEXTURE_2D)
    glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_S,GL_REPEAT); glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_T,GL_REPEAT)
    glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_LINEAR_MIPMAP_LINEAR); glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_LINEAR)
    glTexParameterf(GL_TEXTURE_2D, GLenum(0x8501), 0f0)   # GL_TEXTURE_LOD_BIAS: neutral (any sharpen shimmers GPL sign text at distance)
    aniso=Ref{Float32}(0f0); glGetFloatv(GLenum(0x84FF),aniso)
    aniso[]>1 && glTexParameterf(GL_TEXTURE_2D,GLenum(0x84FE),min(aniso[],16f0))
    tex[]
end
function load_mip(path)
    w,h,rgba = GPLMip.decode_mip(path); upload_rgba(w,h,rgba)
end

# GPL texture provider: resolves a texture NAME to decoded RGBA, from loose .mip /
# .srb files in a folder AND from any track .dat archive there (both .mip and the
# sprite .srb, which embeds a MIP).  This is how trackside-object textures — many
# packed in the .dat or stored as .srb — get found.
struct GPLTex
    paths::Dict{String,String}            # name(.ext stripped) → loose file path
    dat::Dict{String,Vector{UInt8}}       # lowercase "name.ext" → bytes (from .dat)
end

"""Index a GPL folder's textures: loose .mip/.srb + every .dat archive's .mip/.srb."""
function gpl_texture_index(dir)
    paths=Dict{String,String}(); dat=Dict{String,Vector{UInt8}}()
    for f in readdir(dir; join=true)
        lf=lowercase(f)
        (endswith(lf,".mip")||endswith(lf,".srb")) && (paths[lowercase(basename(f))[1:end-4]] = f)
        if endswith(lf,".dat")
            try; merge!(dat, GPLDat.parse_dat(f)); catch; end
        end
    end
    GPLTex(paths, dat)
end

"""Resolve a texture name → (w,h,rgba) from the provider, or `nothing`."""
function tex_rgba(idx::GPLTex, name::AbstractString)
    key=lowercase(name)
    p = get(idx.paths, key, "")
    if p != ""
        try
            return endswith(lowercase(p),".srb") ? GPLMip.decode_srb_bytes(read(p)) : GPLMip.decode_mip(p)
        catch; end
    end
    for (ext, dec) in ((".mip", GPLMip.decode_mip_bytes), (".srb", GPLMip.decode_srb_bytes))
        v = get(idx.dat, key*ext, nothing)
        if v !== nothing
            try; return dec(v); catch; end
        end
    end
    # SRB/detail-name fallback: a name that prefixes a real texture (e.g. trump→trumphi)
    if length(key) >= 5
        for (k,pp) in idx.paths
            if startswith(k, key)
                try; return endswith(lowercase(pp),".srb") ? GPLMip.decode_srb_bytes(read(pp)) : GPLMip.decode_mip(pp); catch; end
            end
        end
    end
    nothing
end

"""Extract a GPL .3do car into textured TrackParts (one per texture), in the
car rig frame (X fwd, Y up, Z left).  GPL is X=fwd, Y=lateral, Z=up; V is flipped
(GPL 0=top, GL 0=bottom).  The reflection-tray / blob-shadow planes are dropped."""
# `exclude`: GPL environment-only textures — ltraymap (under-car reflection tray)
# and lshad (blob shadow); we do our own shadows.  Untextured + lotblack interior
# panels are KEPT now that positioners place them correctly (they were only "strays"
# when collapsed to the origin) — needed for a solid cockpit.
function extract_gpl_car(path3do; exclude=("ltraymap","lshad"), only=(), grey=(0.72f0,0.74f0,0.76f0), smooth=true, tint=nothing, track=false, mirror=false, exclude_groups=(), cockpit_clean=false, maxedge=Inf32, uflip=nothing, vflip=nothing, maxlat=Inf32, dedup=nothing, drop_green=false)
    # text reads right when the texture mapping preserves handedness: the mirror=true
    # remap (gx,gz,-gy) is a rotation (no flip needed); mirror=false is a reflection
    # (needs V flipped to compensate).  So uflip=false, vflip=!mirror.
    uflip === nothing && (uflip = false)
    vflip === nothing && (vflip = !mirror)
    maxlat = Float32(maxlat)
    m = GPL3DO.parse_3do(path3do)
    groups = Dict{String,Vector{Float32}}()
    edge(a,b) = sqrt((a[1]-b[1])^2+(a[2]-b[2])^2+(a[3]-b[3])^2)
    function triarea(p)
        ux=p[2][1]-p[1][1]; uy=p[2][2]-p[1][2]; uz=p[2][3]-p[1][3]
        vx=p[3][1]-p[1][1]; vy=p[3][2]-p[1][2]; vz=p[3][3]-p[1][3]
        0.5f0*sqrt((uy*vz-uz*vy)^2 + (uz*vx-ux*vz)^2 + (ux*vy-uy*vx)^2)
    end
    # the jaggie tan/yellow cockpit-floor panels are untextured + yellowish — drop
    # them for a clean interior (the cockpit just fades to dark downward instead).
    yellowish(c) = c[1]>0.55f0 && c[2]>0.40f0 && c[3]<0.40f0 && c[1] > c[3]+0.22f0
    # GPL cars carry an under-car reflection TRAY ("<prefix>traymap") + blob SHADOW
    # ("<prefix>shad") — environment planes (the tray resolves to no texture → flat
    # bright-green, the shadow a dark splat) that we never want (we cast our own
    # shadows).  Drop them generically by name suffix so every chassis is covered
    # (Lotus ltraymap/lshad, Ferrari ftraymap, Brabham rtraymap, … all match).
    istray(tex) = endswith(tex,"traymap") || endswith(tex,"shad")
    # some chassis also carry an UNTEXTURED saturated-green placeholder plane (the
    # tray's twin).  Real bodywork green is always textured (livery .mip), so an
    # untextured pure-green poly is the placeholder → drop it.  Gated by `drop_green`
    # (AI cars only) so the player Lotus's green-col cockpit tub is never touched.
    traygreen(c) = drop_green && c[2]>0.45f0 && c[1]<0.30f0 && c[3]<0.30f0
    overlat(t) = maxlat < Inf32 && max(abs(t.p[1][2]),abs(t.p[2][2]),abs(t.p[3][2])) > maxlat  # GPL gy = lateral
    cmax(t) = max(abs(t.p[1][1]),abs(t.p[1][2]),abs(t.p[1][3]), abs(t.p[2][1]),abs(t.p[2][2]),abs(t.p[2][3]),
                  abs(t.p[3][1]),abs(t.p[3][2]),abs(t.p[3][3]))
    keep(t) = let L = max(edge(t.p[1],t.p[2]), edge(t.p[2],t.p[3]), edge(t.p[1],t.p[3])),
                  A = triarea(t.p)
        !isempty(only) && !(t.tex in only) ? false :                   # `only` set ⇒ keep just those textures (e.g. the gauge cluster)
        !(isfinite(L) && isfinite(A) && cmax(t) < 5f4) ? false :       # drop garbage/huge stray verts (e.g. monza10k ~1e6-unit coords)
        (cockpit_clean && t.tex=="" && yellowish(t.col)) || overlat(t) ? false :
        track ? (!(t.tex in exclude) && A >= 1f-7 && L <= maxedge) :   # track: huge legit polys (objects pass maxedge to drop stray giant polys)
                (!(t.tex in exclude) && !istray(t.tex) && !(t.tex=="" && traygreen(t.col)) && L <= 2.0f0 && A >= 1f-7 && !(A > 0 && L/(2A/L) > 200f0))
    end
    kept = [m.tris[i] for i in eachindex(m.tris) if keep(m.tris[i]) && !(m.groups[i] in exclude_groups)]
    qk(p) = (round(Int,p[1]*2000), round(Int,p[2]*2000), round(Int,p[3]*2000))
    # de-duplicate coplanar panels: GPL signs/awnings/walls are double-sided (front+back),
    # often with a few-mm THICKNESS — so they're NOT exact-vertex duplicates and still
    # z-FIGHT (flickers only when moving — depth precision at distance can't separate them).
    # Key each tri by CENTROID (1.5cm grid) + AREA: a panel's front & back share a centroid
    # (offset only by the mm thickness) and identical area, so they collapse regardless of
    # thickness or how the quad was triangulated.  Sort textured tris first → a textured
    # decal wins over a blank backing (keeps the sign legible).  The shader renders the
    # surviving face two-sided (uBackFlip un-mirrors the back).  On for track + objects.
    if dedup === nothing; dedup = track; end
    if dedup
        ckey(t) = (round(Int,(t.p[1][1]+t.p[2][1]+t.p[3][1])/3*64),
                   round(Int,(t.p[1][2]+t.p[2][2]+t.p[3][2])/3*64),
                   round(Int,(t.p[1][3]+t.p[2][3]+t.p[3][3])/3*64),
                   round(Int, triarea(t.p)*1f5))
        sort!(kept, by = t -> (t.tex == "" ? 1 : 0))   # stable: textured tris seen first
        seen = Set{NTuple{4,Int}}()
        kept = filter(kept) do t
            k = ckey(t)
            (k in seen) ? false : (push!(seen, k); true)
        end
    end
    # smooth normals: average the per-triangle normals across shared vertex
    # positions so GPL's flat (T-81F) polys don't facet the curved bodywork
    nsum = Dict{NTuple{3,Int32},NTuple{3,Float32}}()
    if smooth
        for t in kept, i in 1:3
            k=qk(t.p[i]); n=t.n[i]; s=get(nsum,k,(0f0,0f0,0f0))
            nsum[k]=(s[1]+n[1], s[2]+n[2], s[3]+n[3])
        end
    end
    sm(p,fallback) = begin
        s = get(nsum, qk(p), (0f0,0f0,0f0)); l = sqrt(s[1]^2+s[2]^2+s[3]^2)
        l < 1f-6 ? fallback : (s[1]/l, s[2]/l, s[3]/l)
    end
    for t in kept
        v = get!(groups, t.tex, Float32[])
        mz = mirror ? -1f0 : 1f0   # negate render-Z → right-handed track frame (gx,gz,-gy)
        for i in 1:3
            p=t.p[i]; n = smooth ? sm(p, t.n[i]) : t.n[i]; uv=t.uv[i]
            # E36: untextured COCKPIT tris (the tub/floor) take the `grey` shade when JM_TUB_GREY makes it
            # silver — the `grey` param was a no-op before (baked vertex colour used t.col).  Gated on
            # cockpit_clean + a >0.2 grey so the DEFAULT dark tub is unchanged (no regression); only an
            # explicit silver JM_TUB_GREY recolours the tub.
            c = (cockpit_clean && t.tex=="" && grey[1] > 0.2f0) ? grey : (tint === nothing ? t.col : tint)   # GPL flat-shade colour (or override)
            append!(v, (p[1],p[3],p[2]*mz, n[1],n[3],n[2]*mz, c[1],c[2],c[3], uflip ? 1f0-uv[1] : uv[1], vflip ? 1f0-uv[2] : uv[2]))
        end
    end
    [TrackPart(v, tex, grey) for (tex,v) in groups]
end

# GPL Lotus steering-wheel face billboard textures (the painted red rim + spokes
# + badge).  Extracted separately so the app can spin it about its column axis.
const STEER_TEX = ("sterlot","lotster","lsterlog")
"""Extract the steering wheel as its own parts + pivot (centre, column axis) in the
rig frame (X fwd, Y up, Z left), so the app can rotate it with steering input."""
function extract_gpl_steering(path3do)
    m = GPL3DO.parse_3do(path3do)
    groups = Dict{String,Vector{Float32}}()
    cx=cy=cz=0.0; nx=ny=nz=0.0; n=0
    for t in m.tris
        (t.tex == "sterlot" || t.tex == "lsterlog") || continue   # red face + badge only (lotster is the blue dup)
        v = get!(groups, t.tex, Float32[])
        for i in 1:3
            p=t.p[i]; nn=t.n[i]; uv=t.uv[i]
            append!(v, (p[1],p[3],p[2], nn[1],nn[3],nn[2], 0.7f0,0.72f0,0.74f0, uv[1], 1f0-uv[2]))
            cx+=p[1]; cy+=p[3]; cz+=p[2]; nx+=nn[1]; ny+=nn[3]; nz+=nn[2]; n+=1
        end
    end
    n==0 && return (TrackPart[], Float32[0,0,0], Float32[1,0,0])
    center = Float32[cx/n, cy/n, cz/n]
    al = normalize([nx,ny,nz]); axis = Float32[al[1],al[2],al[3]]
    # E50: the LOTUS badge (lsterlog) sits COPLANAR with the red hub face (sterlot) — they
    # z-fought, so the wheel centre shimmered.  Push the badge ~3 mm toward the driver
    # (along the column axis = the front-facing normal) so it always wins the depth test.
    if haskey(groups, "lsterlog")
        v = groups["lsterlog"]; ε = 0.003f0
        for i in 0:11:length(v)-11
            v[i+1] += ε*axis[1]; v[i+2] += ε*axis[2]; v[i+3] += ε*axis[3]
        end
    end
    ([TrackPart(v, tex, (0.7f0,0.72f0,0.74f0)) for (tex,v) in groups], center, axis)
end

"""Build textured Items for GPL parts, resolving each texture via the .mip index."""
function build_gpl(parts, idx::GPLTex)
    cache=Dict{String,GLuint}(); items=Item[]
    for p in parts
        vao,n = upload(p.verts); tid=GLuint(0)
        if p.tex != ""
            key=lowercase(p.tex)
            tid = get!(cache,key) do
                r = tex_rgba(idx, key)
                r === nothing ? GLuint(0) : upload_rgba(r[1], r[2], r[3])
            end
        end
        push!(items, Item(vao,n,tid,p.col))
    end
    items
end

# ---- GPL SRB billboards (trees, crowds, signs, flags) ----------------------
# Many trackside "objects" are camera-facing SPRITES: a stub .3do (a T-003 node +
# one vertex whose Z is the sprite height) that names an .srb/.mip texture.  We
# render each as a quad that yaws to face the camera.
"""Read a GPL billboard stub .3do → (height, width, texture-name candidates).
The SZYX vertices give the sprite size: z-extent = height, horizontal extent = width.
Some stubs carry a real quad (e.g. single1 = 2×3m), some just a height marker
(tree1 z=7), some nothing (flagger = one (0,0,0) vertex → human-scale default).
width=0 means "derive from the texture aspect"."""
function billboard_stub(path)
    b = read(path)
    u32(o)=(o<0||o+4>length(b)) ? UInt32(0) : UInt32(b[o+1])|(UInt32(b[o+2])<<8)|(UInt32(b[o+3])<<16)|(UInt32(b[o+4])<<24)
    f32(o)=reinterpret(Float32,u32(o)); tg(o)=String(b[o+1:o+4])
    xyz=strn=0; nv=0; strnsz=0; o=12
    while o+12<=length(b)
        t=tg(o); sz=Int(u32(o+8)); d=o+12
        t=="SZYX" && (xyz=d; nv=sz÷16); t=="NRTS" && (strn=d; strnsz=sz)
        o=d+sz; o+=(4-o%4)%4
    end
    zmn=Inf32; zmx=-Inf32; xmn=Inf32; xmx=-Inf32; ymn=Inf32; ymx=-Inf32
    for k in 0:nv-1
        x=f32(xyz+k*16+4); y=f32(xyz+k*16+8); z=f32(xyz+k*16+12)
        zmn=min(zmn,z); zmx=max(zmx,z); xmn=min(xmn,x); xmx=max(xmx,x); ymn=min(ymn,y); ymx=max(ymx,y)
    end
    zext = nv>0 ? zmx-zmn : 0f0
    hext = nv>1 ? max(xmx-xmn, ymx-ymn) : 0f0
    height = zext > 0.5f0 ? zext : 2.5f0          # no height marker → human/marshal default
    width  = hext > 0.5f0 ? hext : 0f0             # 0 → derive from texture aspect
    strs=String[]; cur=UInt8[]
    for i in strn:strn+strnsz-1
        c=b[i+1]; c==0xFF && break
        c==0x00 ? (push!(strs,String(copy(cur))); empty!(cur)) : push!(cur,c)
    end
    !isempty(cur) && push!(strs,String(copy(cur)))
    (height, width, strs)
end

"""Build a camera-facing billboard Item for a texture name → (Item, texW, texH) or
nothing.  Unit quad: x∈[-0.5,0.5], y∈[0,1] (stands on the ground), z=0.  Normal points
UP so the sprite is lit bright (not darkened by a facing-the-camera Lambert term)."""
function build_billboard(texname, idx::GPLTex)
    r = tex_rgba(idx, texname); r === nothing && return nothing
    tid = upload_rgba(r[1], r[2], r[3])
    q=Float32[]
    vtx(x,y,u,v) = append!(q, (x,y,0f0, 0f0,1f0,0f0, 1f0,1f0,1f0, u,v))   # normal up
    vtx(-0.5f0,0f0,0f0,1f0); vtx(0.5f0,0f0,1f0,1f0); vtx(0.5f0,1f0,1f0,0f0)
    vtx(-0.5f0,0f0,0f0,1f0); vtx(0.5f0,1f0,1f0,0f0); vtx(-0.5f0,1f0,0f0,0f0)
    vao,n = upload(q)
    (Item(vao,n,tid,(1f0,1f0,1f0)), Float32(r[1]), Float32(r[2]))
end

# ---- GPL horizon ring (sky dome backdrop) ----------------------------------
# GPL's backdrop is not a .3do but 12 square MIP panels (horiz0..horiz11), each a
# 30° slice of a cylinder wrapped around the track: hazy sky in the upper ~80%,
# distant dune/scrub silhouette along the bottom.  We build it as a camera-centred
# ring drawn unlit + unfogged (uSky=1) just after the gradient sky, so the scene
# (which fogs into the same haze) dissolves into it.
"""Build the 12-panel GPL horizon ring as backdrop Items (one textured quad each).
`R` ring radius (kept < far plane); `e_lo`/`e_hi` bottom/top elevation; the
silhouette band (bottom ~20% of each panel) straddles e_lo→0 so it sits on the
horizon line.  `yaw0` rotates the whole ring to register it with the track."""
function build_horizon(idx::GPLTex; R=2500f0, e_lo=deg2rad(-6f0), e_hi=deg2rad(24f0), yaw0=0f0, n=12)
    items = Item[]
    # Two GPL horizon conventions: a 12-panel RING (horiz0..11, each a 30° slice — Zandvoort)
    # or a SINGLE panoramic STRIP (only horiz0, e.g. Watkins Glen) meant to wrap the full 360°.
    # Detect the single-strip case (horiz0 present, horiz1 absent) and wrap that one texture
    # around a thin horizon band, else the lone 30° slice gets stretched ~1.4 km tall (a white
    # vertical "smear").  The strip is hazy-sky-over-hills, so a low, thin band sits at the horizon.
    if tex_rgba(idx, "horiz0") !== nothing && tex_rgba(idx, "horiz1") === nothing
        r = tex_rgba(idx, "horiz0"); tid = upload_rgba(r[1], r[2], r[3])
        # crop the strip's top hazy-white sky rows (they'd read as a bright "smear" band against
        # our own blue sky); keep only the lower ridge + tree content (vtop→bottom) as a low, thin
        # horizon band so the autumn tree-line sits under the blue sky (Watkins gold standard).
        ns = 48; dθ = 2f0π/ns
        slo = deg2rad(parse(Float32, get(ENV,"JM_STRIP_LO","-5")))
        shi = deg2rad(parse(Float32, get(ENV,"JM_STRIP_HI","2.2")))
        vtop = parse(Float32, get(ENV,"JM_STRIP_VTOP","0.52"))
        h_lo = R*tan(Float32(slo)); h_hi = R*tan(Float32(shi))
        q=Float32[]
        sv(x,y,z,u,v)=append!(q,(x,y,z, 0f0,0f0,0f0, 1f0,1f0,1f0, u,v))
        for i in 0:ns-1
            θ0=Float32(yaw0+i*dθ); θ1=Float32(yaw0+(i+1)*dθ)
            x0=R*cos(θ0); z0=R*sin(θ0); x1=R*cos(θ1); z1=R*sin(θ1)
            u0=Float32(i/ns); u1=Float32((i+1)/ns)              # wrap the panorama exactly once around 360°
            sv(x0,h_lo,z0, u0,1f0); sv(x1,h_lo,z1, u1,1f0); sv(x1,h_hi,z1, u1,vtop)
            sv(x0,h_lo,z0, u0,1f0); sv(x1,h_hi,z1, u1,vtop); sv(x0,h_hi,z0, u0,vtop)
        end
        vao,m = upload(q)
        push!(items, Item(vao,m,tid,(1f0,1f0,1f0)))
        return items
    end
    # 12-panel RING: CROP to a thin LOW hill-band.  Drawing the full 30°-tall GPL panels put their
    # grey overcast SKY rows up to +24°, walling against our blue procedural skydome (a hard seam, E19).
    # Keep only the lower (ridge/dune/horizon) rows of each panel (v: vtop→1) as a low band (e_lo→bandhi),
    # so the distant scenery sits on the horizon and the blue sky shows above it — no seam.
    bandhi = deg2rad(parse(Float32, get(ENV,"JM_RING_HI","6"))); vtop = parse(Float32, get(ENV,"JM_RING_VTOP","0.40"))
    h_lo = R*tan(Float32(e_lo)); h_hi = R*tan(Float32(bandhi)); dθ = 2f0π/n
    for i in 0:n-1
        r = tex_rgba(idx, "horiz$(i)"); r === nothing && continue
        tid = upload_rgba(r[1], r[2], r[3])
        θ0 = Float32(yaw0 + i*dθ); θ1 = Float32(yaw0 + (i+1)*dθ)
        x0=R*cos(θ0); z0=R*sin(θ0); x1=R*cos(θ1); z1=R*sin(θ1)
        q=Float32[]
        vtx(x,y,z,u,v)=append!(q,(x,y,z, 0f0,0f0,0f0, 1f0,1f0,1f0, u,v))  # normal unused (unlit)
        vtx(x0,h_lo,z0, 0f0,1f0); vtx(x1,h_lo,z1, 1f0,1f0); vtx(x1,h_hi,z1, 1f0,vtop)
        vtx(x0,h_lo,z0, 0f0,1f0); vtx(x1,h_hi,z1, 1f0,vtop); vtx(x0,h_hi,z0, 0f0,vtop)
        vao,m = upload(q)
        push!(items, Item(vao,m,tid,(1f0,1f0,1f0)))
    end
    items
end

"""Draw the horizon ring centred on the camera, unlit + unfogged, behind the scene
(depth-write off so closer geometry overwrites it)."""
function draw_horizon(prog, ring, vp, campos; tint=(1f0,1f0,1f0))
    isempty(ring) && return
    glUniform1i(glGetUniformLocation(prog,"uSky"), 1)
    u3(prog,"uSkyTint",tint)
    glDepthMask(GL_FALSE)
    M = translate(Float32[campos[1],campos[2],campos[3]])
    for it in ring; draw(prog, it, vp, M; bright=1.0); end
    glDepthMask(GL_TRUE)
    glUniform1i(glGetUniformLocation(prog,"uSky"), 0)
end

"""Model matrix for a billboard at render `pos` (base), sized `w`×`h`, yawed to face
the camera at `eye`."""
function billboard_model(pos, w, h, eye)
    yaw = atan(eye[1]-pos[1], eye[3]-pos[3])
    translate(Float32[pos[1],pos[2],pos[3]]) * roty(Float32(yaw)) * scalexyz(Float32(w),Float32(h),1f0)
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

# ---- generic GPL car loader (player Lotus + the AI grid: Ferrari/Brabham/…) --
"""Axis-aligned bbox over the rig-frame positions of TrackParts (verts stride 11,
pos at offsets 1:3).  Returns a NamedTuple (xmin,xmax,ymin,ymax,zmin,zmax)."""
function parts_bbox(parts)
    xmn=ymn=zmn=Inf32; xmx=ymx=zmx=-Inf32
    for p in parts
        v = p.verts
        @inbounds for i in 1:11:length(v)-10
            x=v[i]; y=v[i+1]; z=v[i+2]
            xmn=min(xmn,x); xmx=max(xmx,x); ymn=min(ymn,y); ymx=max(ymx,y); zmn=min(zmn,z); zmx=max(zmx,z)
        end
    end
    (xmin=xmn, xmax=xmx, ymin=ymn, ymax=ymx, zmin=zmn, zmax=zmx)
end

"A loaded GPL car: body Items, a name→Items wheel cache, an auto-derived body
offset (rig frame), and the wheel placement spec (hubX, hubZ, steers?, radius, mesh)."
struct GPLCarModel
    name::String
    body::Vector{Item}
    wheels::Dict{String,Vector{Item}}
    body_off::NTuple{3,Float32}
    wheelspec::Vector{Tuple{Float32,Float32,Bool,Float32,String}}
end

"""Load a GPL '67 car (body + wheels) from its `cars67/<dir>` folder, AUTO-LEVELLED
to sit centred on its wheels.  `body_floor` = the world-Y the body underside should
reach (pass the player Lotus's `bbox.ymin + BODY_OFF[2]` so the whole grid sits at a
common height).  `wheelspec` reuses the Lotus hub geometry (all '67 cars are
dimensionally near-identical) with each car's own wheel mesh names; a missing mesh
loads as nothing (drawn wheel-less rather than crashing)."""
function load_gpl_car(name, dir, body3do, wheelspec;
                      exclude=("ltraymap","lshad"), maxlat=Inf32, exclude_groups=(),
                      body_floor=0.0f0, wheeltint=(0.12f0,0.12f0,0.13f0))
    tex   = gpl_texture_index(dir)
    parts = extract_gpl_car(joinpath(dir, body3do); exclude=exclude, maxlat=maxlat, exclude_groups=exclude_groups, drop_green=true)
    body  = build_gpl(parts, tex)
    bb    = parts_bbox(parts)
    off_x = -(bb.xmin + bb.xmax) / 2f0
    off_z = -(bb.zmin + bb.zmax) / 2f0
    off_y = body_floor - bb.ymin
    wheels = Dict{String,Vector{Item}}()
    for (_,_,_,_,mesh) in wheelspec
        haskey(wheels, mesh) && continue
        path = joinpath(dir, mesh*".3do")
        wheels[mesh] = isfile(path) ?
            build_gpl(extract_gpl_car(path; exclude=("ltraymap","lshad"), tint=wheeltint), tex) : Item[]
    end
    GPLCarModel(name, body, wheels, (Float32(off_x), Float32(off_y), Float32(off_z)),
                Vector{Tuple{Float32,Float32,Bool,Float32,String}}(wheelspec))
end

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
function draw(prog, item::Item, vp, model; bright::Real=1.0, spec::Real=0.0, ambfill::Real=0.0, graze::Bool=false, alpha::Real=1.0, tint=(1f0,1f0,1f0))
    setmat(prog,"uVP",vp); setmat(prog,"uModel",model)
    glUniform3f(glGetUniformLocation(prog,"uTint"), Float32(tint[1]), Float32(tint[2]), Float32(tint[3]))   # per-draw colour multiply (default white = no-op)
    glUniform1f(glGetUniformLocation(prog,"uBright"), Float32(bright))
    glUniform1f(glGetUniformLocation(prog,"uSpec"), Float32(spec))
    glUniform1f(glGetUniformLocation(prog,"uAlpha"), Float32(alpha))
    glUniform1f(glGetUniformLocation(prog,"uAmbFill"), Float32(ambfill))
    glUniform1i(glGetUniformLocation(prog,"uGraze"), graze ? 1 : 0)
    glUniform1i(glGetUniformLocation(prog,"uCutout"), get(CUTOUT_TEX, item.tex, false) ? 1 : 0)
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
