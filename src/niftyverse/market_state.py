"""Optional observed regulatory facts; absence is never unrestricted trading."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from niftyverse.core import ValidationError
from niftyverse.temporal import Evidence, day, decimal, text, utc


@dataclass(frozen=True)
class MarketStateObservation:
    observation_id: str
    listing_id: str
    segment: str
    state_kind: str
    state: Literal["present", "removed", "unknown", "not_applicable"]
    value: str | None
    observed_on: date
    effective_from: date | None
    effective_to: date | None
    known_at: datetime
    publication_time: datetime | None
    publication_precision: Literal["instant", "date", "unknown"]
    source_timezone: str
    lower: Decimal | None
    upper: Decimal | None
    basis: str
    source_id: str
    locator: str
    publication_date: date | None = None

    def __post_init__(self) -> None:
        text(
            self.observation_id,
            self.listing_id,
            self.segment,
            self.state_kind,
            self.basis,
            self.source_id,
            self.locator,
            self.source_timezone,
        )
        day(self.observed_on)
        Evidence(
            self.effective_from, self.effective_to, self.known_at, self.source_id, self.locator
        )
        if self.effective_from is None and self.effective_to is not None:
            raise ValidationError("state interval end without evidenced start")
        if self.state not in {"present", "removed", "unknown", "not_applicable"}:
            raise ValidationError("invalid market state")
        if self.publication_precision not in {"instant", "date", "unknown"} or (
            self.publication_precision == "instant"
        ) != (self.publication_time is not None):
            raise ValidationError("publication precision/time mismatch")
        if self.publication_time is not None:
            utc(self.publication_time)
            if self.publication_time > self.known_at:
                raise ValidationError("publication follows known-at")
        if (self.publication_precision == "date") != (self.publication_date is not None):
            raise ValidationError("publication date/precision mismatch")
        if self.publication_date is not None:
            day(self.publication_date)
        try:
            ZoneInfo(self.source_timezone)
        except ZoneInfoNotFoundError as error:
            raise ValidationError("unknown source timezone") from error
        decimal(self.lower)
        decimal(self.upper)
        if self.lower is not None and self.upper is not None and self.lower > self.upper:
            raise ValidationError("inverted market state bounds")
        if self.value is not None:
            text(self.value)
        if self.state != "present" and any(
            v is not None for v in (self.value, self.lower, self.upper)
        ):
            raise ValidationError("non-present state cannot assert values/bounds")


def state_on(
    rows: tuple[MarketStateObservation, ...],
    listing_id: str,
    segment: str,
    state_kind: str,
    on: date,
    known_at: datetime,
) -> tuple[MarketStateObservation, ...]:
    """Return all evidenced candidates; empty means unknown, conflicts stay visible.

    Snapshot-only facts apply solely to observed_on. Explicit effective intervals
    may extend only as supplied by the evidence. No automatic carry or removal.
    """
    day(on)
    utc(known_at)
    return tuple(
        r
        for r in rows
        if r.listing_id == listing_id
        and r.segment == segment
        and r.state_kind == state_kind
        and r.known_at <= known_at
        and (
            (r.effective_from is None and on == r.observed_on)
            or Evidence(
                r.effective_from, r.effective_to, r.known_at, r.source_id, r.locator
            ).admits(on, known_at)
        )
    )
