# Thermal / pressure / camber extension to the isothermal tyre.
#
# HONESTY NOTE: unlike the force fits, these are STRUCTURAL physics additions, not
# telemetry fits.  The .ibt exposes surface temp (`tempM`, 34–131 °C here) but its
# iRacing thermal model does NOT track a lumped slip-power model (d(tempM)/dt vs a
# slip-power proxy correlates ~0), the carcass temp + pressure are ~static (152 kPa,
# no buildup for this tyre/setup), and there is no per-tyre force to fit μ(T).  So
# the coefficients below are physics-reasonable defaults calibrated to the observed
# operating RANGES, giving the right qualitative behaviour (grip peaks at an optimal
# temperature/pressure; camber adds lateral thrust); they are not claimed as fits.
#
# Effects:
#   • μ_temp(T)  — grip multiplier, peaks at the optimal temperature, falls cold/hot
#   • μ_press(p) — grip multiplier, peaks at the reference pressure
#   • camber thrust — γ adds Fy ≈ Fz·Cγ·γ
#   • a surface-temperature STATE: Csurf·dT/dt = Q_slip − h·(1+kv·v)·(T−Tamb),
#     Q_slip = |Fx·κ + Fy·sinα|·v (friction power dissipated in the contact patch)

# ---- pure functions (no MTK) ------------------------------------------------
"Grip multiplier vs surface temperature (peaks at Topt)."
mu_temp(T; Topt = 90.0, kT = 0.45) = max(0.30, 1 - kT*((T - Topt)/100)^2)

"Grip multiplier vs hot pressure [kPa] (peaks at pref)."
mu_press(pk; pref = 152.0, kp = 0.6) = max(0.70, 1 - kp*((pk - pref)/pref)^2)

"Surface-temperature rate [°C/s]: friction-power heating vs convective cooling."
tyre_temp_rate(T, Q, v; Csurf = 600.0, h = 40.0, kv = 0.06, Tamb = 30.0) =
    (Q - h*(1 + kv*v)*(T - Tamb)) / Csurf

using ModelingToolkit
using ModelingToolkit: t_nounits as t, D_nounits as D

# ---- ThermalTyre: Tyre + temperature state + p/T/γ-dependent grip ------------
# Inputs Fz, α, κ, v (speed, for slip power & cooling); parameters γ (camber rad),
# pk (hot pressure kPa).  State T (surface temp).  Outputs Fx, Fy, Mz, T.
function ThermalTyre(; name, T0 = 60.0, γ = 0.0, pk = 152.0,
        Fz0 = TYRE_SKIDPAD_FRONT.Fz0, μy = TYRE_SKIDPAD_FRONT.μy, μx = TYRE_SKIDPAD_FRONT.μx,
        Cy = TYRE_SKIDPAD_FRONT.Cy, Cx = TYRE_SKIDPAD_FRONT.Cx, Ey = TYRE_SKIDPAD_FRONT.Ey,
        Ex = TYRE_SKIDPAD_FRONT.Ex, pKy1 = TYRE_SKIDPAD_FRONT.pKy1, pKy2 = TYRE_SKIDPAD_FRONT.pKy2,
        pKx1 = TYRE_SKIDPAD_FRONT.pKx1, t0 = TYRE_SKIDPAD_FRONT.t0, Bt = TYRE_SKIDPAD_FRONT.Bt,
        Cγ = 3.0, Topt = 90.0, kT = 0.45, pref = 152.0, kp = 0.6,
        Csurf = 600.0, hcool = 40.0, kv = 0.06, Tamb = 30.0)
    ps = @parameters Fz0=Fz0 μy=μy μx=μx Cy=Cy Cx=Cx Ey=Ey Ex=Ex pKy1=pKy1 pKy2=pKy2 pKx1=pKx1 t0=t0 Bt=Bt γ=γ pk=pk Cγ=Cγ Topt=Topt kT=kT pref=pref kp=kp Csurf=Csurf hcool=hcool kv=kv Tamb=Tamb
    vars = @variables Fz(t) α(t) κ(t) v(t) Fy(t) Fx(t) Mz(t) T(t)=T0 gT(t) gP(t) μye(t) μxe(t) Fy0(t) Fx0(t) gc(t) Q(t) Ky(t)
    eqs = [
        gT  ~ max(0.30, 1 - kT*((T - Topt)/100)^2),       # temperature grip factor
        gP  ~ max(0.70, 1 - kp*((pk - pref)/pref)^2),      # pressure grip factor
        μye ~ μy*gT*gP,  μxe ~ μx*gT*gP,                    # effective friction
        Ky  ~ mf_stiffness(Fz, Fz0, pKy1, pKy2),
        Fy0 ~ μye*Fz*mf_branch(Ky/(Cy*μye*Fz + 1e-6)*α, Cy, Ey) + Fz*Cγ*γ,   # + camber thrust
        Fx0 ~ μxe*Fz*mf_branch((pKx1*Fz)/(Cx*μxe*Fz + 1e-6)*κ, Cx, Ex),
        gc  ~ min(1.0, 1.0/sqrt((Fx0/(μxe*Fz + 1e-6))^2 + (Fy0/(μye*Fz + 1e-6))^2 + 1e-9)),
        Fx  ~ gc*Fx0,  Fy ~ gc*Fy0,
        Mz  ~ -(t0/(1 + (Bt*α)^2))*Fy,
        Q   ~ abs(Fx*κ + Fy*sin(α))*v,                     # friction power [W]
        D(T) ~ (Q - hcool*(1 + kv*v)*(T - Tamb))/Csurf,    # surface-temperature ODE
    ]
    System(eqs, t, vars, ps; name)
end
