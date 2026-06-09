# Suspension kinematics from the PM multibody graph.
#
# The PM file gives bodies, hinges and rigid bars in global design-position
# coordinates (ISI frame: +x left, +y up, +z rearward).  For kinematics the
# chassis is fixed and each wheel carrier's pose is solved from its bar
# constraints plus prescribed wheel-center heights:
#
#   * independent corner (e.g. 1958 Chapman strut): the spindle has 6 DOF
#     and 5 bars -> 1 DOF, parameterized by wheel-center z (vertical)
#   * solid axle (De Dion): the axle has 6 DOF and 4 bars -> 2 DOF,
#     parameterized by left and right wheel-center heights
#
# Solved with Newton iteration on the exact constraint equations (bar
# lengths + prescribed heights); rotations via Rodrigues, no small-angle
# approximation.  Wheels are rigid on their carriers (spin DOF ignored),
# so camber/toe come from the carrier's rotation applied to the hinge axis.

# --- rigid-body pose -------------------------------------------------------

"""Rodrigues rotation matrix for rotation vector `θ`."""
function rotmat(θ::AbstractVector{<:Real})
    φ = sqrt(θ[1]^2 + θ[2]^2 + θ[3]^2)
    K = [0.0 -θ[3] θ[2]; θ[3] 0.0 -θ[1]; -θ[2] θ[1] 0.0]
    if φ < 1e-9
        return [1.0 0 0; 0 1 0; 0 0 1] + K + K * K / 2
    end
    [1.0 0 0; 0 1 0; 0 0 1] + sin(φ) / φ * K + (1 - cos(φ)) / φ^2 * K * K
end

"""Map a design-position global point `x` through a carrier pose: rotation
`θ` about the carrier origin `o`, then translation `t`."""
transform(x, o, t, θ) = o .+ t .+ rotmat(θ) * (x .- o)

# --- constraint assembly ---------------------------------------------------

"""
A wheel carrier and everything needed to solve its pose: the bars tying it
to the chassis (with design lengths) and the wheel hinge points it carries.
"""
struct Carrier
    name::String
    origin::Vector{Float64}
    barpos::Vector{Vector{Float64}}    # chassis-side attachment (fixed)
    barneg::Vector{Vector{Float64}}    # carrier-side attachment (design pos)
    barlen::Vector{Float64}
    pins::Vector{Vector{Float64}}      # spherical [JOINT]s to the chassis
    wheels::Vector{String}             # wheel body names on this carrier
    hubs::Vector{Vector{Float64}}      # design-position wheel centers
    axes::Vector{Vector{Float64}}      # design-position spin axes
end

"""Build the carrier that holds `wheelname` (its JOINT&HINGE negbody)."""
function Carrier(pm::PMFile, wheelname::AbstractString)
    j = findfirst(jt -> isequal_ci(jt.posbody, wheelname) && jt.axis !== nothing,
                  pm.joints)
    j === nothing && throw(ArgumentError("no hinge for wheel '$wheelname'"))
    carrier = pm.joints[j].negbody
    cb = body(pm, carrier)
    cb === nothing && throw(ArgumentError("carrier body '$carrier' not found"))

    barpos, barneg, barlen = Vector{Float64}[], Vector{Float64}[], Float64[]
    for bar in pm.bars
        from_chassis = isequal_ci(bar.negbody, carrier)
        to_chassis = isequal_ci(bar.posbody, carrier)
        from_chassis || to_chassis || continue
        pchassis = resolve(pm, from_chassis ? bar.pos : bar.neg)
        pcarrier = resolve(pm, from_chassis ? bar.neg : bar.pos)
        push!(barpos, collect(Float64, pchassis))
        push!(barneg, collect(Float64, pcarrier))
        push!(barlen, sqrt(sum(abs2, pchassis .- pcarrier)))
    end

    # spherical [JOINT]s tying the carrier to the chassis: 3 constraints each
    # (stock-car solid axles use one of these plus a track bar)
    pins = Vector{Float64}[]
    for jt in pm.joints
        jt.axis === nothing || continue
        other = isequal_ci(jt.posbody, carrier) ? jt.negbody :
                isequal_ci(jt.negbody, carrier) ? jt.posbody : nothing
        other === nothing && continue
        push!(pins, collect(Float64, resolve(pm, jt.pos)))
    end

    wheels, hubs, axes = String[], Vector{Float64}[], Vector{Float64}[]
    for jt in pm.joints
        (isequal_ci(jt.negbody, carrier) && jt.axis !== nothing) || continue
        wb = body(pm, jt.posbody)
        wb === nothing && continue
        push!(wheels, wb.name)
        push!(hubs, collect(Float64, resolve(pm, jt.pos)))
        push!(axes, collect(Float64, jt.axis isa Vector ? jt.axis : resolve(pm, jt.axis)))
    end
    Carrier(cb.name, collect(Float64, cb.pos), barpos, barneg, barlen, pins,
            wheels, hubs, axes)
end

"""Solved pose of a carrier plus per-wheel kinematic outputs."""
struct CarrierPose
    t::Vector{Float64}
    θ::Vector{Float64}
    hub::Vector{Vector{Float64}}     # wheel centers, current position
    camber::Vector{Float64}          # rad; sign: top of wheel tilted inboard < 0
    toe::Vector{Float64}             # rad; sign: leading edge inboard > 0 (toe-in)
end

"""
    solve_carrier(c, targets; init=zeros(6)) -> CarrierPose

Solve the carrier pose for prescribed wheel-center heights `targets`
(one per wheel on the carrier, in carrier wheel order).  The constraint
count (bars + targets) must equal 6.
"""
function solve_carrier(c::Carrier, targets::AbstractVector{<:Real};
                       init::AbstractVector{<:Real}=zeros(6))
    nb, np, nw = length(c.barlen), length(c.pins), length(targets)
    nb + 3np + nw == 6 || throw(ArgumentError(
        "carrier '$(c.name)': $(nb) bars + $(np) pins + $(nw) height targets ≠ 6"))
    length(c.wheels) == nw || throw(ArgumentError("expected $(length(c.wheels)) targets"))

    function residual!(f, x)
        t = view(x, 1:3); θ = view(x, 4:6)
        for k in 1:nb
            p = transform(c.barneg[k], c.origin, t, θ)
            f[k] = sum(abs2, p .- c.barpos[k]) - c.barlen[k]^2
        end
        for k in 1:np
            p = transform(c.pins[k], c.origin, t, θ)
            f[nb+3k-2:nb+3k] .= p .- c.pins[k]
        end
        for w in 1:nw
            p = transform(c.hubs[w], c.origin, t, θ)
            f[nb+3np+w] = p[2] - (c.hubs[w][2] + targets[w])   # +y is up
        end
        f
    end

    x = collect(Float64, init)
    f = zeros(6); fp = zeros(6); J = zeros(6, 6)
    converged = false
    for _ in 1:50
        residual!(f, x)
        if maximum(abs, f) < 1e-12
            converged = true
            break
        end
        h = 1e-7
        for j in 1:6
            xj = x[j]
            x[j] = xj + h
            residual!(fp, x)
            @. J[:, j] = (fp - f) / h
            x[j] = xj
        end
        x .-= J \ f
    end
    converged || error("carrier '$(c.name)' did not converge for targets $targets")

    t, θ = x[1:3], x[4:6]
    R = rotmat(θ)
    hubs = [transform(c.hubs[w], c.origin, t, θ) for w in 1:nw]
    cam = Float64[]; toe = Float64[]
    for w in 1:nw
        a = R * c.axes[w]
        inboard = -sign(c.hubs[w][1])      # unit sense: toward x=0
        # camber: tilt of the spin axis out of the ground plane.  With the
        # axis pointing outboard, axis_y > 0 means top of wheel leans out.
        aout = a .* (sign(c.axes[w][1]) == sign(c.hubs[w][1]) ? 1.0 : -1.0)
        push!(cam, atan(aout[2], hypot(aout[1], aout[3])))
        # toe: spin-axis yaw; toe-in = leading edge toward the center line
        push!(toe, atan(aout[3], abs(aout[1])) * inboard * -1.0)
    end
    CarrierPose(t, θ, hubs, cam, toe)
end

# --- corner discovery and sweeps -------------------------------------------

"""Wheel body for a corner symbol (`:fl`, `:fr`, `:rl`, `:rr`) by design
position: +x = left, -z = front."""
function corner_wheel(pm::PMFile, corner::Symbol)
    hinged = [j.posbody for j in pm.joints if j.axis !== nothing &&
              body(pm, j.posbody) !== nothing]
    isempty(hinged) && throw(ArgumentError("no hinged wheels in $(pm.path)"))
    want_left = corner in (:fl, :rl)
    want_front = corner in (:fl, :fr)
    zs = [body(pm, w).pos[3] for w in hinged]
    zmid = (minimum(zs) + maximum(zs)) / 2
    for w in hinged
        p = body(pm, w).pos
        (p[1] > 0) == want_left && (p[3] < zmid) == want_front && return w
    end
    throw(ArgumentError("no wheel at corner $corner"))
end

"""
    sweep(pm, corner; travel=-0.08:0.005:0.08) -> NamedTuple

Quasi-static kinematic sweep of one corner: prescribed wheel-center
vertical travel (m), other wheels on the same carrier held at design
height.  Returns vectors `travel`, `camber`, `toe`, `track` (lateral
wheel-center position), `base` (longitudinal).
"""
function sweep(pm::PMFile, corner::Symbol; travel=-0.08:0.005:0.08)
    c = Carrier(pm, corner_wheel(pm, corner))
    wi = findfirst(==(corner_wheel(pm, corner)), c.wheels)
    targets = zeros(length(c.wheels))
    out = (travel=collect(Float64, travel), camber=Float64[], toe=Float64[],
           track=Float64[], base=Float64[])
    x0 = zeros(6)
    for dz in travel
        targets[wi] = dz
        pose = solve_carrier(c, targets; init=x0)
        x0 = vcat(pose.t, pose.θ)
        push!(out.camber, pose.camber[wi])
        push!(out.toe, pose.toe[wi])
        push!(out.track, pose.hub[wi][1])
        push!(out.base, pose.hub[wi][3])
    end
    out
end

"""
    axle_sweep(pm, corner; bump, roll) -> CarrierPose

Solid-axle pose for symmetric `bump` (m) and antisymmetric `roll` (m,
left up / right down) wheel-center travel.
"""
function axle_sweep(pm::PMFile, corner::Symbol; bump::Real=0.0, roll::Real=0.0)
    c = Carrier(pm, corner_wheel(pm, corner))
    length(c.wheels) == 2 ||
        throw(ArgumentError("carrier '$(c.name)' is not a 2-wheel axle"))
    left = sortperm([body(pm, w).pos[1] for w in c.wheels]; rev=true)
    targets = zeros(2)
    targets[left[1]] = bump + roll
    targets[left[2]] = bump - roll
    solve_carrier(c, targets)
end
