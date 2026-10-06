# gplsetup_decode.jl — read a GPL car setup file (.kj1 = Lotus 49, …) and print it in GPL's own units,
# plus the physical (SI) values used to translate it to an iRacing garage (WWSETUP-1).
#
#   julia gplsetup_decode.jl <setup file> [...]
#
# Layout from gpl.exe's own serialiser (FUN_004892c0, chunk 'PGTS' version 3, 249 bytes after a
# 12-byte header). Units from the garage formatters: pressure psi (x6.895 kPa), wheel/roll-bar rate
# lb/in, camber deg, toe / bump rubber / ride in inches (x2.54 cm), fuel US gal (x3.785 L).
# GPL clamps static ride to 2.5..5 in on load, so a stored 1.0 (old files) drives as 2.5.
# The two ramp angles are stored as a pair; GPL never labels them. Read here as power/coast.

const LBIN = 0.175127          # lb/in -> N/mm

function gplsetup(path)
    b = read(path)
    String(b[1:4]) == "PGTS" || error("$path: not a GPL setup (magic $(String(b[1:4])))")
    f(o, n) = [reinterpret(Float32, b[o+1+4k:o+4+4k])[1] for k in 0:n-1]
    i(o, n) = [reinterpret(Int32,   b[o+1+4k:o+4+4k])[1] for k in 0:n-1]
    g = f(0x0c, 9)                                   # R, N, 1st..6th, final drive
    (; gears = g[3:8], final = g[9], ramp = f(0x54, 2), psi = f(0x5c, 4), rate = f(0x6c, 4),
       bump = i(0x7c, 4), rebound = i(0x8c, 4), camber = f(0x9c, 4), rubber = f(0xcc, 4),
       toe = f(0xdc, 2), arb = f(0xe4, 2), ride = clamp.(f(0xec, 2), 2.5, 5.0),
       clutches = i(0xf4, 1)[1], fuel_gal = f(0xf8, 1)[1], steer = f(0xfc, 1)[1], bias = i(0x100, 1)[1])
end

function show_setup(path)
    s = gplsetup(path)
    r(x, d=2) = round(x; digits=d)
    println("== ", basename(path), "   (corners LF RF LR RR, axles F R)")
    println("  tyre pressure  ", s.psi, " psi  = ", r.(s.psi .* 6.895, 0), " kPa")
    println("  wheel rate     ", s.rate, " lb/in = ", r.(s.rate .* LBIN), " N/mm")
    println("  bump/rebound   ", s.bump, " / ", s.rebound, "   (GPL clicks 1..5)")
    println("  camber         ", s.camber, " deg")
    println("  bump rubber    ", s.rubber, " in")
    println("  toe F R        ", s.toe, " in = ", r.(s.toe .* 25.4, 1), " mm   (negative = toe-out)")
    println("  roll bar F R   ", s.arb, " lb/in")
    println("  static ride    ", s.ride, " in")
    println("  gears          ", r.(s.gears, 3), " x final ", r(s.final, 3), "  -> overall ", r.(s.gears .* s.final, 3))
    println("  ramps          ", s.ramp, " deg (power/coast)   clutches ", s.clutches)
    println("  fuel ", s.fuel_gal, " US gal = ", r(s.fuel_gal * 3.785, 1), " L   steering ", s.steer, ":1   brake bias ", s.bias, " % front")
end

abspath(PROGRAM_FILE) == @__FILE__() && foreach(show_setup, ARGS)
