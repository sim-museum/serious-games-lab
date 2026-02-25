# FreeFalcon Main Menu Button Positions

## Button Layout (Y=728 for all buttons at bottom of screen)

| Button | ID | X Position | SDL Click (1024x768) | Callback Function |
|--------|-----|------------|---------------------|-------------------|
| Exit | EXIT_CTRL (80000) | 0 | (30, 745) | ExitButtonCB() |
| Logbook | LB_MAIN_CTRL (50003) | 100 | (130, 745) | OpenLogBookCB() |
| Tactical Ref | TACREF_CTRL (10052) | 200 | (230, 745) | OpenTacticalReferenceCB() |
| ACMI | ACMI_CTRL (10047) | 300 | (330, 745) | ACMIButtonCB() |
| Setup | SP_MAIN_CTRL (70003) | 375 | (405, 745) | OpenSetupCB() |
| Comms | CO_MAIN_CTRL (60003) | 450 | (480, 745) | OpenCommsCB() |
| Theater | UI_THEATER_BUTTON | 524 | (554, 745) | TheaterButtonCB() |
| Tac Engage | TE_MAIN_CTRL (30003) | 624 | (654, 745) | OpenTacticalCB() |
| Instant Action | IA_MAIN_CTRL (10003) | 724 | (754, 745) | OpenInstantActionCB() |
| Dogfight | DF_MAIN_CTRL (20003) | 824 | (854, 745) | OpenDogFightCB() |
| Campaign | CP_MAIN_CTRL (40003) | 924 | (954, 745) | OpenMainCampaignCB() |

## Window Groups

| Button | Group ID |
|--------|----------|
| Exit | 9000 |
| Instant Action | 1000 |
| Dogfight | 2000 |
| Tactical Engagement | 3000 |
| Campaign | 4000 |
| Logbook | 5000 |
| Comms | 6000 |
| Setup | 8000 |
| Theater | 8000 |
| Tactical Reference | 10000 |
| ACMI | 200000 |

## Testing Notes

1. Window resolution: 1024x768 (matches UI resolution, no scaling needed)
2. All main buttons are at Y=728 (near bottom of 768-pixel tall screen)
3. Click positions above include ~30 pixel offset for button center
4. Debug output is enabled - check stderr for callback messages

## Resource Files Required (per button)

### Setup Button
- st_res.lst / ST_ART.LST (case varies)
- st_snd.lst
- st_scf.lst

### Dogfight Button
- df_res.lst / DF_res.LST
- df_snd.lst
- df_scf.lst

### Instant Action Button
- ia_res.lst / IA_res.LST
- ia_snd.lst
- ia_scf.lst

### Campaign Button
- cs_res.lst / CS_res.LST (campaign select)
- cs_snd.lst
- cs_scf.lst
