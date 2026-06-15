# Per-corner vertical load from the measured shock-deflection channels.
#
# iRacing logs {LF,RF,LR,RR}shockDefl [m] and shockVel [m/s].  The dynamic tyre
# load at each corner is the suspension force through the motion ratio:
#
#     Fz_i(t) = cw_i + MR·ks_i·(shockDefl_i − ref_i) + cd·shockVel_i
#                └static┘ └──── spring (compression × wheel-rate) ────┘ └damper┘
#
# cw_i (static corner weight) and ks_i (spring rate) come from the CarSetup YAML;
# ref_i (static shock deflection) is read off quasi-static cruising; MR (motion
# ratio) and cd (lumped damper coeff) are CALIBRATED by the physical constraint
# that the four corner loads sum to the measured total normal load m·VertAccel.
# This gives real per-corner Fz — including lateral/longitudinal transfer — WITHOUT
# assuming CG height or track, which is what the forward-ay tyre fit lacked.

module CornerLoads
export CORNERS, fit_corner_loads, corner_Fz, CLModel

const CORNERS = (:LF, :RF, :LR, :RR)
const G = 9.80665

med(v) = (s = sort(v); isempty(s) ? 0.0 : s[cld(length(s), 2)])

struct CLModel
    MR::Float64                      # motion ratio (shock force → wheel force)
    cd::Float64                      # lumped damper coeff [N/(m/s)]
    ref::Dict{Symbol,Float64}        # static shock deflection per corner [m]
    ks::Dict{Symbol,Float64}         # spring rate per corner [N/m]
    cw::Dict{Symbol,Float64}         # static corner weight per corner [N]
    r2::Float64                      # fit quality of Σ Fz vs m·VertAccel
end

"""    fit_corner_loads(shock, shockvel, vertaccel, m, ks, cw, good, static)

Calibrate the motion ratio + damper coeff.  `shock`/`shockvel` are Dicts corner→
Vector; `good`/`static` are sample-index vectors (general / quasi-static).
Returns a `CLModel`.
"""
function fit_corner_loads(shock, shockvel, vertaccel, m, ks, cw, good, static)
    ref = Dict(c => med([shock[c][i] for i in static]) for c in CORNERS)
    # 2-param least squares:  m·(az−g) ≈ MR·S + cd·V
    #   S_i = Σ ks_c·(shock_c−ref_c)   V_i = Σ shockVel_c
    S = [sum(ks[c]*(shock[c][i] - ref[c]) for c in CORNERS) for i in good]
    V = [sum(shockvel[c][i] for c in CORNERS) for i in good]
    Y = [m*(vertaccel[i] - G) for i in good]
    Sss = sum(abs2, S); Vvv = sum(abs2, V); Svv = sum(S[k]*V[k] for k in eachindex(S))
    SY = sum(S[k]*Y[k] for k in eachindex(S)); VY = sum(V[k]*Y[k] for k in eachindex(V))
    det = Sss*Vvv - Svv^2
    MR  = (SY*Vvv - VY*Svv) / det
    cd  = (Sss*VY - Svv*SY) / det
    pred = [MR*S[k] + cd*V[k] for k in eachindex(S)]
    ȳ = sum(Y)/length(Y)
    r2 = 1 - sum(abs2, pred .- Y)/sum(x->abs2(x-ȳ), Y)
    CLModel(MR, cd, ref, ks, cw, r2)
end

"Per-corner vertical load [N] at one sample (clamped ≥ 0 — tyre can't pull)."
corner_Fz(M::CLModel, shock, shockvel, c::Symbol) =
    max(0.0, M.cw[c] + M.MR*M.ks[c]*(shock - M.ref[c]) + M.cd*shockvel)

end # module
