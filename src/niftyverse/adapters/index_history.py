"""Bounded official Nifty historical wire decoders; no I/O during normalization."""

import hashlib
import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal

from niftyverse.core import ValidationError
from niftyverse.indices import IndexCatalogue, IndexPrice, IndexVariant, SourceLineage
from niftyverse.market_prices import number
from niftyverse.temporal import day, text, utc
from niftyverse.transport import DirectTransport, Download

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


async def fetch_nifty_history(
    transport: DirectTransport,
    *,
    dataset: Literal["price", "valuations", "tri"],
    alias: str,
    start: date,
    end: date,
) -> Download:
    """One explicit bounded window; source dates are inclusive, library end exclusive.

    Downloading does not establish completeness, resolve an alias or open storage.
    The linked source uses a single-quoted cinfo string, not an arbitrary query.
    """
    day(start)
    day(end)
    text(alias)
    if start >= end or (end - start).days > 366:
        raise ValidationError("invalid historical index window")
    if len(alias) > 200 or any(c in alias for c in "'\\\r\n"):
        raise ValidationError("invalid source alias")
    routes = {
        "price": "getHistoricaldatatabletoString",
        "valuations": "getpepbHistoricaldataDBtoString",
        "tri": "getTotalReturnIndexString",
    }
    if dataset not in routes:
        raise ValidationError("unsupported historical index dataset")

    def wire_date(on: date) -> str:
        return f"{on.day:02}-{MONTHS[on.month - 1]}-{on.year:04}"

    inner = (
        f"{{'name':'{alias}','startDate':'{wire_date(start)}',"
        f"'endDate':'{wire_date(end - timedelta(days=1))}','indexName':'{alias}'}}"
    )
    return await transport.post_index_json(
        f"https://www.niftyindices.com/BackPage/{routes[dataset]}",
        json.dumps({"cinfo": inner}).encode(),
    )


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    if len(dict(pairs)) != len(pairs):
        raise ValidationError("duplicate JSON key")
    return dict(pairs)


def _constant(value: str) -> None:
    raise ValidationError("invalid JSON number")


def _rows(body: bytes, max_bytes: int, max_rows: int) -> list[dict[str, Any]]:
    if not isinstance(body, bytes) or max_bytes <= 0 or len(body) > max_bytes:
        raise ValidationError("byte_limit")
    if max_rows <= 0:
        raise ValidationError("row_limit")
    try:
        data = json.loads(
            body, parse_float=Decimal, parse_constant=_constant, object_pairs_hook=_object
        )
    except ValidationError:
        raise
    except ValueError, UnicodeError, RecursionError:
        raise ValidationError("invalid JSON schema or number") from None
    # Only the actually observed list generation is supported. Current snapshots,
    # legacy envelopes and source errors cannot be mistaken for empty history.
    if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
        raise ValidationError("historical index schema mismatch")
    if len(data) > max_rows:
        raise ValidationError("row_limit")
    return data


def _window(start: date, end: date, known_at: datetime) -> None:
    day(start)
    day(end)
    utc(known_at)
    if start >= end or (end - start).days > 366:
        raise ValidationError("invalid historical index window")


def _date(value: object) -> date:
    if not isinstance(value, str):
        raise ValidationError("invalid source date")
    try:
        # Explicit English source months; independent of machine locale.
        d, month, year = value.split()
        return date(int(year), MONTHS.index(month) + 1, int(d))
    except ValueError:
        raise ValidationError("invalid source date") from None


def _lineage(
    body: bytes, row: dict[str, Any], source_id: str, locator: str, index: int, representation: str
) -> SourceLineage:
    # Reject nested fields rather than losing their type via an opaque str cast.
    if any(
        not isinstance(v, (str, int, Decimal, type(None))) or isinstance(v, bool)
        for v in row.values()
    ):
        raise ValidationError("invalid source field number/schema")
    return SourceLineage(
        source_id,
        hashlib.sha256(body).hexdigest(),
        f"{locator}#{index}",
        representation,
        tuple((k, None if v is None else str(v)) for k, v in row.items()),
    )


def decode_index_prices(
    body: bytes,
    *,
    catalogue: IndexCatalogue,
    variant: IndexVariant,
    source_id: str,
    locator: str,
    start: date,
    end: date,
    known_at: datetime,
    max_bytes: int = 8 * 1024 * 1024,
    max_rows: int = 100_000,
) -> tuple[IndexPrice, ...]:
    _window(start, end, known_at)
    text(source_id, locator)
    if variant.kind != "price":
        raise ValidationError("price endpoint incompatible with requested variant")
    rows = []
    seen = set()
    for i, raw in enumerate(_rows(body, max_bytes, max_rows)):
        if not {"INDEX_NAME", "HistoricalDate", "OPEN", "HIGH", "LOW", "CLOSE"} <= raw.keys():
            raise ValidationError("historical price schema mismatch")
        on = _date(raw["HistoricalDate"])
        if not start <= on < end:
            raise ValidationError("source date outside requested window")
        if on in seen:
            raise ValidationError("duplicate historical date")
        seen.add(on)
        resolved = catalogue.resolve(source_id, raw["INDEX_NAME"], "price", on, known_at)
        if resolved != variant:
            raise ValidationError("source/request variant mismatch")
        rows.append(
            IndexPrice(
                resolved,
                on,
                number(raw["OPEN"]),
                number(raw["HIGH"]),
                number(raw["LOW"]),
                number(raw["CLOSE"]),
                _lineage(body, raw, source_id, locator, i, "nifty_price_v1"),
            )
        )
    return tuple(rows)
