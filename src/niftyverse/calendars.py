"""Pure evidenced segment calendars and precision-preserving source times.

No weekday/holiday inference, external calendar authority, or acquisition. A
missing date is unknown. Calendar corrections create a new immutable version.
"""

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from niftyverse.core import ValidationError
from niftyverse.temporal import day, text, utc


def _zone(name: str) -> ZoneInfo:
    text(name)
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as error:
        raise ValidationError("unknown source timezone") from error


@dataclass(frozen=True)
class SourceTime:
    """Date-only evidence never becomes midnight or a same-day availability.

    Naive exact clock readings must have a unique instant in the declared zone.
    Aware timestamps already specify an instant; their original value is retained.
    """

    value: date | datetime | None
    source_timezone: str
    precision: Literal["date", "instant", "unknown"]

    def __post_init__(self) -> None:
        zone = _zone(self.source_timezone)
        if self.precision == "date":
            if type(self.value) is not date:
                raise ValidationError("date precision requires a source date")
        elif self.precision == "unknown":
            if self.value is not None:
                raise ValidationError("unknown precision requires null")
        elif self.precision == "instant":
            if not isinstance(self.value, datetime):
                raise ValidationError("instant precision requires a timestamp")
            if self.value.utcoffset() is None:
                candidates = set()
                for fold in (0, 1):
                    candidate = self.value.replace(tzinfo=zone, fold=fold).astimezone(UTC)
                    if candidate.astimezone(zone).replace(tzinfo=None) == self.value:
                        candidates.add(candidate)
                if not candidates:
                    raise ValidationError("nonexistent local source timestamp")
                if len(candidates) > 1:
                    raise ValidationError("ambiguous local source timestamp; supply offset")
        else:
            raise ValidationError("invalid source precision")

    @property
    def instant(self) -> datetime | None:
        if not isinstance(self.value, datetime):
            return None
        value = self.value
        if value.utcoffset() is None:
            value = value.replace(tzinfo=_zone(self.source_timezone))
        return value.astimezone(UTC)

    @property
    def source_date(self) -> date | None:
        instant = self.instant
        return instant.astimezone(_zone(self.source_timezone)).date() if instant else self.value


@dataclass(frozen=True)
class Session:
    session_date: date
    state: Literal["trading", "closed", "special", "unknown"]
    opens_at: datetime | None
    closes_at: datetime | None
    source_timezone: str
    source_id: str | None
    locator: str | None

    def __post_init__(self) -> None:
        day(self.session_date)
        zone = _zone(self.source_timezone)
        if self.state not in {"trading", "closed", "special", "unknown"}:
            raise ValidationError("invalid session state")
        if self.state != "unknown" or self.source_id is not None or self.locator is not None:
            text(self.source_id, self.locator)  # type: ignore[arg-type]
        if self.state in {"trading", "special"}:
            if self.opens_at is None or self.closes_at is None:
                raise ValidationError("trading session requires evidenced boundaries")
            utc(self.opens_at)
            utc(self.closes_at)
            if self.opens_at >= self.closes_at:
                raise ValidationError("invalid session interval")
            if self.opens_at.astimezone(zone).date() != self.session_date:
                raise ValidationError("session date differs from source open date")
        elif self.opens_at is not None or self.closes_at is not None:
            raise ValidationError("closed/unknown session cannot invent boundaries")

    @property
    def eligible(self) -> bool | None:
        return None if self.state == "unknown" else self.state in {"trading", "special"}

    def contains(self, instant: datetime) -> bool | None:
        utc(instant)
        if self.state == "unknown":
            return None
        return (
            self.opens_at is not None
            and self.closes_at is not None
            and self.opens_at <= instant < self.closes_at
        )


@dataclass(frozen=True)
class Calendar:
    version_id: str
    venue: str
    segment: str
    known_at: datetime
    sessions: tuple[Session, ...]
    source_timezone: str = "Asia/Kolkata"
    prior_version_id: str | None = None

    def __post_init__(self) -> None:
        text(self.version_id, self.venue, self.segment)
        utc(self.known_at)
        _zone(self.source_timezone)
        if not isinstance(self.sessions, tuple):
            raise ValidationError("calendar requires immutable sessions")
        for session in self.sessions:
            session.__post_init__()
            if session.source_timezone != self.source_timezone:
                raise ValidationError("inconsistent segment timezone")
        if len({s.session_date for s in self.sessions}) != len(self.sessions):
            raise ValidationError("duplicate session date")
        if self.prior_version_id == self.version_id:
            raise ValidationError("calendar version cannot replace itself")

    @property
    def content_hash(self) -> str:
        values = asdict(self)
        values["sessions"] = sorted(values["sessions"], key=lambda r: r["session_date"])
        return hashlib.sha256(json.dumps(values, sort_keys=True, default=str).encode()).hexdigest()

    def session(self, on: date) -> Session:
        day(on)
        return next(
            (s for s in self.sessions if s.session_date == on),
            Session(on, "unknown", None, None, self.source_timezone, None, None),
        )

    def sessions_between(
        self, start: date, end: date, *, require_complete: bool = True
    ) -> tuple[Session, ...]:
        day(start)
        day(end)
        if start >= end:
            raise ValidationError("invalid calendar date interval")
        rows = tuple(self.session(start + timedelta(days=i)) for i in range((end - start).days))
        if require_complete and any(r.state == "unknown" for r in rows):
            raise ValidationError("unknown calendar coverage blocks strict session grid")
        return rows

    def correct(
        self, version_id: str, known_at: datetime, replacements: tuple[Session, ...]
    ) -> Calendar:
        utc(known_at)
        if version_id == self.version_id or known_at <= self.known_at:
            raise ValidationError("correction requires new version and later known-at")
        if (
            not isinstance(replacements, tuple)
            or not replacements
            or len({s.session_date for s in replacements}) != len(replacements)
        ):
            raise ValidationError("empty/duplicate calendar correction")
        days = {s.session_date for s in replacements}
        return Calendar(
            version_id,
            self.venue,
            self.segment,
            known_at,
            tuple(s for s in self.sessions if s.session_date not in days) + replacements,
            self.source_timezone,
            self.version_id,
        )


@dataclass(frozen=True)
class CalendarSnapshot:
    snapshot_id: str
    calendar: Calendar
    cutoff: datetime

    def __post_init__(self) -> None:
        text(self.snapshot_id)
        utc(self.cutoff)
        if self.calendar.known_at > self.cutoff:
            raise ValidationError("calendar version not known at snapshot cutoff")
