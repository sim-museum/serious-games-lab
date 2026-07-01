#!/usr/bin/env python3
"""Build-time tool: ingest the personal bridge book library into a committed,
topic-tagged text corpus that the app reads at runtime (stdlib json only).

This is the ONLY component that depends on pymupdf / ebooklib / bs4 — those
libs are installed in the project venv but the running app never imports them.
The app reads the two committed artifacts produced here:

  backend/data/coach/corpus.jsonl     one passage per line:
      {"id","book","topics":[...],"text"}
  backend/data/coach/topic_index.json inverted topic -> [passage_ids] + metadata

Two consumers:
  (a) authoring source for backend/data/coach/note_catalog.json (offline),
  (b) retrieval grounding for the "Ask Claude" hint button (book-grounded).

Run with the venv python:
  ../venv/bin/python tools/ingest_book_library.py \
      --library /home/h/Documents/260619/rumi3_library

De-dupes duplicate editions (same book in pdf+epub or several scans) by
filename word-overlap so the corpus isn't multiply weighted, and skips
scanned PDFs that extract to garbage (too little real text).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ---- Topic lexicon -------------------------------------------------------
# topic -> list of lowercase substrings; a passage gets a topic if any of its
# phrases appear in the (lowercased) text. Deliberately broad — the corpus is
# source material, recall matters more than precision.
TOPIC_LEXICON: dict[str, list[str]] = {
    "notrump_opening": ["1nt opening", "open 1nt", "opening one notrump",
                        "open one notrump", "15-17", "balanced hand"],
    "stayman": ["stayman"],
    "transfer": ["jacoby transfer", "transfer bid", "transfer to", "red-suit transfer"],
    "weak_two": ["weak two", "weak 2", "weak twos", "preempt", "pre-empt",
                 "preemptive"],
    "strong_club": ["precision", "strong club", "strong 1", "strong one club",
                    "16+ ", "forcing club"],
    "two_over_one": ["two over one", "2/1", "two-over-one", "game forcing response"],
    "rkc": ["blackwood", "keycard", "key card", "key-card", "roman key",
            "gerber", "asking for aces", "1430", "ace ask"],
    "negative_double": ["negative double", "takeout double", "take-out double",
                        "responsive double"],
    "overcall": ["overcall", "overcalling", "michaels", "unusual notrump",
                 "unusual 2nt"],
    "opening_lead": ["opening lead", "opening leads", "lead against", "leading against",
                     "choice of lead", "fourth highest", "fourth-best", "fourth best",
                     "top of a sequence", "top of nothing"],
    "finesse": ["finesse", "finessing", "two-way finesse", "ruffing finesse",
                "eight ever", "nine never", "8 ever", "9 never"],
    "holdup": ["hold up", "holdup", "hold-up", "rule of seven", "rule of 7",
               "ducking", "duck the"],
    "drawing_trumps": ["draw trump", "drawing trump", "pull trump", "trump control",
                       "when to draw trump", "leave a trump"],
    "ruff": ["ruff", "ruffing", "cross-ruff", "crossruff", "ruff in dummy",
             "dummy reversal", "trumping"],
    "entries": ["entry", "entries", "communication", "transportation", "overtake",
                "unblock", "unblocking"],
    "establishment": ["establish", "establishing", "set up the suit", "long suit",
                      "promotion", "promote", "develop the suit"],
    "signals": ["signal", "signalling", "signaling", "attitude", "count signal",
                "suit preference", "suit-preference", "high-low", "echo", "discard"],
    "squeeze": ["squeeze", "squeezing", "rectify the count", "menace"],
    "endplay": ["endplay", "end play", "throw-in", "throw in", "elimination",
                "strip and"],
    "safety_play": ["safety play", "safety-play", "guard against", "avoid the loss"],
    "vulnerability": ["vulnerable", "vulnerability", "not vulnerable", "non-vulnerable",
                      "favourable vulnerability", "unfavourable", "red against white"],
    "notrump_play": ["notrump contract", "no-trump contract", "no trump contract",
                     "playing notrump", "count your winners", "count the winners"],
    "responding": ["responding to", "response to", "raise partner", "single raise",
                   "limit raise", "jump shift"],
    "rebid": ["opener's rebid", "rebid", "reverse", "jump rebid"],
    "counting": ["count the hand", "counting the hand", "count out the hand",
                 "count declarer", "assume", "inference"],
}

# Tokens to drop when building the de-dup key (publishers / formats / filler).
_DEDUP_STOP = {
    "the", "and", "with", "for", "how", "1964", "1972", "1979", "1984", "2006",
    "2010", "2011", "2012", "2013", "2017", "2020", "2021", "2022", "2023",
    "2024", "press", "books", "book", "signet", "publishing", "skyhorse",
    "barclay", "baron", "master", "point", "library", "edition", "guide",
    "new", "american", "wiley", "sons", "media", "everything",
}


def _norm_words(name: str) -> set[str]:
    """Significant alpha words (len>=3) from a filename, minus stoplist."""
    stem = re.sub(r"\.[a-z0-9]+$", "", name.lower())
    stem = re.sub(r"\([^)]*\)", " ", stem)              # drop (parentheticals)
    words = re.findall(r"[a-z]{3,}", stem)
    return {w for w in words if w not in _DEDUP_STOP}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _clean_title(name: str) -> str:
    """A tidy display title from a filename: drop extension, parentheticals,
    and a trailing '-Publisher' tail; collapse whitespace."""
    stem = re.sub(r"\.[a-z0-9]+$", "", name, flags=re.I)
    stem = re.sub(r"\([^)]*\)", " ", stem)
    stem = re.sub(r"\s*[-–]\s*[^-–]*(Press|Publishing|Signet|Library|Barclay|"
                  r"Media|Wiley|Skyhorse)[^-–]*$", "", stem, flags=re.I)
    return re.sub(r"\s+", " ", stem).strip()


def _slug(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
    return s[:40] or "book"


# ---- Extraction ----------------------------------------------------------
def _extract_pdf(path: Path) -> str:
    import fitz  # pymupdf — build-time only
    parts = []
    with fitz.open(path) as doc:
        for page in doc:
            parts.append(page.get_text("text"))
    return "\n".join(parts)


def _extract_epub(path: Path) -> str:
    import ebooklib
    from ebooklib import epub
    from bs4 import BeautifulSoup
    book = epub.read_epub(str(path), options={"ignore_ncx": True})
    parts = []
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            soup = BeautifulSoup(item.get_content(), "html.parser")
            parts.append(soup.get_text(" ", strip=True))
    return "\n\n".join(parts)


def _alpha_ratio(text: str) -> float:
    if not text:
        return 0.0
    alpha = sum(1 for c in text if c.isalpha() or c.isspace())
    return alpha / len(text)


# ---- Segmentation + tagging ----------------------------------------------
def _segment(text: str, lo: int = 600, hi: int = 1200) -> list[str]:
    """Paragraph-aware passages roughly in [lo, hi] chars."""
    text = re.sub(r"[ \t]+", " ", text)
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    out, buf = [], ""
    for p in paras:
        if len(buf) + len(p) + 1 <= hi:
            buf = (buf + " " + p).strip()
        else:
            if buf:
                out.append(buf)
            # A single huge paragraph: hard-wrap on sentence-ish boundaries.
            while len(p) > hi:
                cut = p.rfind(". ", lo, hi)
                cut = cut + 1 if cut > 0 else hi
                out.append(p[:cut].strip())
                p = p[cut:].strip()
            buf = p
        if len(buf) >= lo and len(buf) >= hi - 200:
            out.append(buf)
            buf = ""
    if buf:
        out.append(buf)
    return [s for s in out if len(s) >= 120]


def _topics_for(text: str) -> list[str]:
    low = text.lower()
    return [t for t, phrases in TOPIC_LEXICON.items()
            if any(ph in low for ph in phrases)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--library", default="/home/h/Documents/260619/rumi3_library")
    ap.add_argument("--out", default=None,
                    help="output dir (default: <repo>/backend/data/coach)")
    ap.add_argument("--min-chars", type=int, default=4000,
                    help="skip a book whose extracted text is shorter (scanned)")
    args = ap.parse_args()

    lib = Path(args.library)
    if not lib.is_dir():
        print(f"library not found: {lib}", file=sys.stderr)
        return 2
    repo = Path(__file__).resolve().parent.parent
    out_dir = Path(args.out) if args.out else (repo / "backend" / "data" / "coach")
    out_dir.mkdir(parents=True, exist_ok=True)

    files = sorted([p for p in lib.iterdir()
                    if p.suffix.lower() in (".pdf", ".epub")])
    if not files:
        print(f"no .pdf/.epub in {lib}", file=sys.stderr)
        return 2

    # De-dup duplicate editions: union-find on filename word-overlap.
    wsets = {p: _norm_words(p.name) for p in files}
    parent: dict[Path, Path] = {p: p for p in files}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, a in enumerate(files):
        for b in files[i + 1:]:
            if _jaccard(wsets[a], wsets[b]) >= 0.5:
                parent[find(a)] = find(b)
    groups: dict[Path, list[Path]] = {}
    for p in files:
        groups.setdefault(find(p), []).append(p)

    # One representative per group: prefer PDF (page-accurate), else largest.
    reps: list[Path] = []
    for members in groups.values():
        pdfs = [m for m in members if m.suffix.lower() == ".pdf"]
        rep = (min(pdfs, key=lambda m: m.stat().st_size) if pdfs
               else max(members, key=lambda m: m.stat().st_size))
        reps.append(rep)
        if len(members) > 1:
            others = ", ".join(m.name for m in members if m != rep)
            print(f"  dedup: '{rep.name}' (dropped: {others})")
    reps.sort(key=lambda p: p.name)

    corpus_path = out_dir / "corpus.jsonl"
    used_slugs: set[str] = set()
    passage_count = 0
    topic_index: dict[str, list[str]] = {}
    books_meta: list[dict] = []

    with corpus_path.open("w", encoding="utf-8") as cf:
        for path in reps:
            title = _clean_title(path.name)
            slug = _slug(title)
            n = slug
            i = 2
            while n in used_slugs:
                n = f"{slug}{i}"
                i += 1
            slug = n
            used_slugs.add(slug)

            try:
                text = (_extract_pdf(path) if path.suffix.lower() == ".pdf"
                        else _extract_epub(path))
            except Exception as e:
                print(f"  SKIP {path.name}: extract failed: {e!r}",
                      file=sys.stderr)
                continue

            if len(text) < args.min_chars or _alpha_ratio(text) < 0.6:
                print(f"  SKIP {path.name}: {len(text)} chars, "
                      f"alpha={_alpha_ratio(text):.2f} (scanned/garbage)")
                continue

            passages = _segment(text)
            kept = 0
            for j, body in enumerate(passages):
                topics = _topics_for(body)
                if not topics:
                    continue                       # only keep tagged passages
                pid = f"{slug}_{j:04d}"
                rec = {"id": pid, "book": title, "topics": topics, "text": body}
                cf.write(json.dumps(rec, ensure_ascii=False) + "\n")
                for t in topics:
                    topic_index.setdefault(t, []).append(pid)
                kept += 1
            passage_count += kept
            books_meta.append({"title": title, "source": path.name,
                               "chars": len(text), "passages": kept})
            print(f"  OK   {title}: {len(text)} chars -> {kept} tagged passages")

    index = {
        "version": 1,
        "topics": topic_index,
        "books": [b["title"] for b in books_meta],
        "book_meta": books_meta,
        "source_count": len(books_meta),
        "passage_count": passage_count,
        "topic_lexicon": sorted(TOPIC_LEXICON.keys()),
    }
    (out_dir / "topic_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\nWrote {passage_count} passages from {len(books_meta)} books")
    print(f"  {corpus_path}")
    print(f"  {out_dir / 'topic_index.json'}")
    print(f"  topics: {', '.join(sorted(topic_index))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
