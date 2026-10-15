# TD261013-1 / WHEELOFF-1 / SPAFENCE-1 / MONZAROAD-1 / PHYSFID-1 (2026-10-14/15): the PO's test-drive fixes and the
# physics-fidelity changes, as assertions -- each was verified on screen or against the gold when it shipped; this gate
# keeps a later edit from silently undoing it. Text checks on the sim and the car model, plus the FF law evaluated.
const D = joinpath(@__DIR__, "..", "..", "demo", "native")
src = read(joinpath(D, "drive_native_mtk.jl"), String)
ppl = read(joinpath(D, "people_filter.jl"), String)
gai = read(joinpath(D, "gplai.jl"), String)
veh = read(joinpath(@__DIR__, "..", "src", "components", "vehicle_3d.jl"), String)
tyr = read(joinpath(@__DIR__, "..", "src", "components", "brush_tyre.jl"), String)
fails = Ref(0)
chk(name, ok) = (println("  ", rpad(name, 78), ok ? "PASS" : "FAIL"); ok || (fails[] += 1); ok)

println("TD261013-1 / PHYSFID-1 gate")
# (c3) + WHEELOFF-1: SHIFT+R clears a wreck -- unless a wheel is off; the notice says which
chk("(c3) SHIFT+R recovers a wrecked car (clears WRECKED + WRECK_FROZEN)",
    occursin("WRECKED[] && println(\"  [recover] SHIFT+R: the wreck is cleared", src))
chk("WHEELOFF-1: SHIFT+R refused with a wheel off (recover and rst both cleared)",
    occursin("if recover && WRECKED[] && !isempty(LOOSE_WHEELS) && WHEELOFF_RULE\n            recover = false; rst = false", src))
chk("WHEELOFF-1: the refusal sits after the test hooks (they exercise it)",
    (i = findfirst("if recover && WRECKED[] && !isempty(LOOSE_WHEELS)", src); j = findfirst("recover = true; rst = true; RECOVER_I[] += 1", src);
     i !== nothing && j !== nothing && first(j) < first(i)))
chk("the wreck notice offers R only when a wheel is off",
    occursin("\"A wheel has come off -- R: restart the race\"", src))
# (a3): the pit line is outside GPL's corridor (hard edge and the rejoin rule)
chk("(a3) a car on the pit line is not held to the corridor's hard edge", occursin("onpit = PIT_FREE[] && (c.line == PIT", gai))
chk("(a3) think! leaves a car on the pit line alone", occursin("(PIT_FREE[] && c.line == PIT) && return nothing", gai))
# (a1): each race draws its own AI form / reactions / stream
chk("(a1) the AI field is seeded per race (AI_SEED, AI_RNG)",
    occursin("AI_RNG[] = Random.MersenneTwister(AI_SEED)", src) && occursin("GPLAI.Field(GPLAI_T, cars; seed = rand(AI_RNG[], UInt32))", src))
# (c1/c2/b5): the lap window -- two legs, sprites, all five tracks
chk("(c1) geometry near two legs of the lap draws with either", occursin("s2 = lapnear2(cx, -cz, sl, dsq)", src))
chk("(b5) sprites and forest panels take the lap window", occursin("_bbin(_nst + _k) || continue", src))
chk("(c2) the Ring's bkbill row leads its GPL window", occursin("\"bkbill\" => parse(Float64, get(ENV, \"JM_GPLVIS_LEAD_BKBILL\", \"400\"))", src))
# (b1/b6/S10/S11): Spa's objects
chk("(b1) house1a drawn with house1", occursin("get(ENV, \"JM_OBJ_ALIAS\", \"house1a=house1\")", src))
chk("(b1, S11) the marshal hut pform1 is not a loose person", !occursin("\"p_s\", \"pform\"", ppl))
chk("(b6) Spa's buildings are exempt from the footprint rule", occursin("_spa_bldg_fp && occursin(r\"^(house|ho\\d|lasad)\"", src))
chk("S9: the guardrails' placement roll applied", occursin("objrollsign(nm) = (OBJ_PR[2] == 0 && startswith(lowercase(nm), \"armco\")) ? RAIL_ROLL : OBJ_PR[2]", src))
chk("S10: low bush rows drawn (an exempt solid must be visible)", occursin("(_keep_lowsolid && startswith(lowercase(nm), \"bushrow\"))", src))
chk("SPAFENCE-1: the fence on Spa's invisible wall", occursin("get(ENV, \"JM_SPAFENCE\", \"8170:8440:R\")", src))
# (b3): the physics ground projects on the smoothed ribbon
chk("(b3) the physics ground uses TRKSURF_G (sigma 10 m)",
    occursin("hr = JuliaMotor.hat(TRKSURF_G, x, y)", src) && occursin("get(ENV, \"JM_GROUND_RIBBON_SIGMA\", \"10.0\")", src))
# MONZAROAD-1
chk("MONZAROAD-1: the AI road correction is checked on the race line", occursin("dr = GPLAI.dlat(lines[GPLAI.RACE], sa)", src))
# PHYSFID-1
chk("PHYSFID-1 S1: FF by iRacing's law (column torque / 28.33, no spring)",
    occursin("const FFB_IRMODE  = FFB_PHYS && get(ENV, \"JM_FFB_MODE\", \"iracing\") != \"legacy\"", src) &&
    occursin("get(ENV, \"JM_FFB_MAXNM\", \"28.33\")", src) && occursin("get(ENV, \"JM_FFB_SPRING_IR\", \"0.0\")", src))
# the law itself: 11 N·m (≈ 1 g in iRacing) must ask the wheel for ~0.39, 30 N·m saturates at 1
ffb_ir(τ; maxnm = 28.33) = clamp(τ / maxnm, -1.0, 1.0)
chk("PHYSFID-1 S1: 11 N·m -> 0.39 of the wheel; 30 N·m -> 1.0", abs(ffb_ir(11.0) - 0.388) < 0.01 && ffb_ir(30.0) == 1.0)
chk("PHYSFID-1 S2: front cornering stiffness 26", occursin("PHYSFID_S2 ? \"26.0\"", tyr))
chk("PHYSFID-1 S4: the .ibt steering-wheel angle = road angle x ratio", occursin("\"SteeringWheelAngle\"=>δw*STEER_RATIO[]", src))
chk("PHYSFID-1 S5: the driveline efficiency by power-flow direction", occursin("ηdir(T, ηc, ηd) = ηc + (ηd - ηc)*(0.5 + 0.5*tanh(T/5.0))", veh))
println(fails[] == 0 ? "ALL PASS" : "FAILURES: $(fails[])")
exit(fails[] == 0 ? 0 : 1)
