# LOOPSPLIT-1: which main() locals a block of drive_native_mtk.jl main() reads (its arguments if moved) and whether it leaks any.
# usage: julia main_blockscan.jl <file> <line0> <line1>
f = ARGS[1]; l0 = parse(Int, ARGS[2]); l1 = parse(Int, ARGS[3])
src = read(f, String); lines = split(src, '\n')
ex = Meta.parseall(src; filename = f)
# main(): inside const _MAIN_Q = quote ... function main() ... end end
qi = findfirst(x -> x isa Expr && x.head == :const && x.args[1] isa Expr && x.args[1].args[1] === :_MAIN_Q, ex.args)
q = ex.args[qi].args[1].args[2]
fm = q.args[1].args[findfirst(x -> x isa Expr && x.head == :function, q.args[1].args)]
assigned = Set{Symbol}()
function walk_assign(e)
    e isa Expr || return
    if e.head in (:(=), :(+=), :(-=), :(*=), :(/=), :(|=), :(&=)) 
        lhs = e.args[1]
        lhs isa Symbol && push!(assigned, lhs)
        lhs isa Expr && lhs.head == :tuple && foreach(a -> a isa Symbol && push!(assigned, a), lhs.args)
        lhs isa Expr && lhs.head == :call && lhs.args[1] isa Symbol && push!(assigned, lhs.args[1])   # f(x) = ...
    elseif e.head == :for
        it = e.args[1]; it isa Expr && it.head == :(=) && it.args[1] isa Symbol && push!(assigned, it.args[1])
    elseif e.head == :function
        s = e.args[1]; s isa Expr && s.head == :call && s.args[1] isa Symbol && push!(assigned, s.args[1])
    elseif e.head == :local
        foreach(a -> a isa Symbol && push!(assigned, a), e.args)
    end
    foreach(walk_assign, e.args)
end
walk_assign(fm.args[2])
blk = Meta.parse("begin\n" * join(lines[l0:l1], "\n") * "\nend")
used = Set{Symbol}(); asg = Set{Symbol}()
function walk(e)
    e isa Symbol && push!(used, e)
    e isa Expr || return
    if e.head in (:(=), :(+=), :(-=)) && e.args[1] isa Symbol; push!(asg, e.args[1]); end
    e.head == :quote && return
    foreach(walk, e.args)
end
walk(blk)
args = sort(collect(intersect(used, assigned)))
println("reads main() locals: ", join(args, ", "))
println("assigns main() locals: ", join(sort(collect(intersect(asg, assigned))), ", "))
loopv = Set{Symbol}()
function walkfor(e)
    e isa Expr || return
    if e.head == :for
        it = e.args[1]
        its = it isa Expr && it.head == :block ? it.args : [it]
        for x in its
            x isa Expr && x.head == :(=) || continue
            v = x.args[1]; v isa Symbol && push!(loopv, v)
            v isa Expr && v.head == :tuple && foreach(a -> a isa Symbol && push!(loopv, a), v.args)
        end
    end
    foreach(walkfor, e.args)
end
walkfor(blk)
blockdef = union(asg, loopv)
inputs = sort(collect(setdiff(intersect(used, assigned), blockdef)))
after = Meta.parse("begin\n" * join(lines[l1+1:min(end, l1+2000)], "\n") * "\nend"; raise = false)
usedafter = Set{Symbol}(); walkU(e) = (e isa Symbol && push!(usedafter, e); e isa Expr && e.head != :quote && foreach(walkU, e.args))
walkU(after)
println("INPUTS (args): ", join(inputs, ", "))
println("block-defined names read after the block (leaks?): ", join(sort(collect(intersect(blockdef, usedafter, assigned))), ", "))
