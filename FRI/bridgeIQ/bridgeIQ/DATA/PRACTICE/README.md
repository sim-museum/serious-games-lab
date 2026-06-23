# Practice deal files (from the rumi3_library books)

Deal files built from worked example hands in the bridge books under
`/home/h/Documents/260619/rumi3_library`, for loading into biq
(**File → Open Deal File…**, `.bdl` format).

Each deal carries the book's explanation of the correct play in the BDL
`Commentary` field, which biq displays in its deal/replay view. Hands use
biq's BDL per-seat notation (`N: S AK3 H AQ5 D Q873 C A62`, ten = `T`).

## Validation

Every deal is gated through biq's own `backend.bdl_reader.BDLReader`:
exactly four hands, 13 cards each, 52 unique cards. Files are only written
if all deals pass.

## Faithful vs. constructed

- **Faithful** — all four hands are the book's own cards. Used wherever the
  book prints the complete four-hand layout (or gives enough to recover the
  fourth hand as the complement of the other three).
- **Constructed defenders** — many teaching hands show only declarer +
  dummy (the defenders' cards are hidden by design). Where noted, the
  opponents' cards are constructed to be consistent with the book's stated
  solution so the deal is playable; this is flagged in that deal's
  Commentary. (Per the user's "hybrid" choice.)

## Files

| File | Book | Deals | Notes |
|------|------|-------|-------|
| `taste_of_bridge.bdl` | A Taste of Bridge — Jeff Bayone (Master Point Press, 2017) | 6 | All faithful (Ch 5 ×2, Ch 7 ×1, Ch 9 ×3) — declarer-play problems with the correct line explained. Source: digital-text PDF. |
| `bridge_for_dummies.bdl` | Bridge for Dummies — Eddie Kantar (Wiley, 3rd ed.) | 12 | Faithful. Hands transcribed by VISION from the book's diagram images; explanations from the EPUB prose. (A 13th, Fig 17-13, was dropped — the book's diagram misprints the diamond suit.) Declarer-play + defensive-signalling lessons. |
| `bridge_basics.bdl` | Bridge Basics: A Beginner's Guide — Ron Klinger | 5 | Faithful. First 5 of the book's 36 numbered play hands; four single-hand grid pages (one per seat) assembled into deals and vision-transcribed. Commentary = the book's Lead / Correct play / Wrong play notes. 31 more available. |

**Total: 23 validated deals across 3 teaching books.** Every deal verified through
biq's `BDLReader`: four hands, 13 cards each, 52 unique cards.

## Extraction pipelines

- **Digital-text PDF** (Bayone): hands parsed from PDF text (suits positional,
  ♠♥♦♣ top-to-bottom); explanations from prose; cross-checked vs the book's
  stated shapes.
- **Image/EPUB** (Kantar): OCR (tesseract) *locates* the four-hand diagram
  images; the cards are then transcribed by reading the image directly
  (OCR rank reads are too error-prone — `O↔Q`, `I↔9`, `10↔O`); explanations
  from the clean EPUB prose. Same pipeline applies to Bridge Basics (Klinger)
  and The Everything Bridge Book (Manley), and (via page-render OCR) the
  scanned Joy of Bridge (Grant/Rodwell).

## Precision books — no deal files

- **PrecisionBridge.pdf** (C.A. Serino): a bidding-SYSTEM reference (opening-bid
  and relay-sequence tables) — contains **no example deals**, so it yields no
  deal files. (biq already ships Precision systems.)
- **The Hog Takes to Precision** (Mollo): humorous bridge FICTION; the EPUB is
  image-based (hands as images) and deals are embedded in narrative, so it
  produces no clean teaching practice deals.

## Skipped and why

- **No OCR text** without rendering: handled via the image pipeline above now
  that tesseract is installed.
- **Bidding-only / narrative** (no "correct play" deals): Better Bidding with
  Bergen Vol I, The Hog Takes to Precision (Mollo).

### Remaining / not yet built
- **Bridge Basics (Klinger)** — 31 more numbered play hands (Hands 6–36) available via the same grid-assembly pipeline.
- **The Joy of Bridge (Grant/Rodwell)** — scanned PDF; prose OCRs cleanly, but its full four-hand PLAY deals are sparse and scattered (most example hands are single-hand bidding lessons), and deal pages aren't distinguishable from auction tables by OCR. Needs a dedicated page-by-page visual scan to locate the play deals — not completed in this pass.
- **The Everything Bridge Book (Manley)** — EPUB images, same pipeline as Kantar/Klinger.
- **5 Weeks to Winning Bridge (Sheinwold)** — large digital-text PDF.
