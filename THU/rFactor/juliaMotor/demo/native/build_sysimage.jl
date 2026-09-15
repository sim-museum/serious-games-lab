# Build the `jlracer.so` sysimage — bakes the JIT compilation of the physics
# (ModelingToolkit + OrdinaryDiffEq mtkcompile + the Rosenbrock solve loop), the
# render stack (GLFW/ModernGL) and the GPL loaders, so a fresh launch skips the
# ~40-80 s of first-time compilation that dominates the startup delay.  Only the
# per-track GPL data parse (irreducible) then remains.
#
#   julia build_sysimage.jl            # ~20-40 min, writes demo/native/jlracer.so
#   ./run.sh / juliaRacer.py auto-use it via   julia -J jlracer.so …   when present.
using Pkg
Pkg.activate(mktempdir())
Pkg.add("PackageCompiler")
using PackageCompiler

const NATIVE = @__DIR__
# E80-S4 (2026-09-15): the package list is a SETTING. Three builds of the full list were OOM-killed
# on this 15 GB box (peak child RSS 12.4 GB, measured), so the experiment "does a sysimage remove the
# 146 s of compile latency?" needs a variant that fits. JM_SYSIMG_PKGS="A,B,C" overrides; the default
# is unchanged. The physics stack (ModelingToolkit + OrdinaryDiffEq) is where the measured 96 s of
# `mtkcompile` lives, so it is the half worth baking first if only one will fit.
const PKGS = let e = get(ENV, "JM_SYSIMG_PKGS", "")
    isempty(e) ? [:ModelingToolkit, :OrdinaryDiffEq, :GLFW, :ModernGL,
                  :JuliaMotor, :RFactorData, :RFactorTelemetry] :
                 [Symbol(strip(x)) for x in split(e, ",") if !isempty(strip(x))]
end
println("sysimage packages: ", PKGS)
create_sysimage(
    PKGS;
    project = NATIVE,
    sysimage_path = joinpath(NATIVE, "jlracer.so"),
    precompile_execution_file = joinpath(NATIVE, "sysimage_trace.jl"),
    # PERF-1: cpu_target must NOT be "native" for a sysimage that ships inside an AppImage.
    # "native" bakes THIS machine's instruction set (an i7-3770, Ivy Bridge) into jlracer.so; the
    # PO runs these images on a second PC whose CPU is unknown here. If that machine is older or
    # merely different, the sysimage can fault or refuse to load -- and the failure would appear as
    # "julia racer is broken on the other PC", nowhere near this line.
    # The multi-versioned default below emits several variants and picks at load time: slightly
    # larger, portable. JM_CPU_TARGET=native for a local-only build where the speed matters.
    cpu_target = get(ENV, "JM_CPU_TARGET",
                     "generic;sandybridge,-xsaveopt,clone_all;haswell,-rdrnd,base(1)"),
    # E80-S4: transitive deps triple the peak. JM_SYSIMG_TRANSITIVE=0 turns them off for a build
    # that must fit in memory; the baked methods are then only those the trace reached.
    include_transitive_dependencies = get(ENV, "JM_SYSIMG_TRANSITIVE", "1") != "0",
    # STARTUP-1 / 2026-09-06: the build julia reached 12.9 GB RSS and the kernel OOM killer took
    # the terminal (and the Claude session) with it. A heap hint makes the GC collect early; run
    # the build alone, inside `systemd-run --user --scope -p MemoryMax=12G` (see RUNNING.md).
    sysimage_build_args = `--heap-size-hint=$(get(ENV, "JM_SYSIMG_HEAP", "7G"))`,
)
println("\nDONE → ", joinpath(NATIVE, "jlracer.so"))
