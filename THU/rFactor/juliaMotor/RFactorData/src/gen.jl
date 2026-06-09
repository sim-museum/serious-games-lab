# GEN graphics files (vehicle .gen / spinner .gen).
#
# Graphics-only — irrelevant to physics, parsed for completeness of the
# VEH wiring.  Structure differs from the rest of the family: flat
# statements (SearchPath=, MASFile=) plus `Instance=NAME` followed by a
# `{ ... }` block whose lines carry several pairs:
#
#   MeshFile=BRM_body.gmt CollTarget=False LODIn=(0.0) LODOut=(4.0)
#
# Brace discipline in the corpus is loose (blocks left unclosed before the
# next Instance=), so nesting is tolerated rather than enforced: `{` opens
# a block attached to the most recent statement, `}` closes the innermost,
# a new `Instance=` at top level implicitly closes anything left open.

struct GENStatement
    pairs::Vector{Tuple{String,Any}}      # parsed key/value pairs of the line
    block::Vector{GENStatement}           # the { ... } block that followed, if any
    condition::String                     # upgrade directive prefix, e.g. "CORTAS"
    line::Int
end

key(st::GENStatement) = isempty(st.pairs) ? "" : st.pairs[1][1]
value(st::GENStatement) = isempty(st.pairs) ? nothing : st.pairs[1][2]

struct GENFile
    path::String
    statements::Vector{GENStatement}
    issues::Vector{String}
end

Base.show(io::IO, g::GENFile) =
    print(io, "GENFile(\"", basename(g.path), "\", ",
          length(g.statements), " top-level statements",
          isempty(g.issues) ? "" : ", $(length(g.issues)) issues", ")")

"""All statements (any depth) whose first key matches, e.g. `"MeshFile"`."""
function gen_statements(g::GENFile, k::AbstractString)
    out = GENStatement[]
    stack = copy(g.statements)
    while !isempty(stack)
        st = popfirst!(stack)
        isequal_ci(key(st), k) && push!(out, st)
        append!(stack, st.block)
    end
    out
end

"""
    parse_gen(text; path="<string>") -> GENFile
"""
function parse_gen(text::AbstractString; path::AbstractString="<string>")
    issues = String[]
    top = GENStatement[]
    stack = [top]                  # innermost block last
    last_at_depth = Union{GENStatement,Nothing}[nothing]
    forced_closes = 0              # blocks implicitly closed by a new Instance=

    for (lineno, rawline) in enumerate(split(text, '\n'))
        body, _ = split_comment(rstrip(rawline, ['\r']))
        body = strip(body)
        isempty(body) && continue

        # upgrade directives may stand alone (<STARTUPGRADES>) or prefix a
        # statement or brace (<CORTAS> { ... <CORTAS> })
        condition = ""
        if (m = match(r"^<([^<>]+)>\s*(.*)$", body)) !== nothing
            condition = String(strip(m.captures[1]))
            body = strip(m.captures[2])
            if isempty(body)
                st = GENStatement([("directive", condition)], GENStatement[], "", lineno)
                push!(stack[end], st)
                continue
            end
        end

        if body == "{"
            owner = last_at_depth[end]
            if owner === nothing
                push!(issues, "$(path):$(lineno): '{' with no owning statement, skipped block marker")
                continue
            end
            push!(stack, owner.block)
            push!(last_at_depth, nothing)
            continue
        elseif body == "}"
            if length(stack) > 1
                pop!(stack); pop!(last_at_depth)
            elseif forced_closes > 0
                forced_closes -= 1   # delayed close of a force-closed block
            else
                push!(issues, "$(path):$(lineno): unmatched '}'")
            end
            continue
        end

        if !occursin('=', body)
            push!(issues, "$(path):$(lineno): no '=', skipped: $(body)")
            continue
        end

        # corpus leaves Instance blocks unclosed: a new Instance= while
        # nested pops back to top level
        if length(stack) > 1 && match(r"^instance\s*="i, body) !== nothing
            forced_closes += length(stack) - 1
            resize!(stack, 1); resize!(last_at_depth, 1)
        end

        st = GENStatement([(k, parse_value(v))
                           for (k, v) in split_pairs(String(body), issues, path, lineno)],
                          GENStatement[], condition, lineno)
        push!(stack[end], st)
        last_at_depth[end] = st
    end
    GENFile(String(path), top, issues)
end

"""
    read_gen(path) -> GENFile
"""
read_gen(path::AbstractString) = parse_gen(readtext(path); path)

find_gen_files(root::AbstractString=default_gamedata()) = find_ext(root, ".gen")
