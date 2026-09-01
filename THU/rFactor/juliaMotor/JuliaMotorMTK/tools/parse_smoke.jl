# parse_smoke.jl — every .jl in the tree must actually PARSE.
#
# WHY THIS EXISTS, and it is not hypothetical: E103-S1 committed a drive_native_mtk.jl in which two
# statements had been joined onto one line, so the sim would not load at all. It was pushed, and the
# suite stayed 18/18 green for four sprints, because NO GATE LOADS THE MAIN SIM FILE -- the gates
# exercise JuliaMotorMTK modules and small shared includes.
#
# Worse, the check I had been running after every edit was inert:
#
#     Meta.parseall(read(f, String))        # "parse ok"
#
# Meta.parseall DOES NOT THROW on a syntax error. It returns an Expr with :error nodes buried in it,
# so the call succeeds and prints nothing whatever the input. Measured: on "function f()\n x = 1\n"
# (no `end`) it returns normally and the top-level args do not even contain a direct :error node.
#
# So: parse, then WALK the tree for :error and :incomplete nodes. The self-test below proves the
# check can fail -- a syntax gate that has never been seen to reject anything is worth nothing.
using Printf

function haserr(x)
    x isa Expr || return false
    (x.head === :error || x.head === :incomplete) && return true
    any(haserr, x.args)
end

function check(path)
    src = read(path, String)
    ex = try
        Meta.parseall(src)
    catch e
        return (false, string(typeof(e)))
    end
    haserr(ex) ? (false, "syntax error") : (true, "")
end

const ROOT = normpath(joinpath(@__DIR__, "..", ".."))
files = String[]
for d in (joinpath(ROOT, "demo", "native"), joinpath(ROOT, "JuliaMotorMTK", "src"),
          joinpath(ROOT, "JuliaMotorMTK", "src", "components"), joinpath(ROOT, "JuliaMotorMTK", "tools"))
    isdir(d) || continue
    for f in readdir(d; join=true)
        endswith(f, ".jl") && push!(files, f)
    end
end

# SELF-TEST FIRST: the check must reject known-bad syntax. A gate that cannot fail proves nothing,
# and the reason this file exists is that the previous check could not.
selfbad = haserr(Meta.parseall("function f()\n  x = 1\n"))
selfok  = !haserr(Meta.parseall("function f()\n  x = 1\nend\n"))
@printf("  self-test: rejects bad syntax = %s, accepts good = %s\n", selfbad, selfok)
if !(selfbad && selfok)
    println("\n  PARSE GATE: BROKEN -- the check cannot tell good from bad")
    exit(2)
end

# In a FUNCTION: `bad += 1` inside a top-level `for` hits Julia's soft-scope rule and throws
# UndefVarError -- the third time that trap has bitten in one session, so it stops being written.
function scan(files)
    bad = 0
    for f in sort(files)
        (ok, why) = check(f)
        ok || (@printf("  FAIL %-60s %s\n", relpath(f, ROOT), why); bad += 1)
    end
    bad
end
bad = scan(files)
@printf("  %d file(s) checked, %d bad\n", length(files), bad)
println(bad == 0 ? "\n  PARSE GATE: PASS ✓" : "\n  PARSE GATE: FAIL ($bad)")
exit(bad == 0 ? 0 : 1)
