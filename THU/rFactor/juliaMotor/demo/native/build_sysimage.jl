# Build the `jlracer.so` sysimage — bakes the JIT compilation of the physics
# (ModelingToolkit + OrdinaryDiffEq mtkcompile + the Rosenbrock solve loop), the
# render stack (GLFW/ModernGL) and the GPL loaders, so a fresh launch skips the
# ~40-80 s of first-time compilation that dominates the startup delay.  Only the
# per-track GPL data parse (irreducible) then remains.
#
#   julia build_sysimage.jl            # ~20-40 min, writes demo/native/jlracer.so
#   ./run.sh / gui.py auto-use it via   julia -J jlracer.so …   when present.
using Pkg
Pkg.activate(mktempdir())
Pkg.add("PackageCompiler")
using PackageCompiler

const NATIVE = @__DIR__
create_sysimage(
    [:ModelingToolkit, :OrdinaryDiffEq, :GLFW, :ModernGL,
     :JuliaMotor, :RFactorData, :RFactorTelemetry];
    project = NATIVE,
    sysimage_path = joinpath(NATIVE, "jlracer.so"),
    precompile_execution_file = joinpath(NATIVE, "sysimage_trace.jl"),
    cpu_target = "native",
    include_transitive_dependencies = true,
)
println("\nDONE → ", joinpath(NATIVE, "jlracer.so"))
