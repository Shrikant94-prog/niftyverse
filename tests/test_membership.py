"""Independent membership timelines; no network or inferred tradability."""

from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from niftyverse.calendars import SourceTime
from niftyverse.core import ValidationError
from niftyverse.membership import (
    Correction,
    Coverage,
    Event,
    Member,
    Reference,
    Replay,
    ReviewState,
    Snapshot,
    replay,
)

D1, D2, D3, D4 = (date(2025, 1, d) for d in (1, 2, 3, 4))
EARLY = datetime(2025, 1, 5, tzinfo=UTC)
LATE = datetime(2025, 2, 1, tzinfo=UTC)
RAW_HASH = "a" * 64
A = Member("security-a", "security", "instrument-a")
B = Member("security-b", "security", "instrument-b")
T = Member("component-t", "temporary", None)
REF = Reference("official", "https://example.test/notice#p1", "b" * 64, EARLY, "reviewer")
ANNOUNCED = SourceTime(date(2024, 12, 30), "Asia/Kolkata", "date")
BASE = Snapshot("start", D1, (A,), REF)
EVENT = Event("switch", D2, (B,), (A,), ANNOUNCED, REF)
CHECKS = (Snapshot("independent-start", D1, (A,), REF), Snapshot("end", D4, (B,), REF))
COVERAGE = Coverage(D1, D4, REF)


def run(
    events: tuple[Event, ...] = (EVENT,),
    corrections: tuple[Correction, ...] = (),
    checks: tuple[Snapshot, ...] = CHECKS,
    coverage: tuple[Coverage, ...] = (COVERAGE,),
    known_at: datetime = LATE,
) -> Replay:
    return replay(
        original_sha256=RAW_HASH,
        scope="Nifty500",
        start=D1,
        end=D4,
        baseline=BASE,
        events=events,
        corrections=corrections,
        checks=checks,
        coverage=coverage,
        known_at=known_at,
    )


def test_independent_expected_intervals() -> None:
    result = run()
    assert [(r.start, r.end, r.members, r.status) for r in result.intervals] == [
        (D1, D2, (A,), "independently_verified"),
        (D2, D4, (B,), "independently_verified"),
    ]
    assert result.strict_members(D1) == (A,)
    assert result.strict_members(D2) == (B,)
    with pytest.raises(ValidationError, match="outside"):
        result.strict_members(D4)


def test_consistent_but_contradicted_and_missing_checks_never_verify() -> None:
    contradicted = run(checks=(CHECKS[0], replace(CHECKS[1], members=(A,))))
    assert all(r.status == "quarantined" for r in contradicted.intervals)
    assert all("independent_snapshot_mismatch" in r.reasons for r in contradicted.intervals)
    for result in (run(checks=()), run(coverage=()), run(checks=CHECKS[:1])):
        assert all(r.status != "independently_verified" for r in result.intervals)
        with pytest.raises(ValidationError, match="unverified"):
            result.strict_members(D1)


def correction(state: ReviewState, reviewed_at: datetime = LATE) -> Correction:
    return Correction(
        "fix",
        EVENT,
        replace(EVENT, effective_date=D3),
        D2,
        D4,
        (REF,),
        "effective date was wrong",
        "author",
        state,
        EARLY,
        None if state == "pending" else "reviewer",
        None if state == "pending" else reviewed_at,
    )


@pytest.mark.parametrize("state", ["pending", "rejected", "accepted"])
def test_review_and_knowledge_time_are_explicit(state: ReviewState) -> None:
    ledger = (correction(state),)
    result = run(corrections=ledger)
    expected_day = D3 if state == "accepted" else D2
    assert result.intervals[0].end == expected_day
    assert run(corrections=ledger, known_at=EARLY).intervals[0].end == D2
    assert result.applied_corrections == (("fix",) if state == "accepted" else ())
    assert EVENT.effective_date == D2


def test_invalid_correction_and_original_mismatch_reject() -> None:
    with pytest.raises(ValidationError, match="review"):
        replace(correction("accepted"), reviewer=None)
    with pytest.raises(ValidationError, match="affected"):
        replace(correction("accepted"), affected_from=D3)
    with pytest.raises(ValidationError, match="original"):
        run(corrections=(replace(correction("accepted"), original=replace(EVENT, includes=(T,))),))
    with pytest.raises(ValidationError, match="duplicate"):
        run(corrections=(correction("accepted"), correction("accepted")))


def test_missing_events_can_be_added_and_existing_removed_by_review() -> None:
    add = replace(correction("accepted"), original=None, replacement=EVENT)
    result = run(events=(), corrections=(add,))
    assert result.strict_members(D2) == (B,)
    delete = replace(correction("accepted"), replacement=None)
    result = run(corrections=(delete,))
    assert "independent_snapshot_mismatch" in result.intervals[0].reasons


def test_unexplained_and_same_day_events_are_not_auto_repaired() -> None:
    bad = replace(EVENT, excludes=(T,))
    result = run(events=(bad,))
    assert result.intervals[-1].members == (A,)
    assert "remove_absent_member" in result.intervals[-1].reasons
    first = replace(EVENT, event_id="first", includes=(T,))
    second = replace(EVENT, event_id="second", includes=(B,), excludes=(T,))
    unordered = run(events=(first, second))
    assert "same_date_order_unknown" in unordered.intervals[-1].reasons
    ordered = run(events=(replace(second, order=2), replace(first, order=1)))
    assert ordered.strict_members(D2) == (B,)
    overlap = run(events=(replace(EVENT, includes=(A,)),))
    assert "event_overlap" in overlap.intervals[-1].reasons


def test_temporary_and_unresolved_members_never_become_instruments() -> None:
    temporary = replace(EVENT, includes=(T,))
    checks = (CHECKS[0], replace(CHECKS[1], members=(T,)))
    result = run(events=(temporary,), checks=checks)
    assert result.strict_members(D2) == (T,)
    assert result.security_instrument_ids(D2) == ()
    with pytest.raises(ValidationError, match="temporary"):
        replace(T, instrument_id="fake-price-id")
    unknown = Member("literal:M& M", "unresolved", None)
    result = run(
        events=(replace(EVENT, includes=(unknown,)),),
        checks=(CHECKS[0], replace(CHECKS[1], members=(unknown,))),
    )
    assert "identity_unresolved" in result.intervals[-1].reasons


def test_original_input_cannot_be_its_own_independent_evidence() -> None:
    checks = tuple(replace(c, evidence=replace(REF, sha256=RAW_HASH)) for c in CHECKS)
    assert all(r.status != "independently_verified" for r in run(checks=checks).intervals)


def test_raw_event_is_not_verified_by_matching_endpoints_alone() -> None:
    result = run(events=(replace(EVENT, evidence=replace(REF, sha256=RAW_HASH)),))
    assert "event_evidence_unverified" in result.intervals[-1].reasons
    with pytest.raises(ValidationError, match="unverified"):
        result.strict_members(D2)


def test_evidence_unavailable_at_cutoff_and_invalid_windows() -> None:
    result = run(known_at=datetime(2025, 1, 1, tzinfo=UTC))
    assert all(r.status != "independently_verified" for r in result.intervals)
    with pytest.raises(ValidationError, match="interval"):
        replace(COVERAGE, end=D1)
    with pytest.raises(ValidationError, match="sha256"):
        replace(REF, sha256="wrong")


def test_acceptance_cannot_precede_replacement_evidence() -> None:
    future = datetime(2025, 3, 1, tzinfo=UTC)
    with pytest.raises(ValidationError, match="review precedes"):
        replace(
            correction("accepted"),
            replacement=replace(EVENT, evidence=replace(REF, known_at=future)),
        )
