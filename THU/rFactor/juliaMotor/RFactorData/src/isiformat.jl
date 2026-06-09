# Generic machinery for the ISI plain-text format family
# ([SECTION] headers, Key=value entries, // comments) shared by
# HDV / TBC / PM / ENG / VEH / SVM files.
#
# Format quirks confirmed in this install's corpus and handled here:
#   * PM lines carry several pairs:  name=body mass=(825) inertia=(...)
#   * HDV jammed-pair typos:         CGRearSetting=0WedgeRange=(0,0,0)
#   * HDV duplicated-key typo:       FuelTankMotion=FuelTankMotion=(...)
#   * TBC glued section header:      [COMPOUND]Name="F60R15 RWL GY Polyglas"
#   * TBC multi-line numeric blocks: Data: <rows of floats>   (data_blocks=true)
#   * TBC scope markers:             FRONT: / REAR: / Rear:   (scopes=true)
#   * empty tuple slots:             (0,,0)
#   * missing '=' lines, files without trailing newline, CRLF throughout
#
# The parser is deliberately lenient — we must load every file isiMotor
# loads.  Anything repaired or skipped is recorded in `ISIFile.issues`
# rather than silently dropped.

"""
One `Key=value` assignment.  `value` is the parsed form:

  * `Int` / `Float64`   — bare scalars, and 1-element tuples like `(0.349)`
  * `Vector{Any}`       — tuples `(a, b, c)` / bare lists `a,b`; numeric
                          elements parsed, empty slots become `missing`,
                          anything else stays `String`
  * `Vector{Float64}`   — multi-line `Data:` blocks (key is `"Data"`)
  * `String`            — quoted strings (unquoted) and bare words/filenames

`raw` keeps the comment-stripped right-hand side verbatim, `comment` any
trailing `//` text, and `scope` the active `FRONT:`/`REAR:`-style marker
(`""` outside any scope).
"""
struct ISIEntry
    key::String
    value::Any
    raw::String
    comment::Union{String,Nothing}
    scope::String
    line::Int
end

struct ISISection
    name::String
    comment::Union{String,Nothing}
    entries::Vector{ISIEntry}
end

struct ISIFile
    path::String
    sections::Vector{ISISection}
    issues::Vector{String}   # malformed input that was repaired or skipped
end

Base.show(io::IO, f::ISIFile) =
    print(io, "ISIFile(\"", basename(f.path), "\", ",
          length(f.sections), " sections, ",
          sum(s -> length(s.entries), f.sections; init=0), " entries",
          isempty(f.issues) ? "" : ", $(length(f.issues)) issues", ")")

# --- lookup API ------------------------------------------------------------
# Section and key matching is case-insensitive, as in isiMotor.

"""All sections named `name` (sections like [AIDPENALTIES] legitimately repeat)."""
sections(f::ISIFile, name::AbstractString) =
    [s for s in f.sections if isequal_ci(s.name, name)]

"""First section named `name`, or `nothing`."""
function section(f::ISIFile, name::AbstractString)
    i = findfirst(s -> isequal_ci(s.name, name), f.sections)
    i === nothing ? nothing : f.sections[i]
end

"""
    entries(s, key; scope=nothing)

All entries for `key` (keys like Undertray00..08 are distinct, but genuinely
repeated keys also occur, e.g. RPMTorque).  `scope=nothing` matches any
scope; pass `""` for unscoped entries only, or e.g. `"FRONT"`.
"""
entries(s::ISISection, key::AbstractString; scope=nothing) =
    [e for e in s.entries if isequal_ci(e.key, key) &&
        (scope === nothing || isequal_ci(e.scope, scope))]

"""Last entry for `key` (later assignments override earlier ones), or `nothing`."""
function entry(s::ISISection, key::AbstractString; scope=nothing)
    i = findlast(e -> isequal_ci(e.key, key) &&
                      (scope === nothing || isequal_ci(e.scope, scope)), s.entries)
    i === nothing ? nothing : s.entries[i]
end

function Base.getindex(f::ISIFile, name::AbstractString)
    s = section(f, name)
    s === nothing && throw(KeyError(name))
    s
end

function Base.getindex(s::ISISection, key::AbstractString)
    e = entry(s, key)
    e === nothing && throw(KeyError(key))
    e.value
end

Base.get(s::ISISection, key::AbstractString, default) =
    (e = entry(s, key); e === nothing ? default : e.value)

Base.haskey(s::ISISection, key::AbstractString) = entry(s, key) !== nothing
Base.keys(s::ISISection) = unique!([e.key for e in s.entries])

"""Comment-stripped right-hand side text for `key`, or `nothing`."""
rawvalue(s::ISISection, key::AbstractString) =
    (e = entry(s, key); e === nothing ? nothing : e.raw)

isequal_ci(a::AbstractString, b::AbstractString) =
    lowercase(strip(a)) == lowercase(strip(b))

"""Read file text, tolerating stray non-UTF-8 bytes (decoded as Latin-1)."""
function readtext(path::AbstractString)
    bytes = read(path)
    isvalid(String, bytes) ? String(bytes) : join(Char(b) for b in bytes)
end

# --- parsing ---------------------------------------------------------------

"""
    parse_isi(text; path="<string>", data_blocks=false, scopes=false) -> ISIFile

Parse ISI `[SECTION]` / `Key=value` text.  Entries before any section
header land in a section named `""` (VEH and engine files are entirely
flat).  `data_blocks` enables TBC-style multi-line `Data:` numeric blocks;
`scopes` enables TBC-style `FRONT:` / `REAR:` markers.
"""
function parse_isi(text::AbstractString; path::AbstractString="<string>",
                   data_blocks::Bool=false, scopes::Bool=false)
    issues = String[]
    secs = ISISection[]
    cur = ISISection("", nothing, ISIEntry[])  # implicit preamble section
    scope = ""
    datavec = nothing  # Vector{Float64} currently being filled, or nothing

    function open_section(name, comment)
        isempty(cur.name) && isempty(cur.entries) || push!(secs, cur)
        cur = ISISection(name, comment, ISIEntry[])
        scope = ""
        datavec = nothing
    end

    for (lineno, rawline) in enumerate(split(text, '\n'))
        line = rstrip(rawline, ['\r'])
        body, comment = split_comment(line)
        body = strip(body)
        isempty(body) && continue

        # inside a Data: block, rows of bare numbers accumulate
        if datavec !== nothing
            nums = tryparse_row(body)
            if nums !== nothing
                append!(datavec, nums)
                continue
            end
            datavec = nothing  # block ended; process line normally
        end

        m = match(r"^\[([^\]]*)\]\s*(.*)$", body)
        if m !== nothing
            open_section(strip(m.captures[1]), comment)
            body = strip(m.captures[2])  # glued [COMPOUND]Name="..." remainder
            isempty(body) && continue
        end

        if data_blocks && match(r"^data\s*:$"i, body) !== nothing
            datavec = Float64[]
            push!(cur.entries, ISIEntry("Data", datavec, "Data:", comment, scope, lineno))
            continue
        end

        if scopes && (m = match(r"^([A-Za-z_][A-Za-z0-9_]*):$", body)) !== nothing
            scope = String(m.captures[1])
            continue
        end

        if !occursin('=', body)
            push!(issues, "$(path):$(lineno): no '=', skipped: $(body)")
            continue
        end

        for (key, raw) in split_pairs(String(body), issues, path, lineno)
            push!(cur.entries,
                  ISIEntry(key, parse_value(raw), raw, comment, scope, lineno))
        end
    end
    isempty(cur.name) && isempty(cur.entries) || push!(secs, cur)
    ISIFile(String(path), secs, issues)
end

"""Strip a trailing `//` comment, respecting double-quoted strings."""
function split_comment(line::AbstractString)
    inquote = false
    i = firstindex(line)
    while i < lastindex(line)
        c = line[i]
        if c == '"'
            inquote = !inquote
        elseif !inquote && c == '/' && line[nextind(line, i)] == '/'
            return line[1:prevind(line, i)], String(strip(line[nextind(line, nextind(line, i)):end]))
        end
        i = nextind(line, i)
    end
    return line, nothing
end

"""Parse a whitespace-separated row of numbers, or `nothing` if any token isn't one."""
function tryparse_row(body::AbstractString)
    nums = Float64[]
    for tok in split(body)
        n = tryparse(Float64, tok)
        n === nothing && return nothing
        push!(nums, n)
    end
    nums
end

"""
Split a `Key=value` line into its pairs.  Multiple whitespace-separated
pairs per line are normal PM/GEN syntax:

    name=body mass=(825) inertia=(0.0, 0.0, 0.0)

while pairs glued without whitespace are corpus typos, repaired and
reported as issues:

    CGRearSetting=0WedgeRange=(0,0,0)         -> two entries
    FuelTankMotion=FuelTankMotion=(560.0,0.8) -> one entry (empty outer dropped)

A quoted value consumes everything to its closing quote, so `=` inside
quotes never splits.
"""
function split_pairs(body::String, issues::Vector{String},
                     path::AbstractString, lineno::Int)
    pairs = Tuple{String,String}[]
    eq = findfirst('=', body)
    key = String(strip(body[1:prevind(body, eq)]))
    rest = String(strip(body[nextind(body, eq):end]))

    while true
        search_from = firstindex(rest)
        if startswith(rest, '"')  # skip over the quoted value
            close = findnext('"', rest, nextind(rest, firstindex(rest)))
            close === nothing || (search_from = nextind(rest, close))
        end
        m = match(r"^(.*?)([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$",
                  rest[search_from:end])
        m === nothing && break
        quoted_prefix = search_from == firstindex(rest) ? "" :
                        rest[firstindex(rest):prevind(rest, search_from)]
        val = strip(quoted_prefix * m.captures[1])
        glued = isempty(m.captures[1]) || !isspace(m.captures[1][end])
        if isempty(val) && isequal_ci(m.captures[2], key)
            # duplicated-key typo: FuelTankMotion=FuelTankMotion=(...)
            push!(issues, "$(path):$(lineno): duplicated key repaired at '$(m.captures[2])='")
        elseif isempty(val)
            # ambiguous glue like HATTarget=FalseLODIn=(0): the boundary
            # inside 'FalseLODIn' is unknowable, the first pair is lost
            push!(issues, "$(path):$(lineno): glued pair at '$(m.captures[2])=', value of '$(key)' lost")
        elseif glued      # value glued straight onto the next key
            push!(issues, "$(path):$(lineno): jammed pair repaired at '$(m.captures[2])='")
            push!(pairs, (key, String(val)))
        else              # normal multi-pair line (PM, GEN)
            push!(pairs, (key, String(val)))
        end
        key, rest = String(m.captures[2]), String(strip(m.captures[3]))
    end
    push!(pairs, (key, rest))
    pairs
end

"""Parse a comment-stripped RHS into Int/Float64/String/Vector{Any}."""
function parse_value(raw::AbstractString)
    s = strip(raw)
    isempty(s) && return ""
    if length(s) >= 2 && startswith(s, '"') && endswith(s, '"')
        return String(s[nextind(s, firstindex(s)):prevind(s, lastindex(s))])
    end
    if startswith(s, '(') && endswith(s, ')')
        return parse_list(s[nextind(s, firstindex(s)):prevind(s, lastindex(s))])
    end
    n = parse_scalar(s)
    n === nothing || return n
    # bare unparenthesized list, e.g. `BrakeDuctCooling=1,5`
    occursin(',', s) && return parse_list(s)
    return String(s)   # bare word / filename
end

"""Comma-separated elements; empty slots like `(0,,0)` become `missing`.
1-element all-numeric lists collapse to the scalar, so `(0.349)` == `0.349`."""
function parse_list(inner::AbstractString)
    vals = Any[]
    for part in split(inner, ',')
        p = strip(part)
        if isempty(p)
            push!(vals, missing)
        else
            n = parse_scalar(p)
            push!(vals, n === nothing ? String(p) : n)
        end
    end
    length(vals) == 1 && vals[1] isa Number && return vals[1]
    vals
end

function parse_scalar(s::AbstractString)
    i = tryparse(Int, s)
    i === nothing || return i
    tryparse(Float64, s)
end
