"""Explicit local CSV audit; original data is never copied or overwritten."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from niftyverse.membership_audit import audit_membership, notice_conflicts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
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


if __name__ == "__main__":
    main()
