# E82 gold reference frames — the external ("nintendo") view

Extracted 2026-08-29 from `gold standard/julia racer/watkinsGlenn/260802_watkinsGlen_nintendo.mp4`
(1920x1080, 118.1 s, 7051 frames) at t = 20/45/70/95 s.

## Why these exist

E75 spent **16 sprints** on "no axles in the external view" and the PO still reports it. E82 records
why: *"every S15/S16 number was fitted to the car's own hub line and wheel face, not to a gold
frame. That is why 'the arithmetic works' and 'the PO still sees no axles' can both be true."*

So the missing input was never a measurement of OUR car — it was a matched-view frame of the REAL
one. These are that input.

## How to use them, and how NOT to

* Match the VIEW first (camera distance/height/angle), then the landmark. A suspension offset
  measured against a differently-framed shot is another number fitted to nothing.
* The constant (`JM_SUSP_INBOARD`, shipped OFF at 0.30 m) should FOLLOW from the gold comparison,
  not be validated by it. It was derived from our own geometry; if the gold says something else,
  the gold wins.
* ⚠️ Four frames from ONE track. The E82 entry lists gold nintendo videos for all five tracks
  (`monza`, `zandervoort`, `nurburgring`, `watkinsGlenn`, `spa`) — a fix that matches one track and
  is never checked against the others repeats E75's error at a larger scale.
