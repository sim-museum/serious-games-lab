# HDV chassis files.
#
# An HDV is plain ISI key-value text; this layer adds reading, corpus
# discovery, and validation of the section inventory every HDV in the
# install carries (confirmed across all 202 files: GENERAL, BODYAERO,
# SUSPENSION, CONTROLS, ENGINE, DRIVELINE and the four wheel corners
# appear in every one; PITMENU/wings/DIFFUSER/AIDPENALTIES are optional).

const HDV_REQUIRED_SECTIONS = (
    "GENERAL", "BODYAERO", "SUSPENSION", "CONTROLS", "ENGINE", "DRIVELINE",
    "FRONTLEFT", "FRONTRIGHT", "REARLEFT", "REARRIGHT",
)

"""
    parse_hdv(text; path="<string>") -> ISIFile

Parse HDV chassis text already in memory.
"""
parse_hdv(text::AbstractString; path::AbstractString="<string>") =
    parse_isi(text; path)

"""
    read_hdv(path; validate=true) -> ISIFile

Read and parse an HDV chassis file.  With `validate`, missing required
sections are appended to `ISIFile.issues` (never thrown: we want the
whole corpus loadable, with problems inspectable).
"""
function read_hdv(path::AbstractString; validate::Bool=true)
    f = parse_hdv(read(path, String); path)
    validate && for name in HDV_REQUIRED_SECTIONS
        section(f, name) === nothing &&
            push!(f.issues, "$(path): missing required section [$name]")
    end
    f
end

"""All files under `root` with extension `ext` (case-insensitive), sorted."""
function find_ext(root::AbstractString, ext::AbstractString)
    found = String[]
    for (dir, _, files) in walkdir(root), file in files
        endswith(lowercase(file), lowercase(ext)) && push!(found, joinpath(dir, file))
    end
    sort!(found)
end

"""
    find_hdv_files(root=default_gamedata()) -> Vector{String}

All `*.hdv` files under `root` (case-insensitive), sorted.
"""
find_hdv_files(root::AbstractString=default_gamedata()) = find_ext(root, ".hdv")
