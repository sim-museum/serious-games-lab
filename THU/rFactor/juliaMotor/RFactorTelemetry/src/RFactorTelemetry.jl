"""
    RFactorTelemetry

Ingestion for rFactor DAQ Plugin telemetry logs (Phase 0 of the juliaMotor
project).  The plugin (rFactorDAQPluginSetup_1.3.2, installed by
`addTelemetryLoggerToRfactor.sh`) writes motec_convert-compatible CSV at
up to 100 Hz into `UserData/LOG/MoTeC/`; channels are configured in
`DataAcquisitionPlugin.ini`.

The CSV layout (verified against real plugin output, 2026-06-05) is the
MoTeC CSV export: a quoted 2-column metadata block —

    "Format","MoTeC CSV File"
    "Venue","%s" / "Vehicle","%s" / "User","%s" / "Date","%s" / "Time","%s"
    "Sample Rate","%.4f"
    "Beacon Markers","%s"   <- comma-separated start/finish crossing times

— a blank line, then FOUR pre-data rows: a short-alias row (whose Time
alias is the empty cell), the channel-name header row, a units row, and a
numeric channel-ID row; then data rows.  The reader sniffs rather than
assumes: metadata is optional, the header row is the first row with a
`Time` cell where every non-empty cell starts with a letter (this skips
both the metadata block's 2-cell `"Time","19:43:12"` row and the alias
row), the units row is optional, the channel-ID row is rejected by its
non-numeric Time cell, and data cells parse tolerantly (non-numeric
cells become NaN, short rows are padded).  Lap segmentation prefers
beacon markers, then a lap-number channel, then `Lap Distance` resets.
"""
module RFactorTelemetry

export TelemetrySession, read_daq_csv, channels, channel, haschannel,
       nsamples, duration, samplerate, laps, lapranges,
       metadata, beacons, find_daq_logs, default_log_dir

"""
One logging stint.  `data` is samples × channels; column order matches
`channels`.  `meta` holds any pre-header lines verbatim.
"""
struct TelemetrySession
    path::String
    channels::Vector{String}
    units::Vector{String}        # empty if the file has no units row
    data::Matrix{Float64}
    meta::Vector{String}
end

channels(s::TelemetrySession) = s.channels
nsamples(s::TelemetrySession) = size(s.data, 1)

Base.show(io::IO, s::TelemetrySession) =
    print(io, "TelemetrySession(\"", basename(s.path), "\", ",
          nsamples(s), " samples × ", length(s.channels), " channels, ",
          round(duration(s); digits=1), " s)")

channelindex(s::TelemetrySession, name::AbstractString) =
    findfirst(c -> strip(lowercase(c)) == strip(lowercase(name)), s.channels)

haschannel(s::TelemetrySession, name::AbstractString) =
    channelindex(s, name) !== nothing

"""Column vector for a channel, by case-insensitive name."""
function channel(s::TelemetrySession, name::AbstractString)
    i = channelindex(s, name)
    i === nothing && throw(KeyError(name))
    view(s.data, :, i)
end

Base.getindex(s::TelemetrySession, name::AbstractString) = channel(s, name)

"""
    metadata(s) -> Dict{String,String}

The MoTeC metadata block (`"Venue"`, `"Vehicle"`, `"Sample Rate"`,
`"Beacon Markers"`, ...) as a dict; keys are matched case-insensitively
via `metadata(s, key, default)`.
"""
function metadata(s::TelemetrySession)
    d = Dict{String,String}()
    for line in s.meta
        cells = split_csv(line)
        length(cells) == 2 && (d[String(cells[1])] = String(cells[2]))
    end
    d
end

function metadata(s::TelemetrySession, key::AbstractString, default="")
    for (k, v) in metadata(s)
        lowercase(strip(k)) == lowercase(strip(key)) && return v
    end
    default
end

"""Start/finish crossing times from the `"Beacon Markers"` metadata
(comma-separated seconds in real plugin output, on the Time channel's clock)."""
function beacons(s::TelemetrySession)
    raw = metadata(s, "Beacon Markers")
    [t for t in (tryparse(Float64, tok) for tok in split(raw, r"[,\s]+"; keepempty=false))
     if t !== nothing]
end

"""Session length in seconds (from the Time channel)."""
function duration(s::TelemetrySession)
    t = channel(s, "Time")
    isempty(t) ? 0.0 : t[end] - t[1]
end

"""Median sample rate in Hz."""
function samplerate(s::TelemetrySession)
    t = channel(s, "Time")
    length(t) < 2 && return 0.0
    dts = sort!(diff(collect(t)))
    dt = dts[(length(dts) + 1) ÷ 2]
    dt > 0 ? 1.0 / dt : 0.0
end

# --- parsing ---------------------------------------------------------------

"""
    read_daq_csv(path) -> TelemetrySession
"""
function read_daq_csv(path::AbstractString)
    lines = readlines(path)
    meta = String[]
    header = String[]
    units = String[]
    datastart = 0

    # locate the channel header: a row with a "Time" cell where every
    # non-empty cell looks like a channel name (starts with a letter) —
    # this skips the metadata block's 2-cell "Time","19:43:12" row
    for (i, line) in enumerate(lines)
        cells = split_csv(line)
        nonempty = [strip(c) for c in cells if !isempty(strip(c))]
        if length(nonempty) >= 2 &&
           any(c -> lowercase(c) == "time", nonempty) &&
           all(c -> isletter(first(c)), nonempty)
            header = [String(strip(c)) for c in cells]
            datastart = i + 1
            break
        end
        isempty(strip(line)) || push!(meta, line)
    end
    isempty(header) &&
        error("$(path): no header row containing a Time channel found")

    # optional units row: next non-empty row with no numeric cells
    if datastart <= length(lines)
        cells = split_csv(lines[datastart])
        if !isempty(cells) && all(c -> tryparse(Float64, strip(c)) === nothing, cells) &&
           !all(c -> isempty(strip(c)), cells)
            units = [String(strip(c)) for c in cells]
            datastart += 1
        end
    end

    ncol = length(header)
    timecol = something(findfirst(c -> strip(lowercase(c)) == "time", header), 1)
    rows = Vector{Vector{Float64}}()
    for line in @view lines[datastart:end]
        isempty(strip(line)) && continue
        cells = split_csv(line)
        all(c -> isempty(strip(c)), cells) && continue
        # rows without a numeric Time cell are not samples (the real plugin
        # emits a channel-ID row between the units row and the data)
        if length(cells) < timecol || tryparse(Float64, strip(cells[timecol])) === nothing
            push!(meta, line)
            continue
        end
        row = fill(NaN, ncol)
        for (j, c) in enumerate(cells)
            j > ncol && break
            v = tryparse(Float64, strip(c))
            v === nothing || (row[j] = v)
        end
        push!(rows, row)
    end

    data = isempty(rows) ? Matrix{Float64}(undef, 0, ncol) :
                           permutedims(reduce(hcat, rows))
    TelemetrySession(String(path), header, units, data, meta)
end

"""Split a CSV line, unquoting double-quoted cells.  Quote-aware: the
`"Beacon Markers","188.072, 381.704, ..."` metadata line carries commas
inside a quoted value."""
function split_csv(line::AbstractString)
    s = strip(line, ['\r'])
    cells = String[]
    buf = IOBuffer()
    inquote = false
    for c in s
        if c == '"'
            inquote = !inquote
        elseif c == ',' && !inquote
            push!(cells, String(take!(buf)))
        else
            write(buf, c)
        end
    end
    push!(cells, String(take!(buf)))
    [String(strip(c)) for c in cells]
end

# --- lap segmentation ------------------------------------------------------

"""
    lapranges(s; min_lap_time=10.0) -> Vector{UnitRange{Int}}

Sample ranges of complete laps.  Start/finish crossings come from the
`"Beacon Markers"` metadata when present, else a `Lap Number`-style
channel, else backward jumps of the `Lap Distance` channel.  Segments
shorter than `min_lap_time` seconds (out-laps clipped by logging toggles,
spins across the line) are merged forward rather than reported as laps.
"""
function lapranges(s::TelemetrySession; min_lap_time::Real=10.0)
    n = nsamples(s)
    n == 0 && return UnitRange{Int}[]
    t = channel(s, "Time")

    bounds = Int[]
    bcn = beacons(s)
    lapchan = findfirst(c -> occursin("lap", lowercase(c)) &&
                             occursin(r"number|count", lowercase(c)), s.channels)
    if !isempty(bcn)
        for tb in bcn
            i = searchsortedfirst(collect(t), tb)
            1 < i <= n && push!(bounds, i)
        end
        sort!(unique!(bounds))
    elseif lapchan !== nothing
        lapno = view(s.data, :, lapchan)
        for i in 2:n
            lapno[i] != lapno[i-1] && push!(bounds, i)
        end
    elseif haschannel(s, "Lap Distance")
        d = channel(s, "Lap Distance")
        for i in 2:n
            # crossing start/finish: distance falls back toward zero
            d[i] < d[i-1] - 50.0 && push!(bounds, i)
        end
    else
        return [1:n]
    end

    ranges = UnitRange{Int}[]
    start = 1
    for b in vcat(bounds, n + 1)
        stop = b - 1
        if stop >= start
            if t[stop] - t[start] >= min_lap_time
                push!(ranges, start:stop)
            elseif !isempty(ranges)
                ranges[end] = first(ranges[end]):stop   # merge short tail
            end
        end
        start = b
    end
    ranges
end

"""
    laps(s; min_lap_time=10.0) -> Vector{TelemetrySession}

The session cut into one `TelemetrySession` per complete lap.
"""
laps(s::TelemetrySession; min_lap_time::Real=10.0) =
    [TelemetrySession(s.path, s.channels, s.units, s.data[r, :], s.meta)
     for r in lapranges(s; min_lap_time)]

# --- discovery -------------------------------------------------------------

"""Default DAQ plugin output directory in this repository's rFactor install."""
function default_log_dir()
    get(ENV, "RFACTOR_DAQ_LOGS") do
        joinpath(@__DIR__, "..", "..", "..",
                 "WP", "drive_c", "Program Files", "rFactor",
                 "UserData", "LOG", "MoTeC") |> normpath
    end
end

"""All `*.csv` stint logs under `dir`, newest first."""
function find_daq_logs(dir::AbstractString=default_log_dir())
    isdir(dir) || return String[]
    files = [joinpath(dir, f) for f in readdir(dir) if endswith(lowercase(f), ".csv")]
    sort!(files; by=mtime, rev=true)
end

end # module
