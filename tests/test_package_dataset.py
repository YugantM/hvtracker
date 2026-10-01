"""scripts/package_dataset.py builds a correct Zenodo bundle (plan 3.3)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

import fetch_and_build as fab  # noqa: E402
import package_dataset as pkg  # noqa: E402

DOC = {"count": 2, "generated_at": "2026-09-30T23:40:00Z", "methodology_version": "v4.3", "agents": [{}, {}]}


def test_data_dictionary_covers_exactly_the_exported_fields():
    assert list(pkg.FIELDS) == fab.EXPORT_CSV_FIELDS


def test_readme_and_metadata():
    text = pkg.readme("2026-Q3", DOC)
    assert "HVTrust quarterly export 2026-Q3" in text and "CC BY 4.0" in text
    assert all(f"`{k}`" in text for k in fab.EXPORT_CSV_FIELDS)
    meta = pkg.zenodo("2026-Q3", DOC)
    assert meta["upload_type"] == "dataset" and meta["license"] == "cc-by-4.0"
    assert meta["publication_date"] == "2026-09-30" and meta["version"] == "2026-Q3"
    assert meta["creators"] == [{"name": "HVTracker"}]


def test_refuses_a_quarter_that_has_not_ended():
    with pytest.raises(SystemExit, match="hasn't ended"):
        pkg.main("2999-Q1")
    with pytest.raises(SystemExit, match="usage"):
        pkg.main("2026-3")


def _serve(monkeypatch, records):
    import csv
    import gzip
    import io
    import json
    doc = dict(DOC, count=len(records), agents=records)
    buf = io.StringIO()
    fields = [f for f in fab.EXPORT_CSV_FIELDS if f in records[0] or f != "listing_class"]
    w = csv.DictWriter(buf, fieldnames=fields)
    w.writeheader()
    w.writerows({k: r.get(k, "") for k in fields} for r in records)
    files = {"json.gz": gzip.compress(json.dumps(doc).encode()), "csv": buf.getvalue().encode()}
    monkeypatch.setattr(pkg, "fetch", lambda url: files["csv" if url.endswith(".csv") else "json.gz"])


def _read(tmp_path):
    import csv
    import gzip
    import json
    out = tmp_path / "dist" / "hvtrust-2026-Q2"
    with open(out / "hvtrust-2026-Q2.csv", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    doc = json.loads(gzip.decompress((out / "hvtrust-2026-Q2.json.gz").read_bytes()))
    meta = json.loads((out / ".zenodo.json").read_text())
    return out, rows, doc, meta, (out / "README.md").read_text()


# 2026-Q3 shape: no listing_class, agent and skill ranks both start at 1.
Q3_SHAPE = [{"slug": "a1", "rank": 1, "category": "Agent Frameworks"},
            {"slug": "s1", "rank": 1, "category": "Agent Skills"},
            {"slug": "a2", "rank": 2, "category": "MCP Servers"},
            {"slug": "s2", "rank": 2, "category": "Agent Skills"}]


def test_packages_a_frozen_quarter(tmp_path, monkeypatch):
    _serve(monkeypatch, [dict(r, listing_class="agent") for r in Q3_SHAPE[::2]])
    pkg.main("2026-Q2", out_root=str(tmp_path))
    out, rows, doc, meta, readme = _read(tmp_path)
    assert {p.name for p in out.iterdir()} == {"hvtrust-2026-Q2.json.gz", "hvtrust-2026-Q2.csv", "README.md", ".zenodo.json"}
    assert (tmp_path / "dist" / "hvtrust-2026-Q2.zip").is_file()
    # An export that already carries its board is packaged as-is.
    assert meta["related_identifiers"][1]["relation"] == "isIdenticalTo"
    assert "Packaging note" not in readme


def test_q3_export_gets_its_board_backfilled(tmp_path, monkeypatch):
    _serve(monkeypatch, [dict(r) for r in Q3_SHAPE])
    pkg.main("2026-Q2", out_root=str(tmp_path))
    _, rows, doc, meta, readme = _read(tmp_path)
    expected = [("agent", "1", "a1"), ("agent", "2", "a2"), ("skill", "1", "s1"), ("skill", "2", "s2")]
    assert [(r["listing_class"], r["rank"], r["slug"]) for r in rows] == expected
    assert list(rows[0]) == list(pkg.FIELDS)
    assert [(a["listing_class"], a["slug"]) for a in doc["agents"]] == [(c, s) for c, _, s in expected]
    assert meta["related_identifiers"][1]["relation"] == "isDerivedFrom"
    assert "Packaging note" in readme


def test_refuses_a_board_it_cannot_derive(tmp_path, monkeypatch):
    broken = [dict(r) for r in Q3_SHAPE]
    broken[1]["category"] = "Coding Agents"  # a skill outside "Agent Skills": agent ranks 1,1,2
    _serve(monkeypatch, broken)
    with pytest.raises(SystemExit, match="can't be derived"):
        pkg.main("2026-Q2", out_root=str(tmp_path))
