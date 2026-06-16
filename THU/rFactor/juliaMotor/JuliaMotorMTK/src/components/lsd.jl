# Clutch-pack limited-slip differential (LSD).
#
# A clutch-pack LSD generates a LOCKING torque that resists the speed difference
# between the two driven (rear) wheels, transferring torque from the faster
# (spinning) wheel to the slower (gripping) one.  The locking torque is set by a
# spring PRELOAD plus a ramp that converts transmitted torque into clutch axial
# load — separate DRIVE and COAST ramp angles (smaller angle ⇒ more locking):
#
#     T_lock = preload + κ_drive·max(T_in,0) + κ_coast·max(−T_in,0)
#     κ_ramp = Clsd · n_plates / tan(ramp_angle)
#     T_lsd  = T_lock · tanh((ω_RR − ω_RL)/ε)     # opposes the speed diff (fast→slow)
#
# Lotus 49 CarSetup: 6 plates, preload 41 N·m, drive ramp 50°, coast ramp 80°.
# Requires the tyre law (tyre_fx) and engine_torque (powertrain.jl).

using ModelingToolkit
using ModelingToolkit: t_nounits as t, D_nounits as D

"Clutch-pack locking-torque capacity [N·m] from transmitted torque T_in."
function lsd_lock_torque(T_in; preload = 41.0, drive_ramp = 50.0, coast_ramp = 80.0,
                         plates = 6, Clsd = 0.18)
    κd = Clsd*plates/tan(deg2rad(drive_ramp))
    κc = Clsd*plates/tan(deg2rad(coast_ramp))
    preload + κd*max(T_in, 0.0) + κc*max(-T_in, 0.0)
end

# Standalone rear axle + clutch-pack LSD: two rear wheels (ωRL, ωRR) driven through
# an open diff (equal torque split) PLUS the LSD locking torque; engine couples to
# the carrier speed.  Per-wheel vertical loads Fz_RL/Fz_RR are parameters (set them
# unequal to model an in-corner inner/outer split).  lock_scale=0 ⇒ open diff.
function RearAxleLSD(; name, m = 617.0, Rw = 0.33, Iw = 1.0, Ieng = 0.10, η = 0.9,
        gear = 1.32, final = 4.11, CdA = 0.9, ρair = 1.10,
        Fz_RL = 1700.0, Fz_RR = 1700.0, throttle = 1.0, lock_scale = 1.0,
        preload = 41.0, drive_ramp = 50.0, coast_ramp = 80.0, plates = 6,
        tyre = TYRE_SKIDPAD_REAR)
    ps = @parameters m=m Rw=Rw Iw=Iw Ieng=Ieng η=η gear=gear final=final CdA=CdA ρair=ρair Fz_RL=Fz_RL Fz_RR=Fz_RR throttle=throttle lock_scale=lock_scale preload=preload drive_ramp=drive_ramp coast_ramp=coast_ramp plates=plates
    vars = @variables u(t)=20.0 ωRL(t)=60.6 ωRR(t)=60.6 rpm(t) κRL(t) κRR(t) FxRL(t) FxRR(t) Tdrive(t) Tlock(t) Tlsd(t) ax(t)
    gr = gear*final
    Icar = 2*Iw + Ieng*gr^2                          # total reflected inertia at the axle
    eqs = [
        rpm    ~ (ωRL+ωRR)/2*gr*60/(2π),             # engine ↔ carrier (avg wheel) speed
        Tdrive ~ engine_torque(rpm, throttle)*gr*η,
        Tlock  ~ lsd_lock_torque(Tdrive; preload=preload, drive_ramp=drive_ramp,
                                  coast_ramp=coast_ramp, plates=plates),
        Tlsd   ~ lock_scale*Tlock*tanh((ωRR-ωRL)/2.0),
        κRL ~ (ωRL*Rw - u)/(u+0.5),  κRR ~ (ωRR*Rw - u)/(u+0.5),
        FxRL ~ tyre_fx(Fz_RL, κRL; p=tyre),  FxRR ~ tyre_fx(Fz_RR, κRR; p=tyre),
        # wheel dynamics: open-diff equal split T/2, plus LSD locking (+RL / −RR)
        (Icar/2)*D(ωRL) ~ Tdrive/2 + Tlsd - FxRL*Rw,
        (Icar/2)*D(ωRR) ~ Tdrive/2 - Tlsd - FxRR*Rw,
        ax ~ (FxRL + FxRR - 0.5*ρair*CdA*u^2)/m,
        D(u) ~ ax,
    ]
    System(eqs, t, vars, ps; name)
end
