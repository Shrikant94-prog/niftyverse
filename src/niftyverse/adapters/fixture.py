"""Decode an explicitly supplied owned JSON fixture."""

import hashlib
from datetime import date
from decimal import Decimal, InvalidOperation

import msgspec

from niftyverse.core import FixtureBatch, FixtureRow, ValidationError


class _WireRow(msgspec.Struct, frozen=True, forbid_unknown_fields=True):
    instrument_id: str
    session_date: date
    close: str | None
    label: str | None


def decode_fixture(payload: bytes) -> FixtureBatch:
    """Decode and validate all rows before any sink can be opened."""
    try:
        wire = msgspec.json.decode(payload, type=list[_WireRow])
    except msgspec.DecodeError as error:
        raise ValidationError(f"fixture JSON: {error}") from error
    rows: list[FixtureRow] = []
    for index, row in enumerate(wire):
        try:
            close = Decimal(row.close) if row.close is not None else None
            rows.append(FixtureRow(row.instrument_id, row.session_date, close, row.label))
        except (InvalidOperation, ValidationError) as error:
            raise ValidationError(f"fixture[{index}].close/row: {error}") from error
    rows.sort(key=lambda row: (row.session_date, row.instrument_id))
    return FixtureBatch(tuple(rows), hashlib.sha256(payload).hexdigest())
