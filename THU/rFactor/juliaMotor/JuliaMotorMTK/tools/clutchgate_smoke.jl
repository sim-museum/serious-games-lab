# GATE: the refused-G clutch gate must not kill the session.
#
#   PO 2026-08-29: "Make auto easy, I never use it so I don't care. Make manual right.
#                   Require that the slider be down before you can enter manual mode."
#
# WHY THIS EXISTS. The refusal path added on 2026-09-01 set `CLUTCH_GATE[] = 2.0` from
# `read_input()` so the gate could be shown on screen. But the Ref was declared as a LOCAL of
# `main()`, so `read_input` referenced a *global* of that name which did not exist. Every refused
# G -- press G in AUTO with the slider up, exactly what the rule above tells you to do -- raised
#     UndefVarError: `CLUTCH_GATE` not defined in `Main`
# and ended the race. It cost the PO a session 30 minutes into a Watkins Glen race, and no gate
# caught it because the file parses fine: a write to an undefined global is a RUNTIME error.
#
# This is a scope check, not a physics check, so it reads the source rather than driving a car:
# the binding the writer sees and the binding the reader sees must be the SAME one.
#
# Headless: pure text, no window, no car.

const SRC = normpath(joinpath(@__DIR__, "..", "..", "demo", "native", "drive_native_mtk.jl"))

fails = Ref(0)
check(name, cond, msg) = (cond || (fails[] += 1); println("  ", cond ? "PASS" : "FAIL", "  ", rpad(name, 52), msg))

"""Scope verdict for `name` in `src`: module-level `const` binding? shadowing local? used?"""
function scopecheck(src::AbstractString, name::AbstractString)
    lines = split(src, '\n')
    modconst = any(l -> occursin(Regex("^const\\s+$name\\s*="), l), lines)          # column 0 = module scope
    shadow   = any(l -> occursin(Regex("^\\s+$name\\s*=\\s*Ref\\("), l), lines)     # indented = a local
    uses     = count(l -> occursin(Regex("$name\\s*\\["), l), lines)
    (modconst = modconst, shadow = shadow, uses = uses)
end

println("Clutch-gate scope gate (PO: refused G must not end the session)")

src = read(SRC, String)
r   = scopecheck(src, "CLUTCH_GATE")

check("CLUTCH_GATE has a module-scope binding", r.modconst,
      r.modconst ? "const at column 0" : "NOT defined at module scope — a write from read_input() throws")
check("no shadowing local rebinds it", !r.shadow,
      r.shadow ? "an indented `CLUTCH_GATE = Ref(...)` splits writer from reader" : "none")
check("the gate is actually wired up", r.uses >= 2, "$(r.uses) CLUTCH_GATE[] sites")

# NEGATIVE CONTROL. A gate that cannot fail proves nothing, so re-run the same check against the
# code as it was before the fix and require that it FAILS. Reconstructed here rather than read from
# a stale backup so the control travels with the repo.
buggy = """
function read_input()
    CLUTCH_GATE[] = 2.0
end
function main()
    CLUTCH_GATE = Ref(-1.0)
    CLUTCH_GATE[] > 0 && (CLUTCH_GATE[] -= dt)
end
"""
b = scopecheck(buggy, "CLUTCH_GATE")
check("control: the pre-fix shape is detected", !b.modconst && b.shadow,
      "local-only binding flagged as the bug it was")

println()
println(fails[] == 0 ? "  CLUTCH-GATE SCOPE GATE: PASS ✓" : "  CLUTCH-GATE SCOPE GATE: FAIL ($(fails[]))")
exit(fails[] == 0 ? 0 : 1)
