# Loose-people name filter — shared by the sim's drop() and by the gate that checks it.
#
# PO 2026-08-27, standing: "remove line-of-people objects if there's any chance they could be in
# the road or partially hanging in air."
#
# The rule is by NAME, not by texture: the seated grandstand/pit-wall crowds are KEPT (they are
# part of the scene and sit safely off-track), and only LOOSE standing figures go — the ones GPL
# scatters at ground level, which is exactly the population that can end up straddling the road
# or floating when a placement is off.
#
# Extracted (E101) because the sim held this list inside a closure where nothing could test it,
# and a name list is the kind of thing that silently stops covering a track someone adds later.
module PeopleFilter
export is_loose_person

# Named loose figures that carry no useful prefix. NB deliberately NOT prinz*/spider* — those are
# CARS — and not p_armco/p_* generally, which is why the p_s prefix below is that narrow.
const NAMED = ("chrisa", "sergioa", "thomasa", "hatzia", "stefana", "starter")

# E101: "people" widened to "peop" and "person" added, because the COVERAGE arm of
# tools/people_smoke.jl found eleven figures on disk this list had never heard of:
# mosport/peopflag and person1..6 across rouen, silver and snett67. That is exactly the silent
# degradation a by-name filter suffers -- it kept passing every test written about it while not
# covering four installed tracks. Found by scanning the tracks, not by re-reading the list.
const PREFIXES = ("ppl", "peop", "person", "pelf",   # loose standing spectators
                  "p_s",                       # Spa scattered standing sprites
                  # TD261013-1 S11 (PO 2026-10-14: "the spa house on the other side of the road on the 90 degree left turn
                  # must be in the GPL data, as it displays when running wine GPL"): `pform` was listed here as a
                  # "photographer" -- it is the MARSHAL'S HUT (pform1.3do: 1.4 x 1.6 m, 2.7 m tall, pfrnt1/pside1/pside2),
                  # the dark hut behind the rail at the exit of Spa's 90 deg left (gold 260802 Spa cockpit t 78). Kept now.
                  "grndp", "crowd", "spect",   # ground-level crowd rows
                  "flagger", "rescu",          # marshals
                  "photo", "fotograf")         # photographers

"""True if `nm` (lowercase object name) is a LOOSE person that must not be placed."""
is_loose_person(nm::AbstractString) = (nm in NAMED) || any(p -> startswith(nm, p), PREFIXES)

end
