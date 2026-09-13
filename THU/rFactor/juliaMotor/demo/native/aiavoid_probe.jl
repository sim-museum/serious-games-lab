# AI-AVOID-1 headless probe: exercise the AI the RACE actually runs.
#
# ai_field_smoke drives `step_field!` (the kinematic field). The race drives `plan!` (the
# hybrid-physics brain) -- two different implementations in ai.jl, and until this file `plan!` had
# NO headless coverage at all, so the PO's "the AI are not very good at avoiding collision" could
# not be measured, only argued about.
#
# `plan!` decides target rail and target speed without moving anything, so the probe supplies the
# motion the game's physics+controller normally would: advance v toward vt, s by v*dt, and slew the
# lane toward (racing line + tlane) at the same 2.4 m/s the kinematic field uses. That is a
# simplification of the car model, deliberately -- the question here is what the BRAIN decides, and
# the brain only ever sees s / lane / v.
#
# Spa, not Monza: the defect is corner-specific (`straight` is a radius > 75 m) and Monza is mostly
# straights, which is exactly why the existing gate could not see it.
#
# Arms via env: JM_AI_AVOID_CORNER (the fix), JM_AI_GPLLINE / JM_AI_GAPCTL as usual.
include("gpldat.jl"); using .GPLDat; include("gpltrack.jl"); using .GPLTrack; include("ai.jl"); using .RaceAI
using Statistics, Random
Random.seed!(11)

T = get(ENV, "JM_AVOID_TRACK", "/home/admin/sgl-julia-racer/THU/WP/drive_c/Sierra/GPL/tracks/spa")
name = basename(T)
# The .DAT case varies by track (monza.DAT, spa.dat), so find it rather than guessing.
datfile = let c = filter(f -> lowercase(f) == lowercase(name)*".dat", readdir(T))
    isempty(c) && error("no $(name).dat in $T -- have: $(join(first(readdir(T), 12), ", "))")
    joinpath(T, first(c))
end
d = GPLDat.parse_dat(datfile); tmp = tempname()*".trk"
trkkey = let k = filter(x -> lowercase(x) == lowercase(name)*".trk", collect(keys(d)))
    isempty(k) && error("no $(name).trk inside $datfile -- have: $(join(first(collect(keys(d)), 12), ", "))")
    first(k)
end
write(tmp, d[trkkey])
line = RaceAI.build_line(GPLTrack.trk_centreline(tmp), (x,z) -> 0.0)

N     = parse(Int,     get(ENV, "JM_AVOID_CARS",  "6"))
secs  = parse(Int,     get(ENV, "JM_AVOID_SECS",  "300"))
warm  = parse(Int,     get(ENV, "JM_AVOID_WARM",  "20"))
dt    = 1/60
amax  = 8.0; vmax = 74.0

cars = RaceAI.init_cars(line, N; start_s = 30.0)
# S3: the probe advances `s` itself and never touches `car.lap`, so `sum(c.lap)` was always 0 and the
# denominator was broken. Accumulate distance instead, as e89_field_probe does.
travelled = zeros(N)
for (i, c) in enumerate(cars); c.pace = 1.0 + 0.01*(i-2); end
RaceAI.aistat_reset!()

# A CONTACT is two cars within a car length longitudinally AND inside a car width laterally --
# i.e. occupying the same piece of road. Counted as EPISODES (rising edge), not frames, so one long
# scrape is one event; and split by whether the road there is a corner, because the PO's complaint
# is specifically that straights are fine.
CAR_LEN = 3.8; CAR_WID = 1.7
# S2 measured Spa: median radius 2500 m, p90 275 m, only 0.5 % of the lap under the code's own 75 m
# `straight` threshold. So "corner" must be a SWEEPABLE parameter here, not the code's constant --
# the whole S3 question is what radius the AI should stop treating as a straight.
CORNER_R = parse(Float64, get(ENV, "JM_AVOID_CORNER_R", "300.0"))   # metres; corner if radius < this
CORNER_K = 1.0 / CORNER_R
pairs   = [(i,j) for i in 1:N for j in (i+1):N]
intouch = Dict(p => false for p in pairs)
corner_contacts = 0; straight_contacts = 0
# S3: record the RADIUS at every contact. Sweeping a classification threshold answers the question
# indirectly and needs one run per value; the radii themselves answer it in one run and cannot be
# biased by the threshold I happened to pick.
contact_radii = Float64[]
minsep_corner = Inf
frames_in_corner = 0

for f in 1:secs*60
    vts = RaceAI.plan!(cars, line; player = nothing, amax = amax, vmax = vmax, dt = dt)
    for (i, c) in enumerate(cars)
        c.v = RaceAI.advance_speed(c.v, vts[i], dt)
        c.s = mod(c.s + c.v*dt, line.total); travelled[i] += c.v*dt
        tgt = RaceAI.racelane(line, c.s) + c.tlane
        c.lane += clamp(tgt - c.lane, -2.4*dt, 2.4*dt)
    end
    f <= warm*60 && continue
    for p in pairs
        i, j = p
        dl = mod(cars[i].s - cars[j].s, line.total); dl = min(dl, line.total - dl)
        dw = abs(cars[i].lane - cars[j].lane)
        touching = dl < CAR_LEN && dw < CAR_WID
        if touching && !intouch[p]
            κ = line.κ[RaceAI._locate(line, cars[i].s)[1]]
            push!(contact_radii, κ > 1e-6 ? 1.0/κ : Inf)
            κ > CORNER_K ? (global corner_contacts += 1) : (global straight_contacts += 1)
        end
        intouch[p] = touching
        κ2 = line.κ[RaceAI._locate(line, cars[i].s)[1]]
        if κ2 > CORNER_K && dl < CAR_LEN*3
            global minsep_corner = min(minsep_corner, dw)
            global frames_in_corner += 1
        end
    end
end

laps = sum(travelled) / line.total
println("AI-AVOID probe: track=", name, " cars=", N, " secs=", secs,
        " AVOID_CORNER=", get(ENV, "JM_AI_AVOID_CORNER", "1"),
        "  corner<", CORNER_R, "m")
println("  contact episodes in CORNERS   ", corner_contacts,
        "   per car-lap ", laps > 0 ? round(corner_contacts/laps, digits=3) : -1.0)
println("  contact episodes on STRAIGHTS ", straight_contacts)
println("  min lateral separation in corners (when within 3 car lengths) ",
        isfinite(minsep_corner) ? round(minsep_corner, digits=3) : -1.0, " m")
println("  corner-proximity frames ", frames_in_corner, "  car-laps ", laps)
println("  fix firings (AVOIDSTAT) ", RaceAI.AVOIDSTAT[])
if !isempty(contact_radii)
    r = sort(filter(isfinite, contact_radii))
    if !isempty(r)
        q(p) = r[clamp(round(Int, p*length(r)), 1, length(r))]
        println("  RADIUS AT CONTACT (m): min ", round(r[1],digits=0), "  p25 ", round(q(0.25),digits=0),
                "  median ", round(q(0.5),digits=0), "  p75 ", round(q(0.75),digits=0),
                "  max ", round(r[end],digits=0))
        for thr in (75.0, 150.0, 300.0, 500.0, 1000.0)
            println("    contacts at radius < ", Int(thr), " m: ", count(<(thr), r), " / ", length(r))
        end
    end
end
