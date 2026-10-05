# serious_games_week.jl — Julia Racer's side of the Serious Games Week matchmaker (github.com/sim-museum/serious-games-week).
#
# Serious Games Week is an iGOR-style lobby the PLAYER chooses: `sgw url http://<matchmaker>:8090` (or $SGW_URL). The racer talks
# to it through the `sgw` client, never directly, the same way MiG Alley, Battle of Britain, FreeFalcon, pokerIQ and
# bridgeIQ do:
#   hosting -> `sgw announce --game juliaracer ...` runs for as long as the race is hosted; we hold its stdin, so the
#              listing is withdrawn when the racer exits. Racing is Thursday's game: on another day the matchmaker
#              refuses the listing (the race still runs for drivers who know the address) and sgw says why.
#   joining -> `sgw list --game juliaracer` gives "host port players title" lines; JM_NET=join with no JM_NET_HOST
#              (or JM_NET_HOST=matchmaker) joins the first race listed.
# Inert unless a matchmaker is configured. SGW_OFF=1 disables it. Pure stdlib, like netplay.jl.
module SeriousGamesWeek

export matchmaker_configured, matchmaker_announce, matchmaker_withdraw, matchmaker_races

const GAME_ID = "juliaracer"

function matchmaker_configured()
    haskey(ENV, "SGW_OFF") && return false
    isempty(get(ENV, "SGW_URL", "")) || return true
    for p in (joinpath(homedir(), ".config", "sgw", "url"),
              joinpath(homedir(), ".config", "sgweek", "url"))   # second: read-only fallback, setups before 2026-10-05
        isfile(p) && return !isempty(strip(readline(p)))
    end
    false
end

"""The sgw command: \$SGW_BIN, the AppImage's own, ~/serious-games-week/sgw.py, or `sgw` on PATH."""
function sgw_cmd()
    cands = String[get(ENV, "SGW_BIN", "")]
    haskey(ENV, "APPDIR") && push!(cands, joinpath(ENV["APPDIR"], "usr", "bin", "sgw"))
    push!(cands, joinpath(homedir(), "serious-games-week", "sgw.py"))
    for c in cands
        isempty(c) || !isfile(c) || return endswith(c, ".py") ? `python3 $c` : `$c`
    end
    p = Sys.which("sgw")
    p === nothing ? nothing : `$p`
end

const ANNOUNCE = Ref{Union{Base.Process,Nothing}}(nothing)

"""List this hosted race on the matchmaker until the racer exits (or `matchmaker_withdraw()`)."""
function matchmaker_announce(port::Integer, title::AbstractString; name::AbstractString = "", max_players::Integer = 0)
    (ANNOUNCE[] === nothing && matchmaker_configured()) || return false
    cmd = sgw_cmd()
    cmd === nothing && (println("  matchmaker:  no sgw client found"); return false)
    args = `announce --game $GAME_ID --port $port --title $title --max $max_players`
    isempty(name) || (args = `$args --name $name`)
    # sgw's own messages ("listed as ...", or why today refuses racing) go to our stdout
    ANNOUNCE[] = open(pipeline(`$cmd $args`, stdout = stdout, stderr = stdout), "w")
    atexit(matchmaker_withdraw)
    println("  matchmaker:  announcing \"", title, "\" on udp/", port); flush(stdout)
    true
end

function matchmaker_withdraw()
    p = ANNOUNCE[]
    p === nothing && return
    ANNOUNCE[] = nothing
    try
        close(p.in)                       # sgw withdraws the listing and exits
        t = time(); while process_running(p) && time() - t < 5; sleep(0.05); end
        process_running(p) && kill(p)
    catch
    end
    nothing
end

"""Races the matchmaker lists: [(host, port, players, title)], or []."""
function matchmaker_races()
    matchmaker_configured() || return Tuple{String,Int,Int,String}[]
    cmd = sgw_cmd()
    cmd === nothing && return Tuple{String,Int,Int,String}[]
    out = try
        read(pipeline(`$cmd list --game $GAME_ID`, stderr = devnull), String)
    catch
        ""
    end
    races = Tuple{String,Int,Int,String}[]
    for l in split(out, '\n'; keepempty = false)
        f = split(l, ' '; limit = 4)
        length(f) >= 3 || continue
        port = tryparse(Int, f[2]); pl = tryparse(Int, f[3])
        (port === nothing || pl === nothing) && continue
        push!(races, (String(f[1]), port, pl, length(f) == 4 ? String(f[4]) : ""))
    end
    races
end

end # module
