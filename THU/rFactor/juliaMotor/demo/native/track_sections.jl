# TRACKSEG-1 (PO 2026-10-04): "in GPL, nurunberg has trackside signs labeling which section of the track, e.g.
# flugplatz, swedencriz, hoch oct, you are on. Create a similar effect by printing out the name of the track
# segment, at top center of the julia 3D view, for a few seconds when you enter it, e.g. esses, carossel, big
# bend at watkins glen."
#
# Each entry is (s, name): the segment starts at .trk lap distance s [m] and runs to the next entry. `lap` is
# the .trk's own lap length; the sim scales s by its ribbon lap (≤ 0.4 % longer) when it loads the table.
#
# Where the names and positions come from:
#   * nurburgring -- GPL's OWN section boards: the 23 Papyrus `s_*` objects in nurburg.dat (s_flug = Flugplatz,
#     s_schwed = Schwedenkreuz, s_hohe = Hohe Acht, ...; text read off their textures), each projected onto the
#     sim's ribbon (JuliaMotorMTK/tools/section_signs.jl). A board stands at the corner it names (the Karussell
#     board is at 13,846 m, the 220° left at 13,852). Südkehre and Nordkehre, the pits loop before the first
#     board, are placed from the .trk arcs.
#   * the other tracks have no boards. Names are the ones on the BAPOM maps GPL ships with each track
#     (tracks/<t>/map-<t>.pdf), matched in order to the corners of the .trk arcs
#     (JuliaMotorMTK/tools/track_corners.jl): s is where the named corner's first arc begins (a straight's
#     name starts where the corner before it ends). Watkins Glen's "The Loop" is shown as "Carousel", the PO's
#     name for it.
const TRACK_SECTIONS = Dict(
    "nurburgring" => (lap = 22815.2, secs = [
        (0.0,     "Start und Ziel"),
        (574.0,   "Südkehre"),
        (1760.0,  "Nordkehre"),
        (2571.4,  "Hatzenbach"),
        (3984.7,  "Flugplatz"),
        (5258.3,  "Schwedenkreuz"),
        (5626.4,  "Aremberg"),
        (6349.2,  "Fuchsröhre"),
        (6913.5,  "Adenauer Forst"),
        (7776.0,  "Metzgesfeld"),
        (8133.4,  "Kallenhard"),
        (9157.1,  "Wehrseifen"),
        (9869.1,  "Ex-Mühle"),
        (10686.0, "Bergwerk"),
        (11924.6, "Kesselchen"),
        (13133.8, "Klostertal"),
        (13845.8, "Karussell"),
        (14764.7, "Hohe Acht"),
        (15046.9, "Wippermann"),
        (15501.0, "Brünnchen"),
        (15944.3, "Eschbach"),
        (17107.8, "Pflanzgarten"),
        (18553.4, "Schwalbenschwanz"),
        (19577.1, "Döttinger Höhe"),
        (21557.4, "Antoniusbuche"),
        (21992.7, "Tiergarten")]),
    "watglen" => (lap = 3755.5, secs = [
        (329.0,  "Esses"),
        (806.0,  "Front Straight"),
        (1596.0, "Carousel"),
        (1942.0, "Back Straight"),
        (2461.0, "The Speed Trap"),
        (3065.0, "Big Bend"),
        (3524.0, "The \"90\"")]),
    "monza" => (lap = 5749.7, secs = [
        (950.0,  "Curva Grande"),
        (1672.0, "Della Roggia"),
        (2135.0, "Lesmos"),
        (2918.0, "Serraglio"),
        (3456.0, "Ascari"),
        (3952.0, "Rettifilo Centrale"),
        (4803.0, "Parabolica")]),
    "spa" => (lap = 14112.0, secs = [
        (220.0,   "L'Eau Rouge"),
        (1843.0,  "Les Combes"),
        (3340.0,  "Burnenville"),
        (4231.0,  "Malmedy"),
        (6491.0,  "Masta"),
        (7924.0,  "Stavelot"),
        (9925.0,  "La Carrière"),
        (12104.0, "Blanchimont"),
        (13643.0, "La Source")]),
    "zandvoort" => (lap = 4190.5, secs = [
        (331.0,  "Tarzanbocht"),
        (592.0,  "Gerlachbocht"),
        (846.0,  "Hugenholtzbocht"),
        (1082.0, "Hunzerug"),
        (1286.0, "Zijn Veld"),
        (1465.0, "Jan de Wyker"),
        (1683.0, "Scheivlak"),
        (2157.0, "Hondenvlak"),
        (2872.0, "Tunnel Oost"),
        (3115.0, "Panoramabocht"),
        (3275.0, "Pulleveld"),
        (3506.0, "Huzaren Vlak")]),
)

# TRACKSEG-2 (PO 2026-10-04: "when a track section name is not in English, and when it has an English translation, include
# the English translation in parentheses after track section name"). Generic words only; place and person names (Hatzenbach,
# Burnenville, Ascari, Tarzan ...) have none and stay as they are. JM_SEGNAME_EN=0 shows the bare names.
const SECTION_EN = Dict(
    # Nürburgring (German)
    "Start und Ziel" => "Start and Finish", "Südkehre" => "South Hairpin", "Nordkehre" => "North Hairpin",
    "Flugplatz" => "Airfield", "Schwedenkreuz" => "Swedish Cross", "Fuchsröhre" => "Foxhole",
    "Adenauer Forst" => "Adenau Forest", "Ex-Mühle" => "Ex-Mill", "Bergwerk" => "Mine", "Kesselchen" => "Little Cauldron",
    "Klostertal" => "Monastery Valley", "Karussell" => "Carousel", "Hohe Acht" => "High Eight", "Brünnchen" => "Little Well",
    "Pflanzgarten" => "Plant Garden", "Schwalbenschwanz" => "Swallow's Tail", "Döttinger Höhe" => "Dötting Heights",
    "Antoniusbuche" => "St Anthony's Beech", "Tiergarten" => "Animal Park",
    # Monza (Italian)
    "Curva Grande" => "Big Curve", "Rettifilo Centrale" => "Central Straight", "Parabolica" => "Parabolic",
    # Spa (French)
    "L'Eau Rouge" => "Red Water", "La Carrière" => "The Quarry", "La Source" => "The Spring",
    # Zandvoort (Dutch)
    "Tarzanbocht" => "Tarzan Bend", "Gerlachbocht" => "Gerlach Bend", "Hugenholtzbocht" => "Hugenholtz Bend",
    "Hondenvlak" => "Dogs' Flat", "Tunnel Oost" => "Tunnel East", "Panoramabocht" => "Panorama Bend",
    "Huzaren Vlak" => "Hussars' Flat")
section_label(n) = (get(ENV, "JM_SEGNAME_EN", "1") != "0" && haskey(SECTION_EN, n)) ? string(n, " (", SECTION_EN[n], ")") : n

"""Section boundaries for `track`, scaled onto a ribbon of length `laplen`: a sorted Vector{Tuple{Float64,String}}
(empty if the track has none)."""
function track_sections(track::AbstractString, laplen::Real)
    t = get(TRACK_SECTIONS, track, nothing)
    t === nothing && return Tuple{Float64,String}[]
    k = laplen / t.lap
    sort!([(s*k, section_label(n)) for (s, n) in t.secs]; by = first)
end

"Index of the section containing lap distance `s` (the last boundary at or before it; wraps to the last section)."
function section_at(secs, s::Real, laplen::Real)
    isempty(secs) && return 0
    s = mod(s, laplen)
    i = searchsortedlast(secs, (s, ""); by = first)
    i == 0 ? length(secs) : i
end

"""Per-frame update of the section banner. Returns the new (current index, banner text, banner start time).
A banner starts only once the car is ≥ `hyst` metres into a new section, so lap-distance jitter on a
boundary cannot make it flicker, and the first call only records where the car is (no banner at spawn)."""
function section_update(secs, s::Real, laplen::Real, t::Real, cur::Int, text::String, t0::Float64; hyst = 3.0)
    isempty(secs) && return (0, text, t0)
    i = section_at(secs, s, laplen)
    cur == 0 && return (i, text, t0)
    (i == cur || section_at(secs, s - hyst, laplen) != i) && return (cur, text, t0)
    (i, secs[i][2], Float64(t))
end
