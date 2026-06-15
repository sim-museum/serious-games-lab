# CornerAssembly — one wheel station as an acausal MTK model: the `Corner`
# (quarter-car ride dynamics) feeds its computed vertical load into the `Tyre`,
# i.e. the structural coupling  tyre.Fz ~ corner.Fz.  This closes the vertical
# load path: road input + sprung-mass load transfer (Fext) → suspension → tyre
# vertical load → tyre grip.  The validated data-side counterpart is the
# shock-deflection load model in `corner_loads.jl` (MR=0.78, R²=0.89).
#
# Remaining inputs (driven by the chassis in the full vehicle, or by a test rig):
#   corner.zr   road displacement [m]
#   corner.Fext vertical force on the sprung corner [N]  (lateral/long load transfer)
#   tyre.α      slip angle [rad]      tyre.κ  slip ratio [-]
# Outputs: corner.Fz (tyre load), tyre.Fy / tyre.Fx / tyre.Mz.
#
# Requires `Corner` (corner.jl) and `Tyre` (tyre.jl) in scope.

using ModelingToolkit
using ModelingToolkit: t_nounits as t, D_nounits as D

function CornerAssembly(; name, corner = (;), tyre = (;))
    @named corner = Corner(; corner...)
    @named tyre   = Tyre(;   tyre...)
    eqs = [tyre.Fz ~ corner.Fz]              # suspension load → tyre vertical load
    System(eqs, t, Num[], []; systems = [corner, tyre], name)
end
