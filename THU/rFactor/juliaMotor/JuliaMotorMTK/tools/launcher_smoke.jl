# Launcher gate (TRACKSEG-3, GUI-1): runs every demo/native/tests/*_test.py headless (Qt offscreen), each against its
# own throw-away settings directory, so the user's real launcher settings are never read or written.
dir = normpath(joinpath(@__DIR__, "..", "..", "demo", "native", "tests"))
tests = sort(filter(f -> endswith(f, "_test.py"), readdir(dir)))
fails = String[]
for t in tests
    cmd = addenv(`python3 $(joinpath(dir, t))`, "QT_QPA_PLATFORM" => "offscreen", "XDG_CONFIG_HOME" => mktempdir())
    success(pipeline(cmd; stdout = stdout, stderr = devnull)) || push!(fails, t)
end
println(isempty(fails) ? "LAUNCHER GATE: PASS ($(length(tests)) tests)" : "LAUNCHER GATE: FAIL $(fails)")
exit(isempty(fails) ? 0 : 1)
