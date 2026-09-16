include(joinpath(@__DIR__, "..", "src", "ibt.jl")); using .IBT
f = ibt_open(ARGS[1]); ch = channels(f)
println(join(filter(c -> occursin(r"(?i)speed|rpm|wheel|shaft", c), ch), ", "))
