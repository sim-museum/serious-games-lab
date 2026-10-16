# IRTEST-261015: how to analyse the PO's files when they arrive

Copy the session's .ibt files to `~/gold standard/julia racer/<YYMMDD>/` (one folder per session). From
`JuliaMotorMTK/`:

| test | question | run | compare with |
|---|---|---|---|
| 1 skidpad limit, both setups | where iRacing's front gives up vs the rear (julia turns ~0.75 of iRacing at 1.25-1.5 g) | `JM_ST_DIR="~/gold standard/julia racer/<YYMMDD>" julia --project=. tools/irgold_steady.jl` | per 0.1 g cell: steer, yaw, sideslip, axle slip angles, gold vs sim; PHYSFID-1 S6-S11 |
| 2 4th-gear pulls, both setups | does WW103 put ~6 % more drive down at the same gear/rpm? | `tools/longval_261002.jl` (edit its `ring`/REF to the new folder) or `tools/irgold_replay.jl` on the pull windows | PHYSFID-1 S6 (5-8 % WOT deficit on WW103) |
| 3 in-gear coasts | drivetrain loss under engine braking vs under power | `tools/coast_compare.jl` / `tools/coast_split.jl` on the folder | E91, IRFIT-261004 |
| 4 contact | iRacing's contact law: what a touch costs | `julia --project=. tools/irtest_contact_261015.jl "<folder>"` | julia: car hits damage the player by the wall law from 3 m/s (CARINTERACT-1 S1) |
| 5 draft / slingshot | drag cut by gap | `julia --project=. tools/irtest_draft_261015.jl "<folder>"` (JM_DRAFT_MASS if fuel differs) | julia: 45 % right behind, 0 at 26 m (drive_native_mtk.jl DRAFT_DRAG_CUT/DRAFT_LEN) |

Then: tests 1-3 feed PHYSFID-1 (cap 25, 11 used); 4-5 feed CARINTERACT-1 (fit the draft shape; set the car-hit damage
onset/scale and the AI side). The PO's notes per contact test (what was seen) go with test 4's table.
