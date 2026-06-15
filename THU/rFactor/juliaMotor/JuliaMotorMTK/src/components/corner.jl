# Corner — vertical (ride) dynamics of one wheel station: a classic 2-DOF
# quarter-car (sprung corner mass on suspension spring/damper on unsprung mass on
# tyre vertical spring/damper on the road).  Written in EQUILIBRIUM coordinates
# (displacements measured from the static rest state), so gravity + spring preload
# fold into `Fz_static` and the static tyre load is exact by construction; the
# dynamic part captures road inputs and (later) load transfer.
#
# Outputs the tyre vertical load `Fz`, which feeds the `Tyre` component.  Inputs:
# `zr` road displacement [m] and `Fext` an external vertical force on the sprung
# corner [N] (this is how the chassis injects lateral/longitudinal LOAD TRANSFER
# in the full vehicle; zero in the standalone ride test).
#
# Parameter defaults are a Lotus 49 front corner from the skidpad CarSetup
# (629 kg / 4 sprung, 26 N/mm suspension); fitted per-corner later.

using ModelingToolkit
using ModelingToolkit: t_nounits as t, D_nounits as D

function Corner(; name,
        m_s = 157.0,       # sprung corner mass [kg]  (~629/4)
        m_u = 20.0,        # unsprung mass [kg]
        ks  = 26_000.0,    # suspension stiffness [N/m]  (26 N/mm — LF)
        cs  = 2_500.0,     # suspension damping [N·s/m]
        kt  = 180_000.0,   # tyre vertical stiffness [N/m]
        ct  = 300.0,       # tyre vertical damping [N·s/m]
        Fz_static = 1547.0 + 20.0*9.81)   # static tyre load [N] (LF corner wt + unsprung)
    ps = @parameters m_s=m_s m_u=m_u ks=ks cs=cs kt=kt ct=ct Fz_static=Fz_static
    vars = @variables zs(t)=0.0 vs(t)=0.0 zu(t)=0.0 vu(t)=0.0 Fz(t) zr(t) Fext(t)
    #   zs/zu: sprung/unsprung displacement from rest [m];  Fz: tyre load [N] (out)
    #   zr: road displacement [m] (in);  Fext: vertical force on sprung corner [N] (in, load transfer)
    eqs = [
        D(zs) ~ vs,
        D(zu) ~ vu,
        m_s*D(vs) ~ -ks*(zs - zu) - cs*(vs - vu) + Fext,
        m_u*D(vu) ~  ks*(zs - zu) + cs*(vs - vu) - kt*(zu - zr) - ct*(vu - D(zr)),
        Fz ~ Fz_static + kt*(zr - zu) + ct*(D(zr) - vu),
    ]
    System(eqs, t, vars, ps; name)
end
