"""Explicit local CSV audit; original data is never copied or overwritten."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from niftyverse.membership_audit import audit_membership, notice_conflicts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--require-original", action="store_true",
                        help="Fail unless every inherited exact-input audit expectation reconciles")
    args = parser.parse_args()
    before = args.input.read_bytes()
    report = audit_membership(
        args.input,
        source_statement="owner supplied; reported niftyhistory.in; export provenance unverified",
        imported_at=datetime.now(UTC),
    )
    result = {
        "sha256": report.sha256,
        "bytes": len(before),
        "original_hash_matches": report.original_hash_matches,
        "rows": report.row_count,
        "index_types": sorted({r.index_type for r in report.rows}),
        "first_date": min((r.effective_date.isoformat() for r in report.rows), default=None),
        "last_date": max((r.effective_date.isoformat() for r in report.rows), default=None),
        "ascending_unique_dates": not report.count("date_order"),
        "snapshot_sizes": sorted({len(set(r.symbols)) for r in report.rows}),
        "distinct_strings": report.distinct_strings,
        "failing_transitions": report.failing_transitions,
        "duplicate_event_rows": report.duplicate_event_rows,
        "weekend_rows": report.weekend_rows,
        "notice_conflicts": [
            {"line": i.line, "code": i.code, "detail": i.detail} for i in notice_conflicts(report)
        ],
        "unchanged": args.input.read_bytes() == before,
        "structurally_valid": report.structurally_valid,
        "imported_at": report.imported_at.isoformat(),
    }
    print(json.dumps(result, indent=2))
    if args.require_original:
        expected = {
            "bytes": 302057, "original_hash_matches": True, "rows": 72,
            "index_types": ["Nifty500"], "first_date": "2010-06-04", "last_date": "2026-03-31",
            "ascending_unique_dates": True, "snapshot_sizes": [500], "distinct_strings": 756,
            "failing_transitions": 50, "duplicate_event_rows": 11, "weekend_rows": 5, "unchanged": True,
        }
        mismatches = [key for key, value in expected.items() if result[key] != value]
        if len(notice_conflicts(report)) != 7:
            mismatches.append("notice_conflicts")
        if mismatches:
            parser.exit(1, "Original-input audit gate failed: " + ", ".join(mismatches) + "\n")


if __name__ == "__main__":
    main()
