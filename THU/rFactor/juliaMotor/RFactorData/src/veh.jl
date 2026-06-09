# VEH car-instance files, SVM garage setups, and cross-file resolution.
#
# A VEH is flat key=value text naming everything a car instance uses
# (HDVehicle=, Graphics=, Sounds=, ...).  The HDV in turn references the
# tire brand (TireBrand=, possibly without its .tbc extension), suspension
# (PhysicalModelFile=), engine ([ENGINE] Normal=) and gears (GearFile=).
#
# isiMotor resolves referenced filenames case-insensitively anywhere in
# the vehicle directory tree; in practice files sit next to the referencing
# file or in an ancestor directory (mod-shared tires/suspensions), so we
# search ancestors first and fall back to a recursive sweep of the mod.

"""
    read_veh(path) -> ISIFile

VEH files are flat: all entries land in the preamble section `f[""]`.
"""
read_veh(path::AbstractString) = parse_isi(readtext(path); path)

"""
    read_svm(path) -> ISIFile

Garage setup; sections mirror the HDV sections they override.
"""
read_svm(path::AbstractString) = parse_isi(readtext(path); path)

find_veh_files(root::AbstractString=default_gamedata()) = find_ext(root, ".veh")

"""
    resolve_file(refdir, name; ext="", vehicles_root=nothing) -> String | nothing

Find referenced file `name` (case-insensitive) starting from the directory
of the referencing file: each ancestor directory up to the `Vehicles` root
is checked directly, then the mod subtree is swept recursively.  `ext` is
appended when `name` has no extension (TireBrand=1997_GT1_Goodyear_Tires).
"""
function resolve_file(refdir::AbstractString, name::AbstractString;
                      ext::AbstractString="", vehicles_root=nothing)
    isempty(name) && return nothing
    target = lowercase(basename(replace(name, '\\' => '/')))
    occursin('.', target) || (target *= lowercase(ext))
    root = vehicles_root === nothing ? find_vehicles_root(refdir) : abspath(vehicles_root)

    # ancestors of the referencing file, nearest first
    dir = abspath(refdir)
    while true
        hit = find_in_dir(dir, target)
        hit === nothing || return hit
        (dir == root || dirname(dir) == dir) && break
        dir = dirname(dir)
    end

    # fall back: recursive sweep of the topmost mod directory
    moddir = abspath(refdir)
    while dirname(moddir) != root && dirname(moddir) != moddir
        moddir = dirname(moddir)
    end
    for (d, _, files) in walkdir(moddir), file in files
        lowercase(file) == target && return joinpath(d, file)
    end
    nothing
end

function find_in_dir(dir::AbstractString, target::AbstractString)
    isdir(dir) || return nothing
    for file in readdir(dir)
        lowercase(file) == target && return joinpath(dir, file)
    end
    nothing
end

"""Nearest ancestor directory named `Vehicles` (else the filesystem root)."""
function find_vehicles_root(dir::AbstractString)
    d = abspath(dir)
    while lowercase(basename(d)) != "vehicles" && dirname(d) != d
        d = dirname(d)
    end
    d
end

"""
Every physics file behind one VEH instance, fully parsed.  `setting` keys
that pick within files (tire compound index, etc.) stay in `hdv`/`veh`.
"""
struct Vehicle
    veh::ISIFile
    hdv::ISIFile
    tbc::TBCFile
    pm::PMFile
    engine::EngineFile
    gears::ISIFile
    unresolved::Vector{String}   # reference keys that could not be resolved
end

Base.show(io::IO, v::Vehicle) =
    print(io, "Vehicle(\"", get(get_section(v.veh, ""), "Description", basename(v.veh.path)),
          "\"", isempty(v.unresolved) ? "" :
          ", unresolved: " * join(v.unresolved, ", "), ")")

"""
    load_vehicle(veh_path; vehicles_root=nothing) -> Vehicle

Follow a VEH file to its HDV and on to tires/suspension/engine/gears.
Unresolvable or missing references are listed in `Vehicle.unresolved`
(with empty parsed placeholders) rather than thrown.
"""
function load_vehicle(veh_path::AbstractString; vehicles_root=nothing)
    veh = read_veh(veh_path)
    unresolved = String[]
    root = vehicles_root === nothing ? find_vehicles_root(dirname(veh_path)) :
                                       abspath(vehicles_root)

    function res(refdir, name, ext)
        name isa AbstractString && !isempty(name) || return nothing
        resolve_file(refdir, name; ext, vehicles_root=root)
    end

    hdvpath = res(dirname(veh_path), get(get_section(veh, ""), "HDVehicle", ""), ".hdv")
    hdvpath === nothing && push!(unresolved, "HDVehicle")
    hdv = hdvpath === nothing ? parse_hdv(""; path="<missing>") : read_hdv(hdvpath)
    hdvdir = hdvpath === nothing ? dirname(veh_path) : dirname(hdvpath)

    tbcpath = res(hdvdir, get(get_section(hdv, "GENERAL"), "TireBrand", ""), ".tbc")
    tbcpath === nothing && push!(unresolved, "TireBrand")
    tbc = tbcpath === nothing ? parse_tbc(""; path="<missing>") : read_tbc(tbcpath)

    pmpath = res(hdvdir, get(get_section(hdv, "SUSPENSION"), "PhysicalModelFile", ""), ".pm")
    pmpath === nothing && push!(unresolved, "PhysicalModelFile")
    pm = pmpath === nothing ? parse_pm(""; path="<missing>") : read_pm(pmpath)

    engpath = res(hdvdir, get(get_section(hdv, "ENGINE"), "Normal", ""), ".ini")
    engpath === nothing && push!(unresolved, "Engine:Normal")
    engine = engpath === nothing ? parse_engine(""; path="<missing>") : read_engine(engpath)

    gearpath = res(hdvdir, get(get_section(hdv, "DRIVELINE"), "GearFile", ""), ".ini")
    gearpath === nothing && push!(unresolved, "GearFile")
    gears = gearpath === nothing ? parse_isi(""; path="<missing>") : read_gears(gearpath)

    Vehicle(veh, hdv, tbc, pm, engine, gears, unresolved)
end

"""Section by name, or an empty placeholder (keeps `load_vehicle` total)."""
function get_section(f::ISIFile, name::AbstractString)
    s = section(f, name)
    s === nothing ? ISISection(String(name), nothing, ISIEntry[]) : s
end
