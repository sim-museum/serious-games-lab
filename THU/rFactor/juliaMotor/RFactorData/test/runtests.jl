using RFactorData
using Test

@testset "RFactorData" begin

@testset "value grammar" begin
    f = parse_hdv("""
        [GENERAL]
        Mass=765
        CGHeight=0.27                  // height of body mass
        Inertia=(894.5862389, 902.6038691, 132.154451)
        BodyDragBase=(0.349)           // 1-element tuple collapses to scalar
        Notes=""
        Name="BRM P25"
        DamageFile=1958_damage.ini     // bare filename
        PackerRange=(0,,0)             // empty tuple slot
        BrakeDuctCooling=1,5           // bare unparenthesized list
        Negative=-1.5e-3
        """)
    g = f["GENERAL"]
    @test g["Mass"] === 765
    @test g["CGHeight"] === 0.27
    @test g["Inertia"] == [894.5862389, 902.6038691, 132.154451]
    @test g["BodyDragBase"] === 0.349
    @test g["Notes"] == ""
    @test g["Name"] == "BRM P25"
    @test g["DamageFile"] == "1958_damage.ini"
    @test isequal(g["PackerRange"], [0, missing, 0])
    @test g["BrakeDuctCooling"] == [1, 5]
    @test g["Negative"] === -0.0015
    @test entry(g, "CGHeight").comment == "height of body mass"
    @test rawvalue(g, "Inertia") == "(894.5862389, 902.6038691, 132.154451)"
    @test isempty(f.issues)
end

@testset "corpus oddities are repaired, not dropped" begin
    # jammed pair (Mustang69/302Mcoupe.hdv:21)
    f = parse_hdv("[GENERAL]\r\nCGRearSetting=0WedgeRange=(0,0,0)\r\n")
    g = f["GENERAL"]
    @test g["CGRearSetting"] === 0
    @test g["WedgeRange"] == [0, 0, 0]
    @test length(f.issues) == 1

    # duplicated key (BRM P25.hdv FuelTankMotion)
    f = parse_hdv("[GENERAL]\nFuelTankMotion=FuelTankMotion=(560.0,0.8)\n")
    @test f["GENERAL"]["FuelTankMotion"] == [560.0, 0.8]
    @test length(entries(f["GENERAL"], "FuelTankMotion")) == 1

    # missing '=' (Simca_Rallye2.hdv:274) is skipped but reported
    f = parse_hdv("[DRIVELINE]\nAllowGearingChanges0\n")
    @test isempty(f["DRIVELINE"].entries)
    @test occursin("no '='", only(f.issues))

    # repeated sections and last-wins repeated keys
    f = parse_hdv("[AIDPENALTIES]\nA=1\n[AIDPENALTIES]\nA=2\nA=3\n")
    reps = sections(f, "AIDPENALTIES")
    @test length(reps) == 2
    @test reps[1]["A"] === 1
    @test reps[2]["A"] === 3
    @test length(entries(reps[2], "A")) == 2

    # section header with trailing comment; case-insensitive lookup
    f = parse_hdv("[REARWING]                      // spoiler\nRWSetting=1\n")
    @test section(f, "rearwing")["rwsetting"] === 1
    @test f["REARWING"].comment == "spoiler"

    # no trailing newline on last line
    f = parse_hdv("[ENGINE]\nRestrictorPlate=0.000011")
    @test f["ENGINE"]["RestrictorPlate"] === 1.1e-5
end

@testset "TBC grammar" begin
    f = parse_tbc("""
        [SLIPCURVE]
        Name="Lateral"
        Step=0.00250
        DropoffFunction=0.0
        Data:
        0.0 0.5 1.0
        0.9 0.8
        [COMPOUND]Name="Glued Header"      // corpus: F60R15 RWL GY Polyglas
        DryLatLong=(2.05, 2.10)
        FRONT:
        Temperatures=(90.0, 10.0)
        Rear:
        Temperatures=(95.0, 10.0)
        [COMPOUND]
        Name="Per-corner"
        WearGrip1=(0.99)
        FRONTRIGHT:
        Temperatures=(80.0, 10.0)
        """)
    c = slipcurve(f, "lateral")
    @test c.data == [0.0, 0.5, 1.0, 0.9, 0.8]   # rows accumulate
    @test c.step == 0.0025
    @test collect(slips(c)) == [0.0, 0.0025, 0.005, 0.0075, 0.01]

    g = compound(f, "Glued Header")
    @test g === compound(f, 0)                  # 0-based HDV compound index
    @test g["DryLatLong", :front] == [2.05, 2.10]   # common fallback
    @test g["Temperatures", :front] == [90.0, 10.0]
    @test g["Temperatures", :rear] == [95.0, 10.0]  # `Rear:` case variant
    @test g["Temperatures", :rearright] == [95.0, 10.0]  # corner -> axle

    pc = compound(f, "Per-corner")
    @test pc["Temperatures", :frontright] == [80.0, 10.0]
    @test pc["WearGrip1", :frontright] === 0.99
    @test get(pc, ("Temperatures", :frontleft), nothing) === nothing
    @test isempty(issues(f))
end

@testset "PM grammar" begin
    f = parse_pm("""
        [BODY]
        name=body mass=(825) inertia=(0.0, 0.0, 0.0)
        pos=(0.0,0.0,0.0) ori=(0.0,0.0,0.0)
        [BODY]
        name=fl_wheel mass=(12.5) inertia=(1.25,0.7,0.7)
        pos=(0.735,0,-1.40) ori=(0.0,0.0,0.0)
        [JOINT&HINGE]
        posbody=fl_wheel negbody=body pos=fl_wheel axis=(-1.00,0.0,0.0)
        [BAR]
        name=fl_fore_upper posbody=body negbody=fl_wheel pos=(0.45, 0.06, -1.3) neg=(0.68, 0.07, -1.4)
        ____________________________________________________________
        """)
    @test length(f.bodies) == 2
    b = body(f, "FL_WHEEL")
    @test b.mass == 12.5 && b.inertia == [1.25, 0.7, 0.7]
    j = only(f.joints)
    @test j.kind === :joint_hinge
    @test j.pos == "fl_wheel"                  # body-name reference
    @test resolve(f, j.pos) == [0.735, 0, -1.4]
    @test j.axis == [-1.0, 0.0, 0.0]
    bar = only(f.bars)
    @test bar.name == "fl_fore_upper" && bar.neg == [0.68, 0.07, -1.4]
    # multi-pair lines are normal PM syntax, only the divider is an issue
    @test length(issues(f)) == 1 && occursin("no '='", issues(f)[1])
end

@testset "engine and gears" begin
    e = parse_engine("""
        // Engine data generated by PhysicsEditor
        RPMTorque=( 0.0, -12.5, -20.0)
        RPMTorque=( 250.0, -14.3, -11.0)
        RPMTorque=( 500.0, -16.8, 0.0)
        Fuel=(2.39e-5)
        [SOMETHING]
        OptimumOilTemp=99.0
        """)
    @test e.rpm == [0.0, 250.0, 500.0]
    @test e.coast == [-12.5, -14.3, -16.8]
    @test e.torque == [-20.0, -11.0, 0.0]
    @test param(e, "Fuel") == 2.39e-5            # preamble param
    @test param(e, "OptimumOilTemp") == 99.0     # sectioned param
    @test param(e, "Missing", 42) == 42

    g = parse_isi("[GEAR_RATIOS]\nratio=(8, 31)\nratio=(10, 37)\n")
    @test RFactorData.gear_ratios(g) == [31/8, 37/10]

    f = parse_isi("[FINAL_DRIVE]\nbevel=(2, 3)\nratio=(5, 31)\nratio=(6, 34)\n")
    @test final_drive_ratios(f) ≈ [31/5 * 3/2, 34/6 * 3/2]
end

@testset "GEN grammar" begin
    f = parse_gen("""
        SearchPath=<VEHDIR>
        MASFile=BRM\\BRM P25.mas
        Instance=SLOT<ID>
        {
          Moveable=True
          MeshFile=BRM_body.gmt CollTarget=False LODIn=(0.0) LODOut=(4.0)
          Instance=COCKPIT
        {
          MeshFile=BRM_cockpit.gmt CollTarget=False
        }
        }
        """)
    @test length(gen_statements(f, "Instance")) == 2
    meshes = gen_statements(f, "MeshFile")
    @test length(meshes) == 2
    @test RFactorData.value(meshes[1]) == "BRM_body.gmt"
    @test ("CollTarget", "False") in
          [(k, v) for (k, v) in meshes[1].pairs]
    # nested-then-double-closed: the forced close absorbs the stray '}'
    @test isempty(f.issues)

    # upgrade-conditional directives, standalone and brace-prefixed
    f = parse_gen("""
        <STARTUPGRADES>
        Instance=RWING
        {
          MeshFile=wing_long.gmt CollTarget=False
        <CORTAS>  {
          MeshFile=wing_short.gmt CollTarget=False
        <CORTAS>  }
        }
        """)
    @test isempty(f.issues)
    meshes = gen_statements(f, "MeshFile")
    @test length(meshes) == 2
    @test RFactorData.key(f.statements[1]) == "directive"
    @test RFactorData.value(f.statements[1]) == "STARTUPGRADES"
end

gamedata = default_gamedata()
if isdir(gamedata)
    @testset "BRM P25 reference car" begin
        hdv = read_hdv(joinpath(gamedata, "Vehicles", "F158", "BRM", "BRM P25.hdv"))
        g = hdv["GENERAL"]
        @test g["Mass"] === 765
        @test g["Inertia"] == [894.5862389, 902.6038691, 132.154451]
        @test g["CGHeight"] === 0.27
        @test g["FuelSetting"] === 173
        @test g["TireBrand"] == "DunlopR4-16inches.tbc"
        @test g["FuelTankMotion"] == [560.0, 0.8]   # duplicated-key line repaired
        @test all(haskey(g, "Undertray0$i") for i in 0:8)
        @test g["Undertray00"] == [0.30913, 0.03675, -1.22662]
        @test hdv["BODYAERO"]["BodyDragBase"] === 0.349
        @test hdv["SUSPENSION"]["PhysicalModelFile"] ==
              "1958FrontChapman-RearLeafAndDeDion.pm"
        @test section(hdv, "FRONTLEFT") !== nothing
    end

    @testset "full corpus: every HDV isiMotor loads, we load" begin
        files = find_hdv_files(gamedata)
        @test length(files) >= 200
        nentries = 0
        issuefiles = String[]
        for path in files
            f = read_hdv(path)
            @test f isa ISIFile
            # every HDV in this install carries the full required inventory
            @test all(section(f, s) !== nothing
                      for s in RFactorData.HDV_REQUIRED_SECTIONS)
            # GENERAL essentials parse to numbers everywhere
            g = f["GENERAL"]
            @test g["Mass"] isa Number
            # >= 3: F1LR_Grabham_BT24_hdc.hdv has `(780.51, 1075.13, 295,33)`
            # (decimal-comma typo); isiMotor reads the first three values.
            @test g["Inertia"] isa Vector && length(g["Inertia"]) >= 3
            @test all(x -> x isa Number, g["Inertia"][1:3])
            nentries += sum(s -> length(s.entries), f.sections)
            isempty(f.issues) || push!(issuefiles, basename(path) *
                ": " * join(f.issues, "; "))
        end
        @info "corpus" files=length(files) entries=nentries issues=length(issuefiles)
        # exactly the known corpus defects, nothing new slips through silently
        @test length(issuefiles) == 4
        for line in issuefiles
            println("  issue: ", line)
        end
    end
    vroot = joinpath(gamedata, "Vehicles")

    @testset "TBC corpus" begin
        files = find_tbc_files(vroot)
        @test length(files) == 193
        ncurves = ncompounds = 0
        for path in files
            t = read_tbc(path)
            @test isempty(issues(t))
            for c in t.slipcurves
                @test !isempty(c.data) && c.step > 0
                @test !isempty(c.name)
            end
            ncurves += length(t.slipcurves)
            ncompounds += length(t.compounds)
        end
        @test ncurves == 901
        @test ncompounds == 255
    end

    @testset "TBC reference: DunlopR4 (BRM P25 tires)" begin
        t = read_tbc(joinpath(vroot, "F158", "DunlopR4-16inches.tbc"))
        lat = slipcurve(t, "Lateral")
        @test lat.step == 0.0025
        @test lat.dropoff == 0.0
        @test lat.data[1] == 0.0
        @test maximum(lat.data) == 1.0          # normalized peak
        @test slipcurve(t, "Braking").step == 0.005
        @test !isempty(t.compounds)
    end

    @testset "PM corpus" begin
        files = find_pm_files(vroot)
        @test length(files) == 121
        nb = nj = nbar = 0
        for path in files
            m = read_pm(path)
            @test !isempty(m.bodies)
            # every joint/bar references defined bodies
            for j in m.joints
                @test body(m, j.posbody) !== nothing && body(m, j.negbody) !== nothing
            end
            for b in m.bars
                @test body(m, b.posbody) !== nothing && body(m, b.negbody) !== nothing
            end
            nb += length(m.bodies); nj += length(m.joints); nbar += length(m.bars)
        end
        @test (nb, nj, nbar) == (1299, 485, 2225)
    end

    @testset "PM reference: De Dion (BRM P25 suspension)" begin
        m = read_pm(joinpath(vroot, "F158", "1958FrontChapman-RearLeafAndDeDion.pm"))
        @test body(m, "body").mass == 825.0
        w = body(m, "fl_wheel")
        @test w.mass == 12.5 && w.pos == [0.735, 0, -1.40]
        @test any(j -> j.posbody == "fl_wheel" && j.negbody == "fl_spindle",
                  m.joints)
        @test any(b -> b.name == "fl_fore_upper", m.bars)
    end

    @testset "vehicle wiring: all 1172 VEH resolve end to end" begin
        vehs = find_veh_files(vroot)
        @test length(vehs) == 1172
        for path in vehs
            v = load_vehicle(path; vehicles_root=vroot)
            @test isempty(v.unresolved)
            @test !isempty(v.engine.rpm)        # every engine has a torque curve
            @test issorted(v.engine.rpm)
        end
    end

    @testset "vehicle reference: BRM P25 (Schell)" begin
        v = load_vehicle(joinpath(vroot, "F158", "BRM", "Teams", "Schell", "Schell.veh");
                         vehicles_root=vroot)
        @test isempty(v.unresolved)
        @test v.hdv["GENERAL"]["Mass"] === 765
        @test basename(v.tbc.path) == "DunlopR4-16inches.tbc"
        @test basename(v.pm.path) == "1958FrontChapman-RearLeafAndDeDion.pm"
        @test lowercase(basename(v.engine.path)) == "brm p25 l4 (1958).ini"  # .INI on disk
        @test v.engine.rpm[end] >= 8000          # it's a 1958 F1 engine
        @test maximum(v.engine.torque) > 150
        @test !isempty(RFactorData.gear_ratios(v.gears))
    end

    @testset "GEN corpus" begin
        files = find_gen_files(vroot)
        @test length(files) == 357
        nmesh = 0
        nissue = 0
        for path in files
            g = read_gen(path)
            nmesh += length(gen_statements(g, "MeshFile"))
            nissue += length(g.issues)
        end
        # 17414 == case-insensitive grep of MeshFile= lines over the corpus
        @test nmesh == 17414
        # 250 jammed pairs, 24 ambiguous glues, 14 junk lines, 2 stray braces
        @test nissue == 290
    end

    @testset "AIW track corpus" begin
        files = find_aiw_files(joinpath(gamedata, "Locations"))
        @test length(files) == 68
        for p in files
            t = read_aiw(p)
            @test t.lap_length > 100
            @test length(mainpath(t)) > 50
        end
    end

    @testset "AIW reference: Zandvoort 67" begin
        a = read_aiw(joinpath(gamedata, "Locations", "Zandvoort67", "zandvoort67.AIW"))
        @test length(a.waypoints) == 1004
        @test a.lap_length ≈ 4176.754883
        @test a.sector_lengths[1] ≈ 1452.181152
        @test length(a.grid) == 36
        mp = mainpath(a)
        @test length(mp) == 804
        @test issorted([w.lapdist for w in mp])
        @test mp[end].lapdist < a.lap_length
        # AI speeds span slow corners to the main straight
        @test minimum(w.speed for w in mp) > 20
        @test maximum(w.speed for w in mp) < 80
        # waypoint spacing is a few meters along the lap
        @test 3 < a.lap_length / length(mp) < 8
        # geometric lap closure: consecutive positions are close
        gaps = [sqrt(sum(abs2, mp[i+1].pos .- mp[i].pos)) for i in 1:length(mp)-1]
        @test maximum(gaps) < 30

        g = read_gdb(joinpath(gamedata, "Locations", "Zandvoort67", "zandvoort67.gdb"))
        vals = Dict(k => v for st in gen_statements(g, "TrackName") for (k, v) in st.pairs)
        @test vals["TrackName"] == "Zandvoort"
    end

    @testset "MAS archives" begin
        m = read_mas(joinpath(gamedata, "Vehicles", "F158", "BRM", "BRM P25.mas"))
        @test length(m.entries) == 105
        d = extract(m, "50HELMET.DDS")
        @test length(d) == 2796368
        @test String(d[1:4]) == "DDS "
        g = extract(m, "brm_body.gmt")           # case-insensitive lookup
        @test bytes2hex(g[1:4]) == "f2225500"    # gMotor2 mesh magic
        @test_throws KeyError extract(m, "nope.gmt")

        # every archive in the install: TOC parses, first member extracts
        # (covers both zlib and stored members)
        files = find_mas_files(gamedata)
        @test length(files) == 274
        for p in files
            mm = read_mas(p)
            isempty(mm.entries) && continue
            e = mm.entries[1]
            @test length(extract(mm, e)) == e.usize
        end
    end

    @testset "GMT mesh geometry" begin
        zmas = read_mas(joinpath(gamedata, "Locations", "Zandvoort67", "Zand67.mas"))
        g = read_gmt_from_mas(zmas, "GROUNDPLANE.GMT")
        # validated decode: a flat ground quad
        @test length(g.positions) == 6
        @test g.triangles == [(0, 1, 2), (3, 4, 5)]
        @test all(n[2] > 0.9 for n in g.normals)        # all normals point up
        @test all(abs(p[2] - g.positions[1][2]) < 0.1 for p in g.positions)  # flat in y
        @test g.name == "groundplane"
        # decoded positions lie within the in-file bounding box (axis order
        # in the bbox block differs from the vertices — permutation-tolerant)
        for p in g.positions
            @test RFactorData.inbox_perm(p, g.bbox_min, g.bbox_max)
        end

        # road meshes: sequential triangle-soup extraction with valid indices
        # and triangles spanning the mesh (not degenerate)
        for (nm, ntri) in (("asphalt01.gmt", 675), ("grass01.gmt", 3380),
                           ("sand02.gmt", 511), ("curb01.gmt", 482))
            r = read_gmt_from_mas(zmas, nm)
            @test length(r.triangles) == ntri
            @test length(r.positions) == 3 * ntri          # sequential soup
            @test all(0 <= t[j] < length(r.positions) for t in r.triangles for j in 1:3)
        end

        # whole-track corpus: every GMT decodes with valid indices, and the
        # drivable/scenery meshes carry real geometry
        ngmt = 0; ntri = 0; valid = 0
        for e in zmas.entries
            endswith(lowercase(e.name), ".gmt") || continue
            mesh = parse_gmt(extract(zmas, e))
            ngmt += 1
            all(0 <= t[j] < length(mesh.positions) for t in mesh.triangles for j in 1:3) &&
                (valid += 1)
            ntri += length(mesh.triangles)
        end
        @test ngmt == 260
        @test valid == 260          # every mesh's indices are in range
        @test ntri > 10_000         # full track triangle geometry recovered
    end

    @testset "SVM corpus (garage setups)" begin
        userdata = normpath(joinpath(gamedata, "..", "UserData"))
        files = RFactorData.find_ext(userdata, ".svm")
        @test length(files) >= 100
        for path in files
            f = read_svm(path)
            @test f isa ISIFile
            @test isempty(f.issues)
        end
    end
else
    @warn "rFactor GameData not found; corpus tests skipped" gamedata
end

end
