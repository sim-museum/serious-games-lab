using RFactorTelemetry
using Test

# Synthetic fixtures covering the header shapes the sniffer must accept.
# When the first real DAQ lap is recorded (drive with CTRL-m logging on),
# add a regression test against it here.

function fixture(dir, name, content)
    path = joinpath(dir, name)
    write(path, content)
    path
end

@testset "RFactorTelemetry" begin

mktempdir() do dir

@testset "quoted header with units row" begin
    p = fixture(dir, "quoted.csv", """
        "Time","Ground Speed","Lap Distance","Engine RPM"
        "s","m/s","m","rpm"
        0.00,41.2,10.0,5500.0
        0.10,41.5,14.2,5520.0
        0.20,41.9,18.4,5560.0
        """)
    s = read_daq_csv(p)
    @test channels(s) == ["Time", "Ground Speed", "Lap Distance", "Engine RPM"]
    @test s.units == ["s", "m/s", "m", "rpm"]
    @test nsamples(s) == 3
    @test s["ground speed"] == [41.2, 41.5, 41.9]   # case-insensitive
    @test duration(s) ≈ 0.2
    @test samplerate(s) ≈ 10.0
    @test isempty(s.meta)
end

@testset "bare header, metadata preamble, CRLF, ragged rows" begin
    p = fixture(dir, "bare.csv", join([
        "Track: Monaco 1958",
        "Vehicle: BRM P25",
        "",
        "Time,Gear,Throttle Position",
        "0.00,3,0.95",
        "0.01,3,bad_cell",
        "0.02,4",          # short row -> padded with NaN
        ""], "\r\n"))
    s = read_daq_csv(p)
    @test s.meta == ["Track: Monaco 1958", "Vehicle: BRM P25"]
    @test isempty(s.units)
    @test nsamples(s) == 3
    @test s["Gear"] == [3.0, 3.0, 4.0]
    @test isnan(s["Throttle Position"][2])    # bad cell -> NaN, not an error
    @test isnan(s["Throttle Position"][3])    # short row -> NaN
    @test haschannel(s, "gear") && !haschannel(s, "Brake")
    @test_throws KeyError s["Brake"]
end

@testset "MoTeC CSV layout (real plugin format)" begin
    # exact metadata block per the format strings in DataAcquisitionPlugin.dll;
    # the 2-cell "Time","19:43:12" row must NOT be mistaken for the header
    rows = String[]
    for i in 0:99
        push!(rows, "\"$(i * 0.1)\",\"$(40 + 0.01i)\",\"$(mod(i, 40) * 75.0)\",\"5500\"")
    end
    p = fixture(dir, "motec.csv", join(vcat([
        "\"Format\",\"MoTeC CSV File\"",
        "\"Venue\",\"Monaco58\"",
        "\"Vehicle\",\"BRM P25\"",
        "\"User\",\"Curator\"",
        "\"Data Source\",\"MoTeC ADL 2\"",
        "\"Comment\",\"\"",
        "\"Date\",\"04/06/2026\"",
        "\"Time\",\"19:43:12\"",
        "\"Sample Rate\",\"10.0000\"",
        "\"Segment\",\"Session\"",
        "\"Beacon Markers\",\"4.000000, 8.000000\"",   # comma-separated, as real
        "",
        "\"\",\"Speed\",\"LapDist\",\"RPM\"",            # alias row (empty Time alias)
        "\"Time\",\"Ground Speed\",\"Lap Distance\",\"Engine RPM\"",
        "\"sec\",\"m/s\",\"m\",\"rpm\"",
        "\"\",\"121\",\"8033\",\"1\"",                   # channel-ID row, not a sample
    ], rows), "\r\n"))
    s = read_daq_csv(p)
    @test channels(s) == ["Time", "Ground Speed", "Lap Distance", "Engine RPM"]
    @test s.units == ["sec", "m/s", "m", "rpm"]
    @test nsamples(s) == 100                     # ID row not counted as a sample
    @test !any(isnan, s["Time"])
    @test metadata(s, "Venue") == "Monaco58"
    @test metadata(s, "vehicle") == "BRM P25"     # case-insensitive
    @test metadata(s, "Sample Rate") == "10.0000"
    @test beacons(s) == [4.0, 8.0]
    # beacons (preferred) split at t=4.0 and t=8.0 -> 3 segments, but the
    # 2 s tail after the last beacon is shorter than min_lap_time
    rs = lapranges(s; min_lap_time=1.9)
    @test length(rs) == 3
    @test rs[1] == 1:40 && rs[2] == 41:80 && rs[3] == 81:100
    rs = lapranges(s; min_lap_time=3.0)
    @test length(rs) == 2
    @test rs[2] == 41:100                          # short tail merged forward
end

@testset "lap segmentation by Lap Distance resets" begin
    # 3 laps of 30 samples at 1 Hz over a 3000 m "track", plus a 5 s tail
    rows = String[]
    t = 0.0
    for lap in 1:3, i in 0:29
        push!(rows, "$(t),$(i * 100.0)")
        t += 1.0
    end
    for i in 0:4   # short out-lap tail, merged into lap 3
        push!(rows, "$(t),$(i * 100.0)")
        t += 1.0
    end
    p = fixture(dir, "laps.csv", "Time,Lap Distance\n" * join(rows, "\n") * "\n")
    s = read_daq_csv(p)
    rs = lapranges(s)
    @test length(rs) == 3
    @test rs[1] == 1:30 && rs[2] == 31:60
    @test rs[3] == 61:95               # tail merged forward into final lap
    cut = laps(s)
    @test length(cut) == 3
    @test nsamples(cut[1]) == 30
    @test cut[2]["Lap Distance"][1] == 0.0
end

@testset "lap segmentation by lap-number channel" begin
    rows = ["$(Float64(i)),$(i ÷ 20 + 1)" for i in 0:59]
    p = fixture(dir, "lapno.csv", "Time,Lap Number\n" * join(rows, "\n") * "\n")
    s = read_daq_csv(p)
    rs = lapranges(s)
    @test length(rs) == 3
    @test all(r -> length(r) == 20, rs)
end

@testset "no lap channel: one segment" begin
    p = fixture(dir, "flat.csv", "Time,Speed\n0.0,1.0\n1.0,2.0\n")
    s = read_daq_csv(p)
    @test lapranges(s) == [1:2]
end

@testset "header required" begin
    p = fixture(dir, "junk.csv", "no,telemetry,here\n1,2,3\n")
    @test_throws ErrorException read_daq_csv(p)
end

end # mktempdir

logs = find_daq_logs()
if isempty(logs)
    @info "no real DAQ logs yet — record one: run addTelemetryLoggerToRfactor.sh, " *
          "drive, toggle logging with CTRL-m (see UserData/LOG/MoTeC)"
else
    @testset "real DAQ logs load" begin
        for p in logs
            s = read_daq_csv(p)
            @test nsamples(s) > 0
            @test haschannel(s, "Time")
            @test !any(isnan, s["Time"])           # ID row must not leak in
            @test duration(s) >= 0
            @test 9 < samplerate(s) < 110          # plugin rates: 10.24 .. 102.4
        end
    end

    # pinned regression against the first recorded calibration session:
    # Vanwall VW10, Monaco 1967, 10 laps, 2026-06-05 (closes Phase 0)
    ref = filter(p -> occursin("2026_06_05_13_24_33", basename(p)), logs)
    if !isempty(ref)
        @testset "reference session: Vanwall @ Monaco67, 10 laps" begin
            s = read_daq_csv(only(ref))
            @test nsamples(s) == 17658
            @test length(channels(s)) == 88
            @test s.units[1] == "sec"
            @test metadata(s, "Vehicle") == "S. Lewis-Evans - Vanwall VW10"
            @test metadata(s, "Venue") == "Monaco 1967"
            @test metadata(s, "Sample Rate") == "10.2400"
            @test samplerate(s) ≈ 10.24 atol = 0.01
            @test length(beacons(s)) == 9
            @test beacons(s)[1] ≈ 188.072

            rs = lapranges(s)
            @test length(rs) == 10                 # out-lap + 8 flyers + 12 s tail
            t = s["Time"]
            laptimes = [t[last(r)] - t[first(r)] for r in rs]
            @test minimum(laptimes[1:9]) ≈ 157.71 atol = 0.2   # fastest: lap 9
            @test laptimes[end] < 15               # clipped in-lap tail

            # physics consistency: static corner loads vs HDV mass + fuel
            static = sum(sum(s["Tire Load - $c"][1:5]) / 5 for c in ("FL", "FR", "RL", "RR"))
            mass = static / 9.81
            fuel_l = s["Fuel Level"][1]
            @test fuel_l ≈ 160.0 atol = 0.1
            # Vanwall HDV Mass=715 kg + 160 L of ~0.74 kg/L period fuel
            @test mass ≈ 715 + fuel_l * 0.74 atol = 5.0
        end
    end
end

end
