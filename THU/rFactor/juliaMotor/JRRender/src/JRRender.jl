# E80-S10 (2026-10-15): the sim's render and track-geometry modules as a PACKAGE, so Julia's package image caches their
# compiled code across launches -- as JRPhysics does for the car (PHYSPRE-1). Measured on a throwaway prototype (E80-S9):
# Spa's launch 211 → 197 s; the loose `include`s made a NEW module every launch, so nothing compiled for them could be
# reused. The files stay where they are (demo/native) and are included from there; gates that include them directly
# are unaffected.
# The modules' module-level ENV constants (JM_SHADOW_*, JM_FLATPOLY, JM_PLANAR_*, JM_VISOR, JM_CAR_UNMIRROR, JM_ANISO,
# JM_EXPOSURE, JM_WBAL, JM_LOD_ALL, JM_GPLVIS_CHILD36, JM_ROADCURVE_OBLIQUE) are fixed at precompile time to their
# defaults: A/B probes that neither the launcher nor any gate sets. JM_RENDER_INCLUDE=1 in the sim loads the loose files
# instead, with those knobs live.
module JRRender
const NAT = normpath(joinpath(@__DIR__, "..", "..", "demo", "native"))
include(joinpath(NAT, "render.jl"));    using .Render       # (+ GPL3DO, GPLMip, GPLDat)
include(joinpath(NAT, "gpltrack.jl"));  using .GPLTrack
include(joinpath(NAT, "gplwall.jl"));   using .GPLWall
include(joinpath(NAT, "roadcurve.jl")); using .RoadCurve    # (its `..Render` is the sibling above)
export Render, GPLTrack, GPLWall, RoadCurve

using PrecompileTools
@compile_workload begin
    # The signatures the sim's launches compiled for these modules (all five tracks, 5 AI; tools/jrrender_gen.py).
    # A signature whose types no longer exist after an edit is skipped -- the cache is smaller, never wrong.
    for st in eachline(joinpath(@__DIR__, "workload.jl"))
        startswith(st, "precompile(") || continue
        try; Core.eval(@__MODULE__, Meta.parse(st)); catch; end
    end
end
end # module
