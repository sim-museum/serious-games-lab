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
                Render.draw(prog, it, mvp, wheelmat(wx,wz,steer,r,nm); bright=1.0, ambfill=0.75)
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
        if AUTODRIVE_TRAFFIC                    # AUTODRIVE-TRAFFIC-1: follow the car ahead, ~12 m gap
            for (ax, az, av) in AD_TRAFFIC[]
                (as_, al) = RaceAI.project(CLINE, ax, az)
                gap = mod(as_ - s0 + CLINE.total/2, CLINE.total) - CLINE.total/2
                (0.0 < gap < 40.0 && abs(al - lat0) < 2.2) || continue
                _vt = min(_vt, max(0.0, av + (gap - 12.0)/2.0))
            end
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
    # CRASHBODY-1 (PO 2026-10-20: "don't rock the ff back and forth when the car crashes"): a wrecked car's rim torque is the
    # crash's own chatter (contacts, a pinned or tumbling body) -- the wheel keeps only its centring spring. JM_CRASHBODY=0 = before.
    (CRASHBODY && WRECKED[]) && (mz = 0.0; τrim = nothing)
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

"""The player car's physics step inputs, one frame (CAR3D): object/fence/wreck forces, loose wheels, per-wheel surface
grip, then the step itself. Returns (cfx, cfy, cpk, ffb_jolt). LOOPSPLIT-1 cycle 3 S2: moved unchanged."""
function player_step3d!(cs, dt, rst, inp, groundz, ffb_jolt, groundz_phys, race_go, BND_FX, BND_FY, BND_MZ, OFFDIST, OFFTRACK_PROBE,
                        ONTRACK, PLAYER_CDA)
    cfx = cfy = cmz = 0.0
    cpk = 0.0   # (set below only when !SKIDPAD && !rst; the loop read it only then -- defined here so the return never throws)
    if !SKIDPAD && !rst
        update_world_velocity!(cs, cs.x, cs.z, dt > 1e-4 ? dt : 1/60)   # E96-S2/S6: once per frame, before every contact test
        (cfx, cfy, cmz, cpk, chard, cclose) = solid_contact(cs.x, cs.z, cs.θ, cs.v, dt > 1e-4 ? dt : 1/60)
        # PERF-5 (2026-10-16): not for a frozen wreck -- it is re-placed at its rest pose every frame (E95g), so the
        # contact forces move nothing, and the clamp below pushed it out of the obstacle it rests in only to have it
        # put back: 3 iterations x 2 rounds over every nearby face, 3 ms a frame for the rest of the race (Zandvoort).
        if GPLW_PHYS && CAR3D && !(WRECK_FROZEN[] && WRECK_NOCLAMP)     # GPLWALL-1: GPL's .trk walls + every drawn obstacle, summed with the solids, re-capped
            _tgw = time()
            (gfx, gfy, gmz, gpk, ghd, gcl) = gplwall_contact(cs.x, cs.z, cs.θ, dt > 1e-4 ? dt : 1/60)
            if OBS_ON
                (ofx, ofy, omz, opk, ohd, ocl) = obs_contact(cs.x, cs.z, cs.θ, dt > 1e-4 ? dt : 1/60)
                gfx += ofx; gfy += ofy; gmz += omz; gpk = max(gpk, opk); ghd = max(ghd, ohd); gcl = max(gcl, ocl)
            end
            GPLW_T[] = (GPLW_T[][1] + time() - _tgw, GPLW_T[][2] + 1)
            if gpk > 0.0
                cθ_ = cos(cs.θ); sθ_ = sin(cs.θ)
                (cfx, cfy, sc_) = DriveRT3D.cap_total_contact(cfx + gfx, cfy + gfy, WVX[]*cθ_ + WVZ[]*sθ_,
                                                             -WVX[]*sθ_ + WVZ[]*cθ_; dt = dt > 1e-4 ? dt : 1/60)
                cmz = (cmz + gmz)*sc_; cpk = max(cpk, gpk); chard = max(chard, ghd); cclose = max(cclose, gcl)
            end
        end
        # E95: a hard enough hit ends the race. Triggered on the contact PEAK, not on
        # speed -- what wrecks a car is the impulse it absorbs, and a slow scrape into a
        # hedge must never latch it. The impact direction is taken from the net contact
        # force, which points outward from whatever was hit.
        # E95b: the first cut watched ONLY solid_contact, so a hit on the WORLD-EDGE
        # FENCE -- a separate force (BND_*) -- could never wreck the car. That is what
        # the PO hit at 200 km/h, and why nothing fired.
        hitpk = max(cpk, BND_PK[])
        # E95c (PO 2026-08-29): "any off-track collision at all at high speed should
        # total the car ... Sure, if it's a hedge that gets hit it's ok to just bury the
        # car in the hedge." So the test is CONTACT-WITH-SOMETHING-HARD + SPEED, not a
        # force threshold: a force threshold made totalling depend on how deep the
        # penetration got that frame, which is why a 200 km/h hit could slip under it.
        # Hedges (:soft) are excluded by construction -- they contribute to cpk but not
        # to chard, so you still just bury the car in them.
        # E99 (PO 2026-08-30): "a graze at speed should scrub you but not end your race."
        # The old test was `chard > 1.0e3 && |v| > WRECK_MS`, and chard saturates at
        # ~296 kN for ANY non-hedge contact -- so it never discriminated and the speed
        # gate ended the race for a 3 cm clip at 108 km/h just as for a square hit.
        # Trigger on the CLOSING SPEED ALONG THE CONTACT NORMAL instead: that is small
        # for a graze (the normal is mostly lateral) and near the full speed for a
        # square hit, which is exactly the distinction the PO is drawing.
        # The fence keeps its own peak test -- driving off the edge of the world is
        # never a graze.
        # S371: ONE implementation of the rule, shared with wreck_smoke.jl. A gate
        # holding its own copy passes against a sim that has moved on -- this one had,
        # missing the boundary branch below entirely.
        if DriveRT3D.wrecks(cclose, BND_PK[], cs.v;
                            close_ms = WRECK_CLOSE, bnd_peak_max = 1.0e3,
                            vmin_ms = WRECK_MS)
            wreck!(abs(cs.v); closing = cclose, bnd_peak = BND_PK[],
                   x = cs.x, z = cs.z)
        end
        # E98: a stall in MANUAL drops straight to AUTO. Conditions, all required:
        # MANUAL, engine below the floor, clutch ENGAGED (an idling engine with the
        # clutch OUT is not stalled -- that is the PO's own "applying throttle with
        # slider down just revs the engine, as it should"), and NOT wrecked, because a
        # wreck decouples the engine deliberately and must not look like a stall.
        # Sustained, so a launch dip cannot trigger it.
        # S366: the rule itself now lives in DriveRT3D.stall_step and is gated by
        # JuliaMotorMTK/tools/stall_smoke.jl. Keep ONE implementation -- a copy here
        # would drift from the one the gate checks, and the gate would still pass.
        STALL_T[], _stallfire = DriveRT3D.stall_step(STALL_T[], dt;
            auto = CTL.auto, wrecked = WRECKED[], rpm = cs.rpm, clutch = CLU_NOW[],
            rpm_floor = STALL_RPM, secs = STALL_SECS, speed = abs(cs.v), vmax = 5.0)   # start line only (PO 2026-10-03)
        if _stallfire
            CTL.auto = true
            println("  [gearbox] ENGINE STALLED (", round(Int, cs.rpm),
                    " rpm, clutch engaged) -- switched to AUTO")
            flush(stdout)
        end
        # E95: while wrecked AND still moving, keep testing each corner -- a second wheel
        # that reaches the barrier before the car stops comes off too. Gated on cpk so
        # the per-corner SOLIDS scan only runs during an actual contact.
        if WRECKED[] && hitpk > 1.0e3 && abs(cs.v) > 1.0
            detach_hit_wheels!(cs.x, cs.z, cs.θ, cs.v;
                               fence = BND_PK[] > 1.0e4,
                               fence_nx = BND_NX[], fence_nz = BND_NZ[])
        end
        # E94-P4: a SURVIVABLE contact now costs something. Until this, a hit that did
        # not end the race left the car mechanically perfect, so the E99 graze rule
        # ("scrubs you but does not end your race") had no lasting cost at all -- you
        # could bounce off the scenery all lap and finish on a factory-fresh car.
        # Damage is accumulated from the CLOSING speed, the same quantity the wreck
        # rule uses, so both read the impact the same way and a rub below the onset
        # costs nothing (the PO's low-impulse exception).
        # E94-P4 S2: the corners that FACED the blow take it. The contact point is
        # not needed after all -- contact_force returns the force in the BODY frame
        # and a contact can only push, so the impact arrived from the direction
        # opposite that force. Each corner is weighted by how squarely it faces it.
        if cpk > 1.0e3 && !WRECKED[] && cclose > 0.0
            DriveRT3D.damage_impact!(cfx, cfy, cclose)
            if DriveRT3D.damaged()
                # BNDWRECK-1 S3: car speed alongside closing speed, and one line per
                # DMG_EVERY seconds carrying how many contacts it stands for.
                DMG_RUN_N[] += 1
                if DMG_EVERY <= 0.0 || cs.t - DMG_LAST_T[] >= DMG_EVERY
                    println("  [damage] contact at ", round(cclose, digits=1),
                            " m/s closing, car ", round(abs(cs.v), digits=1), " m/s",
                            DMG_RUN_N[] > 1 ? string("  (x", DMG_RUN_N[], " since the last line)") : "",
                            " -- corner grip now ",
                            round(100*DriveRT3D.damage_mu(1)), "%")
                    flush(stdout)
                    DMG_LAST_T[] = cs.t
                    DMG_RUN_N[]  = 0
                end
            end
        end
        cpk > 1.0e3 && (ffb_jolt = clamp(sign(cmz != 0 ? cmz : 1.0) * min(cpk/4.0e4, 1.0), -1.0, 1.0))  # feel the hit (stronger — PO: object kick was too small)
        # BNDWRECK-1 S2: STUCK watchdog. A contact this frame AND the car going nowhere.
        # Armed only once the race is running and not already wrecked (a wreck is a
        # deliberate stop and must not be reported as a stall).
        if STUCK_SECS > 0 && cpk > 1.0e3 && race_go[] && !WRECKED[] && abs(cs.v) < 0.5
            if STUCK_T0[] < 0.0
                STUCK_T0[] = cs.t
                # Prove the predicate runs even on races that never trip the threshold:
                # without this, a clean run and a broken watchdog look identical.
                haskey(ENV,"JM_TRACE_STUCK") && println("  [stuck?] armed at t=",
                    round(cs.t, digits=2), "s  |v|=", round(abs(cs.v), digits=2),
                    " m/s at (", round(cs.x, digits=1), ", ", round(cs.z, digits=1), ")")
            elseif cs.t - STUCK_T0[] >= STUCK_SECS
                println("\n  ═══════ STUCK — not wrecked, pinned against something ═══════")
                println("  [STUCK] ", round(cs.t - STUCK_T0[], digits=1),
                        " s at |v| < 0.5 m/s with a contact every frame")
                println("  [STUCK]   at world (", round(cs.x, digits=1), ", ",
                        round(cs.z, digits=1), ")  lap ", cs.laps,
                        "  lapdist ", round(cs.lapdist, digits=1))
                println("  [STUCK]   JM_STUCK_SECS=0 disables this watchdog")
                flush(stdout)
                GLFW.SetWindowShouldClose(win, true)
            end
        elseif STUCK_T0[] >= 0.0 && abs(cs.v) >= 0.5
            haskey(ENV,"JM_TRACE_STUCK") && println("  [stuck?] cleared after ",
                round(cs.t - STUCK_T0[], digits=2), " s -- moving again")
            STUCK_T0[] = -1.0      # moving again: the spell is over
        end
    end
    # add last frame's world-edge physical-wall force (E56.6) to the trackside contact force
    # E95: once wrecked the car's motion BLEEDS OUT. Fed through the same force port the
    # collision uses, so the solver integrates it -- not a velocity hack applied after
    # the step (which is what bumpX! does and why it was replaced in E56).
    # E95e (PO 2026-08-29: "hit the red wall, bounced back ... levitated and bounced.
    # There should be no bounce back. The car should come to a stop, not bounce back").
    # A wrecked car gets NO OUTWARD PUSH AT ALL. Every spring term -- trackside and
    # world-edge -- is dropped, because a spring is the only thing here that can return
    # energy, and bounding its stored energy (E94b) still leaves SOME. Zero is the only
    # value that cannot bounce. What remains is pure dissipation, so the car buries into
    # whatever it hit and stops there, which is what "totalled" should look like.
    if WRECKED[]
        cfx = 0.0; cfy = 0.0; cmz = 0.0
        BND_FX[] = 0.0; BND_FY[] = 0.0; BND_MZ[] = 0.0
    end
    # OFFTRACK-2 (PO 2026-09-19): the wreck damper was `-617*WRECK_DAMP*cs.v` on the BODY X
    # axis, with cs.v an UNSIGNED speed. That opposes motion only while the car travels nose-
    # first: a wreck sliding sideways or backwards (the PO's was at 35 deg of slip when the
    # world-edge wall took it) gets a 24 g push along -x that is NOT against its velocity,
    # so each frame ADDS speed instead of removing it -- the "torn off at 346 km/h" wheel
    # from a 190 km/h car, and the teleport-and-bounce that followed. Damp the actual
    # body-frame velocity on both axes instead. JM_WRECK_DAMP_OLD=1 restores the old term.
    wfx = 0.0; wfy = 0.0
    if WRECKED[]
        if haskey(ENV, "JM_WRECK_DAMP_OLD")
            wfx = -617.0 * WRECK_DAMP * cs.v
        else
            cθw, sθw = cos(cs.θ), sin(cs.θ)
            vbx =  WVX[]*cθw + WVZ[]*sθw          # body forward speed (signed)
            vby = -WVX[]*sθw + WVZ[]*cθw          # body lateral speed (signed)
            wfx = -617.0 * WRECK_DAMP * vbx
            wfy = -617.0 * WRECK_DAMP * vby
        end
    end
    DriveRT3D.extforce3d!(cs; Fx = cfx + BND_FX[] + wfx, Fy = cfy + BND_FY[] + wfy, Mz = cmz + BND_MZ[],
                          CdA_scale = PLAYER_CDA[])
    if OFFTRACK_PROBE[] > 0
        OFFTRACK_PROBE[] -= 1
        println("  [offtrack] t=", round(cs.t, digits=3), " v=", round(cs.v*3.6, digits=1), " x=", round(cs.x, digits=2),
                " z=", round(cs.z, digits=2), " y=", round(cs.y, digits=3), " heave=", round(cs.heave, digits=3),
                " ontrack=", ONTRACK[], " wrecked=", WRECKED[], " bndpk=", round(BND_PK[], digits=0),
                " bndF=(", round(BND_FX[], digits=0), ",", round(BND_FY[], digits=0), ") wfx=", round(wfx, digits=0),
                " cF=(", round(cfx, digits=0), ",", round(cfy, digits=0), ") off=", round(OFFDIST[], digits=1),
                " nl=", round(BND_NL[], digits=2))
        OFFTRACK_PROBE[] == 0 && haskey(ENV, "JM_OFFTRACK_EXIT") && (flush(stdout); exit(0))
    end
    # E95g: a totalled car comes to REST and STAYS there. Once it is down to walking
    # pace, pin it: the alternative is a dead car creeping, drifting off the HAT and
    # re-entering the containment/levitation cycle the PO saw. Pinning is honest here in
    # a way it would never be for a driveable car -- the race is over by definition.
    if WRECKED[]
        if !WRECK_FROZEN[] && abs(cs.v) < 2.0
            WRECK_FROZEN[] = true
            WRECK_PX[] = cs.x; WRECK_PZ[] = cs.z; WRECK_PT[] = cs.θ
            println("  [WRECK] car came to rest"); flush(stdout)
            WRECK_PH[] = Float64(groundz_phys(cs.x, cs.z))   # HEDGEJOLT-1: the ground it rests on, once
        end
        if WRECK_FROZEN[]
            # HEDGEJOLT-1: pin ALL of it (yaw rate, heave, pitch, roll on the ground), not just x/z/heading --
            # the vertical states ran on against a smashed corner: the wreck hovered and twitched. JM_WRECK_PIN=0 = before.
            WRECK_PIN && CAR3D ? DriveRT3D.pin3d!(cs, WRECK_PX[], WRECK_PZ[], WRECK_PT[], WRECK_PH[]) :
                                 DriveRT3D.place3d!(cs, WRECK_PX[], WRECK_PZ[], WRECK_PT[]; v=0.0)
        end
    end
    # E95: the torn-off wheels live in the world now, not on the car.
    step_loose_wheels!(dt > 1e-4 ? dt : 1/60, (gx, gzz) -> (h = groundz(gx, gzz); h > -900 ? Float64(h) : 0.0))
    # E56 grass = per-wheel tyre μ: any wheel off the racing surface loses real grip (and
    # pulls the car) in the brush model — replaces the bumpX! grass drag/yaw hack (which is
    # now AI-only).  Only project the 4 wheels when the car is near/over the edge (cheap on-track).
    μFL = μFR = μRL = μRR = 1.0
    if !SKIDPAD && !rst
        hc = JuliaMotor.hat(TRKSURF, cs.x, cs.z)
        if hc.found && abs(hc.lateral) > ROAD_HALFW - 1.2
            cθg = cos(cs.θ); sθg = sin(cs.θ)
            cx_ = Float64(cs.x); cz_ = Float64(cs.z)
            μFL = wheel_mu(cx_, cz_, cθg, sθg,  1.314,  0.75); μFR = wheel_mu(cx_, cz_, cθg, sθg,  1.314, -0.75)
            μRL = wheel_mu(cx_, cz_, cθg, sθg, -1.096,  0.75); μRR = wheel_mu(cx_, cz_, cθg, sθg, -1.096, -0.75)
        end
    end
    # E94-P4: damage MULTIPLIES into the surface grip rather than replacing it --
    # a bent corner on grass is worse than either alone, and overwriting here would
    # have quietly cancelled the grass-grip model whenever the car was damaged.
    DriveRT3D.wheelmu3d!(cs, μFL*DriveRT3D.damage_mu(1), μFR*DriveRT3D.damage_mu(2),
                             μRL*DriveRT3D.damage_mu(3), μRR*DriveRT3D.damage_mu(4))
    (cfx, cfy, cpk, ffb_jolt)
end

"""The shared world draw (main pass and E64 mirror pass): track, objects, billboards, AI and remote cars. LOOPSPLIT-1
cycle 3 S3: the per-frame `drawworld` closure's body, moved unchanged; the loop's closure now only forwards to it."""
function drawworld_impl!(vp_, eye_, flip::Bool, cs, AICHASSIS, _tp_d, aiBody, aiWheel, ai_poses, spin)
    (HORIZON_RING === nothing || LAYOFF_HZ) || Render.draw_horizon(prog, HORIZON_RING, vp_, eye_; tint=GRADE.ringtint)   # GPL horizon ring backdrop
    # E60 (D6, 260801 gold video): TRACK-mesh signs (VREDESTEIN at Tarzan …) drew with uBackFlip=0, so
    # when the coplanar dedup keeps the away-facing decal the text renders MIRRORED.  Objects already
    # un-mirror back faces; give the track mesh the same treatment (road/kerb back faces are unseen).
    glUniform1i(Render.uloc(prog,"uBackFlip"), 1)
    secfrom = (@isdefined SEC_FROM) ? SEC_FROM : typemax(Int)
    PROF_DEPTH[] += time() - _tp_d; _tp_t = time()
    glUniform1f(Render.uloc(prog,"uMaxDist"), TRACK_MAXD)    # TRACKS-TD-1 S2: the track mesh's draw range
    _clap = _LW === nothing ? 0.0 : lapnear(Float64(eye_[1]), -Float64(eye_[3]))   # BLINDTURN-1: the eye's lap position
    for (ti, it) in enumerate(trackItems)                        # ambfill lifts shadowed walls/fences out of the "carbonized" black under the flat overcast light
        # RING-HAIRPIN-1 S3: with the tessellated road on, the .3do's asphalt/groove strips are not drawn
        # SKIDPAD-GOLD-1 S2: same guard as RINGSPRITES above -- ROADTESS is a const defined
        # inside the GPL-track branch, so on the synthetic SKIDPAD it does not exist and this
        # line threw UndefVarError from inside main(). Second of the same class in one file.
        if (@isdefined ROADTESS) && ROADTESS && ti <= length(TRACKMAIN) && TRACK_ASPGROOVE[ti]   # PERF-3: precomputed (was a lowercase() String per part per frame)
            continue
        end
        # E68 S9b: landmass SECTIONS draw single-sided like GPL — culls the dark edge-skirt
        # slabs (Ring s≈18400) that our two-sided draw exposed.  Winding per OBJ_FF_CW.
        # E68 S10b: rail-family parts also draw single-sided (guardrail shimmer).
        # TRACKGOLD-1 S4 probe: JM_SEC_TWOSIDED=1 draws the landmass sections two-sided again -- if a
        # section's winding is the wrong way it is invisible from the road and the ground behind a bank
        # (last01 at s=1000) is sky; the bank then reads as a ramp into the air.
        if ti == secfrom && SEC_TWOSIDED; glDisable(GL_CULL_FACE)
        elseif ti == secfrom; glEnable(GL_CULL_FACE); glCullFace(xor(OBJ_FF_CW, flip) ? GL_FRONT : GL_BACK)
        elseif ti < secfrom && (@isdefined TRACK_RAILCULL) && ti <= length(TRACK_RAILCULL)
            if TRACK_RAILCULL[ti]; glEnable(GL_CULL_FACE); glCullFace(xor(OBJ_FF_CW, flip) ? GL_FRONT : GL_BACK)
            elseif TRACK_BOARDCULL[ti]; glEnable(GL_CULL_FACE); glCullFace(flip ? GL_FRONT : GL_BACK)   # BOARDCULL-1: keep the faces whose normal faces the eye
            else; glDisable(GL_CULL_FACE); end
        end
        TRACKCULL && !infrustum(vp_, TRACKBOUND[ti][1], TRACKBOUND[ti][2]) && continue   # PERF-3 (after the cull-state toggles)
        if MONZA                                                 # E57: per-surface grade — its asphalt MIP is over-bright, its barriers carbonized
            cat = TRACKCAT[ti]
            b, a = cat === :road ? (MZ_ROAD_B, MZ_ROAD_A) : cat === :dark ? (MZ_DARK_B, MZ_DARK_A) :
                   cat === :bank ? (MZ_BANK_B, MZ_BANK_A) : (MZ_OTHER_B, MZ_OTHER_A)
            gg = ti <= length(TRACKGAIN) ? TRACKGAIN[ti] : 1f0
            Render.draw(prog, it, vp_, Render.IDENT; bright=b*gg, ambfill=a*gg)
        else
            # E69-S7: make the track-draw lighting tunable so the warm cast measured against
            # gold (asphalt R-B: gold -2.5..-5.3, native +7.8..+12.7 across three tracks
            # each) can be attributed rather than guessed at.
            gg = ti <= length(TRACKGAIN) ? TRACKGAIN[ti] : 1f0   # GRADEGOLD-1
            if _LW !== nothing && ti <= length(TRACKLAPOFF)     # BLINDTURN-1 S5: GPL's lap window
                for (f0, n0) in lapranges(TRACKLAPOFF[ti], _clap)
                    n0 > 0 && Render.draw(prog, it, vp_, Render.IDENT; bright=TRACK_BRIGHT*gg, ambfill=TRACK_AMB*gg, first=f0, count=n0)
                end
            else
                Render.draw(prog, it, vp_, Render.IDENT; bright=TRACK_BRIGHT*gg, ambfill=TRACK_AMB*gg)
            end
        end
    end
    glUniform1f(Render.uloc(prog,"uMaxDist"), 0f0)
    (@isdefined SEC_FROM) && length(trackItems) >= SEC_FROM && glDisable(GL_CULL_FACE)   # E68 S9b: section cull off before objects
    if OBJ_CULLFACE                                           # E60: GPL culls single-sided faces —
        # double-sided signs keep both decals (dedup=:orient), each visible only from its own side.
        # NEVER touch glFrontFace: the two-sided-Lambert shader keys off gl_FrontFacing globally
        # (flipping the convention darkened the whole world) — pick the culled SIDE instead.
        # GPL is D3D-era (CW front); after the winding-preserving remap those faces are GL "back",
        # so cull GL_FRONT to keep them.  JM_OBJ_FF=ccw culls GL_BACK if a track's data disagrees.
        glEnable(GL_CULL_FACE); glCullFace(xor(OBJ_FF_CW, flip) ? GL_FRONT : GL_BACK)
        glUniform1i(Render.uloc(prog,"uBackFlip"), 0)
    end
    PROF_TRACK[] += time() - _tp_t; _tp_o = time()
    # SPA-FPS-1 S3 (2026-09-07): Spa's frame was 9-15 ms of trackside objects + 9-15 ms of billboards, one
    # draw call each for everything inside the radius -- behind the camera and off to the sides included.
    # A clip-space test skips what this pass's camera cannot see (each mirror pass brings its own vp_,
    # so it culls for its own view). JM_FRUSTUM_CULL=0 reverts.
    # PERF-1: function barrier -- OBJECTS/OBJBOUND are untyped globals, so the loop body boxed every value
    # (a top allocation site). Passing them in lets the loop compile for their concrete types.
    (function (_OBJS, _BND)
    _cseg = gplvis_seg(eye_[1], eye_[3])
    _olap = _LW === nothing ? 0.0 : lapnear(Float64(eye_[1]), -Float64(eye_[3]))
    if _LW !== nothing && length(OBJLAP) != length(_OBJS)                 # BLINDTURN-1 S5: each object's lap position
        resize!(OBJLAP, length(_OBJS)); resize!(OBJLAP2, length(_OBJS))
        for (k, o) in enumerate(_OBJS)
            if isbackdrop(lowercase(String(o[5])))
                OBJLAP[k] = NaN; OBJLAP2[k] = NaN
            else
                sl, dsq = lapnear_d(Float64(o[4][1]), -Float64(o[4][3]))
                OBJLAP[k] = sl; OBJLAP2[k] = lapnear2(Float64(o[4][1]), -Float64(o[4][3]), sl, dsq)
            end
        end
    end
    for (oi,(items,mat,grz,opos,onm)) in enumerate(_OBJS)   # trackside objects
        LAYOFF_OBJ && continue   # (trees graze-fade; uBackFlip stays 1 when un-culled)
        _ocl = oi <= length(OBJCLIP) ? OBJCLIP[oi] : nothing                 # GPLVIS-1 S4: GPL's cells (clipped)
        (_ocl === nothing && _cseg > 0 && oi <= length(OBJVIS) && OBJVIS[oi] !== nothing && !OBJVIS[oi][_cseg]) && continue   # GREY-1: GPL's window
        (OBJ_SCENEDUP[oi] && _ocl === nothing && !(oi <= length(OBJVIS) && OBJVIS[oi] !== nothing)) && continue   # RING-GOLD-1 S3 (E109-S15: not the veils -- their scenery copy is hidden; GPLVIS-1: nor a cell-clipped object)
        bc, br = oi <= length(_BND) ? _BND[oi] : ((opos[1], opos[2], opos[3]), 80f0)   # CULLBOUND-1: the object's real bounding sphere
        (_LW !== nothing && oi <= length(OBJLAP) && !isnan(OBJLAP[oi]) && !isnan(_olap) && !lapwin_in(OBJLAP[oi], _olap) &&
         !(oi <= length(OBJLAP2) && !isnan(OBJLAP2[oi]) && lapwin_in(OBJLAP2[oi], _olap))) && continue   # BLINDTURN-1 S5 (+ TD261013-1: either leg)
        max(sqrt((eye_[1]-bc[1])^2+(eye_[2]-bc[2])^2+(eye_[3]-bc[3])^2) - br, 0f0)^2 > (flip ? MIR_OBJ_CULL2 : OBJ_CULL2) && continue   # distance cull (mirror gets its own radius, S14)
        FRUSTUM_CULL && !infrustum(vp_, bc, br) && continue
        # PERF-1: size cull -- an object whose bounding sphere covers < JM_MINPIX pixels is not drawn
        br < (flip ? MINPIX_K_MIR : MINPIX_K) * sqrt((eye_[1]-bc[1])^2+(eye_[2]-bc[2])^2+(eye_[3]-bc[3])^2) && continue
        ob, oa = OBJ_BRIGHT, OBJ_AMB                           # default object grade (grandstands/buildings); SHADE-1. PERF-4 S2: Float32 like the
                                                               # vegetation branch -- a Float64/Float32 mix made every draw's keywords allocate
        # SPAYELLOW-1 (PO 2026-09-26, Spa: "the initial view shows mostly a yellow blob, like a
        # hillside colored bright yellow, on the left side of the screen"). Bisected with
        # JM_LAYERS_OFF: with objects off the pixel is sky, so the blob is a placed OBJECT --
        # `hill13`, a 300 x 20 m foliage backdrop ridge 61 m from the Spa grid, textured `pinend`
        # (a dark green tree-line: mean RGB 61,85,76). It was drawn at the GRANDSTAND grade,
        # 1.05/0.55, while the SAME foliage on the track draws at TRACK_BRIGHT*VEG_GAIN = 0.583
        # and TRACK_AMB*VEG_GAIN = 0.275 -- GRADEGOLD-1 gave the track's vegetation a gain and
        # never gave one to objects. Measured on the Spa grid: the ridge rendered (249,250,73),
        # i.e. 2.4x its texture with red and green CLIPPED, against ~1.2x for the same texture on
        # the track, and gold shows no yellow there at all. Ground cover is ground cover: grade a
        # vegetation-textured object like the track's vegetation. JM_OBJ_VEG=0 restores 1.05/0.55.
        _ovg = OBJ_VEG_GRADE ? get(OBJVEG, onm, nothing) : nothing
        if MONZA                                               # E57: tone the combined-circuit paved/banking object surfaces
            g = monza_obj_grade(onm)
            g === :road && ((ob, oa) = (Float32(MZ_ROAD_B), Float32(MZ_ROAD_A))); g === :bank && ((ob, oa) = (Float32(MZ_BANK_B), Float32(MZ_BANK_A)))
        end
        otint = is_crowd_obj(onm) ? CROWD_TINT : (1f0,1f0,1f0)   # E46: warm/de-blue the over-blue grandstand crowd MIP
        # OBJDUP-1 (PO 2026-09-19, WG: "banner over start/finish is placed twice, a couple of metres
        # apart"). The `startbox` gantry's DUNLOP board is a 1 m-thick box with a textured face on
        # each side; drawn two-sided (objects are, JM_OBJ_CULL=0) the far face shows through as a
        # ghost copy. The A/B with E60's cull rule (parity/po_260919/wg_banner_cull_ab.jpg) kept
        # the WRONG face (mirrored text): this model winds the other way. Cull it by name with the
        # opposite face; nothing else changes. JM_STARTBOX_CULL=0 reverts.
        _twin = OBJ_CULLFACE ? nothing : get(TWINBOARD, onm, nothing)   # OBJDUP-2: geometric face choice
        _sbcull = (STARTBOX_CULL && !OBJ_CULLFACE && onm == "startbox") || _twin !== nothing
        if _sbcull
            glEnable(GL_CULL_FACE); glCullFace(_twin === nothing ? (xor(OBJ_FF_CW, flip) ? GL_BACK : GL_FRONT) : (xor(_twin, flip) ? GL_BACK : GL_FRONT))
            glUniform1i(Render.uloc(prog,"uBackFlip"), 0)
        end
        _obd = BACKDROP_ON ? get(OBJBACKDROP, onm, nothing) : nothing
        _bdfar = _obd !== nothing && hypot(eye_[1] - opos[1], eye_[3] - opos[3]) > backdrop_r(onm)   # out of its viewing area
        for _cpl in (_ocl === nothing ? (nothing,) : _ocl)                       # GPLVIS-1 S4: once per GPL cell, clipped
        _cpl === nothing || Render.clip_planes!(prog, _cpl)
        for (_ii, it) in enumerate(items)                                        # SPAYELLOW-1: foliage PARTS take the track's vegetation grade
            _fol = _ovg !== nothing && _ii <= length(_ovg) && _ovg[_ii]
            _bd = _obd !== nothing && _ii <= length(_obd) && _obd[_ii]       # RING-GOLD-1 S2: backdrop panorama part
            (_bd && _bdfar) && continue
            Render.draw(prog, it, vp_, mat; bright = _fol ? TRACK_BRIGHT*VEG_GAIN : (OBJ_FLAT[1] > 0f0 ? 1f0 : ob),
                        ambfill = _fol || OBJ_FLAT[1] > 0f0 ? (_fol ? TRACK_AMB*VEG_GAIN : 0f0) : oa, graze=grz || _bd, tint=otint,
                        flat = _fol ? (0f0, 0f0) : OBJ_FLAT)   # SHADE-1: buildings flat-lit as GPL; foliage keeps its grade
        end
        end
        _ocl === nothing || Render.clip_planes!(prog, nothing)   # grandstands/buildings: ambfill kills the "post-Hiroshima carbonized" shadow faces → vibrant GPL look
        if _sbcull; glDisable(GL_CULL_FACE); glUniform1i(Render.uloc(prog,"uBackFlip"), 1); end
    end
    end)(OBJECTS, OBJBOUND)
    PROF_OBJ[] += time() - _tp_o; _tp_b = time()
    # TD261013-1 (b5) (PO 2026-10-13, Spa: "around white mountain after stavelot you can see the road ribbon after the
    # start/finish line like a suspended bridge in the distance"): the lap window (now on at Spa) hides that ground, so the
    # sprites standing on it must go with it -- else a row of tree tops floats in the sky. Sprites and forest panels take
    # the objects' window (either leg). JM_LAPWIN_SPRITES=0 = the distance cull only.
    _blap = (_LW === nothing || !LAPWIN_SPRITES) ? NaN : lapnear(Float64(eye_[1]), -Float64(eye_[3]))
    if !isnan(_blap) && length(BBLAP) != length(BILLBOARDS) + length(STATICTREES)
        empty!(BBLAP); empty!(BBLAP2)
        for (_, pos) in Iterators.flatten((((x[1], x[2]) for x in STATICTREES), ((x[1], x[2]) for x in BILLBOARDS)))
            sl, dsq = lapnear_d(Float64(pos[1]), -Float64(pos[3])); push!(BBLAP, sl); push!(BBLAP2, lapnear2(Float64(pos[1]), -Float64(pos[3]), sl, dsq))
        end
    end
    _bbin(k) = isnan(_blap) || k > length(BBLAP) || isnan(BBLAP[k]) || lapwin_in(BBLAP[k], _blap) || (!isnan(BBLAP2[k]) && lapwin_in(BBLAP2[k], _blap))
    for (_k, (it,pos,w,h,yaw)) in enumerate(STATICTREES)     # wide forest-edge panels (authored yaw, graze-fade)
        _bbin(_k) || continue
        (eye_[1]-pos[1])^2+(eye_[2]-pos[2])^2+(eye_[3]-pos[3])^2 > BB_CULL2 && continue
        FRUSTUM_CULL && !infrustum(vp_, pos, max(w, h) + 5f0) && continue
        Render.draw(prog, it, vp_, Render.translate(pos[1],pos[2],pos[3])*Render.roty(yaw)*Render.scalexyz(w,h,1f0); bright=1.3, ambfill=0.8, graze=true, unlit=!BB_LIT)   # E63/MZ3: the comment always claimed graze-fade but the call never passed it → a wide Monza forest strip seen EDGE-ON rendered as a dark triangular SLAB at the S/F. graze=true fades edge-on quads (uGraze) so the strip shows face-on as a tree-line and vanishes edge-on
    end
    OBJ_CULLFACE && glDisable(GL_CULL_FACE)
    glUniform1i(Render.uloc(prog,"uBackFlip"), 0)
    (function (_BBS, _nst, _bbin)   # PERF-1: function barrier (BILLBOARDS is an untyped global)
    for (_k, (it,pos,w,h)) in enumerate(_BBS)            # trees/sprites
        LAYOFF_BB && continue
        _bbin(_nst + _k) || continue                     # TD261013-1 (b5): the lap window
        _d2 = (eye_[1]-pos[1])^2+(eye_[2]-pos[2])^2+(eye_[3]-pos[3])^2
        _d2 > (flip ? MIR_BB_CULL2 : BB_CULL2) && continue       # distance cull (mirror radius, S14)
        max(w, h) < 2f0 * (flip ? MINPIX_K_MIR : MINPIX_K) * sqrt(_d2) && continue       # PERF-1: sub-pixel sprite
        FRUSTUM_CULL && !infrustum(vp_, pos, max(w, h) + 5f0) && continue
        Render.draw(prog, it, vp_, Render.billboard_model(pos,w,h,eye_); bright=BB_BRIGHT, ambfill=BB_AMB, unlit=!BB_LIT)  # E83-S3: unlit by default (GPL pre-lit art); E70-S7 tunables only matter with JM_BILLBOARD_LIT=1
    end
    end)(BILLBOARDS, length(STATICTREES), _bbin)
    PROF_BB[] += time() - _tp_b; _tp_c = time()
    # AI grid (Ferrari/Brabham/BRM/Eagle/Cooper). E106-S25: JM_NO_AI_WHEELS=1 suppresses the AI wheel draw
    # (the rods on the AI rear tyre were neither the wheel mesh nor the wrapper). PERF-3: typed barrier.
    draw_ai_main!(prog, vp_, ai_poses, AICHASSIS, spin, AI_NOWHEELS)
    PROF_CARS[] += time() - _tp_c
    # E85-S5: the REMOTE cars, drawn through exactly the same path as the AI field -- same
    # body/wheel transforms, so anything true of an AI car's placement is true of theirs.
    if !isempty(NETPOSES[]) && !isempty(AICARMODELS)
        for (nid, p) in NETPOSES[]          # MP-5: the host's AI ids pick their own chassis
            cm = AICARMODELS[NetPlay.chassis_slot(nid, length(AICARMODELS))]
            let _bm = aiBody(p, cm); for it in cm.body; Render.draw(prog, it, vp_, _bm; bright=AI_BRIGHT, spec=0.10, ambfill=AI_AMB); end; end
            for (wx,wz,_,r,nm) in cm.wheelspec, it in cm.wheels[nm]; Render.draw(prog, it, vp_, aiWheel(p,cm,wx,wz,r)); end
        end
    end
end

"""Cockpit view: the gloved hands on the wheel and the sleeves laid from glove to shoulder (ARMS2), one frame.
LOOPSPLIT-1 cycle 3 S4: moved unchanged."""
function hands_draw!(cs, inp, vp, bodyModel, swModel)
    _hcull = glIsEnabled(GL_CULL_FACE) == GL_TRUE
    # COCKPIT-2 S7: the lever-side glove's offset to the knob (body-local), zero with the hands on the rim
    _hoff = (0f0, 0f0, 0f0)
    if SHIFT_HAND && SHIFT_KNOB !== nothing && !isempty(shiftItems) && length(handLR) == 2
        _u = Float32(shift_hand_u(cs.gear))
        if _u > 0f0
            _swr = Render.translate(SWCENTER) * Render.rotaxis(SWAXIS, Float32(HSIGN*inp.steer*2.5 + SW_ROT)) * Render.translate(-SWCENTER[1], -SWCENTER[2], -SWCENTER[3])
            _g = _swr * gripmat(SHIFT_HAND_K == 1 ? 1 : -1) * Float32[FIST_C[SHIFT_HAND_K]..., 1f0]
            _k = SHIFT_LASTM[] * Float32[SHIFT_KNOB..., 1f0]
            _hoff = (_u*(_k[1] + SHIFT_HAND_UP[1] - _g[1]), _u*(_k[2] + SHIFT_HAND_UP[2] - _g[2]), _u*(_k[3] + SHIFT_HAND_UP[3] - _g[3]))
        end
    end
    HAND_CULL || glDisable(GL_CULL_FACE)          # HANDS-1 S2: A/B the gloves two-sided (inside-out fists?)
    if ARMS
        # HANDS-1 S4: in lotus.3do the arms and gloves share the steering-wheel assembly's positioner (node 15060), so
        # GPL turns the arms with the wheel; JM_ARMS_ON_WHEEL=1 draws them with the gloves' transform, no ARMFIX (A/B).
        if ARMS2 && length(armLR) == 2 && SLEEVE_ENDS[1] !== nothing && SLEEVE_ENDS[2] !== nothing
            swRel = Render.translate(SWCENTER) * Render.rotaxis(SWAXIS, Float32(HSIGN*inp.steer*2.5 + SW_ROT)) * Render.translate(-SWCENTER[1], -SWCENTER[2], -SWCENTER[3])
            for (k, sgn) in ((1, 1), (2, -1))          # armLR[1] = z > 0 with gripmat(+1), as handLR
                W, E, nf = SLEEVE_ENDS[k]
                Wt = (CUFF && CUFF_RAW[k] !== nothing) ? CUFF_RAW[k] : W     # WRISTS-4: the sleeve ends at the glove's cuff
                h = swRel * gripmat(sgn) * Float32[Wt[1], Wt[2], Wt[3], 1f0]
                k == SHIFT_HAND_K && (h = Float32[h[1] + _hoff[1], h[2] + _hoff[2], h[3] + _hoff[3], 1f0])   # COCKPIT-2 S7
                S = (SHOULDER[1], SHOULDER[2], sgn*SHOULDER[3])
                # TD261013-1 (a2) (PO 2026-10-13: "a large white triangle on the left when the player turns all the way
                # right"): at full lock (~143 deg) the glove crosses to the top of the rim and a strip from a shoulder
                # beside the eye lies broad across the view. GPL's sleeve then rises steeply from below (gold Spa La Source
                # t 361-363): the elbow drops and comes in. The far end slides toward ARM_LOCK_S as the wheel passes
                # 50 deg, fully by 130 deg; straight ahead it is the gold-fitted shoulder. JM_ARM_LOCK_S="" = fixed.
                if ARM_LOCK_S !== nothing
                    _u = clamp((abs(HSIGN*inp.steer*2.5) - deg2rad(ARM_LOCK_DEG[1])) / deg2rad(ARM_LOCK_DEG[2] - ARM_LOCK_DEG[1]), 0.0, 1.0)
                    S = (S[1] + _u*(ARM_LOCK_S[1] - S[1]), S[2] + _u*(ARM_LOCK_S[2] - S[2]), S[3] + _u*(sgn*ARM_LOCK_S[3] - S[3]))
                end
                if SLEEVE_HOLD && SLEEVE_NREF[k] === nothing    # the straight-wheel face normal, once
                    sw0 = Render.translate(SWCENTER) * Render.rotaxis(SWAXIS, Float32(SW_ROT)) * Render.translate(-SWCENTER[1], -SWCENTER[2], -SWCENTER[3])
                    h0 = sw0 * gripmat(sgn) * Float32[Wt[1], Wt[2], Wt[3], 1f0]
                    sleeve_mat(W, E, (h0[1], h0[2], h0[3]), S, nf); SLEEVE_NREF[k] = SLEEVE_LASTR[] * collect(nf)
                end
                # HANDS-2 S3: lit toward the gold's white sleeve (it read grey at 1.15 / 0.60)
                # COCKPIT-2 S4 (PO 2026-10-07: "the wrists are see-through"): the sleeve's end stopped AT the glove's
                # cuff point, and the glove is an open band round the rim -- between them the dash showed through.
                # Run the sleeve on along its own line ARM_INTO metres into the glove so the two overlap.
                # TD261016-1 (c1) (PO 2026-10-16: "wrists are still transparent in places"): at 6 cm the rim and dash still
                # showed between sleeve and glove near straight ahead; 12 cm closes it (sweep 0/6/12/18 cm, Ring cockpit),
                # but at full lock 12 cm pushes the sleeve out past the rim -- so 12 cm fades to 6 cm over the arms'
                # lock schedule (ARM_LOCK_DEG). JM_ARM_INTO fixes one value for every angle, as before.
                _ul = clamp((abs(HSIGN*inp.steer*2.5) - deg2rad(ARM_LOCK_DEG[1])) / deg2rad(ARM_LOCK_DEG[2] - ARM_LOCK_DEG[1]), 0.0, 1.0)
                _into = haskey(ENV, "JM_ARM_INTO") ? parse(Float64, ENV["JM_ARM_INTO"]) :
                        haskey(ENV, "JM_CUFF_INTO") && CUFF ? parse(Float64, ENV["JM_CUFF_INTO"]) :
                        (CUFF && CUFF_RAW[k] !== nothing) ? CUFF_INTO[1] + clamp((abs(HSIGN*inp.steer*2.5) - deg2rad(CUFF_LOCK_DEG[1])) /
                                                              deg2rad(CUFF_LOCK_DEG[2] - CUFF_LOCK_DEG[1]), 0.0, 1.0)*(CUFF_INTO[2] - CUFF_INTO[1]) :
                        ARM_INTO_STRAIGHT + _ul*(ARM_INTO - ARM_INTO_STRAIGHT)
                _d = (h[1] - S[1], h[2] - S[2], h[3] - S[3]); _l = sqrt(_d[1]^2 + _d[2]^2 + _d[3]^2)
                h = _l > 1e-6 ? (h[1] + _into*_d[1]/_l, h[2] + _into*_d[2]/_l, h[3] + _into*_d[3]/_l) : h
                # TD261013-1 (a2) (PO 2026-10-13: "the driver's left arm has a large white triangle on the left when the
                # player turns all the way right"): at full lock the wheel turns ~143 deg and the left glove sits top-right;
                # the strip, still held to its straight-wheel face, crossed the wheel FACE-ON -- the white sail. GPL turns
                # the arms with the wheel assembly (HANDS-1 S4), so the held face turns with the wheel too.
                # JM_ARM_ROLLWHEEL=0 = the straight-wheel face, as before.
                _tgt = SLEEVE_HOLD ? (ARM_ROLLWHEEL && SLEEVE_NREF[k] !== nothing ?
                       (Render.rotaxis(SWAXIS, Float32(HSIGN*inp.steer*2.5)) * Float32[SLEEVE_NREF[k]..., 0f0])[1:3] : SLEEVE_NREF[k]) : nothing
                Render.draw(prog, armLR[k], vp, bodyModel * sleeve_mat(W, E, (h[1], h[2], h[3]), S, nf; target = _tgt);
                            bright=1.35, spec=0.05, ambfill=0.85)
            end
        else
            _amod = ARMS_ON_WHEEL ? swModel : bodyModel*ARMFIX
            for it in armItems;  Render.draw(prog, it, vp, _amod; bright=1.15, spec=0.05, ambfill=0.60); end
        end
    end
    if length(handLR) == 2                      # left fist +grip, right fist −grip → gold's 10-and-2
        _hm(k) = (k == SHIFT_HAND_K && _hoff != (0f0, 0f0, 0f0)) ? bodyModel * Render.translate(_hoff) * inv(bodyModel) : Render.ident()   # COCKPIT-2 S7
        Render.draw(prog, handLR[1], vp, _hm(1)*swModel*gripmat(+1)*fistrot(1); bright=1.15, spec=0.05, ambfill=0.60)
        Render.draw(prog, handLR[2], vp, _hm(2)*swModel*gripmat(-1)*fistrot(2); bright=1.15, spec=0.05, ambfill=0.60)
    else
        for it in handItems; Render.draw(prog, it, vp, swModel; bright=1.15, spec=0.05, ambfill=0.60); end
    end
    (!HAND_CULL && _hcull) && glEnable(GL_CULL_FACE)
    nothing
end

"""JM_RAM_AI test hook: place the player to ram AI car k, then brake as a driver would, one frame. LOOPSPLIT-1 cycle 3 S6: moved unchanged."""
function ram_ai_step!(cs, ai_poses, ddt, AICARS, PLAYER_G, groundz)
    isnan(RAM_STATE[].t0) && (RAM_STATE[] = (t0 = cs.t, done = false))
    if cs.t - RAM_STATE[].t0 >= RAM_AI[4]
        k = Int(RAM_AI[1]); q = ai_poses[k]; qθ = q[4]; vk = AICARS[k].v
        rx = q[1] - 4.7*cos(qθ) - RAM_AI[3]*sin(qθ); rz = q[3] - 4.7*sin(qθ) + RAM_AI[3]*cos(qθ)
        PLAYER_G[] = NaN; GPLW_ON && gplw_teleported!()
        DriveRT3D.place3d!(cs, rx, rz, qθ; v = vk + RAM_AI[2])
        h = groundz(rx, rz; acquire = true); isfinite(h) && (cs.zref = Float64(h); cs.y = cs.zref)
        RAM_STATE[] = (t0 = RAM_STATE[].t0, done = true)
        println("  [ram] t=", round(cs.t, digits = 2), " player placed 4.7 m behind AI ", k, " (", round(vk*3.6), " km/h), lat ",
                RAM_AI[3], " m, closing ", RAM_AI[2], " m/s"); flush(stdout)
    end
    nothing
end

"""CARCOLLIDE-2 S4: each AI car knocked loose steps as its pool Car3D (tumble, locked brakes, recovery, rejoin), one frame. LOOPSPLIT-1 cycle 3 S6: moved unchanged."""
function loose_cars_step!(cs, ai_poses, ddt, AICARS, AILINE, GPLAI_T, PLAYER_G, aibankP, frames, gplai_field!, groundz, groundz_ai)
    # S5 probe: JM_RAM_SOLO=1 moves the player 30 m aside once a car is loose -- the spin with no follow-up contact
    if RAM_SOLO && !RAM_SOLO_DONE[]
        RAM_SOLO_DONE[] = true; PLAYER_G[] = NaN; GPLW_ON && gplw_teleported!()
        DriveRT3D.place3d!(cs, cs.x - 30*sin(cs.θ), cs.z + 30*cos(cs.θ), cs.θ; v = 0.0)
    end
    for (k, sl) in collect(LOOSE_OF)
        if k > length(ai_poses) || k > length(AICARS)
            delete!(LOOSE_OF, k); continue
        end
        pc = LOOSE_CARS[sl]
        # tumble with the brakes locked until settled; then (the field would snap a car sitting 100-160 deg off its
        # line back round in half a second) drive it slowly round to the line with the physics AI's controller
        (lrs, _) = RaceAI.project(AILINE, pc.x, pc.z; hint = AICARS[k].s)
        lherr = RaceAI.wrapπ(pc.θ - RaceAI.pose_at(AILINE, lrs, 0.0)[4])
        if !LOOSE_REC[sl] && ((pc.v < 4.0 && abs(DriveRT3D.yawrate3d(pc)) < 0.5) || cs.t - LOOSE_T0[sl] > 4.0)
            LOOSE_REC[sl] = true; LOOSE_T0[sl] = cs.t
        end
        if LOOSE_REC[sl]
            (lthr, lbrk, lst) = RaceAI.controller(AILINE, lrs, 0.0, 0.0, 6.0, pc.x, pc.z, pc.θ, pc.v, DriveRT3D.yawrate3d(pc))
            DriveRT3D.step_car3d!(pc, lthr, lbrk, lst, ddt; manual = false, groundz = groundz_ai)
        else
            DriveRT3D.step_car3d!(pc, 0.0, LOOSE_BRAKE, 0.0, ddt; manual = true, groundz = groundz_ai)
        end
        LOOSE_DIAG && (frames % 6 == 0) && println("   [loosediag] t ", round(cs.t, digits = 2), " v ", round(pc.v, digits = 2),
            " r ", round(DriveRT3D.yawrate3d(pc), digits = 2), " θ ", round(pc.θ, digits = 2), " grounded ", pc.grounded,
            " rh ", round.(pc.rh, digits = 3), " heave ", round(pc.heave, digits = 3), " ddt ", round(ddt, digits = 4), " rec ", LOOSE_REC[sl])
        bk = aibankP(pc)
        gy = isfinite(pc.y) ? pc.y : groundz(pc.x, pc.z)
        ai_poses[k] = (pc.x, gy, pc.z, pc.θ, bk[1], bk[2])
        done = (LOOSE_REC[sl] && ((abs(lherr) < 0.35 && pc.v > 2.0) || cs.t - LOOSE_T0[sl] > 10.0)) || !isfinite(pc.x)
        if GPLAI_T !== nothing
            gc = gplai_field!().cars[k]
            (gs, gd, _) = GPLAI.tlocate(GPLAI_T, pc.x, pc.z, 0)
            (lo, hi) = GPLAI.corridor(GPLAI_T, gs)
            gc.s = gs; gc.d = done ? clamp(gd, lo + 0.5, hi - 0.5) : gd; gc.v = pc.v; gc.dv = 0.0
            gc.yaw = pc.θ; gc.yawr = DriveRT3D.yawrate3d(pc); gc.pose = ai_poses[k]; gc.prev = gc.pose
            (rs, rl) = RaceAI.project(AILINE, pc.x, pc.z; hint = AICARS[k].s); AICARS[k].s = rs; AICARS[k].lane = rl; AICARS[k].v = pc.v
        else
            (rs, rl) = RaceAI.project(AILINE, pc.x, pc.z; hint = AICARS[k].s)
            AICARS[k].s = rs; AICARS[k].lane = clamp(rl, -RaceAI.LANE_MAX, RaceAI.LANE_MAX); AICARS[k].v = pc.v
            done && (AICARS[k].spin = RaceAI.wrapπ(pc.θ - RaceAI.pose_at(AILINE, rs, 0.0)[4]))
        end
        if done
            delete!(LOOSE_OF, k)
            println("  [loose] t=", round(cs.t, digits = 2), " AI ", k, " rejoins at ", round(pc.v*3.6), " km/h after ", LOOSE_HITS[sl], " more hits, heading off the line ",
                    round(rad2deg(RaceAI.wrapπ(pc.θ - RaceAI.pose_at(AILINE, RaceAI.project(AILINE, pc.x, pc.z)[1], 0.0)[4]))), " deg"); flush(stdout)
        end
    end
    nothing
end

"""The GPL AI field, one frame (AIGPL-2): step the field with the player's position, the off-road diagnostic, the race
bookkeeping (laps, order) in our frame, the cool-down. Returns the field's poses. LOOPSPLIT-1 cycle 4 S1: moved unchanged
(in the loop its `(ps, ...) =` wrote main()'s own `ps`)."""
function gplai_poses!(cs, ddt, ai_hit, AICARS, AILINE, GPLAI_PD, GPLAI_PH, GPLAI_SC, GPLAI_T, ent_name, gplai_field!, phase, race_done, race_go)
    # AIGPL-2: the field steps in GPL's frame at GPL's 36 Hz; the human is a car in the same frame
    f = gplai_field!()
    (ps, pdl, GPLAI_PH[]) = GPLAI.tlocate(GPLAI_T, cs.x, cs.z, GPLAI_PH[])
    pdv = ddt > 1e-4 ? (pdl - GPLAI_PD[][2])/ddt : 0.0
    abs(ps - GPLAI_PD[][1]) > 30 && (pdv = 0.0)
    GPLAI_PD[] = (ps, pdl)
    poses, hit = GPLAI.step!(f, ddt; player = (ps, pdl, clamp(pdv, -15.0, 15.0), cs.v), scale = GPLAI_SC,
                             vrel = isfinite(AI_REL) ? max(cs.v*AI_REL, 6.0) : Inf)
    ai_hit[] = hit
    if AI_OFFROAD_DIAG && race_go[]                       # SPATD-1 S4: AI centres off the drawn road, by 100 m of lap
        for gc in f.cars
            (wx, wz, _) = GPLAI.tworld(GPLAI_T, gc.s, gc.d); AI_OFF[2] += 1
            if !JuliaMotor.hat3d(ROADHAT, wx, wz; ref = Inf)[3]
                AI_OFF[1] += 1; b = floor(Int, gc.s/100); AI_OFFBIN[b] = get(AI_OFFBIN, b, 0) + 1
            end
            # WGTD-1 S4: the car's EDGES too (centre +- 0.95 m along the frame's lateral) -- "a little off the track"
            (lx, lz, _) = GPLAI.tworld(GPLAI_T, gc.s, gc.d + 0.95); (rx, rz, _) = GPLAI.tworld(GPLAI_T, gc.s, gc.d - 0.95)
            if !(JuliaMotor.hat3d(ROADHAT, lx, lz; ref = Inf)[3] && JuliaMotor.hat3d(ROADHAT, rx, rz; ref = Inf)[3])
                AI_OFF[3] += 1; b = floor(Int, gc.s/100); AI_EDGEBIN[b] = get(AI_EDGEBIN, b, 0) + 1
            end
            if AI_OFF_POS !== nothing                     # WGTD-1 S7: the same edge test, the car moved AI_OFF_POS m
                (lx2, lz2, _) = GPLAI.tworld(GPLAI_T, gc.s, gc.d + AI_OFF_POS + 0.95); (rx2, rz2, _) = GPLAI.tworld(GPLAI_T, gc.s, gc.d + AI_OFF_POS - 0.95)
                (JuliaMotor.hat3d(ROADHAT, lx2, lz2; ref = Inf)[3] && JuliaMotor.hat3d(ROADHAT, rx2, rz2; ref = Inf)[3]) || (AI_OFF[4] += 1)
            end
        end
    end
    crossed = falses(length(AICARS))
    for (i, gc) in enumerate(f.cars)                      # keep the race bookkeeping (laps, order, HUD) in our frame
        i > length(AICARS) && break
        prevs = AICARS[i].s
        s, lat = RaceAI.project(AILINE, poses[i][1], poses[i][3]; hint = prevs)
        AICARS[i].s = s; AICARS[i].lane = lat; AICARS[i].v = gc.v
        (prevs > AILINE.total*0.7 && s < AILINE.total*0.3) && (AICARS[i].lap += 1; crossed[i] = true)
    end
    # WGTD-1 (e) (PO 2026-10-08: "after the race the AI do one slow lap and stop in the pits, as GPL"): once any car
    # has run the race distance the flag is out, and each AI car's next crossing ends ITS race (lapped cars too, as in
    # racing). It then drives one cool-down lap at AI_COOL_PACE of its pace; at the line after that it moves to the outer edge of the
    # corridor (GPL's own line transition, held there) and slows to a stop over 300 m. (GPL brings them into the pit
    # lane; our AI have no pit line yet, so they stop at the edge of the straight.) JM_AI_COOLDOWN=0: racing on.
    ai_cooldown_step!(f, AICARS, GPLAI_T, crossed, ent_name, phase, race_done, race_go)   # LOOPSPLIT-1 cycle 2 S2: moved to main_loop.jl
    poses
end

"""The physics AI field (JM_AI_PHYSICS), one frame: plan, drive and step each AI Car3D, grass and solids, car-car
contact; returns the field's poses. LOOPSPLIT-1 cycle 4 S2: moved unchanged."""
function aiphys_poses!(cs, ddt, ai_hit, AICARS, AILINE, AIPHYS, ai_onroad, ai_stuck, groundz_ai, aibankP, groundz)
    # GC HYBRID: project each physics car onto the line → update the brain → the controller
    # steers it toward its rail at the planned speed → step the JM 2-D physics.
    for (i, pc) in enumerate(AIPHYS)
        # SEAM-1: last frame's arc length as the projection hint -- it keeps the search on this
        # car's own stretch of rail (a circuit that passes close to itself has two feet to find)
        # and costs 0.355 us instead of 2.12 (measured); a stale hint falls back to a full sweep.
        prevs = AICARS[i].s
        s, lat = RaceAI.project(AILINE, pc.x, pc.z; hint = prevs)
        AICARS[i].s = s; AICARS[i].lane = lat; AICARS[i].v = pc.v
        (prevs > AILINE.total*0.7 && s < AILINE.total*0.3) && (AICARS[i].lap += 1)
        TRACE_DS && ds_note!(s - prevs, pc.v, ddt, AILINE.total)
        # recovery: a stalled AI, or one that's run WAY off the racing line (off track at a
        # corner), is snapped back onto the line — so an AI can never drive off and vanish.
        # recover BEFORE it can climb a dune/leave the world: at the road-edge (not 14 m out),
        # and hard-recover if it's off the terrain HAT entirely (the "mid-air on the dune" case).
        offhat = !JuliaMotor.hat3d(TERRAIN, pc.x, pc.z; ref=Inf)[3]
        railθ = RaceAI.pose_at(AILINE, s, 0.0)[4]
        spun = abs(atan(sin(pc.θ - railθ), cos(pc.θ - railθ))) > SPIN_LIM   # heading way off the rail = spun out
        off = pc.v < 1.4 || abs(lat) > 9.0 || offhat || spun
        if off
            ai_stuck[i] += 1
            lim = (offhat || abs(lat) > 12.0 || spun) ? 6 : (abs(lat) > 9.0 ? 18 : 90)   # snap back fast when truly off / spun
            if ai_stuck[i] > lim
                rp = RaceAI.pose_at(AILINE, s + 10.0, 0.0); AIplace!(pc, rp[1], rp[3], rp[4]; v = max(8.0, pc.v*0.6)); ai_stuck[i] = 0
            end
        else; ai_stuck[i] = 0; end
    end
    # physics handles the pace (engine + grip); no per-frame rubber-band (rel=Inf), no corner-speed
    # scaling — the FIXED tune is the engine power (AI_POWER).  Conservative grip cap (amax).
    # The HUMAN is fed in as a racecraft object so the AI tailgate-then-pass the player too
    # (strategic: wait for a straight, own the corner — see RaceAI.plan!).
    ppr = RaceAI.project(AILINE, cs.x, cs.z)
    vts = RaceAI.plan!(AICARS, AILINE; scale = 1.0, amax = AI_AMAX, dt = ddt,
                       player = (ppr[1], ppr[2], cs.v))
    for (i, pc) in enumerate(AIPHYS)
        thr, brk, st = RaceAI.controller(AILINE, AICARS[i].s, AICARS[i].lane, AICARS[i].tlane, vts[i],
                                         pc.x, pc.z, pc.θ, pc.v, AIyaw(pc); power = AI_POWER)
        _tas = time(); DriveRT3D.step_car3d!(pc, thr, brk, st, ddt; manual=false, groundz=groundz_ai); DS_SIM[2] += time() - _tas
        # GRASS by the rendered road half-width (|lateral|>ROAD_HALFW), the SAME yardstick as the
        # player — NOT TRKSURF.on_track, whose 9 m half-width is far wider than the visible road, so
        # AI ran the verge near the finish straight penalty-free + drafting (PO saw them do exactly that).
        hs = JuliaMotor.hat(TRKSURF, pc.x, pc.z)
        ai_onroad[i] = !(hs.found && abs(hs.lateral) > ROAD_HALFW)
        if !ai_onroad[i] && pc.v > 2.5                        # AI off the racing surface → grass penalty
            AIbump!(pc, -GRASS_DRAG*pc.v*cos(pc.θ)*ddt, -GRASS_DRAG*pc.v*sin(pc.θ)*ddt, (2*rand()-1)*GRASS_SLIP*ddt)
        end
        ho = solid_hit(pc.x, pc.z, pc.θ, pc.v)               # E15: AI vs solid objects (no driving through bales)
        ho !== nothing && AIbump!(pc, ho[1], ho[2], ho[3], ho[4], ho[5], ho[6])
    end
    # slipstream: each AI tucked behind the player or another AI on a straight gets a forward tow
    let plead = (cs.x, cs.z, cs.θ, cs.v)
        for (i, pc) in enumerate(AIPHYS)
            ai_onroad[i] || continue                         # no slingshot while off the road (you crawl on grass)
            leads = NTuple{4,Float64}[plead]
            for j in 1:length(AIPHYS); j != i && push!(leads, (AIPHYS[j].x, AIPHYS[j].z, AIPHYS[j].θ, AIPHYS[j].v)); end
            tw = draft_tow(pc.x, pc.z, pc.θ, pc.v, leads)
            tw > 0.0 && AIbump!(pc, tw*cos(pc.θ)*ddt, tw*sin(pc.θ)*ddt, 0.0)
        end
    end
    # AI↔AI collisions (physics): pairwise overlap + closing → PLANAR momentum exchange only.
    # E55 (PO-authorised "ignore wheelspin in AI collisions"): the old response injected a
    # wheel-climb LAUNCH (upward heave) + ROLL into each car's 3-D body, so AI flipped, cartwheeled
    # and — the violent impulse diverging the MTK integrator — hyperspaced off-track (E38).  AI now
    # bump like billiard balls: push apart along the contact normal + a mild yaw nudge, NO vertical
    # launch and NO roll, so the field stays flat and nose-to-tail.  Impulse capped (no hyperspace).
    for a in 1:length(AIPHYS)-1, b in a+1:length(AIPHYS)
        pa = AIPHYS[a]; pb = AIPHYS[b]
        dx = pb.x-pa.x; dz = pb.z-pa.z; d = hypot(dx,dz)
        (d < 1e-3 || d > contact_d(dx, dz, d, pa.θ, pb.θ)) && continue   # oriented contact
        nx = dx/d; nz = dz/d
        vrel = (pa.v*cos(pa.θ)-pb.v*cos(pb.θ))*nx + (pa.v*sin(pa.θ)-pb.v*sin(pb.θ))*nz
        vrel <= 0.2 && continue
        imp = clamp(1.45*vrel*280.0/560, 0.0, 4.0)   # (1+e)·vrel·reduced-mass / m, capped at 4 m/s
        AIbump!(pa, -imp*nx, -imp*nz, clamp(-imp*0.04, -0.6, 0.6))   # planar push + mild yaw; no dvy/dpp
        AIbump!(pb,  imp*nx,  imp*nz, clamp( imp*0.04, -0.6, 0.6))
    end
    [(b=aibankP(pc); (pc.x, isfinite(pc.y) ? pc.y : groundz(pc.x, pc.z), pc.z, pc.θ, b[1], b[2])) for pc in AIPHYS]   # pc.y = 3-D height → AI visibly jump/heave; pitch/roll → list + roll
end

# LOOPSPLIT-1 cycle 4 S3: the frame loop's track-position block (moved unchanged): the player's lapdist / lateral from
# the .trk, lap progress and lap count (teleport-safe), the JM_TRACE_PROG / approach-trail diagnostics, and the world
# edge (the terrain HAT) as a physical wall with its last-resort seal. Returns the three loop locals it updates.
function track_position_step!(cs, dt, rst, race_go, player_prog, player_s_prev, ffb_jolt, groundz_phys,
                              BND_FX, BND_FY, BND_MZ, CLINE, LASTGX, LASTGZ, OFFDIST, ONTRACK, TRACE_PROG, prog_bad, prog_t0)
    hr = JuliaMotor.hat(TRKSURF, cs.x, cs.z)            # track-relative position (for lapdist/lateral HUD)
    if hr.found
        cs.lapdist = hr.lapdist; cs.lateral = hr.lateral; cs.along = hr.lapdist; cs.ontrack = hr.on_track
    else; cs.ontrack = false; end
    # ROBUST lap counting via ACCUMULATED track progress (a lap = a lap's worth of arc-length
    # covered), so it counts even if you cross the line OFF the road (slid wide at the finish).
    if CLINE !== nothing
        ps = RaceAI.project(CLINE, cs.x, cs.z)[1]
        # PO 2026-09-04 (Watkins Glen): "my first lap was listed at 1.19 seconds ... maybe
        # because I hit r to get back on the road at one point". It was.
        # R (respawn at the start) and SHIFT+R (recover) both TELEPORT the car BACKWARD along
        # the centreline, and the unwrap below assumes every step is a small FORWARD one: a
        # backward jump of more than half a lap gets `+= CLINE.total` applied to it and comes
        # out as a large FORWARD step, crediting up to 40% of a lap in a single frame. Enough
        # of that pushes player_prog past the next integer and banks an instant lap -- which
        # is what a 1.19 s lap is. It also corrupts the lap COUNT, so `cs.laps >= RACE_LAPS`
        # can be reached early or skipped, which is the likeliest reason the race never
        # announced it was over and the replay (written at exit) never matched the race.
        # A teleport is not motion: resynchronise and accumulate nothing for that frame.
        ds = prog_delta(ps, player_s_prev, CLINE.total; teleport = rst)
        race_go[] && (player_prog += ds)
        player_s_prev = ps
        while cs.laps < floor(Int, player_prog/CLINE.total); cs.laps += 1; end
        # STANDINGS-1 S2 (2026-09-16): measure HOW LONG the two progress views disagree.
        # S1 fixed the ranking, but the old expression is also what the live position readout
        # in the window title used all race (it calls the same standings()).  cs.laps ticks
        # when player_prog crosses an integer; cs.lapdist wraps when the TRKSURF probe passes
        # the start/finish line.  If those two events are not simultaneous there is a window
        # each lap in which the old expression is a full lap too high -- and the size of that
        # window is the difference between "one bad frame" and "the readout lies for seconds".
        # Prints only the window's start and end, with sim time, so it cannot flood.
        # JM_TRACE_PROG=1.
        if TRACE_PROG
            _oldpp = cs.laps + (LAPLEN > 0 ? clamp(cs.lapdist/LAPLEN, 0.0, 1.0) : 0.0)
            _newpp = player_prog/CLINE.total
            _bad = abs(_oldpp - _newpp) > 0.5
            if _bad && !prog_bad[]
                prog_bad[] = true; prog_t0[] = cs.t
                println("  [prog] DISAGREE from t=", round(cs.t, digits=2),
                        "s  laps=", cs.laps, " lapdist=", round(cs.lapdist, digits=1),
                        "  old=", round(_oldpp, digits=3), " new=", round(_newpp, digits=3))
            elseif !_bad && prog_bad[]
                prog_bad[] = false
                println("  [prog] agree again at t=", round(cs.t, digits=2),
                        "s  -- the readout was a lap out for ",
                        round(cs.t - prog_t0[], digits=2), " s")
            end
        end
    end
    # E56: the PLAYER grass penalty is now per-wheel tyre μ applied BEFORE the step (above) —
    # a wheel off the racing surface loses real grip in the brush model and pulls the car, rather
    # than the old post-step bumpX! drag/yaw scrub.  (The AI keep the bumpX! grass penalty.)
    # E7 boundary = the WORLD edge (the terrain HAT): you can drive the road AND the grass
    # freely, but if you go off the HAT you've left the world → snap back to the last spot
    # inside it (a fence/hedge collision) and bleed speed.  (Based on the HAT, NOT the racing
    # line, so it never slows you on a wide road/grass — that was the Watkins Glen "molasses".)
    # A short off-HAT distance GRACE (JM_FENCE_GRACE m) lets the car cross narrow mesh seams
    # / bridge gaps in the HAT (e.g. 4 on the Nürburgring racing line) without a false
    # containment; a genuine excursion exceeds it within a few metres and is held at the edge.
    # BNDWRECK-1 S4: sample the approach trail (see TRAIL_SECS). Sited HERE because this
    # branch runs every frame whether or not anything is touching; the STUCK/damage blocks
    # are inside a contact test and would only ever record the crash itself.
    if TRAIL_SECS > 0.0 && !WRECKED[] && cs.t - TRAIL_LAST[] >= 1.0/TRAIL_HZ
        TRAIL_LAST[] = cs.t
        # BNDWRECK-1 S6: carry the two track-relative numbers as well. S5's trail had
        # position, speed, slip and off-HAT distance -- and off-HAT was 0.0 on every
        # sample but the last, so it could not show the car running wide, which is what
        # the slip opening implies. `lateral` is the signed offset from the racing line
        # and `lapdist` says WHERE on the lap, so two wrecks at different sites become
        # directly comparable without a map. NaN when the HAT probe missed.
        _lat = hr.found ? hr.lateral : NaN
        _lap = hr.found ? hr.lapdist : NaN
        push!(TRAIL_BUF, (cs.t, cs.x, cs.z, cs.v, cs.θ, OFFDIST[], _lat, _lap))
        while length(TRAIL_BUF) > 1 && TRAIL_BUF[end][1] - TRAIL_BUF[1][1] > TRAIL_SECS
            popfirst!(TRAIL_BUF)
        end
    end
    if ONTRACK[]; LASTGX[] = cs.x; LASTGZ[] = cs.z; OFFDIST[] = 0.0   # inside the world
        BND_FX[] = 0.0; BND_FY[] = 0.0; BND_MZ[] = 0.0               # E56: release the world-edge wall
    elseif (hr.found && abs(hr.lateral) < ROAD_HALFW) ||
           (RUNOFF_W > 0 && CLINE !== nothing && abs(RaceAI.project(CLINE, cs.x, cs.z)[2]) < RUNOFF_W)
        # RUNOFF-1 (2026-09-25, PO: "tires fall off/bouncing car which ended several of the races"): at
        # Spa's Bus Stop the collision terrain ENDS 9 m from the centreline while grass is drawn beyond,
        # so a car running wide met the invisible world-edge wall at 131 km/h and lost its wheels.
        # A hole in the collision mesh within JM_RUNOFF_W m (20) of the centreline is run-off, not
        # the edge of the world: coast at the held height like the corridor case below.
        # E52: off the TERRAIN .3do mesh but still inside the road corridor (the .trk ribbon
        # is continuous) → a gap in the collision mesh UNDER the Monza banking overpass, not the
        # world edge.  Coast through at the held height; advance the in-world anchor so the
        # FENCE_GRACE containment never fires across the (~20 m) underpass.
        LASTGX[] = cs.x; LASTGZ[] = cs.z; OFFDIST[] = 0.0
        BND_FX[] = 0.0; BND_FY[] = 0.0; BND_MZ[] = 0.0; BND_PK[] = 0.0
    else
        OFFDIST[] += cs.v * (dt > 1e-4 ? dt : 1/60)
        # E56: the WORLD EDGE is now a PHYSICAL WALL, not a position snap-back.  nl = the car's
        # straight-line distance past the last in-world spot = the instantaneous penetration; feed a
        # stiff spring-damper (the same contact_force(:wall) kernel) back INTO the world so the car
        # bounces off the edge as a real wall — no teleport.  Recovery from a spin/excursion is
        # SHIFT-R only (the auto routine snap-back is gone).  FENCE_GRACE keeps the wall off narrow
        # HAT mesh seams; a last-resort hard containment (FENCE_FAR) still seals the world if the
        # wall somehow fails (so the car can NEVER fall into the void).
        nwx = LASTGX[]-cs.x; nwz = LASTGZ[]-cs.z; nl = hypot(nwx,nwz)   # wall normal: back into the world
        nl < 1e-3 && (nwx = cos(cs.θ+π); nwz = sin(cs.θ+π); nl = 1.0)
        nwx /= nl; nwz /= nl
        if nl > FENCE_GRACE
            pvx = WVX[]; pvz = WVZ[]                     # E96-S2: true world velocity, not v*cos/sin(θ)
                                                         # -- cs.v is unsigned, so the old form
                                                         # read a retreating car as approaching
            vn = pvx*nwx + pvz*nwz                       # car speed along the INWARD normal (<0 = leaving)
            gdt = dt > 1e-4 ? dt : 1/60
            (bfx, bfy, bmz) = DriveRT3D.contact_force(nl - FENCE_GRACE, nwx, nwz, vn, cs.θ; kind = :wall, dt = gdt)
            BND_FX[] = bfx; BND_FY[] = bfy; BND_MZ[] = bmz
            BND_PK[] = hypot(bfx, bfy)   # E95b: the wreck trigger must SEE the world-edge wall
            BND_NL[] = nl - FENCE_GRACE; BND_VN[] = vn; BND_OFF[] = OFFDIST[]   # BNDWRECK-1 S1
            # E95f: keep the WORLD-frame wall normal (points INTO the world). contact_force
            # returns BODY-frame forces, and the first cut dotted those against WORLD wheel
            # displacements to pick the leading corner -- mixing frames, which is why the
            # REAR wheels came off a head-on impact instead of the fronts.
            BND_NX[] = nwx; BND_NZ[] = nwz
            ffb_jolt = clamp(-vn*0.05, -1.0, 1.0)        # FF jolt off the world-edge wall
            # E95g: skipping containment entirely for a wreck (E95e) was WRONG -- with no
            # push-back AND no seal the car escaped the world, got caught somewhere else and
            # was flung back to the start, over and over: the PO's infinite loop. Contain it,
            # but with vdamp = 0 so the seal KILLS the velocity instead of returning any of
            # it. A wreck is stopping; it must never be handed energy back.
            # E103 (PO 2026-09-01): "when wheels come off during a collision, the car stops
            # dead where the impact happened. It does not hyperspace back to the start line,
            # which is the current behavior."
            #
            # THIS LINE WAS THE HYPERSPACE. containX! -> contain3d! does not push, it PLACES:
            #   c.s_pos(c.integ, [xnew, znew]); c.x = xnew; c.z = znew
            # and (LASTGX, LASTGZ) is the last position that was ON TRACK, which only updates
            # while ONTRACK[]. A car that wrecks and leaves the mesh stops updating it, so the
            # seal teleports the wreck back to wherever it last had grip -- and since both are
            # initialised to the SPAWN point, a car that wrecks before ever registering
            # on-track is sent to the start line exactly as the PO describes.
            #
            # E95g got close: it saw the car "flung back to the start, over and over" and
            # fixed the ENERGY (vdamp = 0 for a wreck) without changing WHERE it is sealed to.
            #
            # A wreck is not lost, it is finished: seal it WHERE IT IS. For a driveable car
            # the old behaviour stands -- putting it back on the track is a rescue and the
            # race continues. JM_WRECK_SEAL_BACK=1 restores the old path.
            if nl > FENCE_GRACE + FENCE_FAR                  # the wall failed to contain → last-resort seal (rare; never seen since E56)
                (sealx, sealz) = WreckSeal.seal_target(WRECKED[], cs.x, cs.z,
                                     LASTGX[], LASTGZ[];
                                     seal_back = haskey(ENV, "JM_WRECK_SEAL_BACK"))
                GPLW_ON && gplw_teleported!()
                containX!(cs, sealx, sealz; vdamp=(WRECKED[] ? 0.0 : 0.3), settle=true, groundz=groundz_phys)
                BND_FX[] = 0.0; BND_FY[] = 0.0; BND_MZ[] = 0.0; BND_PK[] = 0.0; OFFDIST[] = 0.0
            end
        else
            BND_FX[] = 0.0; BND_FY[] = 0.0; BND_MZ[] = 0.0; BND_PK[] = 0.0
        end
    end
    return (player_prog, player_s_prev, ffb_jolt)
end

# LOOPSPLIT-1 cycle 4 S4: the frame loop's network block (moved unchanged): yield to the socket reader, send this car's
# pose (and the host's AI field), take the remote poses re-grounded on this machine's terrain, the JM_NET_ERR prediction
# error, the closest-approach / overlap measures and the JM_NET_DIAG report. In the loop, JM_NET_ERR's packet interval
# `dt = (q.tick - pv.tick)/1000` overwrote the frame's dt for the rest of the frame; it is local here.
function netlink_step!(cs, inp, frames, ai_poses, AICARS, CLINE, aibankK, ai_ground, net_last)
    # ⚠️ YIELD FIRST. The socket reader is an `@async` task (netplay.jl keeps one long-lived
    # reader so `poll!` never blocks the frame), and a Julia task only runs when something
    # yields to the scheduler. The probe loops `sleep(0.002)` and so yields constantly; this
    # render loop does not sleep at all, so the reader was NEVER SCHEDULED and every packet
    # sat in the kernel buffer. Measured before this line existed: client `peers=1` (it was
    # sending) and host `rx=0 peers=0` (it received nothing, so never learned a peer, so
    # never replied) -- a one-way link that was really a starved task.
    yield()
    NetPlay.poll!(NETLINK)
    if cs.t - net_last[] >= 1/NET_HZ
        net_last[] = cs.t
        NetPlay.send_pose!(NETLINK, NET_ID, round(Int, cs.t*1000),
                           cs.x, cs.y, cs.z, cs.θ, cs.v, inp.steer)
        # MP-5: the HOST is the authority for the AI field -- one packet per AI car, ids
        # AI_ID0.., at the same cadence as its own car. The client has no field of its own.
        if NETMODE == "host" && !isempty(ai_poses)
            for (k, p) in enumerate(ai_poses)
                NetPlay.send_pose!(NETLINK, NetPlay.AI_ID0 + (k - 1), round(Int, cs.t*1000),
                                   p[1], p[2], p[3], p[4],
                                   k <= length(AICARS) ? AICARS[k].v : 0.0, 0.0)
            end
        end
    end
    # ⚠️ THE E104(a) RULE, ENFORCED AT THE RECEIVING END. `predict` deliberately does not
    # extrapolate height, and the packet's y is the SENDER's ground -- which is not this
    # machine's ground if the two disagree by so much as a terrain rounding. A remote car's
    # height must come from the terrain UNDER IT, exactly as the AI field's does since
    # E104-S4, or remote cars float for the same reason the AI did.
    netp = Tuple{Int,NTuple{6,Float64}}[]; empty!(NETVEL[])
    for (id, q) in NetPlay.remote_poses_at(NETLINK, time())
        b = aibankK((q.x, 0.0, q.z, q.yaw))
        push!(netp, (Int(id), ai_ground((q.x, q.y, q.z, q.yaw, b[1], b[2]))))
        NETVEL[][Int(id)] = (q.v*cos(q.yaw), q.v*sin(q.yaw))
    end
    # ── E85-S7: PREDICTION ERROR, measured receiver-side with no clock sync ─────────────
    # When a NEW packet arrives for a car, we already know what the PREVIOUS packet
    # predicted for that instant: dead-reckon the old pose forward by the tick difference
    # and compare against the position the new packet actually reports. Both numbers come
    # from the same sender's own clock, so nothing has to be synchronised and no two logs
    # have to be correlated afterwards -- which is what made S4's version need an analytic
    # trajectory. Here the trajectory is whatever the other car really did.
    if NET_ERR
        for (id, q) in NETLINK.remote
            pv = get(NET_PREV[], id, nothing)
            if pv !== nothing && q.tick != pv.tick
                dt = (q.tick - pv.tick) / 1000
                if 0 < dt < 1.0                       # ignore huge gaps (startup, stalls)
                    pr = NetPlay.predict(pv, dt)
                    push!(NET_ERRS, hypot(q.x - pr.x, q.z - pr.z))
                    push!(NET_DTS, dt)
                end
            end
            NET_PREV[][id] = q
        end
        if !isempty(NET_ERRS) && (frames % 600) == 0
            m = sum(NET_ERRS)/length(NET_ERRS)
            println("  [neterr] n=", length(NET_ERRS),
                    "  interval mean=", round(sum(NET_DTS)/length(NET_DTS), digits=3), "s",
                    "  ERR mean=", round(m, digits=4), " m  max=",
                    round(maximum(NET_ERRS), digits=4), " m")
            flush(stdout)
        end
    end
    NETPOSES[] = netp
    for (_, p) in netp
        _d = hypot(p[1] - cs.x, p[3] - cs.z)
        # CARCOLLIDE-2: open wheelers alongside touch tyre to tyre at 1.72-1.80 m and interleave closer, so the
        # pass-through measure is the deepest OVERLAP of the two cars' parts (carcontact.jl), not the distance
        _g = _d < CAR_BOUND_D ? car_contact_geom(cs.x, cs.z, cs.θ, p[1], p[3], p[4]) : nothing
        _g !== nothing && (NET_PENMAX[] = max(NET_PENMAX[], _g[5]))
        NET_PENNOW[] = _g === nothing ? 0.0 : _g[5]
        if _d < NET_DMIN[]
            NET_DMIN[] = _d
            # LOADHANG-1 S4: WHERE the closest approach was -- each car's (s, lateral) on the centreline, so a
            # miss alongside says which car is off the line (netcollide_smoke went red with dmin 2.4-2.7 m)
            CLINE !== nothing && (NET_DMIN_AT[] = (RaceAI.project(CLINE, cs.x, cs.z), RaceAI.project(CLINE, p[1], p[3])))
        end
    end
    # JM_NET_DIAG=<n>: report the link every n frames. "No car appeared" has at least four
    # causes -- nothing sent, nothing received, everything judged stale, or nothing drawn --
    # and a screenshot cannot tell them apart, especially with the two cars 80 m apart on a
    # curving track. Print the counts instead of squinting.
    if NET_DIAG > 0 && (frames % NET_DIAG) == 0
        println("  [net] t=", round(cs.t,digits=1), " rx=", NETLINK.rx,
                " dropped=", NETLINK.dropped, " peers=", length(NETLINK.peers),
                " known=", length(NETLINK.remote), " drawn=", length(netp),
                " hits=", NET_HITS[], " dmin=", round(NET_DMIN[], digits = 2), " pen=", round(NET_PENMAX[], digits = 2), " pennow=", round(NET_PENNOW[], digits = 2), " v=", round(cs.v, digits = 1),
                NET_DMIN_AT[] === nothing ? "" : string(" at self(s,lat)=", round.(NET_DMIN_AT[][1], digits = 2),
                                                        " remote=", round.(NET_DMIN_AT[][2], digits = 2)))
        flush(stdout)
    end
    return nothing
end

"""CRASHBODY-1: the wreck as a free rigid body (wreck_body.jl), one frame. Hands the car over on the first call -- its pose,
speed and yaw rate, the wheels still on, each corner's grip -- then steps it on the ground under it against the GPL walls
and the trackside objects near it (a hedge gives and holds), with the driver's brake on the wheels, and writes the result
back to the game's car (position, heading, speed, attitude, the session clock) so lap position, camera, telemetry and the
replay carry on. Torn-off wheels leave the body as they leave the car (is_loose)."""
function wreck_body_step!(cs, inp, dt, groundz_phys::G, roll_ter; dry::Bool = false) where {G}   # ::G: specialise on the closure (passed only into hq, Julia would not)
    WB = WreckBody; V3 = WB.V3
    gdt = dt > 1e-4 ? dt : 1/60
    b = WBODY[]
    if dry
        # the hidden warm-up frame: one step of a scratch body at the car's pose, nothing written back -- so the crash path
        # is COMPILED before the race (a precompile of this function left ~140 ms of its callees to compile at the impact)
        b = WB.Body(WB.Geometry(m = DriveRT3D.MASS[]))
        WB.start!(b, cs.x, cs.z, cs.y, cs.θ, cs.pitch, roll_ter + cs.roll, V3(WVX[], 0.0, -WVZ[]), V3(0.0, Float64(DriveRT3D.yawrate3d(cs)), 0.0))
    elseif b === nothing
        b = WB.Body(WB.Geometry(m = DriveRT3D.MASS[]))
        on = ntuple(i -> !is_loose(WHEEL_NAMES[i]), 4)
        WB.start!(b, cs.x, cs.z, cs.y, cs.θ, cs.pitch, roll_ter + cs.roll, V3(WVX[], 0.0, -WVZ[]),
                  V3(0.0, Float64(DriveRT3D.yawrate3d(cs)), 0.0); on = on, dmu = ntuple(i -> DriveRT3D.damage_mu(i), 4))
        WBODY[] = b; WBODY_PLANE[] = WB.Plane(cs.x, -cs.z, cs.y, 0.0, 0.0)
        println("  [crashbody] the wreck is a free rigid body from here: ", round(cs.v*3.6, digits = 0), " km/h, ", count(on),
                " wheels on"); flush(stdout)
    end
    dry || for i in 1:4; b.on[i] = !is_loose(WHEEL_NAMES[i]); b.dmu[i] = DriveRT3D.damage_mu(i); end
    b.brake = clamp(inp.brake, 0.0, 1.0)
    # the ground: a plane fitted under the car (render frame, Z = -game z); over a hole in the mesh keep the last one
    hq(X, Z) = (y = groundz_phys(X, -Z); y > -900 ? Float64(y) : NaN)
    pl = WB.fit_plane(hq, b.p[1], b.p[3])
    (isfinite(pl.h0) && isfinite(pl.gx) && isfinite(pl.gz)) ? (dry || (WBODY_PLANE[] = pl)) : (pl = WBODY_PLANE[])
    # the walls near it, as planes through the CG's nearest face point (game frame -> render frame)
    walls = WB.WallPlane[]
    gx, gz = b.p[1], -b.p[3]
    if GPLW_PHYS && !dry                                   # (gplwall_gaps keeps the wall's "came from" state)
        (lat, lo, hi, glo, ghi, ngx, ngz, nlo, nhi, gend, nend) = gplwall_gaps(gx, gz, cs.θ)
        for (g, n) in ((glo, nlo), (ghi, nhi))
            d = g + CARLF*abs(cos(cs.θ)*n[1] + sin(cs.θ)*n[2]) + CARW           # the CG to that face along its normal
            (isfinite(d) && d < 4.0) || continue
            push!(walls, WB.WallPlane(V3(gx - d*n[1], b.p[2], -(gz - d*n[2])), V3(n[1], 0.0, -n[2])))
        end
        if isfinite(gend) && gend < 3.0
            d = gend + CARLF
            push!(walls, WB.WallPlane(V3(gx - d*nend[1], b.p[2], -(gz - d*nend[2])), V3(nend[1], 0.0, -nend[2])))
        end
    end
    for k in eachindex(SOLIDS)
        (ox, oz, r, kind) = SOLIDS[k]
        hypot(ox - gx, oz - gz) < r + 6.0 || continue
        (g, nx, nz) = solid_gap(gx, gz, k)
        g < 4.0 || continue
        push!(walls, WB.WallPlane(V3(gx - g*nx, b.p[2], -(gz - g*nz)), V3(nx, 0.0, -nz), kind === :soft))
    end
    # each touching point asks the TERRAIN mesh for the surface just below it (a pure query: groundz_phys keeps the
    # driving car's step-guard and layer state, which 24 points a substep would scramble)
    th(X, Z, yref) = (r = JuliaMotor.hat3d(TERRAIN, X, -Z; ref = yref); r[3] ? Float64(r[1]) : NaN)
    WB.step!(b, gdt, WB.Terrain(th, pl); walls = walls)
    dry && return nothing
    # a hard wall hit tears off the wheels that lead into it, as for the driving car (E95: "detach the wheel that hit the
    # barrier"); the wall normal in game coordinates, pointing out of the wall
    (b.wall_peak > 3.0e4 && norm(b.v) > 3.0) &&
        detach_hit_wheels!(cs.x, cs.z, cs.θ, norm(b.v); fence = true, fence_nx = b.wall_n[1], fence_nz = -b.wall_n[3])
    θ, pitch, roll = WB.attitude(b)
    _px = b.p[1]; _pz = b.p[3]          # plain locals for the closure below: capturing `b` (assigned in three branches) boxed it
    if CRASHBODY_DIAG && (floor(Int, 4*b.t) != floor(Int, 4*(b.t - gdt)) || b.rest)
        println("  [crashbody] t ", round(b.t, digits = 2), " CG ", round(b.p[2] - WB.plane_y(pl, b.p[1], b.p[3]), digits = 2),
                " m up  roll ", round(rad2deg(roll), digits = 0), " pitch ", round(rad2deg(pitch), digits = 0), " heading ",
                round(rad2deg(θ), digits = 0), "  v ", round(norm(b.v), digits = 1), " m/s  w ", round(norm(b.ω), digits = 1),
                " rad/s  contacts ", b.contacts, "  walls ", length(walls), b.rest ? "  AT REST" : "",
                "  ground ", round(pl.h0, digits = 2), " [", join([round(hq(_px + dx, _pz + dz), digits = 2) for (dx, dz) in ((1.5, 0.0), (-1.5, 0.0), (0.0, 1.5), (0.0, -1.5))], " "),
                "] at game (", round(b.p[1], digits = 1), ", ", round(-b.p[3], digits = 1), ")"); flush(stdout)
    end
    o = b.p - b.R * V3(0.0, b.g.hcg, 0.0)                 # the model's origin: the ground point under the CG
    cs.x = o[1]; cs.z = -o[3]; cs.y = o[2]; cs.θ = θ
    cs.v = hypot(b.v[1], b.v[3]); WVX[] = b.v[1]; WVZ[] = -b.v[3]
    cs.pitch = pitch; cs.roll = roll
    cs.toff += gdt; cs.t = cs.integ.t + cs.toff           # the session clock runs on (the driving model is not stepped)
    # the safety net the driving car has: never deeper than GPLW_PEN into a GPL wall nor through a drawn obstacle face. The
    # body sees only the walls beside its CG; a fast tumble went 19 m through Watkins Glen's s 1650 wall (gplwall_smoke).
    # Whatever the clamps move the car, the body moves too, and loses its speed into that face.
    if GPLW_PHYS
        x0, z0 = cs.x, cs.z
        for _ in 1:2
            gplwall_clamp!(cs)
            OBS_ON && obs_clamp!(cs)
        end
        dx = cs.x - x0; dz = cs.z - z0; dl = hypot(dx, dz)
        if dl > 1e-4
            nr = V3(dx/dl, 0.0, -dz/dl)
            b.p += V3(dx, 0.0, -dz)
            vn = dot(b.v, nr); vn < 0 && (b.v -= vn*nr)
            WVX[] = b.v[1]; WVZ[] = -b.v[3]; cs.v = hypot(b.v[1], b.v[3])
        end
    end
    nothing
end
