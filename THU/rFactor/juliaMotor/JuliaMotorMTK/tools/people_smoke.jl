# GATE: the PO's standing loose-people requirement.
#
#   PO 2026-08-27: "remove line-of-people objects if there's any chance they could be in the road
#                   or partially hanging in air."
#
# Two questions, and only the second one is interesting:
#   1. does the predicate classify the names we already know about?  (regression cover)
#   2. does it still COVER THE TRACKS ON DISK?  A by-name filter degrades silently -- it keeps
#      passing its own unit tests while a track added later brings people it has never heard of.
#      So this walks every installed GPL track and reports person-looking objects the filter
#      would NOT drop.
#
# Headless: reads object names off disk, no window, no car.
include(joinpath(@__DIR__, "..", "..", "demo", "native", "people_filter.jl")); using .PeopleFilter

const GPLBASE = normpath(joinpath(@__DIR__, "..", "..", "..", "..", "WP", "drive_c", "Sierra", "GPL", "tracks"))
fails = Ref(0)
function check(name, cond, msg)
    cond || (fails[] += 1)
    println("  ", cond ? "PASS" : "FAIL", "  ", rpad(name, 44), msg)
end

println("PO loose-people gate")

# 1. Known people must drop.
for nm in ("ppl01", "people3", "pelf2", "p_s7", "pform1", "grndp2", "crowd1", "spect4",
           "flagger1", "rescu1", "photo2", "fotograf1", "chrisa", "starter")
    check("drops '$nm'", PeopleFilter.is_loose_person(nm), "")
end

# 2. Things that merely LOOK like people must NOT drop -- this is the half that protects the
#    scene. prinz*/spider* are CARS and p_armco is a barrier; dropping them would be a
#    regression that a people-only test would never notice.
for nm in ("prinz1", "spider2", "p_armco", "pitwall", "grandstand", "armco3", "pole1")
    check("keeps '$nm'", !PeopleFilter.is_loose_person(nm), "")
end

# 3. COVERAGE: what is actually on disk that looks like a person and would survive?
if isdir(GPLBASE)
    suspicious = String[]
    tracks = filter(d -> isdir(joinpath(GPLBASE, d)), readdir(GPLBASE))
    for t in tracks, f in readdir(joinpath(GPLBASE, t))
        endswith(lowercase(f), ".3do") || continue
        nm = lowercase(replace(f, r"\.3do$"i => ""))
        PeopleFilter.is_loose_person(nm) && continue
        # person-looking by any reading a human would give it
        if occursin(r"^(ppl|peop|pers|pel|spec|crowd|zusch|figur|man|woman|kid)", nm)
            push!(suspicious, string(t, "/", nm))
        end
    end
    println("  scanned ", length(tracks), " track(s): ", join(tracks, ", "))
    check("no person-looking object survives the filter", isempty(suspicious),
          isempty(suspicious) ? "none" : string(length(suspicious), ": ", join(first(suspicious, 8), " ")))
else
    println("  (GPL tracks not found at $GPLBASE -- coverage arm skipped)")
end

println(fails[] == 0 ? "PEOPLE GATE: PASS" : "PEOPLE GATE: FAIL ($(fails[]))")
exit(fails[] == 0 ? 0 : 1)
