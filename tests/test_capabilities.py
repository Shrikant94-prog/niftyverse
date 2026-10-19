"""Phase 02's frozen scientific claims must stay bound to named observations."""

import hashlib
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "docs" / "capabilities"


def test_probe_evidence_matches_exact_plans_and_never_claims_completeness() -> None:
    evidence = json.loads((ROOT / "observations.json").read_text())
    assert evidence["version"] == 1
    assert evidence["complete"] is False
    assert len(evidence["sets"]) == 5
    for group in evidence["sets"]:
        plan_text = (ROOT / "probes" / group["plan"]).read_text(encoding="utf-8")
        assert hashlib.sha256(plan_text.encode()).hexdigest() == group["plan_sha256"]
        plan = json.loads(plan_text)
        assert [r["name"] for r in group["results"]] == [p["name"] for p in plan["probes"]]
        assert group["requests"] == sum(r["attempts"] for r in group["results"])
        assert group["requests"] <= plan["budget"]["max_requests"]
        for probe, result in zip(plan["probes"], group["results"], strict=True):
            assert 0 < probe.get("window_days", 1) <= 31
            assert result["attempts"] in {0, 1}
            assert datetime.fromisoformat(result["observed_at"]).utcoffset() is not None
            assert result["complete"] is False
            if result["outcome"] == "observed_unverified":
                assert result["status"] == 200
                assert len(result["sha256"]) == 64
                assert 0 < result["bytes"] <= group["budget"]["max_bytes"]
            else:
                assert "sha256" not in result
    assert sum(g["requests"] for g in evidence["sets"]) == 27


def test_minimum_manifest_keeps_concrete_targets_and_missing_families() -> None:
    manifest = json.loads((ROOT / "manifest-v1.json").read_text())
    assert manifest["manifest_version"] == 1
    concepts = manifest["financial_targets"]["concepts"]
    assert {c["statement"] for c in concepts} >= {
        "profit_loss",
        "balance_sheet",
        "cash_flow",
        "segments",
    }
    assert all(c["period"] in {"instant", "duration"} and c["unit"] for c in concepts)
    assert {c["status"] for c in concepts} <= {"experimental", "blocked"}
    assert {f["id"] for f in manifest["filing_families"] if f["status"] == "blocked"} >= {
        "genuine_inline_xbrl",
        "bank_financial_xbrl",
    }
    older = next(f for f in manifest["filing_families"] if f["id"] == "older_financial_xbrl")
    assert older["status"] == "experimental" and older["samples"] == ["phase03:older-indas"]
    assert {s["symbol"] for s in manifest["global_targets"]["series"]} == {"^GSPC", "^IXIC"}
    assert manifest["global_targets"]["capture_kind"] == "sdk_result"
    assert manifest["etf_targets"]["reference_sessions"] == ["2016-09-01", "2026-10-16"]
    assert "past mandate" in manifest["etf_targets"]["unknown"]
    assert "exact ISIN" in manifest["discovery_targets"]["match_types"]
