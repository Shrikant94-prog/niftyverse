"""Pure evidence-gated membership replay. No acquisition, storage or prices."""

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Literal

from niftyverse.calendars import SourceTime
from niftyverse.core import ValidationError
from niftyverse.temporal import day, text, utc

ReviewState = Literal["pending", "accepted", "rejected"]


def fingerprint(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()


def _hash(value: str) -> None:
    if not isinstance(value, str) or not re.fullmatch("[0-9a-f]{64}", value):
        raise ValidationError("invalid sha256")


def _window(start: date, end: date) -> None:
    day(start)
    day(end)
    if start >= end:
        raise ValidationError("invalid half-open interval")


@dataclass(frozen=True)
class Reference:
    source_id: str
    locator: str
    sha256: str
    known_at: datetime
    reviewer: str

    def __post_init__(self) -> None:
        text(self.source_id, self.locator, self.reviewer)
        _hash(self.sha256)
        utc(self.known_at)


@dataclass(frozen=True, order=True)
class Member:
    member_id: str
    kind: Literal["security", "temporary", "unresolved"]
    instrument_id: str | None

    def __post_init__(self) -> None:
        text(self.member_id)
        if self.kind == "security":
            text(self.instrument_id)  # type: ignore[arg-type]
        elif self.kind in {"temporary", "unresolved"}:
            if self.instrument_id is not None:
                raise ValidationError("temporary/unresolved component cannot be an instrument")
        else:
            raise ValidationError("invalid membership identity kind")


def _members(rows: tuple[Member, ...]) -> None:
    if not isinstance(rows, tuple):
        raise ValidationError("membership values must be immutable tuples")
    for row in rows:
        row.__post_init__()
    if len({r.member_id for r in rows}) != len(rows):
        raise ValidationError("duplicate member identity")


@dataclass(frozen=True)
class Snapshot:
    snapshot_id: str
    on: date
    members: tuple[Member, ...]
    evidence: Reference

    def __post_init__(self) -> None:
        text(self.snapshot_id)
        day(self.on)
        _members(self.members)
        self.evidence.__post_init__()


@dataclass(frozen=True)
class Event:
    event_id: str
    effective_date: date
    includes: tuple[Member, ...]
    excludes: tuple[Member, ...]
    announced: SourceTime
    evidence: Reference
    order: int | None = None

    def __post_init__(self) -> None:
        text(self.event_id)
        day(self.effective_date)
        _members(self.includes)
        _members(self.excludes)
        self.announced.__post_init__()
        self.evidence.__post_init__()
        if self.order is not None and (type(self.order) is not int or self.order < 0):
            raise ValidationError("same-date order requires a nonnegative integer")
        instant = self.announced.instant
        if instant is not None and instant > self.evidence.known_at:
            raise ValidationError("event evidence cannot precede announcement")


Record = Event | Snapshot


def _record_id(record: Record) -> str:
    return record.event_id if isinstance(record, Event) else record.snapshot_id


def _record_date(record: Record) -> date:
    return record.effective_date if isinstance(record, Event) else record.on


@dataclass(frozen=True)
class Correction:
    correction_id: str
    original: Record | None
    replacement: Record | None
    affected_from: date
    affected_to: date
    evidence: tuple[Reference, ...]
    rationale: str
    author: str
    state: ReviewState
    proposed_at: datetime
    reviewer: str | None
    reviewed_at: datetime | None

    def __post_init__(self) -> None:
        text(self.correction_id, self.rationale, self.author)
        utc(self.proposed_at)
        _window(self.affected_from, self.affected_to)
        if not isinstance(self.evidence, tuple) or not self.evidence:
            raise ValidationError("correction requires immutable evidence")
        for ref in self.evidence:
            ref.__post_init__()
        records = [r for r in (self.original, self.replacement) if r is not None]
        if not records:
            raise ValidationError("correction needs original or replacement")
        for record in records:
            record.__post_init__()
            if not self.affected_from <= _record_date(record) < self.affected_to:
                raise ValidationError("correction affected interval omits changed date")
        if len(records) == 2 and (
            type(records[0]) is not type(records[1])
            or _record_id(records[0]) != _record_id(records[1])
        ):
            raise ValidationError("replacement must retain record identity/type")
        if self.state == "pending":
            if self.reviewer is not None or self.reviewed_at is not None:
                raise ValidationError("pending correction cannot have a review decision")
        elif self.state in {"accepted", "rejected"}:
            if self.reviewer is None or not self.reviewer.strip():
                raise ValidationError("reviewer required for review decision")
            text(self.reviewer)
            if self.reviewed_at is None:
                raise ValidationError("review time required")
            utc(self.reviewed_at)
            if self.reviewed_at < max(self.proposed_at, *(r.known_at for r in self.evidence)):
                raise ValidationError("review precedes proposal/evidence")
        else:
            raise ValidationError("invalid correction review state")


@dataclass(frozen=True)
class Coverage:
    """Reviewed completeness assertion for all events in the declared scope.

    A notice about one component cannot establish full-index event completeness.
    The caller must retain its reviewed inventory and state the exact scope.
    """

    start: date
    end: date
    evidence: Reference

    def __post_init__(self) -> None:
        _window(self.start, self.end)
        self.evidence.__post_init__()


@dataclass(frozen=True)
class MembershipInterval:
    start: date
    end: date
    members: tuple[Member, ...]
    status: Literal["independently_verified", "quarantined"]
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class Replay:
    version_id: str
    original_sha256: str
    scope: str
    start: date
    end: date
    known_at: datetime
    intervals: tuple[MembershipInterval, ...]
    applied_corrections: tuple[str, ...]
    recipe_json: str

    def strict_members(self, on: date) -> tuple[Member, ...]:
        day(on)
        for interval in self.intervals:
            if interval.start <= on < interval.end:
                if interval.status != "independently_verified":
                    raise ValidationError("unverified membership: " + ",".join(interval.reasons))
                return interval.members
        raise ValidationError("date outside replay interval")

    def security_instrument_ids(self, on: date) -> tuple[str, ...]:
        # Security identity is only a candidate. Listing/session/price eligibility
        # is still the Phase 05 caller's responsibility.
        return tuple(
            m.instrument_id for m in self.strict_members(on) if m.instrument_id is not None
        )


def replay(
    *,
    original_sha256: str,
    scope: str,
    start: date,
    end: date,
    baseline: Snapshot,
    events: tuple[Event, ...],
    corrections: tuple[Correction, ...],
    checks: tuple[Snapshot, ...],
    coverage: tuple[Coverage, ...],
    known_at: datetime,
) -> Replay:
    _hash(original_sha256)
    text(scope)
    _window(start, end)
    utc(known_at)
    baseline.__post_init__()
    for rows in (events, corrections, checks, coverage):
        if not isinstance(rows, tuple):
            raise ValidationError("replay inputs require immutable tuples")
        for row in rows:
            row.__post_init__()
    for rows, key in (
        (events, "event_id"),
        (corrections, "correction_id"),
        (checks, "snapshot_id"),
    ):
        if len({getattr(r, key) for r in rows}) != len(rows):
            raise ValidationError("duplicate replay record identity")
    if any(e.event_id == baseline.snapshot_id for e in events):
        raise ValidationError("duplicate baseline/event identity")
    records: dict[str, Record] = {
        baseline.snapshot_id: baseline,
        **{e.event_id: e for e in events},
    }
    applied = []
    # Ledger order is explicit; do not silently reorder chained revisions.
    for correction in corrections:
        if correction.state != "accepted" or correction.reviewed_at is None:
            continue
        if correction.reviewed_at > known_at:
            continue
        record = correction.original or correction.replacement
        assert record is not None
        key = _record_id(record)
        if records.get(key) != correction.original:
            raise ValidationError("correction original does not match current record")
        if correction.replacement is None:
            records.pop(key, None)
        else:
            records[key] = correction.replacement
        applied.append(correction.correction_id)
    snapshots = [r for r in records.values() if isinstance(r, Snapshot)]
    if len(snapshots) != 1 or snapshots[0].on > start:
        raise ValidationError("replay requires one starting snapshot at/before interval")
    initial = snapshots[0]
    selected = [r for r in records.values() if isinstance(r, Event)]
    if any(e.effective_date <= initial.on for e in selected):
        raise ValidationError("events must follow starting snapshot")
    # Stable IDs cannot silently change identity kind or linked instrument.
    definitions: dict[str, Member] = {}
    for record in (*records.values(), *checks):
        members = (
            record.members
            if isinstance(record, Snapshot)
            else (*record.includes, *record.excludes)
        )
        for member in members:
            if member.member_id in definitions and definitions[member.member_id] != member:
                raise ValidationError("member identity changes kind/instrument")
            definitions[member.member_id] = member
    available_checks = [
        c
        for c in checks
        if c.evidence.known_at <= known_at and c.evidence.sha256 != original_sha256
    ]
    boundaries = sorted(
        {
            initial.on,
            start,
            end,
            *(e.effective_date for e in selected if e.effective_date <= end),
            *(c.on for c in available_checks if initial.on <= c.on <= end),
            *(d for c in coverage for d in (c.start, c.end) if initial.on < d < end),
        }
    )
    current = set(initial.members)
    errors = set()
    if initial.evidence.known_at > known_at:
        errors.add("starting_snapshot_not_known")
    states: dict[date, tuple[Member, ...]] = {}
    failures: dict[date, tuple[str, ...]] = {}
    for boundary in boundaries:
        same_day = [e for e in selected if e.effective_date == boundary]
        if len(same_day) > 1 and (
            any(e.order is None for e in same_day)
            or len({e.order for e in same_day}) != len(same_day)
        ):
            errors.add("same_date_order_unknown")
        else:
            for event in sorted(same_day, key=lambda e: e.order or 0):
                event_errors = set()
                if event.evidence.known_at > known_at:
                    event_errors.add("event_not_known")
                inc, exc = set(event.includes), set(event.excludes)
                if inc & exc:
                    event_errors.add("event_overlap")
                if exc - current:
                    event_errors.add("remove_absent_member")
                if inc & current:
                    event_errors.add("add_existing_member")
                if not event_errors:
                    current = (current - exc) | inc
                errors.update(event_errors)
        states[boundary] = tuple(sorted(current))
        failures[boundary] = tuple(sorted(errors))
    intervals = []
    for left, right in zip(boundaries, boundaries[1:], strict=False):
        if left < start or left >= end:
            continue
        reasons = set(failures[left])
        if any(m.kind == "unresolved" for m in states[left]):
            reasons.add("identity_unresolved")
        before = [c for c in available_checks if initial.on <= c.on <= left]
        after = [c for c in available_checks if right <= c.on <= end]
        if not before:
            reasons.add("independent_start_missing")
        if not after:
            reasons.add("independent_end_missing")
        if before and after:
            a, b = max(c.on for c in before), min(c.on for c in after)
            anchors = [c for c in available_checks if a <= c.on <= b]
            if any(set(c.members) != set(states[c.on]) for c in anchors):
                reasons.add("independent_snapshot_mismatch")
        if not any(
            c.start <= left
            and right <= c.end
            and c.evidence.known_at <= known_at
            and c.evidence.sha256 != original_sha256
            for c in coverage
        ):
            reasons.add("event_coverage_unverified")
        intervals.append(
            MembershipInterval(
                left,
                right,
                states[left],
                "quarantined" if reasons else "independently_verified",
                tuple(sorted(reasons)),
            )
        )
    recipe = {
        "schema_version": 1,
        "original_sha256": original_sha256,
        "scope": scope,
        "start": start,
        "end": end,
        "known_at": known_at,
        "baseline": asdict(baseline),
        "events": [asdict(e) for e in events],
        "corrections": [asdict(c) for c in corrections],
        "checks": [asdict(c) for c in checks],
        "coverage": [asdict(c) for c in coverage],
    }
    recipe_json = json.dumps(recipe, sort_keys=True, default=str, separators=(",", ":"))
    return Replay(
        fingerprint(recipe),
        original_sha256,
        scope,
        start,
        end,
        known_at,
        tuple(intervals),
        tuple(applied),
        recipe_json,
    )
