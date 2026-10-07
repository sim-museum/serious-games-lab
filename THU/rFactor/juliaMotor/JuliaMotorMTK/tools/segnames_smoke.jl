# TRACKSEG-3 gate: runs demo/native/tests/segnames_test.py headless (Qt offscreen) against a throw-away settings
# directory, so the user's real launcher settings are never read or written.
test = normpath(joinpath(@__DIR__, "..", "..", "demo", "native", "tests", "segnames_test.py"))
cfg = mktempdir()
cmd = addenv(`python3 $test`, "QT_QPA_PLATFORM" => "offscreen", "XDG_CONFIG_HOME" => cfg)
ok = success(pipeline(cmd; stdout = stdout, stderr = devnull))
println(ok ? "SEGNAMES GATE: PASS" : "SEGNAMES GATE: FAIL")
exit(ok ? 0 : 1)
