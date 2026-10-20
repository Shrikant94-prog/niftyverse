"""Read-only literal membership audit. No identity inference or acquisition."""

import csv
import hashlib
import io
import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from niftyverse.core import ValidationError
from niftyverse.temporal import text, utc

ORIGINAL_SHA256 = "f3b4ce4dc430b6e88a302096551e576621fb6bdd45c3a1344a5204bd1957a091"
HEADER = ("effective_date", "index_type", "inclusions", "exclusions", "symbols")
MAX_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class Issue:
    line: int | None
    code: str
    detail: str


@dataclass(frozen=True)
class MembershipRow:
    line: int
    effective_date: date
    index_type: str
    inclusions: tuple[str, ...]
    exclusions: tuple[str, ...]
    symbols: tuple[str, ...]


@dataclass(frozen=True)
class AuditReport:
    sha256: str
    source_statement: str
    imported_at: datetime
    row_count: int
    rows: tuple[MembershipRow, ...]
    issues: tuple[Issue, ...]

    @property
    def original_hash_matches(self) -> bool:
        return self.sha256 == ORIGINAL_SHA256

    @property
    def distinct_strings(self) -> int:
        return len({s for row in self.rows for s in row.symbols})

    def count(self, code: str) -> int:
        return len({i.line for i in self.issues if i.code == code})

    @property
    def failing_transitions(self) -> int:
        return self.count("transition_mismatch")

    @property
    def duplicate_event_rows(self) -> int:
        return self.count("duplicate_event_token")

    @property
    def weekend_rows(self) -> int:
        return self.count("weekend_flag")

    @property
    def structurally_valid(self) -> bool:
        invalid = {
            "header_mismatch",
            "csv_error",
            "field_count",
            "invalid_date",
            "date_order",
            "index_type",
            "malformed_tokens",
            "duplicate_snapshot_token",
            "event_overlap",
        }
        return not any(i.code in invalid for i in self.issues)

    def review_csv(self) -> str:
        stream = io.StringIO(newline="")
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["input_sha256", "line", "code", "detail"])
        writer.writerows((self.sha256, i.line, i.code, i.detail) for i in self.issues)
        return stream.getvalue()

    def review_markdown(self) -> str:
        # Code-fenced CSV preserves arbitrary literal tokens without table escaping.
        return f"Input SHA-256: {self.sha256}\n\n```csv\n{self.review_csv()}```\n"


def _tokens(value: str) -> tuple[str, ...]:
    if not value.strip():
        return ()
    if value.lstrip().startswith("["):
        parsed = json.loads(value)
        if not isinstance(parsed, list) or any(not isinstance(s, str) for s in parsed):
            raise ValueError("expected string array")
        parts = parsed
    else:
        if any(c in value for c in '[]"\n\r'):
            raise ValueError("malformed comma-separated tokens")
        parts = value.split(",")
    if any(not s.strip() for s in parts):
        raise ValueError("empty token")
    return tuple(s.strip() for s in parts)


def audit_membership(path: Path, *, source_statement: str, imported_at: datetime) -> AuditReport:
    text(source_statement)
    utc(imported_at)
    with path.open("rb") as handle:
        raw = handle.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValidationError("membership input exceeds byte limit")
    sha256 = hashlib.sha256(raw).hexdigest()
    issues = []
    if sha256 != ORIGINAL_SHA256:
        issues.append(Issue(None, "hash_mismatch", f"expected {ORIGINAL_SHA256}; got {sha256}"))
    rows = []
    count = 0
    previous = None
    try:
        reader = csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True)
        if tuple(next(reader, [])) != HEADER:
            issues.append(Issue(1, "header_mismatch", "expected " + ",".join(HEADER)))
        else:
            for fields in reader:
                count += 1
                line = reader.line_num
                if count > 10_000:
                    raise ValidationError("membership input exceeds row limit")
                if len(fields) != 5:
                    issues.append(Issue(line, "field_count", "expected five CSV fields"))
                    previous = None
                    continue
                try:
                    effective = date.fromisoformat(fields[0])
                    if effective.isoformat() != fields[0]:
                        raise ValueError("expected ISO date")
                except ValueError:
                    issues.append(Issue(line, "invalid_date", fields[0]))
                    previous = None
                    continue
                try:
                    inc, exc, symbols = (_tokens(f) for f in fields[2:])
                except (ValueError, RecursionError) as error:
                    issues.append(Issue(line, "malformed_tokens", str(error)))
                    previous = None
                    continue
                row = MembershipRow(line, effective, fields[1], inc, exc, symbols)
                rows.append(row)
                if fields[1] != "Nifty500":
                    issues.append(Issue(line, "index_type", fields[1]))
                if len(set(symbols)) != len(symbols):
                    issues.append(
                        Issue(line, "duplicate_snapshot_token", "repeated snapshot token")
                    )
                if len(set(symbols)) != 500:
                    issues.append(Issue(line, "snapshot_size", str(len(set(symbols)))))
                if len(set(inc)) != len(inc) or len(set(exc)) != len(exc):
                    issues.append(
                        Issue(line, "duplicate_event_token", "repeated inclusion/exclusion")
                    )
                if set(inc) & set(exc):
                    issues.append(Issue(line, "event_overlap", repr(sorted(set(inc) & set(exc)))))
                if effective.weekday() >= 5:
                    issues.append(
                        Issue(line, "weekend_flag", "requires historical-calendar review")
                    )
                issues.append(Issue(line, "identity_unresolved", ",".join(symbols)))
                if previous is not None:
                    if effective <= previous.effective_date:
                        issues.append(
                            Issue(line, "date_order", "dates must be strictly increasing")
                        )
                    replayed = (set(previous.symbols) - set(exc)) | set(inc)
                    if replayed != set(symbols):
                        detail = {
                            "missing": sorted(set(symbols) - replayed),
                            "unexpected": sorted(replayed - set(symbols)),
                        }
                        issues.append(Issue(line, "transition_mismatch", json.dumps(detail)))
                previous = row
    except (UnicodeError, csv.Error) as error:
        issues.append(Issue(None, "csv_error", str(error)))
    return AuditReport(sha256, source_statement, imported_at, count, tuple(rows), tuple(issues))


def notice_conflicts(report: AuditReport) -> tuple[Issue, ...]:
    """Compare manually reviewed §8.2 notice facts; never apply a correction.

    Notice links/locators and observed facts are recorded in phase evidence.
    This targeted comparison does not claim to discover every historical event.
    """
    issues = []
    for month, effective, expected in (
        ("2025-03", date(2025, 3, 28), 30),
        ("2025-09", date(2025, 9, 30), 18),
        ("2026-03", date(2026, 3, 30), 31),
    ):
        candidates = [r for r in report.rows if r.effective_date.isoformat().startswith(month)]
        if len(candidates) != 1:
            issues.append(Issue(None, "notice_row_missing_or_ambiguous", month))
            continue
        row = candidates[0]
        if row.effective_date != effective:
            issues.append(Issue(row.line, "notice_effective_date", effective.isoformat()))
        if len(set(row.inclusions)) != expected or len(set(row.exclusions)) != expected:
            issues.append(Issue(row.line, "notice_event_count", f"expected {expected} each"))
        if month == "2025-03" and "NTPCGREEN" not in row.inclusions:
            issues.append(Issue(row.line, "notice_identifier", "NTPCGREEN required; NTPC differs"))
    tokens = {s for row in report.rows for s in (*row.symbols, *row.inclusions, *row.exclusions)}
    if not tokens & {"DUMMYHDLVR", "KWIL"}:
        issues.append(
            Issue(None, "temporary_component_missing", "DUMMYHDLVR/KWIL; 2026-02-24 exclusion")
        )
    return tuple(issues)
