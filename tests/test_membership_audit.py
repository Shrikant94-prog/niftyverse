"""Owned literal snapshots; no source corpus or inherited count simulation."""

import csv
import hashlib
import io
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from niftyverse.core import ValidationError
from niftyverse.membership_audit import audit_membership, notice_conflicts

IMPORTED = datetime(2026, 10, 20, tzinfo=UTC)


def write_input(path: Path, rows: list[list[str]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(["effective_date", "index_type", "inclusions", "exclusions", "symbols"])
    writer.writerows(rows)
    raw = stream.getvalue().encode()
    path.write_bytes(raw)
    return raw


def test_literal_audit_and_no_mutation(tmp_path: Path) -> None:
    path = tmp_path / "owned.csv"
    raw = write_input(
        path,
        [
            ["2025-01-03", "Nifty500", "[]", "[]", json.dumps(["A", "M& M"])],
            ["2025-01-04", "Nifty500", '["B", "B"]', '["A"]', '["B", "M&M"]'],
        ],
    )
    report = audit_membership(path, source_statement="owned", imported_at=IMPORTED)
    assert report.sha256 == hashlib.sha256(raw).hexdigest()
    assert report.row_count == 2 and report.distinct_strings == 4
    assert report.failing_transitions == 1 and report.duplicate_event_rows == 1
    assert report.weekend_rows == 1 and not report.original_hash_matches
    assert {i.code for i in report.issues} >= {
        "hash_mismatch",
        "duplicate_event_token",
        "transition_mismatch",
        "weekend_flag",
        "identity_unresolved",
    }
    assert report.rows[0].symbols == ("A", "M& M")
    assert path.read_bytes() == raw
    assert "M& M" in report.review_csv()
    assert "hash_mismatch" in report.review_markdown()


@pytest.mark.parametrize("bad", ['["A", 4]', '["A",', '["A", ""]', "A,,B"])
def test_malformed_tokens_actionable_unchanged(tmp_path: Path, bad: str) -> None:
    path = tmp_path / "invalid.csv"
    raw = write_input(path, [["2025-01-01", "Nifty500", bad, "[]", '["A"]']])
    report = audit_membership(path, source_statement="owned", imported_at=IMPORTED)
    assert any(i.code == "malformed_tokens" and i.line == 2 for i in report.issues)
    assert not report.structurally_valid
    assert path.read_bytes() == raw


def test_structure_date_overlap_and_hash_report(tmp_path: Path) -> None:
    path = tmp_path / "invalid.csv"
    raw = write_input(
        path,
        [
            ["2025-01-03", "Other", '["A"]', '["A"]', '["A", "A"]'],
            ["2025-01-03", "Nifty500", "[]", "[]", '["A"]'],
            ["wrong-date", "Nifty500", "[]", "[]", '["A"]'],
        ],
    )
    report = audit_membership(path, source_statement="owned", imported_at=IMPORTED)
    assert {i.code for i in report.issues} >= {
        "index_type",
        "duplicate_snapshot_token",
        "event_overlap",
        "date_order",
        "invalid_date",
    }
    assert path.read_bytes() == raw


def test_bad_header_is_reported(tmp_path: Path) -> None:
    path = tmp_path / "header.csv"
    path.write_bytes(b"not,the,header\n")
    report = audit_membership(path, source_statement="owned", imported_at=IMPORTED)
    assert [i.code for i in report.issues] == ["hash_mismatch", "header_mismatch"]


def test_source_comma_encoding_and_notice_conflicts(tmp_path: Path) -> None:
    path = tmp_path / "owned.csv"
    raw = write_input(
        path,
        [
            ["2025-03-31", "Nifty500", "AFCONS,SWIGGY,NTPC", "WSI,BALAMINES,DELTACORP", "A,M& M"],
            [
                "2025-09-30",
                "Nifty500",
                "FIRSTCRY,UNIECOM,ACMESOLAR",
                "LUXIND,HERITGFOOD,PCJEWELLER",
                "A,B",
            ],
            [
                "2026-03-31",
                "Nifty500",
                "BLUEJET,ANTHEM,ACUTAAS",
                "METROPOLIS,APLLTD,PRAJIND",
                "A,C",
            ],
        ],
    )
    report = audit_membership(path, source_statement="owned", imported_at=IMPORTED)
    conflicts = notice_conflicts(report)
    assert [i.code for i in conflicts].count("notice_effective_date") == 2
    assert [i.code for i in conflicts].count("notice_event_count") == 3
    assert any(i.code == "notice_identifier" for i in conflicts)
    assert any(i.code == "temporary_component_missing" for i in conflicts)
    assert report.rows[0].symbols == ("A", "M& M")
    assert path.read_bytes() == raw


def test_byte_limit_and_invalid_utf8_never_modify_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import niftyverse.membership_audit as audit_module

    path = tmp_path / "oversize.csv"
    path.write_bytes(b"12345")
    monkeypatch.setattr(audit_module, "MAX_BYTES", 4)
    with pytest.raises(ValidationError, match="byte limit"):
        audit_membership(path, source_statement="owned", imported_at=IMPORTED)
    assert path.read_bytes() == b"12345"
    path.write_bytes(b"\xff")
    report = audit_membership(path, source_statement="owned", imported_at=IMPORTED)
    assert any(i.code == "csv_error" for i in report.issues)
    assert not report.structurally_valid and path.read_bytes() == b"\xff"
