# TRACKSEG-4 (PO 2026-10-07): section names stay up twice as long (6 s) and EVERY non-English name carries an English
# handle in parentheses ("even if the translation is wrong or even absurd"). Checks the table, not a render:
#   * every section of every track has an English label, except names that are English already;
#   * the labels fit the HUD band: at most 48 characters;
#   * the sim's default display time is 6 s.
const ROOT = joinpath(@__DIR__, "..", "..", "demo", "native")
include(joinpath(ROOT, "track_sections.jl"))
const ENGLISH = Set(["Esses", "Front Straight", "Carousel", "Back Straight", "The Speed Trap", "Big Bend", "The \"90\""])
ok = true
check(c, msg) = (global ok &= c; println(c ? "  PASS  " : "  FAIL  ", msg); c)
missing_en = String[]; long = String[]
for (trk, t) in TRACK_SECTIONS, (_s, n) in t.secs
    n in ENGLISH || haskey(SECTION_EN, n) || push!(missing_en, "$trk: $n")
    length(section_label(n)) <= 48 || push!(long, section_label(n))
end
check(isempty(missing_en), "every non-English section name has an English handle" * (isempty(missing_en) ? "" : " -- missing: " * join(missing_en, ", ")))
check(isempty(long), "labels fit the band (<= 48 chars)" * (isempty(long) ? "" : ": " * join(long, ", ")))
check(section_label("Stavelot") == "Stavelot (Stable Lot)", "a place name now reads with its handle: $(section_label("Stavelot"))")
src = read(joinpath(ROOT, "drive_native_mtk.jl"), String)
check(occursin("get(ENV, \"JM_SEGNAME_SECS\", \"6.0\")", src), "names stay up 6 s by default (was 3)")
println("TRACKSEG GATE: ", ok ? "PASS" : "FAIL"); exit(ok ? 0 : 1)
