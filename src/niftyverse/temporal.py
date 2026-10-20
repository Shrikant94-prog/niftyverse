"""Pure evidence boundaries. Unknown starts never mean beginning of time."""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from niftyverse.core import ValidationError


def text(*values: str) -> None:
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValidationError("nonempty evidence/identity text required")


def utc(value: datetime) -> None:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() != UTC.utcoffset(value)
    ):
        raise ValidationError("timestamp requires aware UTC")


def day(value: date) -> None:
    if type(value) is not date:
        raise ValidationError("session/effective date requires date precision")


def decimal(value: Decimal | None) -> None:
    if value is not None and (not isinstance(value, Decimal) or not value.is_finite()):
        raise ValidationError("finite exact decimal required")


@dataclass(frozen=True)
class Evidence:
    """Half-open evidenced validity; null end is open, null start is unknown.

    known_at is the earliest justified availability, not a fabricated publication
    instant. source_id and locator identify reviewed local evidence.
    """

    valid_from: date | None
    valid_to: date | None
    known_at: datetime
    source_id: str
    locator: str

    def __post_init__(self) -> None:
        utc(self.known_at)
        text(self.source_id, self.locator)
        for value in (self.valid_from, self.valid_to):
            if value is not None:
                day(value)
        if (
            self.valid_from is not None
            and self.valid_to is not None
            and self.valid_from >= self.valid_to
        ):
            raise ValidationError("invalid half-open evidence interval")

    def admits(self, on: date, known_at: datetime) -> bool:
        return self.possible(on, known_at) and self.valid_from is not None

    def possible(self, on: date, known_at: datetime) -> bool:
        """Unknown starts may be search candidates; known ends still exclude."""
        day(on)
        utc(known_at)
        return (
            self.known_at <= known_at
            and (self.valid_from is None or self.valid_from <= on)
            and (self.valid_to is None or on < self.valid_to)
        )
