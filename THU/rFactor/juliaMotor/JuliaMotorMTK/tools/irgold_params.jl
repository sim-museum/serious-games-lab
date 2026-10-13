# IRGOLD-1: the runtime parameters the fit tools can move (setp, no rebuild): name -> (wheels, tyre parameter) or
# (:veh, vehicle parameter) or (:col, steering-column parameter). Shared by irgold_fit.jl and irgold_steady.jl.
# parameter name -> (wheels, tyre parameter symbol)  |  or (:veh, vehicle parameter symbol)
const PARAM_MAP = Dict(
    "muf" => ((:FL, :FR), :μ), "mur" => ((:RL, :RR), :μ), "caf" => ((:FL, :FR), :Cα), "car" => ((:RL, :RR), :Cα),
    "muxf" => ((:FL, :FR), :μx), "muxr" => ((:RL, :RR), :μx), "ckf" => ((:FL, :FR), :Cκ), "ckr" => ((:RL, :RR), :Cκ),
    "kmu" => ((:FL, :FR, :RL, :RR), :kμ), "rsy" => ((:FL, :FR, :RL, :RR), :rsy), "rs" => ((:FL, :FR, :RL, :RR), :rs),
    "ws" => ((:FL, :FR, :RL, :RR), :ws), "kg" => ((:FL, :FR, :RL, :RR), :kγ), "ns" => ((:FL, :FR, :RL, :RR), :ns),
    "t0" => ((:FL, :FR, :RL, :RR), :t0), "kpmu" => ((:FL, :FR, :RL, :RR), :kpμ), "kpc" => ((:FL, :FR, :RL, :RR), :kpc),
    "izz" => (:veh, :Izz), "lsdk" => (:veh, :lsd_k),
    "sigf" => ((:rxFL, :rxFR), :σ), "sigr" => ((:rxRL, :rxRR), :σ),   # tyre relaxation (cars built with JM_RELAX)
    "cabl" => (:veh, :c_abl), "trail" => (:col, :trail), "nsh" => ((:FL, :FR, :RL, :RR), :nsh),
    "nshf" => ((:FL, :FR), :nsh), "nshr" => ((:RL, :RR), :nsh), "rho" => (:veh, :ρair),
    "nsf" => ((:FL, :FR), :ns), "nsr" => ((:RL, :RR), :ns),
    "cbf" => ((:sFL, :sFR), :cb), "crf" => ((:sFL, :sFR), :cr), "cbr" => ((:sRL, :sRR), :cb), "crr" => ((:sRL, :sRR), :cr),
    "clo" => ((:sFL, :sFR, :sRL, :sRR), :clo), "vk" => ((:sFL, :sFR, :sRL, :sRR), :vk),
    "ixx" => (:veh, :Ixx), "csf" => ((:sFL, :sFR), :cs), "csr" => ((:sRL, :sRR), :cs),
    "toef" => (:veh, :toe_f), "toer" => (:veh, :toe_r),
    "hrcf" => (:veh, :hrc_f), "hrcr" => (:veh, :hrc_r),
    "pcf" => ((:FL, :FR), :pc), "pcr" => ((:RL, :RR), :pc),
    "claf" => (:veh, :ClAf), "clar" => (:veh, :ClAr))     # IRGOLD-1 S20: lift areas [m²], + = downforce   # JM_TYRE_PC builds only     # IRGOLD-1 S18: roll-centre heights [m]
function setparams!(car, pv)
    sys = car.sys
    for (k, v) in pv
        w, s = PARAM_MAP[k]
        if w === :veh
            ModelingToolkit.setp(sys, getproperty(sys, s))(car.integ, v)
        elseif w === :col
            ModelingToolkit.setp(sys, getproperty(sys.col, s))(car.integ, v)
        else
            n = 0
            for wh in w
                sub = try getproperty(sys, wh) catch; nothing end
                sub === nothing && continue
                p = try getproperty(sub, s) catch; nothing end
                p === nothing && continue
                ModelingToolkit.setp(sys, p)(car.integ, v); n += 1
            end
            n == 0 && error("setparams!: $k ($w.$s) is not in this car -- built without it?")
        end
    end
end
