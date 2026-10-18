"""Immutable records and validation for the owned Phase 01 fixture contract."""

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal


class ValidationError(ValueError):
    """Fixture input failed before opening a destination."""


def validate_price(value: Decimal | None) -> None:
    """Require a finite, exactly representable fixture decimal128(18,4)."""
    if value is None:
        return
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValidationError("fixture.close must be a finite decimal or null")
    # Inspect digits directly: Decimal context precision must not round validation.
    _, digits, exponent = value.as_tuple()
    assert isinstance(exponent, int)
    if value and value.adjusted() >= 14:
        raise ValidationError("fixture.close exceeds decimal128(18,4) range")
    if exponent < -4 and any(
        digits[len(digits) + exponent + 4 :] if len(digits) + exponent + 4 > 0 else digits
    ):
        raise ValidationError("fixture.close is inexact at scale 4")


@dataclass(frozen=True, slots=True)
class FixtureRow:
    """Synthetic observation; no real provider capability is implied."""

    instrument_id: str
    session_date: date
    close: Decimal | None
    label: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.instrument_id, str) or not self.instrument_id.strip():
            raise ValidationError("fixture.instrument_id must be nonempty text")
        if type(self.session_date) is not date:
            raise ValidationError("fixture.session_date must be a date")
        if self.label is not None and not isinstance(self.label, str):
            raise ValidationError("fixture.label must be text or null")
        validate_price(self.close)


@dataclass(frozen=True, slots=True)
class FixtureBatch:
    """Validated immutable rows with the hash of the owned input bytes."""

    rows: tuple[FixtureRow, ...]
    raw_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.rows, tuple) or not self.rows:
            raise ValidationError("fixture must contain a nonempty immutable tuple of rows")
        if not re.fullmatch(r"[0-9a-f]{64}", self.raw_sha256):
            raise ValidationError("fixture raw SHA-256 is invalid")
        keys: set[tuple[str, date]] = set()
        for index, row in enumerate(self.rows):
            if not isinstance(row, FixtureRow):
                raise ValidationError(f"fixture[{index}] must be a FixtureRow")
            row.__post_init__()
            key = (row.instrument_id, row.session_date)
            if key in keys:
                raise ValidationError(f"fixture[{index}] duplicates instrument/date")
            keys.add(key)
