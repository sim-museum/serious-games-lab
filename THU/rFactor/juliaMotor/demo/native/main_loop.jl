# main_loop.jl -- LOOPSPLIT-1: pieces of drive_native_mtk.jl's frame loop, moved out of main() as functions (unchanged
# code; the loop locals they use are arguments). Included above _MAIN_Q, so they see every file-scope global main() sees.

"""The E64 mirror pass: the rear view into the mirror RTT, one camera per disc (see the comments at the call site)."""
function mirror_render!(drawworld, cs, cam_pitch, cam_roll, frames, _mir_alt, lightVP, bodyModel, wheelmat, loosemat)
        glClipControl(GL_LOWER_LEFT, GL_ZERO_TO_ONE); glDepthFunc(GL_GEQUAL); glClearDepth(0.0)   # same reversed-Z as the main pass
        glBindFramebuffer(GL_FRAMEBUFFER, mirfbo); glViewport(0,0,MIRW,MIRH)
        _mir_half = _mir_alt ? (frames % 2) : -1          # PACE-1: which half this frame (-1 = both)
        if _mir_half >= 0
            glEnable(GL_SCISSOR_TEST); glScissor(_mir_half == 0 ? 0 : MIRW÷2, 0, MIRW÷2, MIRH)
        end
        glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
        _mir_half >= 0 && glDisable(GL_SCISSOR_TEST)
        # SPA-FPS-1 S15: JM_MIRROR_HALVES decomposes the mirror's cost. 2 = normal (one camera
        # per disc), 1 = only the left disc, 0 = bind + clear and NOTHING drawn. S14 proved the
        # cost is not the distance-culled object/billboard lists; this says whether it is the
        # two scene DRAWS or the FBO/state hop itself, which decides what S16 can attack.
        if MIRROR_HALVES > 0
        # E64 S10: one camera PER DISC at the mirror's own cowl position (left half of the FBO =
        # RIGHT/z+ camera -- render +z is the car's right; CARHAND-1), so each glass sees backward-outward like the gold — tail at the inner
        # edge only, road dominating.  The glass quads' per-half UV split is unchanged.
        for (x0, side) in (_mir_half == 0 ? ((0, 1),) : _mir_half == 1 ? ((MIRW÷2, -1),) :
                           MIRROR_HALVES == 1 ? ((0, 1),) : ((0, 1), (MIRW÷2, -1)))
            glViewport(x0, 0, MIRW÷2, MIRH)
            mvp, meye = mirror_camera(cs, cam_pitch, cam_roll, side)
            Render.draw_sky(skyprog, skyvao, inv(mvp), meye, LIGHTDIR;
                            cloud = GRADE.cloud, zenith = GRADE.zenith, horizon = GRADE.horizon)
            Render.set_scene_uniforms(prog, meye; fognear=400f0, fogfar=2800f0,
                                      fogcol=GRADE.horizon, suncol=GRADE.suncol, ambsky=GRADE.ambsky, sat=GRADE.sat)
            Render.bind_shadow(prog, shadowtex, lightVP)
            drawworld(mvp, meye, true)
            for (i,it) in enumerate(carItems); _in_car_range(i) || continue; Render.draw(prog, it, mvp, bodyModel; bright=1.2, spec=0.08, ambfill=0.78); end   # your own tail at the inner edge
            for (wx,wz,steer,r,nm) in WHEELS, it in WHEELITEMS[nm]
                is_loose(nm) && continue
                Render.draw(prog, it, mvp, wheelmat(wx,wz,steer,r); bright=1.0, ambfill=0.75)
            end
            for (lx,ly,lz,_,_,_,sp,_,nm) in LOOSE_WHEELS, it in WHEELITEMS[nm]
                Render.draw(prog, it, mvp, loosemat(lx,ly,lz,sp); bright=1.0, ambfill=0.75)
            end
        end
        end   # MIRROR_HALVES > 0 (S15)
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
    nothing
end


"""TEXTHUD-1 (GOLDMATCH-JR-1 S1): the gold's timing overlay -- lap rows top-left, Track Position top-right (LOOPSPLIT-1 S3;
the code is unchanged, the loop locals it reads are arguments)."""
function texthud_draw!(cs, W, H, AICARS, best_lap, fmt_lap, lap_t0, last_lap, player_finpos, race_done, race_go, standings, texthud_name)
        if FONT !== nothing
            # The gold's rows sit on an opaque black band across the top of the frame (its overlay is
            # not blended over the scene). Same here: one flat quad through the HUD program, then text.
            # S2: the band must also cover the Track Position table (three lap rows alone left the
            # table's lower rows blended over the grandstand).
            nrows = (IS_RACE && !isempty(AICARS)) ? max(3, min(7, 1 + length(AICARS)) + 1) : 3
            bv = empty!(HUD_BV); Render.hquad!(bv, 0.0, 0.0, Float64(W), nrows*FONT.lineh + 12.0, (0.0, 0.0, 0.0))
            Render.hud_draw(hudprog, hudvao, hudvbo, bv, W, H)
            tv = empty!(HUD_TV); fy = 6.0; fx = 8.0
            cur = (race_go[] && !race_done) ? cs.t - lap_t0 : (SMOKE ? 23.27 : 0.0)
            Render.text!(tv, FONT, fx, fy,            "I  " * lapfmt(cur),                              (1.0, 0.45, 1.0))
            Render.text!(tv, FONT, fx, fy + FONT.lineh, "B  " * lapfmt(SMOKE ? 92.1 : best_lap),           (0.75, 0.75, 0.75))
            Render.text!(tv, FONT, fx, fy + 2FONT.lineh, "L  " * lapfmt(SMOKE ? 94.3 : last_lap),          (0.45, 0.95, 0.45))
            if IS_RACE && !isempty(AICARS)
                st = standings(); ppy = 0.0
                for e in st; e[1] == 0 && (ppy = e[2]); end
                lapsN = length(st) > 0 ? cs.laps + 1 : 1
                tx = W - 8.0 - 300.0
                Render.text!(tv, FONT, tx, fy, "Track Position ($(lapsN)L)", (0.95, 0.95, 0.95))
                for (i, e) in enumerate(st)
                    i > 7 && break
                    gapm = round(Int, (e[2] - ppy) * LAPLEN)
                    col = e[1] == 0 ? (1.0, 0.82, 0.35) : (0.95, 0.95, 0.95)
                    Render.text!(tv, FONT, tx, fy + i*FONT.lineh, string(i, " ", texthud_name(e[1])), col)
                    Render.text!(tv, FONT, tx + 190.0, fy + i*FONT.lineh, (gapm >= 0 ? "+" : "") * string(gapm) * "m", col)
                end
            end
            Render.text_draw(textprog, textvao, textvbo, FONT, tv, W, H)
            # TRACKSEG-1: the section name, centred in the black timing band above the 3-D view. PO 2026-10-04 (2):
            # "less obtrusive ... higher vertically ... no colored text window behind the words, about the same contrast
            # (but larger font) as the other text above the 3D window" -- the band's own light grey, a larger regular face.
            if !isempty(SECTIONS) && SEGNAME_SECS > 0
                SEG[] = section_update(SECTIONS, cs.lapdist, LAPLEN, cs.t, SEG[]...)
                if cs.t - SEG[][3] < SEGNAME_SECS || !isempty(SEGNAME_FORCE)
                    msg = isempty(SEGNAME_FORCE) ? SEG[][2] : SEGNAME_FORCE; tw = Render.text_width(SEGFONT, msg)
                    bandh = nrows*FONT.lineh + 12.0
                    st = empty!(HUD_ST); Render.text!(st, SEGFONT, (W - tw)/2, max(2.0, (bandh - SEGFONT.lineh)/2), msg, (0.95, 0.95, 0.95))
                    Render.text_draw(textprog, textvao, textvbo, SEGFONT, st, W, H)
                end
            end
            # RACEEND-1 (PO 2026-09-19, WG race: "there should be a graphical signal when the race is
            # over"). Until now the finish was a small line in the standings box and the window title.
            # Now: a chequered strip across the frame under the HUD band and a large centred banner,
            # for RACEEND_SECS seconds after the flag (then just the strip stays, so a late look still
            # says the race is over). JM_RACEEND_SECS overrides; 0 disables the banner.
            if IS_RACE && race_done && RACEEND_SECS > 0
                RACEEND_T0[] < 0 && (RACEEND_T0[] = cs.t)
                sq = 28.0; y0 = nrows*FONT.lineh + 12.0
                cv = Float32[]
                for (r, yy) in enumerate((y0, y0 + sq))
                    for (c, xx) in enumerate(0.0:sq:Float64(W))
                        Render.hquad!(cv, xx, yy, sq, sq, iseven(r + c) ? (0.05, 0.05, 0.05) : (0.97, 0.97, 0.97))
                    end
                end
                Render.hud_draw(hudprog, hudvao, hudvbo, cv, W, H)
                if cs.t - RACEEND_T0[] < RACEEND_SECS
                    msg = "RACE FINISHED" * (isempty(AICARS) ? "" : " - P$(player_finpos[]) of $(length(AICARS)+1)")
                    sub = "best lap $(fmt_lap(best_lap))   -   Esc to leave"
                    sc = 3.0; tw = Render.text_width(FONT, msg; scale=sc); sw = Render.text_width(FONT, sub; scale=1.4)
                    bx = (W - tw)/2 - 24; by = H*0.30
                    bg = Float32[]; Render.hquad!(bg, bx, by - 10, tw + 48, sc*FONT.lineh + 1.4*FONT.lineh + 28, (0.0, 0.0, 0.0))
                    Render.hud_draw(hudprog, hudvao, hudvbo, bg, W, H)
                    fv = Float32[]
                    Render.text!(fv, FONT, (W - tw)/2, by, msg, (1.0, 0.85, 0.2); scale=sc)
                    Render.text!(fv, FONT, (W - sw)/2, by + sc*FONT.lineh + 8, sub, (0.95, 0.95, 0.95); scale=1.4)
                    Render.text_draw(textprog, textvao, textvbo, FONT, fv, W, H)
                end
            end
        end
    nothing
end

"""REPLAY-6: the per-wheel tyre panel on the replay screen (chase view, player car). (LOOPSPLIT-1 S5: moved unchanged from main())"""
function replay_tyres_draw!(W, H, REPLAY, rep_cam, rep_focus, rep_tyres, rep_tyshow)
        if REPLAY && rep_tyshow[] && rep_focus[] == 0 && REPLAY_CAMS[rep_cam[]] === :chase && rep_tyres[] !== nothing && any(t -> t[3] + t[4] > 0, rep_tyres[])
            baseR = 18.0; pitch = 2*1.9*baseR + 12; pcx = W/2; pcy = H - pitch - 18.0
            tyv = empty!(HUD_TY); Render.htyres!(tyv, pcx, pcy, baseR, rep_tyres[])
            Render.hud_draw(hudprog, hudvao, hudvbo, tyv, W, H)
            if FONT !== nothing
                tt = empty!(HUD_TYT); lc = (0.75, 0.78, 0.82)
                for (k, nm) in enumerate(("FL", "FR", "RL", "RR"))
                    lx = pcx + (isodd(k) ? -1 : 1)*pitch/2 + (isodd(k) ? -1.9baseR - 4 - Render.text_width(FONT, nm) : 1.9baseR + 4)
                    ly = pcy + (k <= 2 ? -1 : 1)*pitch/2 - FONT.lineh/2
                    Render.text!(tt, FONT, lx, ly, nm, lc)
                end
                cap = "tyres: ring = grip, dot = force"
                Render.text!(tt, FONT, pcx - Render.text_width(FONT, cap)/2, pcy - pitch - 4 - FONT.lineh, cap, lc)
                Render.text_draw(textprog, textvao, textvbo, FONT, tt, W, H)
            end
        end
    nothing
end

"""TD261013-1 (c3): say on screen that a wreck refuses shifts and throttle, with the way out. (LOOPSPLIT-1 S5: moved unchanged from main())"""
function wreck_notice_draw!(W, H, REPLAY)
        if WRECKED[] && !REPLAY && FONT !== nothing && get(ENV, "JM_WRECK_NOTICE", "1") != "0"
            m1 = "CAR WRECKED -- engine and gearbox out"
            m2 = (WHEELOFF_RULE && !isempty(LOOSE_WHEELS)) ? "A wheel has come off -- R: restart the race" : "SHIFT+R: back onto the track     R: restart the race"
            bw = max(Render.text_width(FONT, m1), Render.text_width(FONT, m2)) + 40; by = H*0.30 - 14
            bx = empty!(HUD_TY); Render.hquad!(bx, W/2 - bw/2, by, bw, 2.4*FONT.lineh + 28, (0.06, 0.06, 0.08))
            Render.hud_draw(hudprog, hudvao, hudvbo, bx, W, H)
            tt = empty!(HUD_TYT)
            Render.text!(tt, FONT, W/2 - Render.text_width(FONT, m1)/2, H*0.30, m1, (1.0, 0.82, 0.25))
            Render.text!(tt, FONT, W/2 - Render.text_width(FONT, m2)/2, H*0.30 + 1.4*FONT.lineh, m2, (0.92, 0.92, 0.92))
            Render.text_draw(textprog, textvao, textvbo, FONT, tt, W, H)
        end
    nothing
end

"""PACE-1: present every 2nd refresh while the work time stays over JM_PACE_HI ms. (LOOPSPLIT-1 S5: moved unchanged from main())"""
function pace_step!(frames, now)
        if PACE_ON && (!SMOKE || haskey(ENV, "JM_PACE_TEST"))
            # PERF-3: the first frame (4.9 s of JIT) seeded the EMA and every session opened at 30 Hz; a single
            # crash/GC hitch (288 ms) flipped it again. Skip the warm-up and clamp each sample, so only a
            # SUSTAINED over-budget load (~30+ frames) drops the rate.
            _wk = min(time() - now, 1.5 * PACE_HI)
            if frames > PACE_WARM
                PACE_EMA[] = PACE_EMA[] == 0.0 ? _wk : 0.95*PACE_EMA[] + 0.05*_wk
            end
            if PACE_INT[] == 1 && PACE_EMA[] > PACE_HI
                PACE_INT[] = 2; GLFW.SwapInterval(2); println("  [pace] work ", round(1000*PACE_EMA[], digits=1), " ms -> steady 30 Hz"); flush(stdout)
            elseif PACE_INT[] == 2 && PACE_EMA[] < PACE_LO
                PACE_INT[] = 1; GLFW.SwapInterval(1); println("  [pace] work ", round(1000*PACE_EMA[], digits=1), " ms -> 60 Hz"); flush(stdout)
            end
        end
    nothing
end

"""PERF-3: a young-generation GC every GC_EVERY frames, while the GPU finishes the frame. (LOOPSPLIT-1 S5: moved unchanged from main())"""
function gc_step!(frames)
        if GC_EVERY > 0 && frames % GC_EVERY == 0 && frames > 0
            _tg = time(); GC.gc(false); _tg = time() - _tg
            GC_MS[1] += _tg; GC_MS[2] = max(GC_MS[2], _tg); GC_MS[3] += 1
            if FPSDIAG > 0 && GC_MS[3] >= 20
                println("  [gc] young collections: mean ", round(1000GC_MS[1]/GC_MS[3], digits=2), " ms  max ", round(1000GC_MS[2], digits=2), " ms  (every ", GC_EVERY, " frames)"); flush(stdout)
                fill!(GC_MS, 0.0)
            end
        end
    nothing
end

"""COUNTDOWN start (PO 2026-08-31): the lights, the held field, the green. Returns `lap_t0` (set at the green).
(LOOPSPLIT-1 S6: moved unchanged from main(); the Refs are shared, lap_t0 comes back.)"""
function countdown_step!(cs, AICARS, HOLD_START, ai_release, cd_armed, cd_left, cd_said, cd_t0, phase, race_go, lap_t0)
        if COUNTDOWN > 0 && HOLD_START && !race_go[] && phase[] == :race
            # Arm on the first race frame, whatever put us here. The first cut armed cd_t0 ONLY in
            # the practice->race transition, so with JM_POLE (no qualifying, grid formed up front)
            # it stayed -1, the countdown never ran -- and because a countdown also disables the
            # old throttle gate, the race could never go green at all. Caught on the grid, before
            # the PO was left sitting on it.
            # STARTSEQ-1: wait for SPACE before the clock starts. cd_armed stays false until then,
            # the HUD shows the prompt, and nobody moves. Automated runs (START_ARM false) skip it.
            # JM_ARM_AFTER=<s>: arm the countdown automatically after <s> seconds. This session runs
            # on WAYLAND, where XTEST keys from xdotool are never delivered to a GLFW surface and
            # /dev/uinput is root-only -- so there is no way to press a key from a gate. Same reason
            # bob grew BOB_SDL_CLICK_MS. It exercises the arm -> countdown -> green sequence; it does
            # NOT exercise GLFW.GetKey itself (that idiom is shared with the driving keys).
            if ARM_AFTER > 0 && !cd_armed[] && cs.t >= ARM_AFTER
                cd_armed[] = true; cd_t0[] = cs.t
                println("  → COUNTDOWN ARMED (JM_ARM_AFTER)"); flush(stdout)
            end
            if START_ARM && !cd_armed[]
                if !cd_said[]
                    cd_said[] = true
                    println("  ★ PRESS ANY KEY TO START COUNTDOWN"); flush(stdout)
                end
                if anykey()
                    cd_armed[] = true
                    cd_t0[] = cs.t
                    println("  → COUNTDOWN ARMED"); flush(stdout)
                end
            elseif cd_t0[] < 0
                cd_t0[] = cs.t
            end
            if !(START_ARM && !cd_armed[])
                cd_left[] = COUNTDOWN - (cs.t - cd_t0[])
            end
            if cd_left[] <= 0 && !(START_ARM && !cd_armed[])
                cd_left[] = 0.0
                race_go[] = true; lap_t0 = cs.t
                ai_release[] = cs.t + AI_HEADSTART
                println("  → GREEN"); flush(stdout)
                for c in AICARS
                    rand() < 0.45 && (c.mishap = 0.4 + 1.4*rand())
                end
            end
        elseif race_go[] && cd_left[] >= 0
            # keep GO on screen for a moment after the start, then clear it
            cd_left[] = (cs.t - cd_t0[] - COUNTDOWN) < 1.5 ? 0.0 : -1.0
        end
    lap_t0
end

"""E18 / REPLAY-2 / REPLAY-6: record every car's pose and the analysis channels at ~15 Hz once the race is green, with the
crash-safe autosave. (LOOPSPLIT-1 cycle 2 S1: moved unchanged from main(); its buffers and Refs are shared.)"""
function replay_record!(cs, inp, AICARS, ai_poses, CLINE, REPLAY_AUTOSAVE, REPLAY_NCAR, phase, race_go, rst, replay_buf, replay_names, replay_out, replay_saved, replay_t, tele_buf, tyre_lp)
        if replay_buf !== nothing && race_go[] && !rst && length(ai_poses) == length(AICARS) && (cs.t - replay_t[]) >= 1/15
            replay_t[] = cs.t
            push!(replay_buf, Float32(cs.t), Float32(cs.x), Float32(cs.y), Float32(cs.z), Float32(cs.θ))
            for p in ai_poses; push!(replay_buf, Float32(p[1]), Float32(p[2]), Float32(p[3]), Float32(p[4])); end
            # REPLAY-2: analysis channels, REPLAY_TELE_P for the player then REPLAY_TELE_AI per AI car
            push!(tele_buf, Float32(cs.laps), Float32(cs.lapdist), Float32(cs.v), Float32(inp.throttle), Float32(inp.brake),
                  Float32(inp.steer), Float32(inp.clutch), Float32(cs.gear), Float32(cs.rpm), Float32(cs.lateral),
                  Float32(cs.ontrack ? 1 : 0), Float32(phase[] == :race ? 1 : 0))
            for w in tyre_lp[], q in w; push!(tele_buf, Float32(q)); end             # REPLAY-6
            for a in AICARS; push!(tele_buf, Float32(a.s), Float32(a.v), Float32(a.lap), Float32(a.lane)); end
            if time() - replay_saved[] > REPLAY_AUTOSAVE           # crash-safe: the session so far is on disk
                replay_saved[] = time(); write_replay(replay_out[], replay_buf, tele_buf, REPLAY_NCAR, replay_names, CLINE; final = false)
            end
        end
    nothing
end

"""WGTD-1 (e) / TD261013-1 (a3): after the flag each AI car drives one cool-down lap and stops in the pit lane.
(LOOPSPLIT-1 cycle 2 S2: moved unchanged from main(); the field `f` and AI state are shared.)"""
function ai_cooldown_step!(f, AICARS, GPLAI_T, crossed, ent_name, phase, race_done, race_go)
        if AI_COOLDOWN && IS_RACE && phase[] == :race && race_go[]
            flag = race_done || any(a -> a.lap >= RACE_LAPS, AICARS)
            for (i, gc) in enumerate(f.cars)
                i > length(AICARS) && break
                st = get(AI_COOL, i, nothing)
                if st === nothing
                    if flag && crossed[i]
                        AI_COOL[i] = (:cool, gc.pace, 0.0); gc.pace = AI_COOL_PACE*gc.pace
                        AI_COOL_DIAG && println("  [cooldown] ", ent_name(i), " finished (lap ", AICARS[i].lap, "): cool-down lap")
                    end
                elseif st[1] === :cool && isfinite(PIT_IN[]) && haskey(GPLAI_T.lines, GPLAI.PIT) &&
                       PIT_IN[] - 60.0 <= gc.s < PIT_BOX[]                      # WGTD-1 S9: into GPL's pit lane
                    q = 15.0*count(v -> v[1] === :pit, values(AI_COOL))          # boxes 15 m apart, the first car furthest on
                    GPLAI.join_pit!(GPLAI_T, gc); gc.hold = typemax(Int) ÷ 4
                    AI_COOL[i] = (:pit, st[2], PIT_BOX[] + 30.0 - q)
                    AI_COOL_DIAG && println("  [cooldown] ", ent_name(i), " into the pits, box at ", round(Int, PIT_BOX[] + 30.0 - q), " m")
                elseif st[1] === :pit
                    rem = st[3] - gc.s                                           # metres to its box
                    gc.pace = st[2] * clamp(rem / 40.0, 0.0, 1.0); gc.hold = typemax(Int) ÷ 4
                    if AI_COOL_DIAG && gc.v < 0.3 && !(i in AI_COOL_STOPPED)
                        push!(AI_COOL_STOPPED, i)                                  # once: where it stopped
                        println("  [cooldown] ", ent_name(i), " stopped at s ", round(Int, gc.s), ", ", round(gc.d, digits = 1),
                                " m off GPL's centre (pit line ", round(GPLAI.dlat(GPLAI_T.lines[GPLAI.PIT], gc.s), digits = 1),
                                ", corridor ", round.(GPLAI.corridor(GPLAI_T, gc.s), digits = 1), ")")
                    end
                elseif st[1] === :cool && crossed[i]
                    # each car stops 25 m beyond the one before it, so they line up along the edge
                    q = 25.0*count(v -> v[1] === :stop, values(AI_COOL))
                    AI_COOL[i] = (:stop, st[2], AICARS[i].s + q)
                    # join! keeps the move as an offset from the race line, which wanders across the straight: aim at the
                    # corridor's outer edge WHERE THE CAR WILL STOP, so that is where it ends up
                    sst = mod(gc.s + 300.0 + q, GPLAI_T.lap); lo, hi = GPLAI.corridor(GPLAI_T, sst)
                    GPLAI.join!(GPLAI_T, gc, hi - 1.2; at = sst, why = :cooldown); gc.hold = typemax(Int) ÷ 4
                    AI_COOL_DIAG && println("  [cooldown] ", ent_name(i), " pulls aside to stop")
                elseif st[1] === :stop
                    frac = clamp((AICARS[i].s - st[3]) / 300.0, 0.0, 1.0)   # (st[3] carries the car's 25 m queue offset)
                    gc.pace = st[2] * 0.6 * (1.0 - frac); gc.hold = typemax(Int) ÷ 4
                end
            end
        end
    nothing
end

"""E10 / FUEL-1: burn fuel once the race is green (the gold's pedal x rpm law), the burnt mass leaving the car; an empty
tank cuts the throttle. Returns `inp`. (LOOPSPLIT-1 cycle 2 S4: moved unchanged from main().)"""
function fuel_step!(cs, inp, dt, FUEL1, FUEL_ON, fuel, fuel_mass_t, race_go, rst)
        if FUEL_ON && race_go[] && !rst
            if FUEL1      # FUEL-1: the gold's burn law (pedal x rpm), and the burnt mass leaves the car twice a second
                fuel[] = max(0.0, fuel[] - DriveRT3D.fuel_rate_kgh(inp.throttle, cs.rpm)/3600*(dt > 1e-4 ? dt : 1/60)/DriveRT3D.FUEL_KG_PER_L)
                if CAR3D && cs.t - fuel_mass_t[] >= 0.5
                    fuel_mass_t[] = cs.t; DriveRT3D.set_fuel_burnt!(cs, (FUEL_START_L[] - fuel[])*DriveRT3D.FUEL_KG_PER_L)
                end
            else
                fuel[] = max(0.0, fuel[] - FUEL_LPK * cs.v * (dt > 1e-4 ? dt : 1/60) / 1000)
            end
            fuel[] <= 0 && (inp = DriveInput(throttle=0.0, brake=inp.brake, steer=inp.steer,
                            clutch=inp.clutch, shift_up=inp.shift_up, shift_down=inp.shift_down, autoshift=inp.autoshift))
        end
    inp
end
