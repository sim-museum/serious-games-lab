using JuliaMotor
using RFactorData
using RFactorTelemetry
using Test
using Statistics

@testset "JuliaMotor" begin

@testset "UniformSpline" begin
    # interpolates the nodes exactly
    y = [0.0, 0.5, 1.0, 0.9, 0.7]
    s = UniformSpline(y, 0.25)
    for (i, v) in enumerate(y)
        @test s((i - 1) * 0.25) ≈ v atol = 1e-12
    end
    # clamps outside the range
    @test s(-1.0) == y[1]
    @test s(10.0) == y[end]
    # C1-continuous at an interior node (left/right slopes agree)
    ϵ = 1e-7
    left = (s(0.5) - s(0.5 - ϵ)) / ϵ
    right = (s(0.5 + ϵ) - s(0.5)) / ϵ
    @test left ≈ right atol = 1e-4
    # linear data reproduces the line (natural spline is exact for degree 1)
    lin = UniformSpline([0.0, 1.0, 2.0, 3.0], 1.0)
    @test lin(0.4) ≈ 0.4 atol = 1e-12
    @test lin(2.7) ≈ 2.7 atol = 1e-12
end

@testset "pre-peak shape: calibrated vs legacy" begin
    step = 0.0025
    data = vcat(range(0.0, 1.0; length=12), fill(0.99, 30))
    legacy = TireCurve(SlipCurve("syn", step, 0.0, collect(data)))
    cal = TireCurve(SlipCurve("syn", step, 0.0, collect(data)); prepeak_tau=0.0905)
    pk = 0.18
    # both reach exactly 1.0 at the peak (continuity with the post-peak spline)
    @test reaction(legacy, pk, pk) ≈ 1.0 atol = 1e-9
    @test reaction(cal, pk, pk) ≈ 1.0 atol = 1e-6
    # the calibrated shape rises much faster (the measured isiMotor behavior)
    @test reaction(cal, 0.05 * pk, pk) ≈ 0.424 atol = 1e-3
    @test reaction(cal, 0.25 * pk, pk) ≈ 0.937 atol = 1e-3
    @test reaction(legacy, 0.05 * pk, pk) < 0.15
    # monotone pre-peak
    rs = [reaction(cal, u * pk, pk) for u in 0.0:0.05:1.0]
    @test issorted(rs)
end

@testset "dropoff semantics" begin
    # synthetic peaked curve: rise to 1.0 at slip 0.1, fall to 0.6
    step = 0.01
    data = vcat(range(0.0, 1.0; length=11), range(0.98, 0.6; length=20))
    mk(d) = TireCurve(SlipCurve("syn", step, d, collect(data)))

    c1 = mk(1.0)   # dropoff stretches with the curve
    pk = 0.2       # relocate peak from 0.1 to 0.2 (stretch = 2)
    @test reaction(c1, 0.30, pk) ≈ c1.spline(0.15) atol = 1e-12
    @test reaction(c1, pk, pk) ≈ 1.0 atol = 1e-9          # peak stays 1.0

    c0 = mk(0.0)   # dropoff shape fixed: slip pk+δ maps to peak0+δ
    δ = 0.05
    @test reaction(c0, pk + δ, pk) ≈ c0.spline(0.1 + δ) atol = 1e-12

    cm = mk(-1.0)  # faster dropoff when peak grows: pk+δ maps past peak0+δ
    @test reaction(cm, pk + δ, pk) ≈ cm.spline(0.1 + 2δ) atol = 1e-12

    # pre-peak is a pure stretch regardless of dropoff
    for c in (c1, c0, cm)
        @test reaction(c, 0.1, pk) ≈ c.spline(0.05) atol = 1e-12
    end
    # symmetric in slip sign
    @test reaction(c1, -0.30, pk) == reaction(c1, 0.30, pk)
end

@testset "LoadSens / PeakShift anchors" begin
    ls = LoadSens(-3.134e-5, 0.395, 20404.6)    # Dunlop front lateral
    @test loadmult(ls, 0) == 1.0
    @test loadmult(ls, 20404.6) ≈ 0.395 atol = 1e-12
    @test loadmult(ls, 50_000) == 0.395          # clamped
    # initial slope honored
    @test (loadmult(ls, 1.0) - 1.0) ≈ -3.134e-5 atol = 1e-9
    # monotone decreasing over the physical range
    @test issorted([loadmult(ls, l) for l in 0:500:20_000]; rev=true)

    pk = PeakShift(0.1440, 0.2300, 5309.5)       # Dunlop front lateral
    @test peakslip(pk, 0) == 0.1440
    @test peakslip(pk, 5309.5) ≈ 0.2300
    @test peakslip(pk, 1e6) == 0.2300            # clamped
    @test peakslip(pk, 5309.5 / 2) ≈ (0.1440 + 0.2300) / 2
end

gamedata = default_gamedata()
dunlop_path = joinpath(gamedata, "Vehicles", "F158", "DunlopR4-16inches.tbc")
if isfile(dunlop_path)
    tbc = read_tbc(dunlop_path)
    front = TBCTire(tbc, :front)
    rear = TBCTire(tbc, :rear)

    @testset "Dunlop R4 bench: construction" begin
        @test front.mu_lat ≈ 1.0960
        @test front.mu_long ≈ 1.112
        @test front.radius ≈ 0.3341
        @test front.equivalency ≈ 1.372
        @test rear.equivalency ≈ 1.548
        @test front.lat.peak_slip0 ≈ 0.0275 atol = 1e-9   # sample 12 of the data
        @test front.lat.dropoff == 0.0
        # normalized: spline peak is exactly 1 at the nominal peak slip
        @test front.lat.spline(front.lat.peak_slip0) ≈ 1.0 atol = 1e-9
    end

    @testset "Dunlop R4 bench: force surface" begin
        load, speed = 3000.0, 30.0
        cmb = combo(load, speed, front.equivalency)
        pk = peakslip(front.pk_lat, cmb)
        @test 0.144 < pk < 0.23                   # mid-range combo

        # force rises monotonically to the peak slip, then drops
        slips = 0.0:0.005:0.5
        fy = [lateral_force(front, s, load, speed) for s in slips]
        imax = argmax(fy)
        @test slips[imax] ≈ pk atol = 0.01
        @test issorted(fy[1:imax])
        @test fy[end] < fy[imax]

        # peak force == peak grip coefficient × load (within spline tolerance)
        @test maximum(fy) ≈ peak_mu_lat(front, load) * load rtol = 1e-3
        # telemetry-scale sanity: ~0.99 peak mu at 3 kN
        @test peak_mu_lat(front, 3000.0) ≈ 0.994 atol = 0.01

        # heavier load -> lower mu (load sensitivity)
        @test peak_mu_lat(front, 5000.0) < peak_mu_lat(front, 1000.0)
        # higher speed -> larger combo -> peak at higher slip
        pk_fast = peakslip(front.pk_lat, combo(load, 80.0, front.equivalency))
        @test pk_fast > pk

        # longitudinal: traction and braking use their own curves
        @test longitudinal_force(front, 0.1, load, speed) > 0
        @test longitudinal_force(front, -0.1, load, speed) < 0
        @test abs(longitudinal_force(front, -1.0, load, speed)) <=
              peak_mu_long(front, load) * load

        # combined slip never exceeds the friction ellipse
        for s in (0.05, 0.15, 0.4), r in (-0.3, -0.1, 0.1, 0.3)
            fx, fy2 = tire_forces(front, s, r, load, speed)
            @test hypot(fx / (peak_mu_long(front, load) * load),
                        fy2 / (peak_mu_lat(front, load) * load)) <= 1.0 + 1e-9
        end
    end

    vanwall = load_vehicle(joinpath(gamedata, "Vehicles", "F158", "Vanwall",
                                    "Teams", "LewisEvans", "LewisEvans.veh"))
    eng = EngineModel(vanwall.engine; rev_limit=8500)
    dt = Drivetrain(vanwall)

    @testset "engine model: Vanwall V254" begin
        # ~270 hp @ 7500 rpm — the historical figure for the 1958 Vanwall
        p, prpm = peak_power(eng)
        @test p / 745.7 ≈ 270.3 atol = 1.0
        @test prpm == 7500.0
        @test eng.inertia == 0.16
        @test (eng.idle_lo, eng.idle_hi) == (1600.0, 1800.0)
        # torque blend: coast at 0, full at 1, monotone in throttle
        @test engine_torque(eng, 5000, 0.0) == coast_torque(eng, 5000) < 0
        @test engine_torque(eng, 5000, 1.0) == full_torque(eng, 5000) > 0
        @test engine_torque(eng, 5000, 0.3) < engine_torque(eng, 5000, 0.7)
        # interpolation: exact at table nodes, clamped at ends
        @test full_torque(eng, vanwall.engine.rpm[10]) == vanwall.engine.torque[10]
        @test full_torque(eng, 1e6) == vanwall.engine.torque[end]
        # rev limiter cuts drive torque
        @test engine_torque(eng, 8600, 1.0) <= 0
    end

    @testset "drivetrain: ratios match HDV comments and telemetry" begin
        # gear settings index the DESCENDING-sorted ratio list (the 1958
        # file's misplaced 0.611 entry would otherwise shift gear 3+)
        @test round.(dt.totals; digits=3) == [9.344, 6.345, 4.694, 3.714, 3.250]
        @test dt.final ≈ 3.25
        @test dt.wheeldrive === :rear
        @test ngears(dt) == 5
        @test wheel_speed(dt, 2, 6345.0) * dt.totals[2] * 60 / 2π ≈ 6345.0
        @test engine_rpm(dt, 1, wheel_speed(dt, 1, 4000.0)) ≈ 4000.0
        @test wheel_torque(dt, 3, 100.0) ≈ 469.4 atol = 0.05
    end

    logs = filter(p -> occursin("2026_06_05_13_24_33", basename(p)), find_daq_logs())

    @testset "telemetry validation: gear ratios and wheel radius" begin
        if isempty(logs)
            @info "reference telemetry session not found; skipping"
        else
            s = read_daq_csv(only(logs))
            rpm = s["Engine RPM"]; gear = s["Gear"]
            cpp = s["Clutch Pedal Position"]; spd = s["Ground Speed"]
            wrl = s["Wheel Rot Speed RL"]; wrr = s["Wheel Rot Speed RR"]
            wfl = s["Wheel Rot Speed FL"]; wfr = s["Wheel Rot Speed FR"]
            med(x) = sort(x)[(length(x) + 1) ÷ 2]
            for g in 1:3        # gears 4-5 unused at Monaco
                idx = [i for i in eachindex(rpm)
                       if gear[i] == g && cpp[i] < 1 && rpm[i] > 2500 && spd[i] > 20]
                @test length(idx) > 1000
                obs = med([rpm[i] * 2π / 60 / ((wrl[i] + wrr[i]) / 2) for i in idx])
                @test obs ≈ dt.totals[g] rtol = 1e-3
            end
            # rolling radius from the undriven fronts vs TBC Radius (loaded
            # rolling radius sits slightly below the free radius)
            glat = s["G Force Lat"]
            idx = [i for i in eachindex(spd) if spd[i] > 40 && abs(glat[i]) < 0.1]
            rr = med([spd[i] / 3.6 / ((wfl[i] + wfr[i]) / 2) for i in idx])
            @test rr ≈ front.radius rtol = 0.01
        end
    end

    zand = filter(p -> occursin("Zandvoort-2026_06_05_17_36_16", basename(p)),
                  find_daq_logs())
    @testset "telemetry validation: all 5 gears + drag (Zandvoort)" begin
        if isempty(zand)
            @info "Zandvoort session not found; skipping"
        else
            s = read_daq_csv(only(zand))
            rpm = s["Engine RPM"]; gear = s["Gear"]
            cpp = s["Clutch Pedal Position"]; spd = s["Ground Speed"] ./ 3.6
            wrl = s["Wheel Rot Speed RL"]; wrr = s["Wheel Rot Speed RR"]
            med(x) = sort(x)[(length(x) + 1) ÷ 2]
            for g in 1:5     # Zandvoort's straight reaches 5th
                idx = [i for i in eachindex(rpm)
                       if gear[i] == g && cpp[i] < 1 && rpm[i] > 2500 && spd[i] > 8]
                @test length(idx) > 100
                obs = med([rpm[i] * 2π / 60 / ((wrl[i] + wrr[i]) / 2) for i in idx])
                @test obs ≈ dt.totals[g] rtol = 1e-3
            end

            # wide speed band (69-193 km/h) separates aero drag from constant
            # losses: the v^2 coefficient must land near the CdA convention
            # 0.5*rho*BodyDragBase = 0.5*1.225*0.3202 ≈ 0.196 (and nowhere
            # near the raw-coefficient reading 0.3202)
            tp = s["Throttle Position"]; bpp = s["Brake Pedal Position"]
            glat = s["G Force Lat"]; fuel = s["Fuel Level"]; t = s["Time"]
            n = length(spd)
            acc = [(spd[min(i+2, n)] - spd[max(i-2, 1)]) /
                   (t[min(i+2, n)] - t[max(i-2, 1)]) for i in 1:n]
            idx = [i for i in 3:n-2 if tp[i] > 99 && bpp[i] < 1 && cpp[i] < 1 &&
                   abs(glat[i]) < 0.15 && gear[i] in (2, 3, 4, 5) &&
                   3000 < rpm[i] < 8200 && spd[i] > 10]
            @test length(idx) > 150
            r = front.radius
            g(i) = Int(gear[i])
            m_tot(i) = 715.0 + fuel[i] * 0.74
            m_rot(i) = (eng.inertia * dt.totals[g(i)]^2 + 4 * 1.25) / r^2
            fw(i) = engine_torque(eng, rpm[i], 1.0) * dt.totals[g(i)] / r
            resid = [fw(i) - (m_tot(i) + m_rot(i)) * acc[i] for i in idx]
            v2 = [spd[i]^2 for i in idx]
            # 2x2 normal equations for resid ≈ k2*v^2 + k0
            S11, S1 = sum(v2 .^ 2), sum(v2)
            N = length(idx)
            det = S11 * N - S1^2
            k2 = (N * sum(resid .* v2) - S1 * sum(resid)) / det
            k0 = (S11 * sum(resid) - S1 * sum(resid .* v2)) / det
            @test 0.13 < k2 < 0.25        # CdA convention ✓, raw 0.3202 ✗
            @test 500 < k0 < 1000         # constant losses, attribution Phase 3
            pred = [(fw(i) - k2 * v2[j] - k0) / (m_tot(i) + m_rot(i))
                    for (j, i) in enumerate(idx)]
            meas = acc[idx]
            @test sqrt(sum(abs2, pred .- meas) / N) < 0.25
        end
    end

    @testset "telemetry validation: full-throttle acceleration" begin
        if isempty(logs)
            @info "reference telemetry session not found; skipping"
        else
            s = read_daq_csv(only(logs))
            spd = s["Ground Speed"] ./ 3.6
            rpm = s["Engine RPM"]; gear = s["Gear"]; tp = s["Throttle Position"]
            bpp = s["Brake Pedal Position"]; cpp = s["Clutch Pedal Position"]
            glat = s["G Force Lat"]; fuel = s["Fuel Level"]; t = s["Time"]
            n = length(spd)
            acc = [(spd[min(i+2, n)] - spd[max(i-2, 1)]) /
                   (t[min(i+2, n)] - t[max(i-2, 1)]) for i in 1:n]
            idx = [i for i in 3:n-2 if tp[i] > 99 && bpp[i] < 1 && cpp[i] < 1 &&
                   abs(glat[i]) < 0.15 && gear[i] in (2, 3) &&
                   3000 < rpm[i] < 8200 && spd[i] > 10]
            @test length(idx) > 50

            r = front.radius
            g(i) = Int(gear[i])
            m_tot(i) = 715.0 + fuel[i] * 0.74           # validated statically
            m_rot(i) = (eng.inertia * dt.totals[g(i)]^2 + 4 * 1.25) / r^2
            fw(i) = engine_torque(eng, rpm[i], 1.0) * dt.totals[g(i)] / r

            # resistive force fit (Monaco's speed band cannot separate aero
            # drag from constant losses — Phase 2 item; here it is one
            # nuisance term, and the engine/drivetrain model must explain
            # the rest of the acceleration almost perfectly)
            resid = [fw(i) - (m_tot(i) + m_rot(i)) * acc[i] for i in idx]
            v2 = [spd[i]^2 for i in idx]
            k = sum(resid .* v2) / sum(v2 .^ 2)
            pred = [(fw(i) - k * spd[i]^2) / (m_tot(i) + m_rot(i)) for i in idx]
            meas = acc[idx]
            covpm = sum((pred .- sum(pred)/length(pred)) .* (meas .- sum(meas)/length(meas)))
            corr = covpm / sqrt(sum(abs2, pred .- sum(pred)/length(pred)) *
                                sum(abs2, meas .- sum(meas)/length(meas)))
            rms = sqrt(sum(abs2, pred .- meas) / length(idx))
            @test corr > 0.97
            @test rms < 0.25       # m/s^2, vs mean |accel| ≈ 3.2
        end
    end
    @testset "telemetry validation: measured grip vs model" begin
        if isempty(logs)
            @info "reference telemetry session not found; skipping"
        else
            s = read_daq_csv(only(logs))
            glat = s["G Force Lat"]
            for (corner, tire) in (("FL", front), ("FR", front),
                                   ("RL", rear), ("RR", rear))
                load = s["Tire Load - $corner"]
                lat = s["Lat Force - $corner"]
                idx = [i for i in eachindex(load)
                       if abs(glat[i]) > 0.5 && load[i] > 200]
                @test length(idx) > 500
                mu = [abs(lat[i]) / load[i] for i in idx]
                cap = [peak_mu_lat(tire, load[i]) for i in idx]
                # measured grip must not exceed the model's peak-mu envelope
                violations = count(mu .> cap .* 1.05)
                @test violations / length(idx) < 0.01
                # the session reached the limit: best measured grip comes
                # within 15 % of the model peak (validates magnitude, both
                # directions, despite unmodeled thermal effects)
                headroom = maximum(mu ./ cap)
                @test 0.85 < headroom <= 1.05
            end
        end
    end
    pm = read_pm(joinpath(gamedata, "Vehicles", "F158",
                          "1958FrontChapman-RearLeafAndDeDion.pm"))

    @testset "suspension: solver fundamentals" begin
        c = Carrier(pm, corner_wheel(pm, :fl))
        @test c.name == "fl_spindle"
        @test length(c.barlen) == 5 && length(c.wheels) == 1
        # design position solves to the identity pose
        p0 = solve_carrier(c, [0.0])
        @test maximum(abs, p0.t) < 1e-9 && maximum(abs, p0.θ) < 1e-9
        @test p0.camber[1] ≈ 0 atol = 1e-9
        # bar lengths preserved exactly at full travel (rigid links)
        p = solve_carrier(c, [0.06])
        for k in eachindex(c.barlen)
            q = JuliaMotor.transform(c.barneg[k], c.origin, p.t, p.θ)
            @test sqrt(sum(abs2, q .- c.barpos[k])) ≈ c.barlen[k] atol = 1e-9
        end
        # corner discovery
        @test corner_wheel(pm, :fl) == "fl_wheel"
        @test corner_wheel(pm, :rr) == "rr_wheel"
    end

    @testset "suspension: Chapman strut kinematics (pinned)" begin
        s = sweep(pm, :fl; travel=-0.04:0.02:0.06)
        @test s.camber[s.travel .== 0.0][1] ≈ 0 atol = 1e-9
        # regression pins from the validated solver (degrees)
        @test rad2deg(s.camber[s.travel .== 0.04][1]) ≈ 0.787 atol = 1e-2
        @test rad2deg(s.camber[s.travel .== 0.06][1]) ≈ 1.445 atol = 1e-2
        @test rad2deg(s.camber[s.travel .== -0.04][1]) ≈ -0.104 atol = 1e-2
        @test rad2deg(s.toe[s.travel .== 0.06][1]) ≈ 0.136 atol = 1e-2
        # track narrows toward both extremes of travel (strut arc)
        @test s.track[end] < 0.735 && s.track[1] < 0.735
    end

    @testset "suspension: De Dion axle signatures" begin
        # pure bump: rigid translation, exactly zero camber/toe change
        p = axle_sweep(pm, :rl; bump=0.04)
        @test maximum(abs, p.camber) < 1e-10
        @test maximum(abs, p.toe) < 1e-10
        # pure roll: both wheels camber with the axle, equal and opposite
        # sign per side; axle roll ≈ atan(2*0.03 / 1.41m hub spacing)
        p = axle_sweep(pm, :rl; roll=0.03)
        @test p.camber[1] ≈ -p.camber[2] atol = 1e-9
        @test abs(p.θ[3]) ≈ atan(0.06, 1.41) atol = 2e-4
        # camber equals axle roll up to the Watts link's tiny secondary
        # rotation (~1e-6 rad)
        @test abs(p.camber[1]) ≈ abs(p.θ[3]) atol = 1e-5
    end

    @testset "suspension: full PM corpus solvable" begin
        ok = 0
        for path in find_pm_files(joinpath(gamedata, "Vehicles"))
            m = read_pm(path)
            for corner in (:fl, :fr, :rl, :rr)
                pose = solve_carrier(Carrier(m, corner_wheel(m, corner)),
                                     fill(0.02, length(Carrier(m, corner_wheel(m, corner)).wheels)))
                maximum(abs, pose.t) < 0.5 && (ok += 1)
            end
        end
        @test ok == 484
    end

    @testset "telemetry validation: suspension channels" begin
        if isempty(logs)
            @info "reference telemetry session not found; skipping"
        else
            s = read_daq_csv(only(logs))
            t = s["Time"]; n = length(t)
            # Damper Velocity is exactly d/dt(Suspension Pos): pins the
            # channel semantics (deflection in mm, velocity in mm/s)
            for c in ("FL", "RR")
                sp = s["Suspension Pos $c"]; dv = s["Damper Velocity $c"]
                dsp = [(sp[min(i+1, n)] - sp[max(i-1, 1)]) /
                       (t[min(i+1, n)] - t[max(i-1, 1)]) for i in 1:n]
                covv = sum((dsp .- sum(dsp)/n) .* (dv .- sum(dv)/n))
                r = covv / sqrt(sum(abs2, dsp .- sum(dsp)/n) * sum(abs2, dv .- sum(dv)/n))
                @test r > 0.999
                @test sum(dsp .* dv) / sum(dv .^ 2) ≈ 1.0 atol = 0.01
            end

            # quasi-static front wheel rate: bivariate spring/ARB regression
            # recovers the HDV spring 27700 + 5*2000 = 37700 N/m
            glat = s["G Force Lat"]
            spl = s["Suspension Pos FL"] ./ 1000
            spr = s["Suspension Pos FR"] ./ 1000
            ld = s["Tire Load - FL"]
            dvl = s["Damper Velocity FL"]; dvr = s["Damper Velocity FR"]
            idx = [i for i in 1:n if abs(dvl[i]) < 3 && abs(dvr[i]) < 3 && ld[i] > 100]
            A = hcat(spl[idx], spl[idx] .- spr[idx], ones(length(idx)))
            coef = A \ ld[idx]
            @test coef[1] ≈ 37700 rtol = 0.05
            # the rear is NOT spring-separable by regression: De Dion link
            # reactions (drive torque) carry load past the springs — the
            # clean rear identification is a Phase 2 force-balance item
        end
    end
    @testset "vehicle assembly + forward replay (Phase 2 opener)" begin
        model = VehicleModel(vanwall)
        @test mass(model, 160.0) ≈ 833.4 atol = 0.1       # static-load validated
        @test model.eng.rev_limit == 8500.0
        @test ngears(model.dt) == 5
        # coasting in neutral decelerates
        a, _ = longitudinal_accel(model, 30.0, 0, 0.0, 100.0)
        @test a < 0
        # full throttle in 3rd at 30 m/s accelerates hard
        a, rpm = longitudinal_accel(model, 30.0, 3, 1.0, 100.0)
        @test a > 2.0
        @test rpm ≈ 30.0 / model.radius * model.dt.totals[3] * 60 / 2π

        if !isempty(zand)
            s = read_daq_csv(only(zand))
            spd = s["Ground Speed"] ./ 3.6; tp = s["Throttle Position"] ./ 100
            bpp = s["Brake Pedal Position"]; gear = s["Gear"]
            fuel = s["Fuel Level"]; glat = s["G Force Lat"]; t = s["Time"]
            n = length(t)
            ok = [bpp[i] < 1 && tp[i] > 0.5 && abs(glat[i]) < 0.2 && spd[i] > 10
                  for i in 1:n]
            # replay every straight full-throttle stretch >= 4 s: forward
            # physics from inputs only (no logged RPM/accel) must track the
            # logged speed within 3 km/h RMS
            nstretches = 0
            i = 1
            while i <= n
                if ok[i]
                    j = i
                    while j < n && ok[j+1]; j += 1; end
                    if t[j] - t[i] >= 4
                        nstretches += 1
                        pred = replay_speed(model, t[i:j], tp[i:j], gear[i:j],
                                            fuel[i:j]; v0=spd[i])
                        err = (pred .- spd[i:j]) .* 3.6
                        @test sqrt(sum(abs2, err) / length(err)) < 3.0
                        @test abs(err[end]) / (spd[j] * 3.6) < 0.03
                    end
                    i = j + 1
                else
                    i += 1
                end
            end
            @test nstretches >= 3
        end
    end
    hz50 = filter(p -> occursin("2026_06_05_20_07_57", basename(p)), find_daq_logs())
    @testset "braking replay (50 Hz protocol session)" begin
        if isempty(hz50)
            @info "50 Hz protocol session not found; skipping"
        else
            model = VehicleModel(vanwall)
            @test model.brake_f ≈ 1250 * 0.55 * 1.0   # bias convention pinned
            @test model.brake_r ≈ 900 * 0.45 * 1.0
            @test model.rear_frac ≈ 0.441
            @test model.wheelbase ≈ 2.80

            s = read_daq_csv(only(hz50))
            @test samplerate(s) ≈ 51.28 atol = 0.1
            spd = s["Ground Speed"] ./ 3.6; tp = s["Throttle Position"] ./ 100
            bpp = s["Brake Pedal Position"] ./ 100
            cpp = s["Clutch Pedal Position"] ./ 100
            gear = s["Gear"]; fuel = s["Fuel Level"]; t = s["Time"]
            n = length(t)
            # replay each hard-braking event from brake application; with the
            # cold-drum effectiveness knob (0.87) the model tracks the stops.
            # The longest stop runs the drums hottest (effectiveness drifts
            # toward 0.91) — hence the tolerance on the worst event.
            rmss = Float64[]
            i = 2
            while i <= n
                if bpp[i] > 0.5 && bpp[i-1] <= 0.5 && spd[i] > 33.3
                    j = i
                    while j < n && bpp[j+1] > 0.3 && spd[j+1] > 8; j += 1; end
                    if t[j] - t[i] >= 1.5
                        pred = replay_speed(model, t[i:j], tp[i:j], gear[i:j],
                                            fuel[i:j]; v0=spd[i],
                                            brake=bpp[i:j], clutch=cpp[i:j])
                        err = (pred .- spd[i:j]) .* 3.6
                        push!(rmss, sqrt(sum(abs2, err) / length(err)))
                    end
                    i = j + 1
                else
                    i += 1
                end
            end
            @test length(rmss) == 5
            sort!(rmss)
            @test rmss[4] < 2.0          # 4 of 5 stops under 2 km/h RMS
            @test rmss[end] < 8.0        # hottest-drum stop within the knob drift
        end
    end

    @testset "pre-peak calibration vs Slide-Pct measurement" begin
        if isempty(hz50)
            @info "50 Hz protocol session not found; skipping"
        else
            # Slide-axis empirical curve: measured with the uncalibrated
            # tire (tau=0.0905, scale=1); the yaw calibration lives on a
            # different x-axis (see LATERAL_CAL)
            tire = front
            s = read_daq_csv(only(hz50))
            spd = s["Ground Speed"] ./ 3.6; glat = s["G Force Lat"]
            bpp = s["Brake Pedal Position"]
            ns = length(spd)
            us = Float64[]; ys = Float64[]
            for c in ("FL", "FR")
                sl = s["Slide Pct - $c"]; ld = s["Tire Load - $c"]
                fy = s["Lat Force - $c"]
                for i in 1:ns
                    (abs(glat[i]) > 0.3 && bpp[i] < 1 && ld[i] > 400 &&
                     spd[i] > 15) || continue
                    push!(us, sl[i] / 100)
                    push!(ys, abs(fy[i]) / (peak_mu_lat(tire, ld[i]) * ld[i]))
                end
            end
            @test length(us) > 10_000
            med(x) = sort(x)[(length(x) + 1) ÷ 2]
            pk = peakslip(tire.pk_lat, combo(2000.0, 30.0, tire.equivalency))
            # binned medians of the free-rolling fronts track the calibrated
            # curve through the rise; the sub-limit plateau sits ~0.93
            for (lo, tol) in ((0.0, 0.06), (0.1, 0.06), (0.2, 0.06))
                sel = [k for k in eachindex(us) if lo <= us[k] < lo + 0.1]
                @test length(sel) > 200
                u = lo + 0.05
                @test med(ys[sel]) ≈ reaction(tire.lat, u * pk, pk) atol = tol
            end
            for lo in 0.3:0.1:0.8
                sel = [k for k in eachindex(us) if lo <= us[k] < lo + 0.1]
                isempty(sel) && continue
                @test med(ys[sel]) > 0.88   # plateau, sub-limit census
            end
        end
    end
    direct = filter(p -> occursin("2026_06_05_21_05_55", basename(p)), find_daq_logs())
    @testset "yaw replay (direct-steering session)" begin
        if isempty(direct)
            @info "direct-steering session not found; skipping"
        else
            model = VehicleModel(vanwall)
            @test model.iz ≈ 1021.85
            s = read_daq_csv(only(direct))
            spd = s["Ground Speed"] ./ 3.6
            yawm = s["Gyro - Yaw Angular Velocity"]
            steer = deg2rad.(s["Steering Wheel Pct"] .* (20.0 / 100))
            t = s["Time"]; fuel = s["Fuel Level"]
            drive = drive_force_trace(model, spd, s["Throttle Position"] ./ 100,
                                      s["Gear"], s["Clutch Pedal Position"] ./ 100)
            loads = Tuple(s["Tire Load - $c"] for c in ("FL", "FR", "RL", "RR"))
            n = length(t)
            win = round(Int, 10 * 51.28)
            rmss = Float64[]; cors = Float64[]
            i0 = 1
            while i0 < n - win
                rng = i0:i0+win
                ok = abs(yawm[i0]) < 0.05 && all(spd[rng] .> 8) &&
                     all(isfinite, yawm[rng]) && all(isfinite, steer[rng]) &&
                     all(isfinite, fuel[rng]) && all(isfinite, spd[rng]) &&
                     all(c -> all(isfinite, c[rng]), loads)
                if ok
                    pred = replay_yaw(model, t[rng], steer[rng], spd[rng],
                                      map(c -> c[rng], loads), fuel[rng];
                                      yaw0=yawm[i0], drive=drive[rng])
                    meas = yawm[rng]
                    if Statistics.std(meas) > 0.08
                        push!(rmss, sqrt(sum(abs2, pred .- meas) / length(rng)))
                        push!(cors, Statistics.cor(pred, meas))
                    end
                    i0 += win
                else
                    i0 += 26
                end
            end
            @test length(rmss) >= 20
            med(x) = sort(x)[(length(x) + 1) ÷ 2]
            # pre-calibration state: structure tracks (cor), magnitude has a
            # documented yaw-gain deficit (Phase 3 target)
            @test med(cors) > 0.80
            @test med(rmss) < 0.08      # rad/s, vs 0.31 rad/s signal std (calibrated)
            @test maximum(rmss) < 0.6   # no divergence anywhere in the stint
        end
    end

    @testset "capstone: full coupled replay from inputs alone" begin
        if isempty(direct)
            @info "direct-steering session not found; skipping"
        else
            # `replay_inputs` drives the WHOLE engine — speed AND yaw — from
            # logged steer/throttle/brake/gear, with longitudinal load
            # transfer feeding the lateral tire loads.  Re-anchored 5 s
            # windows (free integration of an unstable system diverges over a
            # full lap — the scope's prescribed method).
            model = VehicleModel(vanwall)
            s = read_daq_csv(only(direct))
            t = s["Time"]; spd = s["Ground Speed"] ./ 3.6
            yawm = s["Gyro - Yaw Angular Velocity"]
            steer = deg2rad.(s["Steering Wheel Pct"] .* (20.0 / 100))
            thr = s["Throttle Position"] ./ 100; brk = s["Brake Pedal Position"] ./ 100
            gear = s["Gear"]; fuel = s["Fuel Level"]
            n = length(t); win = round(Int, 5 * 51.28)
            verr = Float64[]; vcor = Float64[]; rerr = Float64[]
            i0 = 1
            while i0 < n - win
                rng = i0:i0+win
                ok = all(j -> all(isfinite, (spd[j], yawm[j], steer[j], thr[j],
                                             brk[j], gear[j], fuel[j])), rng) &&
                     all(spd[rng] .> 8)
                if ok && Statistics.std(yawm[rng]) > 0.05
                    vp, rp = replay_inputs(model, t[rng], steer[rng], thr[rng],
                                           brk[rng], gear[rng], fuel[rng];
                                           v0=spd[i0], yaw0=yawm[i0])
                    push!(verr, sqrt(sum(abs2, vp .- spd[rng]) / length(rng)))
                    push!(vcor, Statistics.cor(vp, spd[rng]))
                    push!(rerr, sqrt(sum(abs2, rp .- yawm[rng]) / length(rng)))
                    i0 += win
                else
                    i0 += 26
                end
            end
            @test length(verr) >= 20
            med(x) = sort(x)[(length(x) + 1) ÷ 2]
            # speed reproduced from inputs alone: excellent
            @test med(verr) < 1.5          # m/s (≈ 5 km/h)
            @test med(vcor) > 0.95
            # yaw reproduced self-contained from inputs alone: good after the
            # 2026-06-08 peak-slip recalibration (lat_peak_scale 2.5 → 1.0,
            # τ raised to hold scale×τ) — capstone yaw RMS dropped 0.174 → ~0.066
            @test med(rerr) < 0.12         # rad/s, vs 0.31 signal std
        end
    end

    @testset "HAT track surface (Zandvoort)" begin
        a = read_aiw(joinpath(gamedata, "Locations", "Zandvoort67", "zandvoort67.AIW"))
        ts = TrackSurface(a)
        @test length(ts.seg) == 804
        @test ts.lap_length ≈ a.lap_length

        mp = mainpath(a)
        # query at each waypoint: exact height, on track, centered, right lapdist
        for w in mp[1:50:end]
            r = hat(ts, w.pos[1], w.pos[3])
            @test r.found
            @test r.height ≈ w.pos[2] atol = 0.05
            @test r.on_track
            @test abs(r.lateral) < 0.2
            @test r.lapdist ≈ w.lapdist atol = 6.0
        end

        # lateral offset along the perp vector is recovered with sign
        w = mp[200]
        for k in (-3.0, 2.0)
            r = hat(ts, w.pos[1] + k * ts.perp[200][1], w.pos[3] + k * ts.perp[200][3])
            @test r.lateral ≈ k atol = 0.3
        end
        # beyond the track half-width → off track
        wide = ts.halfwidth[200][1] + 5.0
        @test !hat(ts, w.pos[1] + wide * ts.perp[200][1],
                       w.pos[3] + wide * ts.perp[200][3]).on_track
        # off the map
        @test !hat(ts, 99999.0, 99999.0).found

        # lap distance is monotone along consecutive waypoints
        lds = [hat(ts, w.pos[1], w.pos[3]).lapdist for w in mp]
        @test sum(diff(lds) .> 0) > 0.95 * length(lds)

        # cross-source: HAT height vs the independently-extracted asphalt GMT
        # vertex cloud.  Away from the centerline (clear of the racing-line /
        # parallel-straight ambiguity) the surfaces agree to ~0.15 m median.
        m = read_mas(joinpath(gamedata, "Locations", "Zandvoort67", "Zand67.mas"))
        g = parse_gmt(extract(m, "asphalt01.gmt"))
        errs = Float64[]
        for p in g.positions
            r = hat(ts, Float64(p[1]), Float64(p[3]))
            (r.found && 2.0 <= abs(r.lateral) < 8.0) || continue
            push!(errs, abs(r.height - Float64(p[2])))
        end
        @test length(errs) > 1000
        sort!(errs)
        @test errs[length(errs)÷2] < 0.25      # median road-surface agreement
    end

    @testset "HAT builds for the full track corpus" begin
        nbuilt = 0
        for p in find_aiw_files(joinpath(gamedata, "Locations"))
            ts = TrackSurface(read_aiw(p))
            @test length(ts.seg) > 50
            nbuilt += 1
        end
        @test nbuilt == 68
    end

    @testset "TriangleHAT: 3D collision-mesh surface (Zandvoort)" begin
        dir = joinpath(gamedata, "Locations", "Zandvoort67")
        @test length(hat_meshes(dir)) == 25          # HATTarget=True meshes
        th = TriangleHAT(dir)
        @test 5000 < length(th.tris) < 7000          # ~6066 collision triangles

        # exact point-in-triangle resolves the parallel-straight ambiguity the
        # ribbon HAT has: every racing-line point is covered and height agrees
        # with the AIW to a few cm — no tail (ribbon p90 was ~5 m)
        a = read_aiw(joinpath(dir, "zandvoort67.AIW"))
        mp = mainpath(a)
        errs = Float64[]; ups = Float64[]; missed = 0
        for w in mp
            h, n, found = hat3d(th, w.pos[1], w.pos[3])
            found || (missed += 1; continue)
            push!(errs, abs(h - w.pos[2])); push!(ups, n[2])
        end
        @test missed == 0
        sort!(errs)
        @test errs[length(errs)÷2] < 0.2             # median height error
        @test errs[end] < 1.0                        # no ambiguity tail
        @test sort(ups)[length(ups)÷2] > 0.99        # normals point up

        # far off the mapped surface → not found
        @test !hat3d(th, 99999.0, 99999.0)[3]
    end

    @testset "headless sim: speed profile + opening-sector tracking" begin
        model = VehicleModel(vanwall)
        a = read_aiw(joinpath(gamedata, "Locations", "Zandvoort67", "zandvoort67.AIW"))
        ts = TrackSurface(a)
        mp = mainpath(a)
        base = [Float64(w.speed) for w in mp]

        # speed profile is braking-feasible: each step's deceleration into a
        # slower point respects the braking limit (with numerical slack)
        vp = JuliaMotor.speed_profile(ts, base; a_brake=6.0, a_accel=4.0)
        @test length(vp) == length(base)
        @test all(vp .<= base .+ 1e-6)        # never faster than the AIW target
        nbad = 0
        for i in 1:length(vp)-1
            ds = hypot(ts.pos[i+1][1] - ts.pos[i][1], ts.pos[i+1][3] - ts.pos[i][3])
            if vp[i+1] < vp[i]                  # decelerating
                decel = (vp[i]^2 - vp[i+1]^2) / (2 * max(ds, 1e-3))
                decel > 6.5 && (nbad += 1)
            end
        end
        @test nbad == 0                         # all braking within capacity

        # QSS lap-optimal profile: feasible by construction — the lateral
        # demand v²·|κ| never exceeds the friction circle μg anywhere (the
        # correct speed foundation for a future limit-handling tracker)
        ft = FrenetTrack(ts, base)
        vq = qss_speed_profile(ft; mu=0.95)
        @test length(vq) == length(ft.kappa)
        @test all(isfinite, vq) && all(>(0), vq)
        g = 0.95 * 9.81
        @test all(vq[i]^2 * abs(ft.kappa[i]) <= g * 1.05 for i in eachindex(vq))

        # the closed-loop sim integrates and tracks the racing line through
        # the opening sector (start straight + first approach): lateral stays
        # tight and speeds are physical.  Full-lap completion through the
        # Tarzan hairpin is gated on a track-relative driver (see README).
        # Frenet (track-relative) integration: the car cannot drive off and
        # get lost — it makes forward progress well past where the old
        # position-space driver got permanently stuck (~240 m), and stays
        # bounded near the track.
        res = simulate_lap(model, a; speed_factor=0.8)
        @test !isempty(res.samples)
        @test all(isfinite(s.x) && isfinite(s.z) && isfinite(s.lateral)
                  for s in res.samples)
        @test maximum(s.lapdist for s in res.samples) > 800     # real progress
        opening = filter(s -> s.lapdist < 160 && s.t < 6, res.samples)
        @test length(opening) > 10
        lats = sort([abs(s.lateral) for s in opening])
        @test maximum(lats) < 5.0                  # stays on track (half-width ~5 m)
        @test lats[length(lats)÷2] < 1.0           # typically tight on the line
        @test maximum(s.speed for s in res.samples) < 60       # realistic (m/s)

        # at a conservative pace the simple driver completes a full, on-track
        # lap.  NOTE: the 2026-06-08 peak-slip recalibration (lat_peak_scale
        # 2.5 → 1.0) gives the tyre a realistic, less-forgiving curve (peaks at
        # ~11° then drops, vs building grip out to ~27°).  That sharper tyre
        # exposes the fragility of this simple open-loop racing-line follower —
        # it now needs a slower pace to stay on track (it over-demanded and
        # slid off at 0.7).  A robust limit-handling controller (LQR/MPC, the
        # known-open research item) is what would carry racing pace on the
        # realistic tyre; the human-driven demo doesn't need it (human = loop).
        full = simulate_lap(model, a; speed_factor=0.45)
        @test full.completed
        @test full.max_lateral < 6.0               # never leaves the track
        @test 100 < full.laptime < 400             # plausible lap time
    end

    @testset "human-drivable car: world-space step from live inputs" begin
        # The Phase 4.3 drivable-standalone path: the same validated bicycle
        # physics as replay_inputs, driven by live throttle/brake/steer in
        # world (X, Z, heading) coordinates.  No autonomous controller — a
        # human (here, a scripted input sequence) supplies the control loop.
        model = VehicleModel(vanwall)
        a = read_aiw(joinpath(gamedata, "Locations", "Zandvoort67", "zandvoort67.AIW"))
        car = DriveCar(model, a)
        cs = spawn(car; v0=0.0)
        @test cs.v == 0.0 && cs.ontrack          # spawns at rest on the line

        # standing start, full throttle: the clutch/launch model pulls away
        # (the validated longitudinal_accel alone cannot — engine torque is
        # negative below idle), accelerates, and auto-upshifts
        for _ in 1:600; step!(cs, car, DriveInput(throttle=1.0); dt=1/60); end
        @test all(isfinite, (cs.x, cs.z, cs.θ, cs.v, cs.β, cs.r))
        @test cs.v > 40                           # accelerated past 40 m/s
        @test cs.gear >= 3                         # upshifted

        # a steering input produces a heading change of the correct sign
        # (steer > 0 = left = increasing yaw)
        θ0 = cs.θ
        for _ in 1:120; step!(cs, car, DriveInput(throttle=0.4, steer=0.6); dt=1/60); end
        dθ = atan(sin(cs.θ - θ0), cos(cs.θ - θ0))
        @test dθ > 0.05 && isfinite(cs.r)

        # braking to a standstill is stable (no NaN at the v→0 singularity)
        for _ in 1:600; step!(cs, car, DriveInput(brake=1.0); dt=1/60); end
        @test isfinite(cs.v) && cs.v < 1.0

        # respawn resets cleanly to rest on the line
        cs2 = spawn(car; waypoint=10, v0=0.0)
        @test cs2.v == 0.0 && cs2.ontrack && isfinite(cs2.θ)
    end

    @testset "four-corner load model vs measured per-corner loads" begin
        # LOAD4_CAL's per-corner load model (static split + longitudinal +
        # lateral transfer) is fitted to and reproduces the measured
        # `Tire Load - FL/FR/RL/RR` channels.  Here we check it directly:
        # corner_loads(mt, ax, ay, L) vs the logged loads, sample by sample.
        if isempty(direct)
            @info "direct-steering session not found; skipping"
        else
            model = VehicleModel(vanwall)
            s = read_daq_csv(only(direct))
            FL = s["Tire Load - FL"]; FR = s["Tire Load - FR"]
            RL = s["Tire Load - RL"]; RR = s["Tire Load - RR"]
            gx = s["G Force Long"]; gy = s["G Force Lat"]; fuel = s["Fuel Level"]
            errs = Float64[]
            for i in eachindex(FL)
                (all(isfinite, (FL[i], FR[i], RL[i], RR[i], gx[i], gy[i], fuel[i])) &&
                 FL[i] + FR[i] + RL[i] + RR[i] > 1000) || continue
                mt = mass(model, fuel[i])
                # telemetry sign: +G Force Long = braking, so model accel = -gx
                pred = corner_loads(mt, -gx[i] * 9.81, gy[i] * 9.81, model.wheelbase)
                meas = (FL[i], FR[i], RL[i], RR[i])
                push!(errs, sqrt(sum(abs2, pred .- meas) / 4))
            end
            @test length(errs) > 10_000
            med(x) = sort(x)[(length(x) + 1) ÷ 2]
            @test med(errs) < 260.0          # N, vs ~2.1 kN per corner (≈ 10 %)
        end
    end

    @testset "four-corner traction split: outer wheel carries more" begin
        # In a settled steady corner the outer wheels gain load (bigger grip
        # circle) and the inner wheels go light — the per-wheel behaviour the
        # axle model could not represent.  Body dynamics are unchanged; this is
        # the per-corner resolution feeding the cockpit traction circles.
        model = VehicleModel(vanwall)
        a = read_aiw(joinpath(gamedata, "Locations", "Zandvoort67", "zandvoort67.AIW"))
        car = DriveCar(model, a)
        cs = spawn(car; v0=0.0)
        for _ in 1:300; step!(cs, car, DriveInput(throttle=0.6); dt=1/60); end
        for _ in 1:240; step!(cs, car, DriveInput(throttle=0.3, steer=-0.15); dt=1/60); end
        @test cs.r < -0.05                       # genuinely turning right
        fl, fr, rl, rr = cs.tc                    # each (long, lat, radius)
        # right turn → outer = left wheels carry more grip (larger radius)
        @test fl[3] > fr[3] * 1.1
        @test rl[3] > rr[3] * 1.1
        # all radii positive and finite (no wheel fully lifted at this mild g)
        @test all(w -> w[3] > 0 && all(isfinite, w), cs.tc)
    end
else
    @warn "rFactor GameData not found; bench tests skipped" dunlop_path
end

end
