# Session status — 2026-06-23 (explain-action feature, UI fixes, practice decks)

## 1. "Explain biq's actions" feature (default OFF)

New optional teaching feature: with the preference on, clicking a bid in the
auction or a card biq has played pops up a window explaining *why* — how a bid
fits the chosen bidding system and why it was chosen, or which card-play
technique applies.

- **Preference** `explain_actions_enabled` (default `False`) — `backend/config.py`
  (`PreferencesConfig` + load/save), checkbox in `ui/dialogs/preferences.py`.
- **Backend** `backend/explain.py` (new) — pure presentation layer.
  `explain_bid()` combines the system-grounded meaning (`bid_descriptions.describe_bid`)
  with biq's own captured reason (`Bid.explanation`); `explain_card()` describes
  the play from **public information only** (never reads concealed cards — honours
  the no-peek rule).
- **Dialog** `ui/dialogs/explanation_dialog.py` (new), exported from `ui/dialogs/__init__.py`.
- **Wiring** `ui/table_view.py` (bid cells emit `(seat,bid)`; played cards emit
  `(seat,card)` via a new always-firing `card_pressed` signal) and
  `ui/main_window.py` (`_on_explain_bid` / `_on_explain_card`, gated by the pref,
  biq-seat only for cards).
- **Tests** `test_explain.py` (8 tests, passing). Existing suites still green.

## 2. UI fixes

- **Instrumented view** (`ui/teaching_view.py`): a suit length of exactly 0 now
  renders **"void"** everywhere (previously an *inferred* 0 showed as "0" while a
  shown-out void showed "void"). Single source: `suit_length_text`.
- **"Claude is off" dialog** (`ui/main_window.py`): ragged/clipped text fixed by
  forcing the message-box text column width with a grid spacer (the shared
  stylesheet pins QLabel min-width to 200px, which clipped the line).
- **Closed-room toolbar button** (`ui/main_window.py`): added a persistent
  **Closed room** button to the play toolbar (was only on the opening screen).
  Context-aware: views the open-vs-closed comparison when a closed-room match is
  running, else starts one for the current deal.
- **Quick Claude critique timeout** (`ui/main_window.py`, `ui/dialogs/compare_replay.py`):
  the "Quick verdict (fast)" critique now runs Opus **without extended thinking**
  (the latency driver) and with a longer timeout, so it returns instead of timing
  out at 180s. Deeper scopes keep extended thinking on.

## 3. Practice deal files from the rumi3_library books

New `bridgeIQ/DATA/PRACTICE/` — worked example hands from teaching books, as BDL
deal files biq can load (**File → Open Deal File…**), each carrying the book's
explanation of the correct play in the `Commentary` field.

| File | Book | Deals |
|------|------|-------|
| `taste_of_bridge.bdl` | A Taste of Bridge (Bayone) | 6 |
| `bridge_for_dummies.bdl` | Bridge for Dummies (Kantar) | 12 |
| `bridge_basics.bdl` | Bridge Basics (Klinger) | 5 |

**23 deals total**, every one verified through biq's own `BDLReader`
(four hands, 13 cards each, 52 unique cards). All faithful — the book's own cards.
See `DATA/PRACTICE/README.md` for the full method and sourcing.

### Extraction method
- Digital-text PDF (Bayone): hands from PDF text (suits positional ♠♥♦♣;
  cross-checked vs the book's stated shapes).
- Image/EPUB (Kantar, Klinger): OCR (**tesseract**, newly installed) *locates*
  the diagram images; cards are transcribed by **vision** (OCR rank reads are too
  error-prone — `O↔Q`, `I↔9`, `10↔O`); explanations from the clean EPUB prose.
- The 52-card validator caught several single-card vision slips; two were fixed,
  and it exposed a genuine **diagram misprint** in Bridge for Dummies Fig 17-13
  (dropped that deal) and a lead/holding inconsistency in Klinger Hand 5 (dropped).

### Not yet built / blockers
- **Klinger** — 31 more numbered play hands (6–36) via the same grid-assembly pipeline.
- **The Joy of Bridge** (Grant/Rodwell, scanned) — prose OCRs cleanly, but its full
  four-hand PLAY deals are sparse/scattered and not OCR-distinguishable from auction
  tables; needs a dedicated visual page-scan.
- **The Everything Bridge Book** (Manley, EPUB images) and **5 Weeks to Winning
  Bridge** (Sheinwold, text PDF) remain as further candidates.
- **Precision books yield no deal files**: PrecisionBridge.pdf (Serino) is a
  system reference (no example deals); Mollo's *Hog Takes to Precision* is
  image-based narrative fiction.

### Tooling installed
`tesseract-ocr` (system) + `pytesseract` (venv) for the image/scanned books.
