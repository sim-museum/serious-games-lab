# Natural cubic spline on a uniform grid — the interpolation the TBC spec
# prescribes for slip curves ("Slip curve data points are connected using
# a cubic spline").  Hand-rolled to keep the engine dependency-free and
# the evaluation allocation-free.

"""
Natural cubic spline through samples `y` at `x = 0, h, 2h, ...`.
Evaluation outside the sampled range clamps to the end values (slip
curves extend to slip ≈ 2; isiMotor holds the last value beyond).
"""
struct UniformSpline
    h::Float64
    y::Vector{Float64}
    m::Vector{Float64}   # second derivatives at the nodes
end

function UniformSpline(y::AbstractVector{<:Real}, h::Real)
    n = length(y)
    n >= 3 || throw(ArgumentError("spline needs at least 3 samples"))
    h > 0 || throw(ArgumentError("sample step must be positive"))

    # natural spline: m[1] = m[n] = 0; interior nodes solve the tridiagonal
    #   m[i-1] + 4 m[i] + m[i+1] = 6 (y[i-1] - 2y[i] + y[i+1]) / h^2
    # via the Thomas algorithm.
    m = zeros(n)
    if n > 2
        k = n - 2                      # interior unknowns
        c′ = Vector{Float64}(undef, k) # scratch superdiagonal
        d′ = Vector{Float64}(undef, k) # scratch rhs
        rhs(i) = 6.0 * (y[i-1] - 2.0 * y[i] + y[i+1]) / h^2
        c′[1] = 1.0 / 4.0
        d′[1] = rhs(2) / 4.0
        for j in 2:k
            denom = 4.0 - c′[j-1]
            c′[j] = 1.0 / denom
            d′[j] = (rhs(j + 1) - d′[j-1]) / denom
        end
        m[k+1] = d′[k]
        for j in (k-1):-1:1
            m[j+1] = d′[j] - c′[j] * m[j+2]
        end
    end
    UniformSpline(Float64(h), collect(Float64, y), m)
end

xmax(s::UniformSpline) = s.h * (length(s.y) - 1)

function (s::UniformSpline)(x::Real)
    x <= 0 && return s.y[1]
    x >= xmax(s) && return s.y[end]
    i = min(floor(Int, x / s.h) + 1, length(s.y) - 1)
    a = x - (i - 1) * s.h            # distance from left node
    b = s.h - a                      # distance to right node
    (s.m[i] * b^3 + s.m[i+1] * a^3) / (6.0 * s.h) +
        (s.y[i] / s.h - s.m[i] * s.h / 6.0) * b +
        (s.y[i+1] / s.h - s.m[i+1] * s.h / 6.0) * a
end
