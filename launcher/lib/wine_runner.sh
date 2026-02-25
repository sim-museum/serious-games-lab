#!/usr/bin/env bash
# wine_runner.sh - Resolve and prepend the correct Lutris wine runner to PATH
#
# Sourced inside the subshell in run_game() before the game script runs.
# Expects: REPO_ROOT and SGL_GAME_SCRIPT to be set in the environment.
# Effect:  Prepends the runner's bin/ to PATH and exports WINE.
#          Silent no-op if game is not in wine_runners.csv or runner is missing.

_wine_runner_setup() {
    local csv="$REPO_ROOT/config/wine_runners.csv"
    local runners_base="$HOME/.local/share/lutris/runners/wine"

    [[ -f "$csv" ]] || return 0
    [[ -n "${SGL_GAME_SCRIPT:-}" ]] || return 0

    # Look up the runner for this game script
    local runner=""
    while IFS=',' read -r csv_script csv_runner csv_arch csv_dxvk; do
        if [[ "$csv_script" == "$SGL_GAME_SCRIPT" ]]; then
            runner="$csv_runner"
            break
        fi
    done < <(tail -n +2 "$csv")

    [[ -n "$runner" ]] || return 0

    # Try exact match first
    local runner_dir="$runners_base/$runner"

    if [[ ! -d "$runner_dir" ]]; then
        # Flexible matching: find closest version in the same runner family
        # Extract family and version from runner name
        # e.g. wine-lutris-GE-Proton8-26-x86_64 → family=wine-lutris-GE-Proton, ver=8-26
        # e.g. wine-lutris-5.7-x86_64           → family=wine-lutris, ver=5.7
        # e.g. wine-lutris-fshack-5.7-x86_64    → family=wine-lutris-fshack, ver=5.7
        local arch_suffix=""
        local base="$runner"
        if [[ "$base" =~ ([-_]x86_64)$ ]]; then
            arch_suffix="${BASH_REMATCH[1]}"
            base="${base%"$arch_suffix"}"
        elif [[ "$base" =~ ([-_]i686)$ ]]; then
            arch_suffix="${BASH_REMATCH[1]}"
            base="${base%"$arch_suffix"}"
        fi

        # Split into family + version: last numeric-dotted segment is the version
        local family="" target_ver=""
        if [[ "$base" =~ ^(.*)-([0-9][0-9.]*(-[0-9]+)?)$ ]]; then
            family="${BASH_REMATCH[1]}"
            target_ver="${BASH_REMATCH[2]}"
        elif [[ "$base" =~ ^(.*[A-Za-z])([0-9][0-9.]*(-[0-9]+)?)$ ]]; then
            family="${BASH_REMATCH[1]}"
            target_ver="${BASH_REMATCH[2]}"
        else
            # Can't parse — give up on flexible match
            echo "[wine_runner] WARNING: Runner not found: $runner" >&2
            return 0
        fi

        # Parse version string into major.minor for distance calc
        _ver_parts() {
            local v="$1"
            v="${v//-/.}"  # normalize hyphens to dots
            local major minor
            major="${v%%.*}"
            minor="${v#*.}"
            [[ "$minor" == "$v" ]] && minor="0"
            minor="${minor%%.*}"
            echo "$major $minor"
        }

        local target_major target_minor
        read -r target_major target_minor <<< "$(_ver_parts "$target_ver")"

        local best_dir="" best_dist=999999
        local candidate
        # Try both - and _ separators for arch suffix (e.g. -x86_64 vs _x86_64)
        local arch_stem="${arch_suffix#[-_]}"  # e.g. "x86_64"
        for candidate_dir in "$runners_base"/"${family}"*"-${arch_stem}" "$runners_base"/"${family}"*"_${arch_stem}"; do
            [[ -d "$candidate_dir" ]] || continue
            candidate="$(basename "$candidate_dir")"
            # Strip arch suffix (either separator) and family prefix to get version
            local cand_base="${candidate%[-_]"$arch_stem"}"
            local cand_ver="${cand_base#"$family"}"
            cand_ver="${cand_ver#-}"  # strip leading dash
            [[ -n "$cand_ver" ]] || continue

            local cand_major cand_minor
            read -r cand_major cand_minor <<< "$(_ver_parts "$cand_ver")"

            local major_diff=$(( target_major - cand_major ))
            local minor_diff=$(( target_minor - cand_minor ))
            [[ $major_diff -lt 0 ]] && major_diff=$(( -major_diff ))
            [[ $minor_diff -lt 0 ]] && minor_diff=$(( -minor_diff ))
            local dist=$(( major_diff * 1000 + minor_diff ))

            if (( dist < best_dist )); then
                best_dist=$dist
                best_dir="$candidate_dir"
            fi
        done

        if [[ -n "$best_dir" ]]; then
            runner_dir="$best_dir"
            echo "[wine_runner] Exact runner '$runner' not found; using closest: $(basename "$best_dir")" >&2
        else
            echo "[wine_runner] WARNING: No runner found for family '$family' (wanted $runner)" >&2
            return 0
        fi
    fi

    # Verify the runner has a wine binary
    if [[ ! -x "$runner_dir/bin/wine" ]]; then
        echo "[wine_runner] WARNING: $runner_dir/bin/wine not found or not executable" >&2
        return 0
    fi

    export PATH="$runner_dir/bin:$PATH"
    export WINE="$runner_dir/bin/wine"
    export WINELOADER="$runner_dir/bin/wine"
    export WINESERVER="$runner_dir/bin/wineserver"

    # Set LD_LIBRARY_PATH so the runner can find its own shared libraries
    local lib32="$runner_dir/lib"
    local lib64="$runner_dir/lib64"
    local ldpath=""
    [[ -d "$lib64" ]] && ldpath="$lib64"
    [[ -d "$lib32" ]] && ldpath="${ldpath:+$ldpath:}$lib32"
    if [[ -n "$ldpath" ]]; then
        export LD_LIBRARY_PATH="${ldpath}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    fi

    # Set WINEDLLPATH so the runner can find its own Wine modules
    # (display drivers like winex11.so, etc.)
    local dllpath=""
    [[ -d "$lib64/wine/x86_64-unix" ]] && dllpath="$lib64/wine/x86_64-unix"
    [[ -d "$lib32/wine/i386-unix" ]] && dllpath="${dllpath:+$dllpath:}$lib32/wine/i386-unix"
    if [[ -n "$dllpath" ]]; then
        export WINEDLLPATH="${dllpath}${WINEDLLPATH:+:$WINEDLLPATH}"
    fi

    echo "[wine_runner] Using runner: $(basename "$runner_dir") → $runner_dir/bin/wine" >&2
}

_wine_runner_setup
unset -f _wine_runner_setup
