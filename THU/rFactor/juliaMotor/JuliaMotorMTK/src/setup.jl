# Extract model PARAMETERS from the `.ibt` CarSetup / DriverInfo YAML block.
#
# The CarSetup block is indentation-structured but not strict YAML (values carry
# units and some are multi-valued, e.g. "64.0 mm 104.6 mm" or "39C, 39C, 39C").
# We parse it into a nested Dict and expose a `first-number` helper so callers
# pull clean Float64 parameters (SpringRate, CornerWeight, gear ratios, …).

module Setup

export parse_yaml_block, setup_params, firstnum

"""    firstnum(s) -> Float64

First numeric token in a string, sign/decimals honoured ("26 N/mm"→26.0,
"53.50%"→53.5, "10:1"→10.0, "+0.5 deg"→0.5, "-1 mm"→-1.0). NaN if none.
"""
function firstnum(s::AbstractString)
    m = match(r"[-+]?\d+(?:\.\d+)?", s)
    m === nothing ? NaN : parse(Float64, m.match)
end

"""    parse_yaml_block(yaml, header) -> Dict

Parse the indentation-nested block under a top-level `header` (e.g. "CarSetup")
into nested Dict{String,Any}; leaves are the raw value strings.
"""
function parse_yaml_block(yaml::AbstractString, header::AbstractString)
    lines = split(yaml, '\n')
    # find header line (zero indent) and its block (indent > 0 until next zero-indent)
    istart = findfirst(l -> startswith(l, header * ":"), lines)
    istart === nothing && error("block $header not found")
    root = Dict{String,Any}()
    stack = Tuple{Int,Dict{String,Any}}[(-1, root)]   # (indent, dict)
    for i in istart+1:length(lines)
        line = lines[i]
        isempty(strip(line)) && continue
        indent = length(line) - length(lstrip(line))
        indent == 0 && break                          # left the block
        content = strip(line)
        startswith(content, "- ") && continue         # skip list items (none in CarSetup)
        while length(stack) > 1 && stack[end][1] >= indent
            pop!(stack)
        end
        parent = stack[end][2]
        if endswith(content, ":")                      # nested key
            key = rstrip(content, ':')
            d = Dict{String,Any}()
            parent[key] = d
            push!(stack, (indent, d))
        else                                           # leaf "key: value"
            kv = split(content, ": ", limit=2)
            length(kv) == 2 && (parent[kv[1]] = kv[2])
        end
    end
    root
end

"""    setup_params(yaml) -> NamedTuple

Pull the model parameters we care about out of CarSetup + DriverInfo, units
stripped to SI-ish Float64.  Corner keys are LF/RF/LR/RR.
"""
function setup_params(yaml::AbstractString)
    cs = parse_yaml_block(yaml, "CarSetup")
    di = parse_yaml_block(yaml, "DriverInfo")
    ch = cs["Chassis"]; dt = cs["Drivetrain"]; ti = cs["Tires"]
    corners = ("LeftFront"=>:LF, "RightFront"=>:RF, "LeftRear"=>:LR, "RightRear"=>:RR)
    g(d, k) = haskey(d, k) ? firstnum(d[k]) : NaN
    cw  = Dict(sym => g(ch[name], "CornerWeight") for (name,sym) in corners)   # N
    spr = Dict(sym => g(ch[name], "SpringRate")  for (name,sym) in corners)    # N/mm
    rh  = Dict(sym => g(ch[name], "RideHeight")  for (name,sym) in corners)    # mm
    cmb = Dict(sym => g(ch[name], "Camber")      for (name,sym) in corners)    # deg
    cp  = Dict(sym => g(ti[name], "ColdPressure") for (name,sym) in corners)   # kPa
    trans = dt["Transmission"]
    gears = [firstnum(trans[k]) for k in ("FirstGear","SecondGear","ThirdGear","FourthGear","FifthGear")]
    (; corner_weight_N = cw,
       spring_rate_Npmm = spr,
       ride_height_mm = rh,
       camber_deg = cmb,
       cold_pressure_kPa = cp,
       brake_bias_pct   = g(ch["Front"], "BrakeBias"),
       steering_ratio   = g(ch["Front"], "SteeringRatio"),
       cross_weight_pct = g(ch["Front"], "CrossWeight"),
       final_drive      = firstnum(trans["FinalDrive"]),
       gear_ratios      = gears,
       diff_preload_Nm  = g(dt["Differential"], "Preload"),
       diff_drive_ramp  = g(dt["Differential"], "DriveRampAngle"),
       diff_coast_ramp  = g(dt["Differential"], "CoastRampAngle"),
       fuel_L           = g(ch["Rear"], "FuelLevel"),
       idle_rpm   = firstnum(di["DriverCarIdleRPM"]),
       redline_rpm= firstnum(di["DriverCarRedLine"]),
       n_gears    = firstnum(di["DriverCarGearNumForward"]),
       fuel_kg_per_L = firstnum(di["DriverCarFuelKgPerLtr"]))
end

end # module
