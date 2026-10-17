# 261017 garage screenshots -- transcription notes (raw, per snip)
Base = "261010_rung_official" (iRacing official Monza setup the PO used): fuel 43.2 L.
Front: ARB arms 2, dia 0.375", bias 53.50 %, toe-in -1 mm, steering 10:1. Rear: ARB 0.6875", arms 5, toe-in +1 mm.
Corners F: perch 165.1 mm, spring 30 N/mm, packer 0, bump +4, rebound +8. R: perch 103.6, 48 N/mm, packer 0, bump +4, reb +7.
Tyres 152 kPa cold all four. Gears: FD 4.22; 2.23 126.0 / 1.72 163.3 / 1.32 212.8 / 1.04 270.1 / 0.846 332.1 km/h.
Diff: plates 4, preload 41 Nm, drive 75 deg, coast 60 deg.

snip | change | LF cw rh shock camber | RF ... | LR ... | RR ... | cross | toeF | notes
01-05 | base 43.2 L | 1338 83.1 61.7 -0.4 | same | 1630 105.1 58.7 -0.5 | same | 50.0 | -1 |
06-07 | fuel 4.5 L (min) | 1244 88.1 57.8 -0.3 | same | 1582 107.6 57.1 -0.4 | same | 50.0 | -1 |
08-09 | fuel 179.5 L (max) | 1669 65.5 75.4 -0.9 | same | 1801 96.1 64.2 -0.7 | same | 50.0 | -1 | fails tech (rh too low)
10 | LF perch 94.1 | 1770 131.7 11.8 +0.1 | 905 122.9 38.6 +1.4 | 1230 109.6 51.0 -1.1 | 2030 100.4 66.7 +0.2 | 36.0 | -3 |
11 | LF perch 120.6 | 1606 113.2 30.8 -0.1 | 1070 107.8 47.3 +0.7 | 1386 107.9 53.9 -0.9 | 1874 102.2 63.6 -0.1 | 41.4 | -2 |
12 | LF perch 165.9 | 1333 82.6 62.2 -0.5 | 1343 82.6 62.0 -0.5 | 1634 105.0 58.7 -0.5 | 1626 105.1 58.6 -0.5 | 50.2 | -1 | one click = 0.8 mm
13 | LF perch 204.8 | 1101 57.1 88.3 -0.8 | 1575 61.7 74.4 TooLow | 1841 102.6 62.9 -0.1 | 1419 107.4 54.6 TooLow | 57.6 | -0 |
14 | LF perch 305.6 | 1012 47.4 98.2 -0.9 | 1663 53.8 79.1 -1.8 | 1920 101.6 64.5 -0.0 | 1341 108.3 53.0 -0.9 | 60.4 | +0 | LF shock near 104.6 max
15 | LR perch 41.7 | 967 87.2 50.8 -1.2 | 1708 78.5 72.7 +0.3 | 2025 158.5 16.5 +0.2 | 1236 149.5 38.4 TooHigh | 62.9 | -1 |
16 | LR perch 96.8 | 1297 83.5 60.5 TooLow | 1379 82.6 62.9 -0.4 | 1675 110.7 54.2 -0.4 | 1584 109.7 56.6 -0.2 | 51.5 | -1 |
17 | LR perch 122.6 | 1448 81.9 64.9 -0.2 | 1229 84.4 58.5 TooLow | 1504 89.4 71.0 TooLow | 1755 92.1 64.8 TooLow | 46.0 | -1 |
18 | LR perch 305.2 | 1775 TooLow 74.7 +0.4 | 904 88.4 49.0 TooLow | 1117 TooLow 106.4 TooLow | 2140 55.4 82.3 TooLow | 34.1 | -1 | LR shock 106.4 of 113
19 | LF spring 18 N/mm (perch 165.1) | 1338 83.1 61.7 -0.4 | same as base | base | base | 50.0 | -1 | NOTHING moved?!
20 | LF spring 35 | 1188 TL 78.6 TL | 1488 TL 69.8 TL | 1764 103.5 61.3 -0.3 | 1496 106.6 56.1 TL | 54.8 | -1 | numbers look like a SOFTER LF (display lag? 19 showed base)
21 | LR spring 30 (LF 30) | 1390 TL 63.2 -0.3 | 1286 83.7 60.2 TL | 1571 97.7 64.5 TL | 1689 98.9 61.6 TL | 48.1 | -1 |
22 | LR spring 70 | identical to 21 | | | | 48.1 | | display lags one change?
NB "Too Low"(TL) blinks with the value (snips 08/09 same state): it is a tech flag, not an out-of-range readout.
23 | base reloaded | = base, NO asterisks
24 | LF packer 19.0 (no asterisks) | all = base; LF shock max 104.6 -> 85.6 (= 104.6-19.0) | packer has NO static effect at 0 load on it
25 | LF packer 10.3 (asterisks) | all = base; LF max still 85.6 -> STALE
KEY: an asterisk after the labels ("Spring rate:*", "Camber:*") = garage not re-solved yet -> the numbers are the
PREVIOUS solved state. 21 (no *) == 22 (*) confirms; 19 (*) shows base. Use only asterisk-free frames as truth;
an asterisk frame = the state of the previous setting.
26 | base (no *) | = base
27 | F ARB arms "soft" (greyed = solving) | = base (level car)
28 | F ARB arms "firm" (*) | = base (level car). Arms list: soft, 2(base), firm (names, more?)
29 | F ARB arms 4 (*) | = base
30 | F ARB arms dropdown: soft, 2, 3, 4, 5, 6, firm | = base
31 | F ARB diameter dropdown: Disconnected, 0.375", 0.4375" | = base
32 | F ARB dia Disconnected (*) | = base
33 | F ARB dia 0.4375 (*) | = base
--- B9 twisted car: LF perch 167.1 (+2.0 mm) ---
34 | twist, F ARB 2 / 0.375 (no *) | 1326 81.8 63.0 -0.5 | 1350 82.0 62.3 -0.5 | 1640 105.0 58.9 -0.5 | 1619 105.2 58.5 -0.5 | 50.4 | -1 |
35 | twist, arms soft (*) | 1326 TL 63.1 -0.5 | 1350 TL 62.3 -0.5 | 1641 105.0 58.9 -0.5 | 1619 105.2 58.5 -0.5 | 50.4 |
36 | twist, arms 4 (*) | 1327 81.8 63.0 | 1349 82.0 62.4 | 1640 105.0 58.9 | 1620 105.2 58.5 | 50.3 |
37 | twist, arms firm (*) | 1328 81.8 63.0 | 1348 82.0 62.4 | 1639 105.0 58.8 | 1621 105.2 58.5 | 50.3 |
   (twist of +2 mm is small: arm effect ~ +-1 N, at display resolution)
38 | twist, arms 2 / 0.375 (no *) | 1326 TL 63.0 -0.5 | 1350 TL 62.3 | 1641 105.0 58.9 | 1619 105.2 58.5 | 50.4 |
39 | twist, F dia Disconnected (*) | 1324 81.7 63.1 -0.5 | 1352 82.0 62.3 | 1643 104.9 58.9 -0.4 | 1617 105.2 58.4 -0.5 | 50.4 |
40 | twist, F dia 0.4375 (*) | 1328 81.8 63.0 | 1348 82.0 62.4 | 1639 105.0 58.9 | 1621 105.2 58.5 | 50.3 |
   => a stiffer bar REDUCES perch jacking (spring preload partly reacted by the parallel bar): dLF -14/-12/-10 N for none/0.375/0.4375
41 | base, rear panel: fuel 43.2, R ARB 0.6875, arms 5, toe +1 | = base
42 | R ARB arms soft (level, *) | = base
43 | R ARB arms firm (level, *) | = base
44 | base (no *) | = base
45 | R ARB dia Disconnected (level, *) | = base
46 | R ARB 0.6875/5 (level, *) | = base
--- B10 twisted rear: LR perch 105.6 (+2.0 mm) ---
47 | twist R, arms 5 / 0.6875 (no *, greyed) | 1349 83.0 62.0 -0.4 | 1327 83.2 61.4 -0.5 | 1617 103.5 59.9 -0.5 | 1643 103.7 59.3 TL | 49.6 |
48 | twist R, arms soft (*) | 1352 82.9 62.1 | 1324 83.3 61.3 | 1614 103.4 60.0 | 1646 103.8 59.2 | 49.5 |
49 | twist R, arms firm (*) | 1348 83.0 62.0 | 1328 83.2 61.4 | 1618 103.5 59.9 | 1641 103.7 59.3 | 49.6 |
50 | twist R, arms 5 (*) | 1349 83.0 62.0 | 1327 83.2 61.4 | 1617 103.5 59.9 | 1642 103.7 59.3 | 49.6 |
51 | twist R, dia Disconnected (*) | 1353 82.9 62.1 | 1323 83.3 61.3 | 1613 103.4 60.1 | 1647 103.8 59.2 | 49.5 |
52 | twist R, dia 0.6875 (*) | 1349 83.0 62.0 | 1327 83.2 61.4 | 1617 103.5 59.9 | 1643 103.7 59.3 | 49.6 |
53 | Windows desktop (end)
Not captured: Part C (camber/toe/pressure/gearing/diff/damper sweeps) -- C via the .sto saves (encrypted) + ibt anchors.
