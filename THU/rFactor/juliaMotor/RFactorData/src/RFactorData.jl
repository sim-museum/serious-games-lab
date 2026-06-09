"""
    RFactorData

Parsers for rFactor 1 / isiMotor 2 plain-text physics data files.

Phase 0 of the juliaMotor project (see `DOC/juliaMotorProjectScope.md`):
the rFactor data files are the single source of truth, so this package
turns them into typed Julia structures from which the ModelingToolkit
vehicle is assembled.

Implemented formats:
  * HDV chassis          — `parse_hdv`, `read_hdv`
  * TBC tires            — `parse_tbc`, `read_tbc` (`SlipCurve`, `TBCCompound`)
  * PM suspension        — `parse_pm`, `read_pm` (`PMBody`, `PMJoint`, `PMBar`)
  * engine / gears INI   — `read_engine`, `read_gears`, `gear_ratios`
  * VEH / SVM            — `read_veh`, `read_svm`
  * GEN graphics         — `read_gen` (wiring completeness only)
  * whole car            — `load_vehicle` follows VEH -> HDV -> TBC/PM/ENG/gears
"""
module RFactorData

export ISIEntry, ISISection, ISIFile, parse_isi,
       sections, section, entries, entry, rawvalue, issues,
       parse_hdv, read_hdv, find_hdv_files,
       SlipCurve, TBCCompound, TBCFile, parse_tbc, read_tbc, find_tbc_files,
       slipcurve, compound, slips, axle,
       PMBody, PMJoint, PMBar, PMFile, parse_pm, read_pm, find_pm_files,
       body, resolve,
       EngineFile, parse_engine, read_engine, param,
       read_gears, gear_ratios, final_drive_ratios,
       read_veh, read_svm, find_veh_files,
       Vehicle, load_vehicle, resolve_file,
       GENFile, GENStatement, parse_gen, read_gen, find_gen_files, gen_statements,
       AIWWaypoint, AIWFile, read_aiw, find_aiw_files, mainpath, read_gdb,
       MASEntry, MASFile, read_mas, extract, entrynames, find_mas_files,
       GMTMesh, parse_gmt, parse_gmt_indexed, parse_gmt_uv, gmt_bbox, gmt_name, gmt_header, read_gmt_from_mas,
       default_gamedata

include("isiformat.jl")
include("hdv.jl")
include("tbc.jl")
include("pm.jl")
include("eng.jl")
include("veh.jl")
include("gen.jl")
include("aiw.jl")
include("mas.jl")
include("gmt.jl")

"""
    default_gamedata() -> String

Path to the `GameData` directory of the working rFactor installation,
resolved from `ENV["RFACTOR_GAMEDATA"]` if set, otherwise the wine
prefix this repository wraps.
"""
function default_gamedata()
    get(ENV, "RFACTOR_GAMEDATA") do
        joinpath(@__DIR__, "..", "..", "..",
                 "WP", "drive_c", "Program Files", "rFactor", "GameData") |> normpath
    end
end

end # module
