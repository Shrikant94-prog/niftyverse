"""Exact manually calculated instants; owned fixtures, not exchange coverage."""

from dataclasses import replace
from datetime import UTC, date, datetime

import pytest
from test_identity import CUTOFF, KNOWN

from niftyverse.calendars import Calendar, CalendarSnapshot, Session, SourceTime
from niftyverse.core import ValidationError


def calendar() -> Calendar:
    return Calendar(
        "calendar-v1",
        "NSE",
        "CM",
        KNOWN,
        (
            Session(date(2020, 1, 1), "closed", None, None, "Asia/Kolkata", "owned", "holiday:1"),
            Session(
                date(2020, 1, 2),
                "trading",
                datetime(2020, 1, 2, 3, 45, tzinfo=UTC),
                datetime(2020, 1, 2, 10, tzinfo=UTC),
                "Asia/Kolkata",
                "owned",
                "regular:1",
            ),
            Session(
                date(2020, 1, 4),
                "special",
                datetime(2020, 1, 4, 12, 30, tzinfo=UTC),
                datetime(2020, 1, 4, 13, 30, tzinfo=UTC),
                "Asia/Kolkata",
                "owned",
                "special:1",
            ),
            Session(
                date(2020, 1, 5), "unknown", None, None, "Asia/Kolkata", "owned", "coverage-gap:1"
            ),
        ),
    )


def test_closed_special_unknown_and_exact_boundaries() -> None:
    cal = calendar()
    assert cal.session(date(2020, 1, 1)).state == "closed"
    regular = cal.session(date(2020, 1, 2))
    assert regular.eligible is True
    assert regular.contains(datetime(2020, 1, 2, 3, 45, tzinfo=UTC))
    assert not regular.contains(datetime(2020, 1, 2, 10, tzinfo=UTC))
    special = cal.session(date(2020, 1, 4))  # Saturday is evidenced, never weekday-inferred.
    assert special.state == "special" and special.eligible is True
    assert special.opens_at == datetime(2020, 1, 4, 12, 30, tzinfo=UTC)
    assert cal.session(date(2020, 1, 5)).eligible is None
    assert cal.session(date(2020, 1, 3)).state == "unknown"
    assert cal.session(date(2020, 1, 3)).source_id is None
    with pytest.raises(ValidationError, match="unknown"):
        cal.sessions_between(date(2020, 1, 1), date(2020, 1, 5), require_complete=True)


def test_source_timezone_rollover_and_date_precision_remain_distinct() -> None:
    source = SourceTime(date(2020, 1, 2), "Asia/Kolkata", "date")
    assert source.instant is None and source.source_date == date(2020, 1, 2)
    exact = SourceTime(datetime(2020, 1, 2, 0, 15), "Asia/Kolkata", "instant")
    assert exact.instant == datetime(2020, 1, 1, 18, 45, tzinfo=UTC)
    assert exact.source_date == date(2020, 1, 2)
    assert exact.value == datetime(2020, 1, 2, 0, 15)
    utc_source = SourceTime(datetime(2020, 1, 1, 23, 45, tzinfo=UTC), "Asia/Kolkata", "instant")
    assert utc_source.instant == datetime(2020, 1, 1, 23, 45, tzinfo=UTC)
    assert utc_source.source_date == date(2020, 1, 2)
    assert SourceTime(None, "Asia/Kolkata", "unknown").instant is None


@pytest.mark.parametrize("local", [datetime(2024, 3, 10, 2, 30), datetime(2024, 11, 3, 1, 30)])
def test_unresolved_dst_gap_or_fold_never_invents_an_instant(local: datetime) -> None:
    with pytest.raises(ValidationError, match="ambiguous|nonexistent"):
        SourceTime(local, "America/New_York", "instant")
    # An aware source gives an exact instant even during a repeated clock hour.
    assert SourceTime(
        datetime(2024, 11, 3, 5, 30, tzinfo=UTC), "America/New_York", "instant"
    ).instant == datetime(2024, 11, 3, 5, 30, tzinfo=UTC)


def test_correction_new_version_preserves_pinned_old_snapshot() -> None:
    original = calendar()
    old = CalendarSnapshot("snapshot-1", original, KNOWN)
    corrected_day = replace(
        original.sessions[0],
        state="special",
        opens_at=datetime(2020, 1, 1, 12, 30, tzinfo=UTC),
        closes_at=datetime(2020, 1, 1, 13, 30, tzinfo=UTC),
        locator="correction:1",
    )
    corrected = original.correct("calendar-v2", CUTOFF, (corrected_day,))
    new = CalendarSnapshot("snapshot-2", corrected, CUTOFF)
    assert old.calendar.session(date(2020, 1, 1)).eligible is False
    assert new.calendar.session(date(2020, 1, 1)).eligible is True
    assert old.calendar.version_id == "calendar-v1" and new.calendar.version_id == "calendar-v2"
    assert original.sessions[0].locator == "holiday:1"
    with pytest.raises(ValidationError, match="known"):
        CalendarSnapshot("future-leak", corrected, KNOWN)
    with pytest.raises(ValidationError, match="version"):
        original.correct("calendar-v1", CUTOFF, (corrected_day,))


def test_invalid_calendar_boundaries_and_atomic_correction() -> None:
    cal = calendar()
    with pytest.raises(ValidationError, match="session"):
        replace(cal.sessions[0], state="closed", opens_at=datetime(2020, 1, 1, tzinfo=UTC))
    with pytest.raises(ValidationError, match="session"):
        replace(cal.sessions[1], closes_at=cal.sessions[1].opens_at)
    with pytest.raises(ValidationError, match="date"):
        replace(cal.sessions[1], session_date=date(2020, 1, 3))
    with pytest.raises(ValidationError, match="duplicate"):
        cal.correct("bad", CUTOFF, (cal.sessions[0], cal.sessions[0]))
    with pytest.raises(ValidationError, match="precision"):
        SourceTime(datetime(2020, 1, 1), "Asia/Kolkata", "date")
    with pytest.raises(ValidationError, match="timezone"):
        SourceTime(date(2020, 1, 1), "Mars/Unknown", "date")
    assert cal == calendar()
