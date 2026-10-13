# IRGOLD-1 S22: a per-gear (low/high) driveline inertia remainder. Neutral by default (Igb_low = Igb).
base='/home/g/sgl-jr/THU/rFactor/juliaMotor/JuliaMotorMTK/'
p=base+'src/components/vehicle_3d.jl'; s=open(p).read()
old="Igb=(ENGINE_LUMPED ? 0.0 : DRIVELINE_INPUT ? 0.18 - IE_ENGINE : IE_DRIVELINE)"
assert s.count(old)==1
s=s.replace(old, old+" Igb_low=(ENGINE_LUMPED ? 0.0 : DRIVELINE_INPUT ? 0.18 - IE_ENGINE : IE_DRIVELINE) gsplit=gsplit")
old="push!(eqs, (2*Iw + Igb*(DRIVELINE_INPUT ? gr : final)^2*η)*D(ωr) ~"
assert s.count(old)==1
s=s.replace(old,"push!(eqs, (2*Iw + Igbe*(DRIVELINE_INPUT ? gr : final)^2*η)*D(ωr) ~")
old="Igr  = Igb*(DRIVELINE_INPUT ? gr : final)^2*η/4 "
assert s.count(old)==1
s=s.replace(old,"Igr  = Igbe*(DRIVELINE_INPUT ? gr : final)^2*η/4 ")
old="    ωgb = ωr*gr\n"
assert s.count(old)==1
s=s.replace(old, old+'''    # IRGOLD-1 S22: the driveline remainder PER GEAR. The gold's WOT rows want ~0.03 beyond the crank in 1st/2nd and today's
    # 0.128 in 3rd-5th (261012/tools/wotsession.py: 2nd gear +15-20 N·m too strong in 4 of 5 sessions with 0.128). `gear` is
    # the RATIO (a parameter), so the low-gear value applies above `gsplit` (between 2nd and 3rd) -- parameters only, no
    # mass matrix. Igb_low = Igb: the car before S22.
    Igbe = ifelse(gear > gsplit, Igb_low, Igb)
''')
# gsplit keyword: default between the session's 2nd and 3rd ratios is set by the caller; a generic default here
old="        diff = nothing, toe_f = 0.0, toe_r = 0.0, karb_f = 0.0, karb_r = 0.0, camber = nothing, rc = CAMBER_RC)"
assert s.count(old)==1
s=s.replace(old,"        diff = nothing, toe_f = 0.0, toe_r = 0.0, karb_f = 0.0, karb_r = 0.0, camber = nothing, rc = CAMBER_RC,\n        gsplit = 1.5)   # IRGOLD-1 S22: the gear ratio between 2nd and 3rd (the caller passes the session's)")
open(p,'w').write(s)
p=base+'src/drive_rt3d.jl'; s=open(p).read()
old="a = cg_arms()[1], b = cg_arms()[2]; _chassis_kw()...))   # physics brush by DEFAULT; JM_MAGIC ⇒ Magic-Formula tyre"
assert s.count(old)==1
s=s.replace(old,"a = cg_arms()[1], b = cg_arms()[2], gsplit = _gsplit(); _chassis_kw()...))   # physics brush by DEFAULT; JM_MAGIC ⇒ Magic-Formula tyre")
old="function build_car3d(; x0 = 0.0, z0 = 0.0, θ0 = 0.0, v0 = 0.0, y0 = 0.0,"
assert s.count(old)==1
s=s.replace(old,'"IRGOLD-1 S22: the ratio between the installed gearbox\'s 2nd and 3rd gears (the per-gear inertia\'s split)."\n_gsplit() = length(GEARS) >= 3 ? 0.5*(GEARS[2] + GEARS[3]) : 1.5\n'+old)
open(p,'w').write(s)
p=base+'tools/irgold_params.jl'; s=open(p).read()
old='''    "claf" => (:veh, :ClAf), "clar" => (:veh, :ClAr))'''
assert s.count(old)==1
s=s.replace(old,'''    "claf" => (:veh, :ClAf), "clar" => (:veh, :ClAr),
    "igblow" => (:veh, :Igb_low))     # IRGOLD-1 S22: the driveline remainder in 1st/2nd''')
open(p,'w').write(s)
print("S22 patched")
