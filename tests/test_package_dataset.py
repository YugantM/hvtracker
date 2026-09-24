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


def test_packages_a_frozen_quarter(tmp_path, monkeypatch):
    import gzip
    import json
    doc = dict(DOC, agents=[{"slug": "a"}, {"slug": "b"}])
    csv_text = ",".join(fab.EXPORT_CSV_FIELDS) + "\n" + "\n".join("," * (len(fab.EXPORT_CSV_FIELDS) - 1) for _ in range(2)) + "\n"
    files = {"json.gz": gzip.compress(json.dumps(doc).encode()), "csv": csv_text.encode()}
    monkeypatch.setattr(pkg, "fetch", lambda url: files[url.rsplit(".", 2)[-1] if url.endswith(".csv") else "json.gz"])
    pkg.main("2026-Q2", out_root=str(tmp_path))
    out = tmp_path / "dist" / "hvtrust-2026-Q2"
    assert {p.name for p in out.iterdir()} == {"hvtrust-2026-Q2.json.gz", "hvtrust-2026-Q2.csv", "README.md", ".zenodo.json"}
    assert (tmp_path / "dist" / "hvtrust-2026-Q2.zip").is_file()
