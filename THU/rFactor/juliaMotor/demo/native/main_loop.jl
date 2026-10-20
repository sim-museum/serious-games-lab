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
                    # PITPARK-1: boxes along the pit lane (PIT_BOX = its entrance .. PIT_END), the first car furthest on, 15 m
                    # apart -- closer if the field would not fit -- never short of the entrance (JM_PITPARK=0: as before)
                    nb = count(v -> v[1] === :pit, values(AI_COOL))
                    if PITPARK && isfinite(PIT_END[]) && PIT_END[] - PIT_BOX[] > 30.0
                        sp = min(15.0, (PIT_END[] - PIT_BOX[] - 20.0) / max(length(AICARS) - 1, 1))
                        box = max(PIT_END[] - 10.0 - sp*nb, PIT_BOX[] + 10.0)
                    else
                        box = PIT_BOX[] + 30.0 - 15.0*nb
                    end
                    GPLAI.join_pit!(GPLAI_T, gc); gc.hold = typemax(Int) ÷ 4
                    AI_COOL[i] = (:pit, st[2], box)
                    AI_COOL_DIAG && println("  [cooldown] ", ent_name(i), " into the pits, box at ", round(Int, box), " m")
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

"""CTRL+R: the session restarts on the current track (LOOPSPLIT-1 cycle 2, moved unchanged from the frame loop; the
per-session state that main() holds in plain locals comes back as a NamedTuple). restart_smoke reads THIS body."""
function restart_session!(cs, cs0, groundz, groundz_phys, AICARS, AILINE, CLINE, DO_QUAL, HOLD_START, FUEL1, FUEL_ON, GPLAI_F, PLAYER_G, REPLAY_NCAR, ai_best, ai_lap_prev, ai_lapt0, burn_lap, fuel_laps, fuel, cd_armed, cd_left, cd_said, cd_t0, flush_ibt!, form_grid!, ibt_samples, launch_done, new_replay_path, phase, player_finpos, player_grid, player_laps, race_go, replay_buf, replay_names, replay_out, replay_saved, replay_t, tele_buf, player_s_prev)
    t_restart = time()
    # REPLAY-4: the session that just ended gets its own replay and .ibt; the restart starts new ones
    if replay_buf !== nothing && !isempty(replay_buf)
        write_replay(replay_out[], replay_buf, tele_buf, REPLAY_NCAR, replay_names, CLINE; final = true)
        println("  [session] replay saved: ", basename(replay_out[])); flush(stdout)
        empty!(replay_buf); empty!(tele_buf); replay_t[] = -1.0; replay_saved[] = time()
        replay_out[] = new_replay_path()
    end
    flush_ibt!(ibt_samples)
    # RESTARTGROUND-1 (PO 2026-10-18, Monza: "at start of 2nd lap ... car sinks entirely below road surface, then
    # breaks through road surface and levitates high in the air"): Monza's wall guard in groundz holds LASTZ, and a
    # restart never re-anchored it -- after a wreck at Parabolica (ground ~ -4 m) the new race ran off the road band
    # 1.3 m under the mesh, was launched 12 m when the spline took over at s 460, and the step guard then held the
    # stale -4.17 m so the next wreck sank into the ground. Re-anchor at the spawn first, as SHIFT+R does.
    groundz(cs0.x, cs0.z; acquire = true)
    PLAYER_G[] = NaN; respawnX!(cs; groundz = groundz_phys); DriveRT3D.damage_reset!()
    DC[].lastz = 0.0   # LAPTIME-1: see the respawn below
    WRECKED[] = false; WRECK_FROZEN[] = false; empty!(LOOSE_WHEELS)   # a detached corner is never redrawn otherwise
    CLUTCH_GATE[] = -1.0
    TELLTALE[] = 0.0   # COCKPIT-TACH-1: a restart re-arms the tell-tale
    empty!(AI_COOL)    # WGTD-1 (e): the new race's field races again
    # lap + race state
    cs.laps = 0; lap_t0 = cs.t; last_lap = 0.0; best_lap = 0.0; prev_laps = 0
    race_done = false; empty!(player_laps)
    player_finpos[] = 0; player_grid[] = 0
    launch_done[] = false
    # accumulated arc-length progress. MUST be re-seeded from the RESPAWNED position: zeroing
    # `player_s_prev` would make the next frame's delta a whole lap's worth of progress --
    # the same failure mode as the teleport bug this file already fixes in `prog_delta`.
    player_prog = 0.0
    CLINE !== nothing && (player_s_prev = RaceAI.project(CLINE, cs.x, cs.z)[1])
    # phase + start
    # mirror the ORIGINAL initialisation exactly (line ~5650:
    #   phase = Ref(DO_QUAL ? :practice : :race)
    # -- inventing a variant here is how a restart drifts from a fresh launch.
    phase[] = DO_QUAL ? :practice : :race
    # ...which is `Ref(!HOLD_START)`. Spell it with the FLAG, not a copy of its expression:
    # STARTSEQ-1 added a term (!REPLAY) and this copy would have silently kept the old one,
    # leaving a replay held at a start it can never be given.
    race_go[] = !HOLD_START
    cd_t0[] = -1.0; cd_left[] = -1.0
    # A restart re-asks for the spacebar. Leaving cd_armed latched would skip the prompt and
    # roll straight into the countdown -- the restart would not look like a fresh start.
    cd_armed[] = false; cd_said[] = false
    # AI field back to the grid
    if !isempty(AICARS)
        AICARS .= RaceAI.init_cars(AILINE, length(AICARS); start_s = 30.0)
        fill!(ai_lapt0, cs.t); fill!(ai_lap_prev, 0); fill!(ai_best, Inf)
        RaceAI.aistat_reset!()
        # 2026-10-03 (PO: "rear ended by AI car at start" after R): init_cars is the OLD ad-hoc
        # stagger that RACESTART-2 replaced at launch -- it left AI beside and behind the player.
        # Re-form the grid exactly as the launch does (`if !DO_QUAL && HOLD_START` below the
        # definition of form_grid!): every AI on rows AHEAD of the player.
        (!DO_QUAL && HOLD_START) && (player_grid[] = form_grid!(Inf))
        GPLAI_F[] = nothing                                       # AIGPL-2: rebuilt from the new grid
    end
    # restart refuels (restart_smoke checks for the `fuel[] =` reset here); FUEL-1: and the tank's burnt mass back to 0
    FUEL_ON && (fuel[] = FUEL1 ? FUEL_START_L[] : burn_lap * fuel_laps; CAR3D && FUEL1 && DriveRT3D.set_fuel_burnt!(cs, 0.0))
    println("  [restart] session reset on ", TRACKSEL, " in ",
            round((time() - t_restart)*1000, digits=1), " ms (track NOT reloaded)")
    flush(stdout)
    (lap_t0 = lap_t0, last_lap = last_lap, best_lap = best_lap, prev_laps = prev_laps, race_done = race_done,
     player_prog = player_prog, player_s_prev = player_s_prev)
end

"""E85-S6 HEADLESS AUTODRIVE (JM_AUTODRIVE=1): the AI controller drives the player on the centreline; returns the
frame's input. LOOPSPLIT-1 cycle 2 S2: moved unchanged from the frame loop -- in the loop its `let` wrote main()'s own
`ps` and `step` (and the loop's `up` / `dn` / `thr` / `brk` / `st`) as a side effect; here they are its own."""
function autodrive_step!(cs, CLINE, frames, dt, groundz, inp, ONTRACK)
    let (s0, lat0) = RaceAI.project(CLINE, cs.x, cs.z)
        # BNDWRECK-1 S10: THIS is the actor that wrecks, and S9 showed it consults no
        # previous s at all -- so the measurement has to bring its own.
        if TRACE_DS
            DS_PREV[] >= 0.0 && ds_note!(s0 - DS_PREV[], cs.v, dt, CLINE.total)
            DS_PREV[] = s0
        end
        # ⚠️ The 10th argument is the YAW RATE, not a gain. I first passed a placeholder
        # 1.0 and the car never moved: the controller's anti-spin logic reads ~1 rad/s as a
        # car already sliding and cuts the throttle, so telemetry showed `thr 0.0 kmh 0.0`
        # while steer twitched -- the controller WAS running and correctly refusing to
        # accelerate a car it believed was spinning. Pass the real rate.
        # `cs` has no yaw-rate FIELD -- the model exposes it as a function,
        # DriveRT3D.yawrate3d (aliased AIyaw), which is what the AI field itself uses.
        # `cs.r` would have thrown FieldError at runtime; parse_smoke cannot see that.
        yawrate = try; y = AIyaw(cs); isfinite(y) ? y : 0.0; catch; 0.0; end
        # AUTODRIVE-RING-1 (2026-10-16): one fixed speed wrecks the autodriver in the Ring's first bends (s 619 at
        # 45 m/s; at 28 m/s it stalls by s 816), so whole-lap checks (JM_DRIVECHECK) could not cover the Ring.
        # JM_AUTODRIVE_PROFILE=<pace> caps the target at that fraction of the AI's free-running speed profile on
        # this line (RaceAI.free_speed_profile, computed once), read a car-length ahead. Off by default.
        _vt = AUTODRIVE_V
        if AUTODRIVE_PROF_PACE > 0
            AUTODRIVE_PROF[] === nothing && (AUTODRIVE_PROF[] = RaceAI.free_speed_profile(CLINE; amax = AI_AMAX))
            (ps, pv) = AUTODRIVE_PROF[]
            _k = clamp(floor(Int, mod(s0 + 2.0*cs.v, CLINE.total) / (ps[2] - ps[1])) + 1, 1, length(pv))
            _vt = min(_vt, AUTODRIVE_PROF_PACE * pv[_k])
        end
        thr, brk, st = RaceAI.controller(CLINE, s0, lat0, AUTODRIVE_LAT, _vt,
                                         cs.x, cs.z, cs.θ, cs.v, yawrate; power = 1.0)
        # E106-S15 (PO: "ensure nurburgring and spa can be driven without obstacles
        # (levitation, bouncing) etc on the part of the human driver"). While autodrive is
        # running the lap, WATCH for the three failures the PO named, per frame:
        #   * levitation -- the car's height above the ground under it exceeds AIR_MAX;
        #   * bounce     -- an upward velocity spike with no jump to explain it;
        #   * stuck      -- moving under STUCK_V for STUCK_S seconds ("a graze should scrub
        #                   you but not end your race").
        # Reported at exit as a verdict, so a lap either states it is clean or names where
        # and by how much it was not. JM_DRIVECHECK=1.
        if DRIVECHECK
            # cs.y is the car's WORLD HEIGHT (it is what the replay records as the pose's
            # y and what read back as 620.x at the Ring); cs.x/cs.z are the plan coords.
            # The step comes from the car's own clock, not an assumed `dt` in scope.
            step = max(Float64(cs.t) - DC[].lastt, 1e-4)
            DC[].lastt = Float64(cs.t)
            gh = groundz(cs.x, cs.z)
            # ⚠️ `gh <= -900` CANNOT FIRE HERE, and that is the finding, not an oversight.
            # There are TWO groundz in this file: the top-level one at :2921 returns the
            # -999 "off the HAT" sentinel, but the one in scope here (:5166, nested in
            # main) never does -- off the mesh it HOLDS `LASTZ[]`, the last valid height,
            # and reports the excursion through `ONTRACK[]` instead. So the old
            # `if gh > -900f0` guard was always true (it was guarding against a value this
            # closure cannot produce), and off-mesh frames were measured against a STALE
            # reference height rather than skipped. Read the flag the closure actually
            # sets, immediately after the call that sets it.
            if !ONTRACK[]
                DC[].off_bad += 1
                if DC[].off_bad == 1 || Float64(cs.y) > DC[].off_y
                    DC[].off_s = s0; DC[].off_y = Float64(cs.y)
                end
                length(DC[].offevents) < 24 && (isempty(DC[].offevents) ||
                    abs(DC[].offevents[end][1] - s0) > 20.0) &&
                    push!(DC[].offevents, (s0, Float64(cs.y), Float64(cs.v)*3.6))
            end
            gh < DC[].ghmin && (DC[].ghmin = Float64(gh))   # does the sentinel EVER arrive?
            if gh > -900f0
                air = Float64(cs.y) - Float64(gh)
                if air > DC[].airmax; DC[].airmax = air; DC[].air_s = s0; end
                if air > DC_AIR_MAX
                    DC[].air_bad += 1
                    # log each DISTINCT excursion (a new one only after coming back down),
                    # so the verdict names the SITES rather than one global maximum -- a
                    # single "worst" figure cannot be cross-referenced against the track.
                    if !DC[].inair && length(DC[].events) < 24
                        push!(DC[].events, (s0, air, cs.v*3.6, Float64(cs.x), Float64(cs.z)))
                    elseif DC[].inair && !isempty(DC[].events)
                        # track the PEAK of this excursion, not its onset: recording only
                        # the crossing value made a 9.4 m launch read as 0.84 m, which is
                        # an instrument that understates exactly the thing it is for.
                        (es, epk, ekmh, ex, ez) = DC[].events[end]
                        air > epk && (DC[].events[end] = (es, air, ekmh, ex, ez))
                    end
                    DC[].inair = true
                elseif air < DC_AIR_MAX*0.5
                    DC[].inair = false
                end
            end
            # Skip the first second: the car SETTLES onto the track at spawn, which is a
            # legitimate one-frame height step (27.7 m/s on the Glen). Counting it made
            # every run report a "bounce" at s=0 -- an instrument that always fails is as
            # useless as one that never does.
            if DC[].lastz != 0.0 && cs.t > DC_SETTLE_S
                vz = (Float64(cs.y) - DC[].lastz) / step
                if vz > DC[].vzmax; DC[].vzmax = vz; DC[].vz_s = s0; end
                vz > DC_VZ_MAX && (DC[].vz_bad += 1)
            end
            DC[].lastz = Float64(cs.y)
            if cs.v < DC_STUCK_V
                DC[].stuck += step
                if DC[].stuck > DC[].stuckmax; DC[].stuckmax = DC[].stuck; DC[].stuck_s = s0; end
            else
                DC[].stuck = 0.0
            end
            DC[].maxs = max(DC[].maxs, s0)
        end
        if AUTODRIVE_DIAG > 0 && (frames % AUTODRIVE_DIAG) == 0
            println("  [auto] t=", round(cs.t,digits=1), " v=", round(cs.v*3.6,digits=1),
                    " km/h  thr=", round(thr,digits=2), " brk=", round(brk,digits=2),
                    " steer=", round(st,digits=2), " s=", round(s0,digits=1))
            flush(stdout)
        end
        if AUTODRIVE_MANUAL && !CTL.auto           # (a stall drops the car to AUTO: then drive as AUTO does)
            h = ADM[].hold
            if h == 0
                up = cs.gear == 0 || (cs.rpm > 8700 && cs.gear < 5)
                dn = !up && cs.gear > 1 && cs.rpm < 4300 && brk > 0.1
                (up || dn) && (ADM[] = (hold = 8, up = up, dn = dn))
            end
            h = ADM[].hold; ADM[] = (hold = max(h - 1, 0), up = ADM[].up, dn = ADM[].dn)
            # clutch in for 8 frames; the paddle pulse in the middle one (the gearbox reads an edge)
            # a launch as a driver does it: slip the clutch until the car rolls (70 % in at rest, out by 7 m/s)
            launch = cs.v < 7.0 ? clamp(0.7 - cs.v / 10, 0.0, 1.0) : 0.0
            inp = DriveInput(throttle = h > 0 ? 0.0 : (launch > 0 ? max(clamp(thr, 0, 1), 0.5) : clamp(thr, 0, 1)),
                             brake = clamp(brk, 0, 1), steer = clamp(st, -1, 1), clutch = h > 0 ? 1.0 : launch,
                             shift_up = h == 4 && ADM[].up, shift_down = h == 4 && ADM[].dn, autoshift = false)
        else
            inp = DriveInput(throttle = clamp(thr, 0, 1), brake = clamp(brk, 0, 1),
                             steer = clamp(st, -1, 1), clutch = inp.clutch,
                             shift_up = false, shift_down = false, autoshift = true)
        end
    end
    inp
end

"""E18 replay PLAYBACK, one frame: the VCR keys, then the player's (or the swapped AI's) pose, telemetry and input from the
recording. Returns (inp, rep_ai_raw); the loop then skips the sim. LOOPSPLIT-1 cycle 2 S3: moved unchanged."""
function replay_step!(cs, inp, dt, REP_AICOCKPIT, REP_NT, REP_TEAMCOCKPIT, rep_ai_inputs, rep_ai_lotus, rep_cam, rep_dur, rep_focus, rep_pdn, rep_pend, rep_phome, rep_play, rep_pn, rep_ppd, rep_ppu, rep_psp, rep_pup, rep_pv, rep_pw, rep_rt, rep_speed, rep_swap, rep_team, rep_team_items, rep_tyres, rep_tyshow, repd, replay_poses, replay_tele)
    # REPLAY-5 (PO 2026-10-08: "allow the user to move to the end or the beginning with one command. Currently when you
    # reach the end of the replay it just gets stuck, and you can't back up"): at the end playback kept running into
    # the clamp, so a tap of <- moved back a fraction of a second and play carried it straight back to the end. Now
    # the replay PAUSES at the end (the arrows then scrub freely), SPACE at the end plays again from the start,
    # HOME / END jump to the start / end, PAGE UP / PAGE DOWN jump 10 s back / forward.
    sp = key(GLFW.KEY_SPACE)
    if sp && !rep_psp[]
        rep_play[] = !rep_play[]
        (rep_play[] && rep_rt[] >= rep_dur - 1e-6) && (rep_rt[] = 0.0)   # SPACE at the end: from the start
    end
    rep_psp[] = sp
    kh = key(GLFW.KEY_HOME); (kh && !rep_phome[]) && (rep_rt[] = 0.0); rep_phome[] = kh
    ke = key(GLFW.KEY_END);  (ke && !rep_pend[]) && (rep_rt[] = rep_dur; rep_play[] = false); rep_pend[] = ke
    kpu = key(GLFW.KEY_PAGE_UP);   (kpu && !rep_ppu[]) && (rep_rt[] = clamp(rep_rt[] - 10.0, 0.0, rep_dur)); rep_ppu[] = kpu
    kpd = key(GLFW.KEY_PAGE_DOWN); (kpd && !rep_ppd[]) && (rep_rt[] = clamp(rep_rt[] + 10.0, 0.0, rep_dur)); rep_ppd[] = kpd
    up = key(GLFW.KEY_UP);   (up && !rep_pup[]) && (rep_speed[] = clamp(rep_speed[]*2, 0.25, 8.0)); rep_pup[] = up
    dn = key(GLFW.KEY_DOWN); (dn && !rep_pdn[]) && (rep_speed[] = clamp(rep_speed[]/2, 0.25, 8.0)); rep_pdn[] = dn
    key(GLFW.KEY_RIGHT) && (rep_rt[] = clamp(rep_rt[] + 8*dt, 0.0, rep_dur))   # hold to scrub
    key(GLFW.KEY_LEFT)  && (rep_rt[] = clamp(rep_rt[] - 8*dt, 0.0, rep_dur))
    rep_play[] && (rep_rt[] = clamp(rep_rt[] + dt*rep_speed[], 0.0, rep_dur))
    (rep_play[] && rep_rt[] >= rep_dur - 1e-6) && (rep_play[] = false)   # REPLAY-5: stop AT the end, do not grind on it
    cf = key(GLFW.KEY_C); (cf && !rep_pn[]) && (rep_focus[] = mod(rep_focus[]+1, repd.ncar)); rep_pn[] = cf   # E25: switch CAR
    cvv = key(GLFW.KEY_V); (cvv && !rep_pv[]) && (rep_cam[] = mod1(rep_cam[]+1, length(REPLAY_CAMS))); rep_pv[] = cvv  # E25: switch ANGLE
    (pp, rep_ai_raw) = replay_poses(rep_rt[])
    rep_team[] = (REP_TEAMCOCKPIT && REPLAY_CAMS[rep_cam[]] === :cockpit && rep_focus[] >= 1 && !rep_ai_lotus(rep_focus[])) ?
                 rep_team_items(rep_focus[]) : nothing                                   # COCKPIT-2 S6
    rep_swap[] = REP_AICOCKPIT && REPLAY_CAMS[rep_cam[]] === :cockpit && (rep_ai_lotus(rep_focus[]) || rep_team[] !== nothing)
    if rep_swap[]                                   # COCKPIT-2 S5: ride in the AI Lotus's cockpit
        k_ = rep_focus[]; rep_ai_raw = copy(rep_ai_raw); (pp, rep_ai_raw[k_]) = (rep_ai_raw[k_], pp)
    end
    cs.x = pp[1]; cs.y = pp[2]; cs.z = pp[3]; cs.θ = pp[4]; cs.v = 0.0; cs.pitch = 0.0; cs.roll = 0.0
    if REP_NT > 0     # COCKPIT-2 S1: wheel, gloves, needles and HUD follow the recording, not the live controller
        rt_ = replay_tele(rep_rt[])
        cs.v = rt_.speed; cs.rpm = rt_.rpm; cs.gear = rt_.gear
        inp = DriveInput(throttle = rt_.throttle, brake = rt_.brake, steer = rt_.steer, clutch = rt_.clutch)
        rep_tyres[] = rt_.tyres
    end
    if rep_swap[]                                   # COCKPIT-2 S5: the AI's derived steer / revs / gear
        ai_ = rep_ai_inputs(rep_rt[], rep_focus[])
        cs.v = ai_.v; cs.rpm = ai_.rpm; cs.gear = ai_.gear; rep_tyres[] = nothing
        inp = DriveInput(throttle = 0.0, brake = 0.0, steer = ai_.steer, clutch = 0.0)
    end
    kw = key(GLFW.KEY_W); (kw && !rep_pw[]) && (rep_tyshow[] = !rep_tyshow[]); rep_pw[] = kw   # REPLAY-6: W = tyres
    # cockpit interior only renders for the player car in COCKPIT mode; every other angle shows the driver figure + full car
    CTL.view = (REPLAY_CAMS[rep_cam[]] === :cockpit && (rep_focus[] == 0 || rep_swap[])) ? 0 : 1
    (inp, rep_ai_raw)
end

"""Lap timing, one frame: a completed lap is timed, banked and logged; at race distance the classification, the result
file and the recent-average bank. Returns the five lap-state locals main() keeps. LOOPSPLIT-1 cycle 2 S4: moved unchanged."""
function lap_timing_step!(cs, prev_laps, lap_t0, last_lap, best_lap, race_done, phase, player_laps, telem, AICARS, standings, player_finpos, player_grid, AI_TGT, player_prog, CLINE, FUEL_ON, AILINE, ai_best, ent_name, fmt_lap, save_human_best, banking_allowed, plausible_lap)
    if cs.laps > prev_laps
        last_lap = cs.t - lap_t0; lap_t0 = cs.t
        improved = best_lap == 0.0 || last_lap < best_lap
        improved && (best_lap = last_lap)
        phase[] == :race && push!(player_laps, last_lap)   # C: bank this lap for the per-lap results tab
        # A3: persist the player's best lap for THIS track (practice OR race) the moment it improves, so
        # the GUI can pre-set the AI-speed % to the pace matching the human's best (≈ GPLrank/best·100).
        improved && cs.laps >= 1 && save_human_best(TRACKSEL, best_lap)
        telem !== nothing && (write(telem, "# LAP $(cs.laps)  $(fmt_lap(last_lap))\n"); flush(telem))
        println(phase[] == :practice ? "  practice lap: $(fmt_lap(last_lap))" : "  lap $(cs.laps): $(fmt_lap(last_lap))",
                last_lap==best_lap ? "  (best)" : "")   # practice laps just bank your best for the grid
        begin
        if phase[] == :race && cs.laps >= RACE_LAPS && !race_done    # race distance complete
            race_done = true
            println("\n  ═══════ RACE FINISHED — $RACE_LAPS laps ═══════")
            order = isempty(AICARS) ? [(0, 0.0)] : standings()
            player_finpos[] = findfirst(e -> e[1] == 0, order)
            println("\n  ══════ YOU FINISHED — P$(player_finpos[]) of $(length(order)) ══════")
            println("  started P$(player_grid[])   best lap $(fmt_lap(best_lap))   total $(fmt_lap(cs.t))")
            # R1 DIAG (PO finished-6th-when-1st): dump the ACTUAL progress the standings ranked on, so a
            # mismatch with what you saw on track is unambiguous.  AI pace + the raw lap+fraction each.
            println("  ── R1 DIAG  (AI pace ", round(Int,AI_PCT), "% → target ", round(AI_TGT,digits=1),
                    "s/lap;  YOU laps=", cs.laps, " prog=", round(player_prog/(CLINE===nothing ? 1 : CLINE.total), digits=2), ") ──")
            # STANDINGS-1 S1 (2026-09-16): the DIAG above prints the progress ACCUMULATOR
            # (player_prog), but standings() ranks on a DIFFERENT quantity:
            #   pp = cs.laps + cs.lapdist/LAPLEN
            # cs.laps is derived from player_prog; cs.lapdist is an independent TRKSURF probe.
            # Print BOTH halves and the pp that was actually ranked, so "you finished Pn" can be
            # checked against the number the sort saw instead of against the number we print.
            # Without this, the DIAG and the classification can disagree and neither says so.
            let _old = cs.laps + (FUEL_ON && LAPLEN > 0 ? clamp(cs.lapdist/LAPLEN, 0.0, 1.0) : 0.0),
                _new = CLINE === nothing ? Float64(cs.laps) : player_prog/CLINE.total
                println("     YOU     ranked pp=", round(standings()[findfirst(e -> e[1] == 0, standings())][2], digits=3),
                        "   [old formula ", round(_old, digits=3),
                        " = laps ", cs.laps, " + lapdist ", round(cs.lapdist, digits=1),
                        "/", round(LAPLEN, digits=1), "]",
                        "   [accumulator ", round(_new, digits=3), "]")
            end
            for (i,c) in enumerate(AICARS)
                # AISPREAD-1 S4 (2026-09-16): print each AI's BEST LAP here, not just its
                # progress.  Every number this item has compared against the gold so far has
                # been a stint AVERAGE derived from the player's elapsed time divided by the
                # car's progress -- which includes the standing start and so reads slow, a
                # caveat S3 and TELEMSTATE-1 S4 both had to carry.  ai_best[] has been tracked
                # all along (it skips the grid-launch lap by construction) and nothing printed
                # it, so the gold's BEST laps had no like-for-like counterpart on our side.
                println("     ", rpad(AISPECS[i][1],8), " lap=", c.lap, " prog=", round(c.lap + mod(c.s, AILINE.total)/AILINE.total, digits=2),
                        " v=", round(Int,c.v*3.6), "km/h pace=", round(Int,c.pace*100), "%",
                        "  best=", isfinite(ai_best[i]) ? fmt_lap(ai_best[i]) : "-")
            end
            println("  ── final classification ──")
            for (p, (id, _)) in enumerate(order)
                println("   P$p  ", ent_name(id), id==0 ? "  ← YOU (best $(fmt_lap(best_lap)))" : "")
            end
            println()
            # C (PO): GPL-style classification with a TIME GAP to the winner.  Each car's total race
            # time is its elapsed time scaled to the full distance (cs.t · LAPS / progress) — the leader
            # (most progress) has the smallest, so gap = est − leader_est ≥ 0; a car a full lap or more
            # down is shown "+N lap(s)" instead.  Best lap of ANYONE = min(player best, every AI best).
            lead_prog = order[1][2]
            est_time(prog) = cs.t * RACE_LAPS / max(prog, 0.01)
            lead_est = est_time(lead_prog)
            # best lap turned by anyone in the field (player or an AI)
            best_any = best_lap > 0 ? best_lap : Inf; best_any_who = best_lap > 0 ? "You" : "-"
            for i in 1:length(AICARS)
                if ai_best[i] < best_any; best_any = ai_best[i]; best_any_who = ent_name(i); end
            end
            # E14: write the result for the GUI's post-race results screen (quit / race again / choose track)
            try
                # 2026-10-20: a smoke race that finished overwrote the PO's real results file (the launcher's results tab);
                # smoke runs write theirs to /tmp (as their .ibt and replays do)
                open(SMOKE ? "/tmp/jm_smoke_last_race_result.txt" : joinpath(@__DIR__, "last_race_result.txt"), "w") do io
                    println(io, "track\t$(TRACKSEL)"); println(io, "laps\t$RACE_LAPS")
                    println(io, "you_pos\t$(player_finpos[])"); println(io, "field\t$(length(order))")
                    println(io, "you_start\t$(player_grid[])")
                    println(io, "you_best\t$(best_lap > 0 ? fmt_lap(best_lap) : "-")"); println(io, "you_total\t$(fmt_lap(cs.t))")
                    println(io, "best_any\t$(isfinite(best_any) ? fmt_lap(best_any) : "-")\t$best_any_who")
                    println(io, "you_laps\t", join((fmt_lap(t) for t in player_laps), ","))   # C: per-lap times tab
                    println(io, "win_total\t$(fmt_lap(lead_est))")   # PO: the WINNER's total elapsed time (top row, right)
                    for (p, (id, prog)) in enumerate(order)
                        laps_down = floor(Int, lead_prog - prog)
                        # PO: the winner's row shows the winner's TOTAL TIME; everyone else a gap (or +N laps)
                        gap = p == 1 ? fmt_lap(lead_est) :
                              (laps_down >= 1 ? "+$laps_down lap$(laps_down>1 ? "s" : "")" :
                                                "+$(fmt_lap(est_time(prog) - lead_est))")
                        println(io, "P$p\t$(ent_name(id))\t$gap")   # name + gap-to-winner column
                    end
                end
            catch e; @warn "result write failed" e; end
            # B (PO): pre-fill the AI % from the driver's MOST RECENT race AVERAGE on this track (not the
            # best lap) — so the field is paced to how you ACTUALLY race, not a one-off hot lap.  Overwrite
            # (most-recent, not best) with this race's mean lap time.
            if !isempty(player_laps) && banking_allowed()   # TESTLAP-1: see save_human_best
                avg = sum(player_laps)/length(player_laps)
                if !plausible_lap(TRACKSEL, avg)
                    println("  ⚠ not banking an implausible race average for ", TRACKSEL, ": ",
                            round(avg, digits=3), " s")
                else
                try
                    rp = joinpath(@__DIR__, "human_recent.txt"); recents = Dict{String,Float64}()
                    isfile(rp) && for ln in eachline(rp)
                        sp = split(strip(ln), '\t'); length(sp)==2 && (v=tryparse(Float64,sp[2]))!==nothing && (recents[sp[1]]=v)
                    end
                    recents[TRACKSEL] = avg
                    open(rp, "w") do io; for (k,v) in recents; println(io, "$k\t$(round(v,digits=3))"); end; end
                catch e; @warn "human_recent write failed" e; end
                end
            end
        end
        end
    elseif cs.laps < prev_laps                 # respawn reset the lap counter
        lap_t0 = cs.t
    end
    prev_laps = cs.laps
    (prev_laps = prev_laps, lap_t0 = lap_t0, last_lap = last_lap, best_lap = best_lap, race_done = race_done)
end

"""One iRacing .ibt telemetry row for this frame (the channels the gold tools read). LOOPSPLIT-1 cycle 2 S5: moved unchanged."""
function ibt_sample!(ibt_samples, cs, inp, fuel)
    tl = telemetryX(cs); δw = inp.steer * (CAR3D ? DriveRT3D.MAXSTEER : SKIDPAD ? 0.30 : CAR.max_steer)   # the angle the physics used
    row = Dict{String,Float64}(
        "SessionTime"=>cs.t, "SessionTick"=>Float64(length(ibt_samples)+1),
        "IsOnTrack"=>cs.ontrack ? 1.0 : 0.0,
        "Speed"=>cs.v, "RPM"=>cs.rpm, "Gear"=>Float64(cs.gear),
        "Throttle"=>inp.throttle, "Brake"=>inp.brake, "Clutch"=>1.0-inp.clutch,
        # PHYSFID-1 S4: iRacing's channel is the STEERING-WHEEL angle (rad at the rim); julia wrote the road-wheel angle,
        # ~10x smaller -- julia and iRacing .ibt files could not be compared. Road angle x the session's steering ratio.
        "SteeringWheelAngle"=>δw*STEER_RATIO[], "SteeringWheelAngleMax"=>deg2rad(DriveRT3D.WHEEL_LOCK_DEG), "FrameRate"=>FRAME_FPS[],   # PERF-4: was never filled (always 0)
        "Lap"=>Float64(cs.laps+1), "LapCompleted"=>Float64(cs.laps),
        "LapDist"=>cs.lapdist, "LapDistPct"=>(SKIDPAD ? 0.0 : (LAPLEN>0 ? cs.lapdist/LAPLEN : 0.0)),
        "Yaw"=>cs.θ, "YawRate"=>tl.r,
        "VelocityX"=>tl.u, "VelocityY"=>tl.v, "VelocityZ"=>0.0,
        # VertAccel is REAL in 3-D mode (the planar model has no vertical DOF → 1 g stub)
        "LongAccel"=>tl.ax, "LatAccel"=>tl.ay, "VertAccel"=>(CAR3D ? tl.vacc : 9.80665),
        "LFspeed"=>tl.ωf*0.30, "RFspeed"=>tl.ωf*0.30, "LRspeed"=>tl.ωRL*DriveRT3D.RW_R, "RRspeed"=>tl.ωRR*DriveRT3D.RW_R,
        "Alt"=>cs.y,
        # FUELIBT-1: the tank (litres, as iRacing's FuelLevel) -- it was never written, so 0 for every session
        "FuelLevel"=>fuel[], "FuelLevelPct"=>fuel[]/DriveRT3D.FUEL_MAX_L)
    if CAR3D                                   # real ride heights + body attitude (Flugplatz benchmark)
        # E106-S37: export ride height ONLY while the wheels are loaded. Measured
        # (E106-S36): settled and grounded it reads 0.082/0.082/0.106/0.106 m, matching
        # the .ibt setup (82.9/82.9/105.2/105.2 mm) exactly -- the formula is right. But
        # `zref` is frozen whenever the car is airborne (by design, so the body falls
        # relative to it), and while frozen `terr - zref` is unbounded: the PO's Spa
        # capture exported a minimum of -73.5 m and a mean of -0.16 m. A consumer cannot
        # tell that from a real measurement.
        # NaN, not a clamp: NaN says "not measured here", a clamp would export a
        # plausible lie -- and ride height is the channel the PO's "car is several inches
        # off the ground" report depends on, so a lie there is worse than a gap.
        # JM_RH_RAW=1 exports the raw value for A/B against the old captures.
        _rhok = get(ENV,"JM_RH_RAW","") != "" || getproperty(tl, :grounded)
        row["LFrideHeight"]= _rhok ? tl.rh[1] : NaN
        row["RFrideHeight"]= _rhok ? tl.rh[2] : NaN
        row["LRrideHeight"]= _rhok ? tl.rh[3] : NaN
        row["RRrideHeight"]= _rhok ? tl.rh[4] : NaN
        row["Pitch"]=tl.pitch; row["Roll"]=tl.roll
        bp = DriveRT3D.brakepress3d(cs)            # CARPHYS-1 S6: the BrakeSystem object's line pressures, as iRacing logs them
        if bp !== nothing
            row["LFbrakeLinePress"] = bp[1]; row["RFbrakeLinePress"] = bp[1]
            row["LRbrakeLinePress"] = bp[2]; row["RRbrakeLinePress"] = bp[2]
        end
    end
    push!(ibt_samples, row)
    nothing
end

"""Force feedback, one frame: the rim torque (or the legacy road term), de-spiked, squelched, low-passed, plus any jolt.
Returns the two filter states (fy_lp, ffb_f). LOOPSPLIT-1 cycle 2 S5: moved unchanged."""
function ffb_step!(ffb, cs, inp, dt, fy_lp, ffb_f, ffb_jolt)
    τrim = (FFB_PHYS && CAR3D) ? DriveRT3D.rimtorque3d(cs) : nothing
    if τrim !== nothing                                # CARPHYS-1 S5: the column's rim torque, in old road-term units
        fy = -τrim / FFB_TREF; trail = 1.0
    else                                               # legacy: front Fy × a hand-drawn trail curve
        tl  = telemetryX(cs)
        αf  = atan(tl.v + FFB_AF*tl.r, max(tl.u, 1.0)) - clamp(inp.steer, -1, 1)*FFB_DELTA
        trail = FFB_TFLOOR + (1 - FFB_TFLOOR) * clamp(1 - abs(αf)/FFB_ATRAIL, 0.0, 1.0)
        fy = cs.tc[1][2] + cs.tc[2][2]                 # front-axle lateral force (mg/4 units) — the ROAD feel
    end
    fy_lp += (fy - fy_lp) * clamp(dt/FFB_DESPIKE, 0.0, 1.0)   # de-spike the coarse GPL mesh (1-frame 11g jolts → smooth)
    fy = fy_lp * fy_lp*fy_lp / (fy_lp*fy_lp + FFB_SQ*FFB_SQ)   # squelch tyre-force noise (jostle), not the spring
    mz  = fy * trail
    spd = clamp(cs.v/2.5, 0.0, 1.0)                    # road feel fades in with speed
    # self-centering spring ∝ WHEEL ANGLE — ALWAYS present ⇒ no dead center. Per wheel degree, as it was
    # tuned (raw ±1 = ±450° on the TX): with physical steering (STEER_GAIN) inp.steer is road angle / lock,
    # 2.6x more per wheel degree, which silently stiffened the spring 2.6x (2026-10-03). Divide it back out.
    spr = FFB_SPRING * clamp(STEER_GAIN[] > 0 ? inp.steer / STEER_GAIN[] : inp.steer, -1, 1)
    target = if FFB_IRMODE && τrim !== nothing           # PHYSFID-1 S1: iRacing's linear law (see FFB_IRMODE)
        clamp(FFB_SIGN * (mz * FFB_TREF / FFB_MAXNM) + FFB_SIGN * FFB_SPRING_IR * clamp(STEER_GAIN[] > 0 ? inp.steer / STEER_GAIN[] : inp.steer, -1, 1), -1.0, 1.0)
    else
        tanh(FFB_SIGN * (FFB_GAIN * mz * spd + spr))
    end
    ffb_f += (target - ffb_f) * clamp(dt/FFB_LP, 0.0, 1.0)   # 1st-order low-pass: smooth, continuous
    # the impact JOLT takes PRIORITY over the steering force: scale the road/spring force down by
    # the jolt size so a hit is always FELT, even mid-corner when ffb_f is already near full lock
    # (otherwise `ffb_f + jolt` just clamps and you feel nothing — why AI hits read as "no kick").
    FFB.set_force!(ffb, clamp(ffb_f*(1.0 - min(abs(ffb_jolt), 1.0)) + ffb_jolt, -1.0, 1.0))
    (fy_lp, ffb_f)
end

"""The player against the local AI field, one frame: the draft tow, then each touching car's rigid-body contact
(the player's kick + damage, the AI's response -- loose Car3D, physics AI or the field's nudge). Returns ffb_jolt.
LOOPSPLIT-1 cycle 2 S6: moved unchanged."""
function ai_contact_step!(cs, ai_poses, AICARS, AIPHYS, PLAYER_CDA, ffb_jolt)
    # E56 slipstream for the PLAYER: tuck behind a car on a straight → reduced frontal drag
    # (CdA_scale<1) → you reel them in + slingshot past.  A REAL aero effect integrated by the
    # chassis ODE next frame, not a forward velocity bump.  Works vs the default kinematic field too.
    if CAR3D && (ph = JuliaMotor.hat(TRKSURF, cs.x, cs.z); ph.found && abs(ph.lateral) <= ROAD_HALFW)
        plds = [(p[1], p[3], p[4], AICARS[k].v) for (k,p) in enumerate(ai_poses)]
        ptw = draft_tow(cs.x, cs.z, cs.θ, cs.v, plds)
        ptw > 0.0 && (PLAYER_CDA[] = 1.0 - DRAFT_DRAG_CUT * clamp(ptw/TOW_MAX, 0.0, 1.0))
    end
    pm = 560.0; am = 560.0                    # FFB / AI-response scales; the player's impulse is car_contact_impulse (CAR_E 0.12: inelastic)
    # E96-S5: the PLAYER's world velocity, not speed x heading. `cs.v` is UNSIGNED, so a car
    # being shoved backwards after a clash still read as travelling along its nose -- and the
    # closing test below (`vrel <= 0.2 && continue`) would then see CLOSING where the cars are
    # actually separating, and hand out another impulse every frame. That is the same sign
    # error E96-S2 found in solid_contact and the world fence; this site was missed because
    # car-to-car contact was not what the PO was reporting at the time.
    # The AI side keeps v x heading: AI cars are driven along their own nose and are never
    # shoved backwards by this path (it bounds their response deliberately, R1), so their
    # speed and heading agree. The player is the body that gets pushed around.
    pvx = WVX[]; pvz = WVZ[]
    for (k, p) in enumerate(ai_poses)
        dx = p[1] - cs.x; dz = p[3] - cs.z; d = hypot(dx, dz)
        (d < 1e-3 || !car_near(dx, dz, d, cs.θ, p[4])) && continue   # CARCOLLIDE-2: broad phase; carcontact.jl finds the touching parts
        nx = dx/d; nz = dz/d                          # contact normal, player → AI
        ac = AICARS[k]; aθ = p[4]
        lat = -dx*sin(cs.θ) + dz*cos(cs.θ)            # contact offset in the player's frame → spin sign
        # ANY car contact (even a sustained scrape, before the closing-impulse test) gives a clear
        # FF kick, so you always FEEL the AI — not just on a square closing hit.
        ffb_jolt = clamp(-sign(lat)*0.6, -1.0, 1.0)
        avx = ac.v*cos(aθ); avz = ac.v*sin(aθ)
        if haskey(LOOSE_OF, k)                        # CARCOLLIDE-2 S4: a loose car moves as its Car3D does
            lc = LOOSE_CARS[LOOSE_OF[k]]; la = lc.getall(lc.integ)
            avx = la[4]*cos(lc.θ) - la[5]*sin(lc.θ); avz = la[4]*sin(lc.θ) + la[5]*cos(lc.θ)
        end
        # HANDLING-1 S3: a rigid-body impulse at the contact point (car_contact_impulse) -- no amplification, no
        # side-only yaw kick, no invented hop/roll/scrub; the bodywork friction bleeds speed on a side-swipe.
        imp = car_contact_impulse(cs.x, cs.z, cs.θ, pvx, pvz, CAR3D ? DriveRT3D.yawrate3d(cs) : 0.0, p[1], p[3], avx, avz; θb = aθ)
        imp === nothing && continue                   # separating → no new impulse (the contact kick already fired)
        (pdvx, pdvz, pdr, j) = imp
        bumpX!(cs, pdvx, pdvz, pdr, imp[5], imp[6], imp[7])   # CARCOLLIDE-2 S3: + heave/roll/pitch (nose-dive, launch)
        carhit_damage!(cs, pdvx, pdvz, j)              # CARINTERACT-1: a car hit costs YOU, as a wall does
        ffb_jolt = clamp(ffb_jolt - sign(lat)*(j/pm)*0.4 - 0.5, -1.0, 1.0)   # a CLOSING hit adds a bigger kick
        if !AI_PHYSICS && loose_hit!(k, p, aθ, avx, avz, cs, pvx, pvz, CAR3D ? DriveRT3D.yawrate3d(cs) : 0.0, cs.t)
            # CARCOLLIDE-2 S4: knocked loose (or already loose) -- the struck car answers with its own physics
        elseif AI_PHYSICS                              # the AI is a real physics car → impulse it too
            alat = -dx*sin(aθ) + dz*cos(aθ)
            # E55: PLANAR push + mild yaw only — no vertical launch / roll on the AI (it must not
            # flip or cartwheel when the player nudges it), even though the player still feels the hit.
            AIbump!(AIPHYS[k], (j/am)*nx, (j/am)*nz, clamp(sign(alat)*(j/am)*0.05, -1.0, 1.0))
        else
            # PO: the kinematic AI must NOT "flit off like an insect" or get ROCKETED forward (which
            # inflated its lap count — see R1).  A real crash is ENERGY-LOSSY: it does not propel the
            # victim.  So the AI HOLDS its line (tiny lateral shove + a decaying yaw twitch carry the
            # "knocked" look) and its speed change is BOUNDED — nosed ⇒ slowed, rear-ended ⇒ only a
            # small bounded nudge, never dragged up toward the (fast) player's speed.
            along  = nx*cos(aθ) + nz*sin(aθ); across = -nx*sin(aθ) + nz*cos(aθ)
            ac.v   = max(0.0, ac.v + clamp((j/am)*along, -8.0, 2.5))            # bounded: no escape-velocity boost
            ac.lane = clamp(ac.lane + clamp((j/am)*across*0.04, -0.7, 0.7), -RaceAI.LANE_MAX, RaceAI.LANE_MAX)  # gentle nudge, not a dart
            ac.spin += clamp((j/am)*across*0.06, -0.8, 0.8)   # yaw twitch (decays) — looks knocked, not weightless
        end
    end
    ffb_jolt
end

"""JM_CRASH harness, one frame (GPLWALL-1): teleports the car into the next scripted crash, watches it for going THROUGH
a wall, scores the penetration, and prints one line per scenario. LOOPSPLIT-1 cycle 3 S1: moved unchanged."""
function crash_step!(cs, frames, place_at_s!, crash_i, crash_invis, crash_jit, crash_ninv, crash_plat, crash_rec, crash_sum, crash_t0, crash_thru)
    if crash_i[] == 0 || frames - crash_t0[] >= CRASH_FRAMES
        if crash_i[] > 0                                  # close the running scenario
            (s0, sd, ang, vv) = CRASHES[crash_i[]]
            r = gplw_locate_any(cs.x, cs.z)
            (lo, hi) = r === nothing ? (NaN, NaN) : gplw_road_interval(r[1], r[2])
            ok = !crash_thru[]
            crash_invis[] > 0 && (crash_ninv[] += 1)
            (wp, sp, bp) = crash_rec[]
            crash_sum[] = (crash_sum[][1] + 1, crash_sum[][2] + (ok ? 0 : 1), max(crash_sum[][3], wp), max(crash_sum[][4], sp))
            println("  [crash] ", crash_i[], "/", length(CRASHES), " s=", round(Int, s0), " ", sd > 0 ? "L" : "R", " ",
                    round(Int, ang), "deg ", round(Int, vv), " m/s: wall pen max ", round(wp, digits = 2),
                    " m, drawn-face pen max ", round(sp, digits = 2), " m, old-box pen max ", round(bp, digits = 2), " m, end lat ", r === nothing ? "?" : round(r[3], digits = 2),
                    " in [", round(lo, digits = 1), ", ", round(hi, digits = 1), "] -> ", ok ? "CONTAINED" : "THROUGH",
                    WRECKED[] ? "  (wrecked)" : "", "  v_end ", round(cs.v, digits = 1),
                    isfinite(crash_jit[][1]) ? string("  REST JITTER y ", round(crash_jit[][2] - crash_jit[][1], digits = 3), " m, heading ",
                        round(rad2deg(crash_jit[][4] - crash_jit[][3]), digits = 2), " deg") : "",
                    crash_invis[] > 0 ? "  INVISIBLE-CONTACT frames $(crash_invis[])" : ""); flush(stdout)
        end
        crash_i[] += 1
        if crash_i[] <= length(CRASHES)
            (s0, sd, ang, vv) = CRASHES[crash_i[]]
            place_at_s!(s0)
            DriveRT3D.damage_reset!(); WRECKED[] = false; WRECK_FROZEN[] = false; empty!(LOOSE_WHEELS); DC[].lastz = 0.0
            r = gplw_locate_any(cs.x, cs.z)
            if r !== nothing
                (_, _, _, gx, gz) = r; a = deg2rad(ang)
                dx = cos(cs.θ)*cos(a) + sd*gx*sin(a); dz = sin(cs.θ)*cos(a) + sd*gz*sin(a)
                DriveRT3D.place3d!(cs, cs.x, cs.z, atan(dz, dx); v = vv)
            end
            gplw_teleported!(); OBS_STAT[] = (hits = 0, clamps = 0, maxpen = 0.0)
            crash_t0[] = frames; crash_rec[] = (0.0, 0.0, 0.0)
            crash_plat[] = NaN; crash_thru[] = false; crash_invis[] = 0; crash_jit[] = (Inf, -Inf, Inf, -Inf)
        else
            println("  [crash] SUMMARY ", TRACKSEL, ": ", crash_sum[][1], " scenarios, THROUGH ", crash_sum[][2],
                    ", deepest GPL-wall penetration ", round(crash_sum[][3], digits = 2), " m, deepest drawn-face penetration ",
                    round(crash_sum[][4], digits = 2), " m; scenarios with an INVISIBLE-wall contact ", crash_ninv[],
                    "; wall+obstacle cost ", round(1e6*GPLW_T[][1]/max(GPLW_T[][2], 1), digits = 1), " us/frame"); flush(stdout)
        end
    else
        WRECK_FROZEN[] && (j_ = crash_jit[]; crash_jit[] = (min(j_[1], cs.y), max(j_[2], cs.y), min(j_[3], cs.θ), max(j_[4], cs.θ)))
        (_, _, _, glo, ghi, _, _, _, _, gend_) = gplwall_gaps(cs.x, cs.z, cs.θ)
        glo = min(glo, gend_)          # an END face counts as wall penetration too (measurement only)
        # THROUGH, measured directly: the car's centre inside a blocking wall (beyond the clamp's reach), or in a
        # DIFFERENT free interval from last frame's centre at this same station (it crossed a wall between frames).
        rr = gplw_locate(cs.x, cs.z)                # the player's continuous locator (hint), not nearest-any
        if rr !== nothing
            (sc_, fc_, lc_) = rr
            Icur = GPLWall.free_interval(GPLWALLS, sc_, fc_, lc_, lc_; hmin = GPLW_HMIN)
            inwall = !(Icur[1] <= lc_ <= Icur[2])
            crossed = false
            if !isnan(crash_plat[])
                Iprev = GPLWall.free_interval(GPLWALLS, sc_, fc_, crash_plat[], crash_plat[]; hmin = GPLW_HMIN)
                crossed = (Iprev[1] <= crash_plat[] <= Iprev[2]) && !inwall && Iprev[1:2] != Icur[1:2] &&
                          abs(crash_plat[] - lc_) < 5.0
            end
            # a centre past a face by more than the half-width = the body is wholly beyond it. (A car jammed in a
            # closing wedge narrower than itself has its centre a little past one face; that is not through.)
            (inwall && min(abs(lc_ - Icur[1]), abs(lc_ - Icur[2])) > CARW) && (crash_thru[] = true)
            crossed && (crash_thru[] = true)
            if get(ENV, "JM_CRASH_TRACE", "0") != "0" && frames - crash_t0[] <= parse(Int, get(ENV, "JM_CRASH_TRACE_N", "90"))
                (_, _, _, glo2, ghi2) = gplwall_gaps(cs.x, cs.z, cs.θ)
                println("   [ctrace] f", frames - crash_t0[], " x ", round(cs.x, digits = 1), " z ", round(cs.z, digits = 1),
                        " sec ", sc_, " f ", round(fc_, digits = 2), " lat ", round(lc_, digits = 2), " I ", round.(Icur[1:2], digits = 2),
                        " prev ", round(GPLW_PREV[], digits = 2), " glo ", round(glo2, digits = 2), " ghi ", round(ghi2, digits = 2),
                        " v ", round(cs.v, digits = 1), inwall ? " INWALL" : "", crossed ? " CROSSED" : "")
            end
            crash_plat[] = lc_
        end
        # INVISIBLE contact: touching a GPL wall with nothing drawn (no hard drawn face, no solid) within 0.5 m
        if min(glo, ghi) < 0.0        # touching a GPL wall: is ANY drawn vertical face within 1 m of the car?
            near = false
            ci = floor(Int, cs.x/OBS_C); cj = floor(Int, cs.z/OBS_C)
            for gi in ci-1:ci+1, gj in cj-1:cj+1, (ax, az, bx, bz) in get(DRAWN_GRID, (gi, gj), NTuple{4,Float64}[])
                seg_seg(cs.x + CARLF*cos(cs.θ), cs.z + CARLF*sin(cs.θ), cs.x - CARLF*cos(cs.θ), cs.z - CARLF*sin(cs.θ),
                        ax, az, bx, bz)[1] < CARW + 1.0 && (near = true; break)
            end
            near = near || any(k -> car_gap(cs.x, cs.z, cs.θ, k)[1] < 1.0, eachindex(SOLIDS))
            if !near     # a drawn BANK: GPL models dunes/earth banks as raised strips; we draw them as slopes
                (_, _, _, _, _, gx_, gz_) = gplwall_gaps(cs.x, cs.z, cs.θ)
                sgn_ = glo < ghi ? -1.0 : 1.0                    # toward the wall being touched
                h0 = JuliaMotor.hat3d(TERRAIN, cs.x, cs.z; ref = Inf)
                for dd in 0.5:0.5:(CARW + 2.0)
                    h = JuliaMotor.hat3d(TERRAIN, cs.x + sgn_*gx_*dd, cs.z + sgn_*gz_*dd; ref = Inf)
                    (h0[3] && h[3] && h[1] - h0[1] >= 0.25) && (near = true; break)
                end
            end
            near || (crash_invis[] += 1)
        end
        bpn = 0.0                                   # old SOLIDS (discs/boxes; no positional limit)
        for k in eachindex(SOLIDS); bpn = max(bpn, -car_gap(cs.x, cs.z, cs.θ, k)[1]); end
        opn = 0.0                                   # DRAWN hard faces, at the rendered (post-clamp) position
        if OBS_ON
            (ppx, ppz) = OBS_PREV[]; wi = 0
            for i in obs_near(cs.x, cs.z)
                OBS_KIND[i] === :soft && continue
                g_ = -obs_gap(i, cs.x, cs.z, cs.θ, ppx, ppz)[1]
                g_ > opn && (opn = g_; wi = i)
            end
            if wi > 0 && opn > 0.35 && get(ENV, "JM_CRASH_TRACE", "0") != "0"
                sg = OBS_SEG[wi]
                println("   [otrace] f", frames - crash_t0[], " obstacle ", wi, " ", OBS_NAME[wi], " len ", round(hypot(sg[3]-sg[1], sg[4]-sg[2]), digits = 2),
                        " r ", sg[5], " pen ", round(opn, digits = 2), " car (", round(cs.x, digits = 2), ",", round(cs.z, digits = 2), ") θ ",
                        round(rad2deg(cs.θ), digits = 1), " seg (", round.(sg[1:4], digits = 2), ")")
            end
        end
        crash_rec[] = (max(crash_rec[][1], -min(glo, ghi)), max(crash_rec[][2], opn), max(crash_rec[][3], bpn))
    end
    nothing
end
