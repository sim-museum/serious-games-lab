# Shared fitting helpers: the Magic-Formula branch and a dependency-free
# Nelder-Mead simplex optimiser.  Used by the skidpad/Nürburgring fit scripts.
module FitUtil
export mf, nelder_mead

"Sine Magic-Formula: μ·sin(C·atan(B·x − E·(B·x − atan(B·x))))."
mf(x, μ, B, C, E) = μ * sin(C * atan(B*x - E*(B*x - atan(B*x))))

"Minimise `F` from `x0` with Nelder-Mead (no deps).  Returns (xbest, fbest)."
function nelder_mead(F, x0; iters = 6000, step = 0.12)
    n = length(x0)
    simplex = [copy(x0)]
    for i in 1:n
        x = copy(x0); x[i] += (x[i] != 0 ? step*abs(x[i]) : step); push!(simplex, x)
    end
    fv = [F(x) for x in simplex]
    for _ in 1:iters
        o = sortperm(fv); simplex = simplex[o]; fv = fv[o]
        xbar = sum(simplex[1:end-1]) / n
        xr = xbar + (xbar - simplex[end]); fr = F(xr)
        if fr < fv[1]
            xe = xbar + 2*(xbar - simplex[end]); fe = F(xe)
            simplex[end], fv[end] = fe < fr ? (xe, fe) : (xr, fr)
        elseif fr < fv[end-1]
            simplex[end], fv[end] = xr, fr
        else
            xc = xbar + 0.5*(simplex[end] - xbar); fc = F(xc)
            if fc < fv[end]
                simplex[end], fv[end] = xc, fc
            else
                for i in 2:n+1
                    simplex[i] = simplex[1] + 0.5*(simplex[i] - simplex[1]); fv[i] = F(simplex[i])
                end
            end
        end
    end
    o = sortperm(fv); simplex[o[1]], fv[o[1]]
end

end # module
