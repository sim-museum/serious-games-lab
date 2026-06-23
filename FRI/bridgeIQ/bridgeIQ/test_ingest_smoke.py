#!/usr/bin/env python3
"""Light smoke test for the committed book corpus/index.

Does NOT run the ingestion tool (which needs the build-time libs pymupdf /
ebooklib); it only checks that the committed artifacts the app reads at
runtime parse and look sane. Skips cleanly if they haven't been built yet.
"""
import json
from pathlib import Path

_DIR = Path(__file__).resolve().parent / "backend" / "data" / "coach"


def test_topic_index_parses_and_is_populated():
    idx_path = _DIR / "topic_index.json"
    if not idx_path.exists():
        print("skip: topic_index.json not built")
        return
    idx = json.loads(idx_path.read_text(encoding="utf-8"))
    assert idx.get("topics"), "no topics in index"
    assert idx.get("passage_count", 0) > 0
    assert idx.get("source_count", 0) > 0
    # Every topic maps to a non-empty id list.
    assert all(ids for ids in idx["topics"].values())


def test_corpus_first_records_well_formed():
    corpus = _DIR / "corpus.jsonl"
    if not corpus.exists():
        print("skip: corpus.jsonl not built")
        return
    with corpus.open(encoding="utf-8") as f:
        for _ in range(5):
            line = f.readline()
            if not line:
                break
            rec = json.loads(line)
            assert rec["id"] and rec["text"] and isinstance(rec["topics"], list)


def test_book_passages_retrieval():
    if not (_DIR / "topic_index.json").exists():
        print("skip: index not built")
        return
    from ui.coach_notes import book_passages
    ps = book_passages(["holdup", "finesse"], limit=2)
    assert isinstance(ps, list) and len(ps) <= 2
    for p in ps:
        assert p["text"]


if __name__ == "__main__":
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    for _n, _fn in sorted(globals().items()):
        if _n.startswith("test_") and callable(_fn):
            _fn()
            print(f"ok  {_n}")
    print("ALL INGEST-SMOKE TESTS PASSED")
