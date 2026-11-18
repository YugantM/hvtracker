"""scripts/a2a_census_publish.py: one study run -> the census post's data files."""
import csv
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import a2a_census_publish as pub  # noqa: E402


def _card(**kw):
    base = {"card_url": "https://a.example/.well-known/agent-card.json", "protocol_version": "1.0",
            "v1_valid": True, "v1_problems": [], "interfaces_https": True, "interfaces_same_site": True,
            "auth_types": [], "auth_required": False, "provider_declared": True, "skills": 2,
            "signed": False, "algs": [], "key_source": None, "verified": False, "verify_note": None}
    base.update(kw)
    return base


def _run(rows, **all_metrics):
    return {"study": "State of public A2A agents", "generated_at": "2026-11-01T00:00:00Z",
            "inputs": {}, "metrics": {"all": all_metrics}, "rows": rows}


def test_detail_counts_signatures_and_manifests():
    rows = [
        {"host": "a.example", "sources": ["mcp"], "card": _card(signed=True, algs=["EdDSA"], key_source="jku, same site", verified=True)},
        {"host": "b.example", "sources": ["mcp"], "card": _card(signed=True, algs=["ES256"], key_source="kid only")},
        {"host": "c.example", "sources": ["roster"], "card": None, "legacy_card": _card(skills=0, v1_valid=False, v1_problems=["supportedInterfaces"])},
        {"host": "d.example", "sources": ["mcp"], "card": None,
         "catalog": {"lists_a2a": True, "trust_manifests": 3, "signed_trust_manifests": 1}},
    ]
    metrics, out = pub.build(_run(rows, cards=3), _run([], cards=1))
    d = metrics["detail"]
    assert d["unverifiable_no_key_location"] == 1
    assert d["did_not_verify"] == 0
    assert d["signature_algorithms"] == {"EdDSA": 1, "ES256": 1}
    assert d["v1_problems"] == {"supportedInterfaces": 1}
    assert d["zero_skills"] == 1
    assert (d["trust_manifests_total"], d["signed_trust_manifests_total"], d["hosts_with_signed_trust_manifests"]) == (3, 1, 1)
    assert metrics["change"]["cards"] == {"from": 1, "to": 3}
    by_host = {r["host"]: r for r in out}
    assert by_host["c.example"]["legacy_path_only"] is True
    assert by_host["b.example"]["signature_verified"] is False
    assert by_host["a.example"]["signature_verified"] is True
    assert by_host["d.example"]["ai_catalog"] is True and by_host["d.example"]["card_url"] == ""


def test_main_writes_both_files(tmp_path):
    study = tmp_path / "run.json"
    study.write_text(json.dumps(_run([{"host": "a.example", "sources": ["mcp"], "card": _card()}], cards=1)))
    out = tmp_path / "post"
    sys.argv = ["a2a_census_publish.py", str(study), "--out", str(out)]
    assert pub.main() == 0
    assert json.loads((out / "metrics.json").read_text())["license"] == "CC BY 4.0"
    with open(out / "hosts.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    assert [r["host"] for r in rows] == ["a.example"]
    assert set(rows[0]) == set(pub.CSV_FIELDS)
