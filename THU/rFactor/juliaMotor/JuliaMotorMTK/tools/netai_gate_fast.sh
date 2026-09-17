#!/usr/bin/env bash
# MP-5 netai gate, CHEAP form.
# The guard lives in `const N_AI = let ... end` -- a TOP-LEVEL const, so it evaluates at module
# load, BEFORE any track/car asset loading. The arms therefore never need the sim to run: we only
# need the startup line. That removes the AI-car asset spike that killed two earlier attempts and
# cuts each arm from ~5 min to ~1 min.
# JM_AI=1 rather than the committed gate's JM_AI=3: the guard branches on `n > 0`, so 1 and 3
# exercise identical paths, and 1 loads a third of the AI-car assets. Deviation recorded.
# stdbuf -oL is required: a redirected julia stdout is block-buffered, so an early kill would
# otherwise discard the very line we are testing for.
D=/home/admin/sgl-julia-racer/THU/rFactor/juliaMotor/demo/native
OUT=/home/admin/jr-ds
run_arm() { name="$1"; shift
  timeout -k 5 100 stdbuf -oL env "$@" julia --project="$D" "$D/drive_native_mtk.jl" \
      > "$OUT/fast_$name.log" 2>&1
  grep -aq 'AI field disabled'   "$OUT/fast_$name.log" && dis=yes || dis=no
  grep -aq 'host-authoritative AI' "$OUT/fast_$name.log" && ha=yes  || ha=no
  printf '%-10s AI-disabled=%-4s host-authoritative-announced=%-4s (log %s lines)\n' \
         "$name" "$dis" "$ha" "$(wc -l < "$OUT/fast_$name.log")"
}
run_arm offline  JM_AI=1
run_arm client   JM_AI=1 JM_NET=join JM_NET_PORT=47755 JM_NET_HOST=127.0.0.1
run_arm host     JM_AI=1 JM_NET=host JM_NET_PORT=47757
run_arm override JM_AI=1 JM_NET=join JM_NET_PORT=47756 JM_NET_HOST=127.0.0.1 JM_NET_AI=1
