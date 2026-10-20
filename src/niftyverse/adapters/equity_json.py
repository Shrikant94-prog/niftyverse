"""Independent cash-equity JSON decoder; no CSV representation reuse or I/O.

Wire keys and decimal units follow the directly inspected official equity archive
JSON and its linked column definition. SLBMH lending data is a different contract.
Page metadata is explicit caller evidence, never invented NSE response metadata.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

from niftyverse.ingestion import _source_date
from niftyverse.market_prices import MarketDataFailure, SourcePrice, number, quantity
from niftyverse.temporal import day, text
from niftyverse.transport import DirectTransport, TransportFailure

REQUIRED = (
    "CH_SYMBOL",
    "CH_SERIES",
    "mTIMESTAMP",
    "CH_OPENING_PRICE",
    "CH_TRADE_HIGH_PRICE",
    "CH_TRADE_LOW_PRICE",
    "CH_CLOSING_PRICE",
    "CH_TOT_TRADED_QTY",
    "CH_TOT_TRADED_VAL",
)


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    if len(dict(pairs)) != len(pairs):
        raise MarketDataFailure("duplicate_json_key")
    return dict(pairs)


def _constant(value: str) -> None:
    raise MarketDataFailure("invalid_number")


def decode_equity_json(
    body: bytes,
    *,
    source_id: str,
    locator: str,
    max_bytes: int = 8 * 1024 * 1024,
    max_rows: int = 100_000,
) -> tuple[SourcePrice, ...]:
    text(source_id, locator)
    if not isinstance(body, bytes) or len(body) > max_bytes or min(max_rows, max_bytes) <= 0:
        raise MarketDataFailure("byte_limit")
    try:
        data = json.loads(
            body, parse_float=Decimal, parse_constant=_constant, object_pairs_hook=_object
        )
    except MarketDataFailure:
        raise
    except ValueError, UnicodeError, RecursionError:
        raise MarketDataFailure("invalid_json") from None
    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        raise MarketDataFailure("schema_drift")
    if data.get("error"):
        raise MarketDataFailure("source_error")
    if len(data["data"]) > max_rows:
        raise MarketDataFailure("row_limit")
    rows = []
    sha256 = hashlib.sha256(body).hexdigest()
    for index, row in enumerate(data["data"]):
        if not isinstance(row, dict) or not set(REQUIRED) <= row.keys():
            raise MarketDataFailure("schema_drift")
        if not all(isinstance(row[k], str) and row[k].strip() for k in REQUIRED[:3]):
            raise MarketDataFailure("missing_identity")
        try:
            on = _source_date(row["mTIMESTAMP"], True)
        except ValueError:
            raise MarketDataFailure("invalid_date") from None
        rows.append(
            SourcePrice(
                row["CH_SYMBOL"],
                row["CH_SERIES"],
                on,
                number(row["CH_OPENING_PRICE"]),
                number(row["CH_TRADE_HIGH_PRICE"]),
                number(row["CH_TRADE_LOW_PRICE"]),
                number(row["CH_CLOSING_PRICE"]),
                quantity(row["CH_TOT_TRADED_QTY"]),
                number(row["CH_TOT_TRADED_VAL"]),
                source_id,
                "nse_equity_json_v1",
                sha256,
                f"{locator}#data/{index}",
                tuple((k, None if v is None else str(v)) for k, v in row.items()),
                trades=quantity(row.get("CH_TOTAL_TRADES")),
                previous_close=number(row.get("CH_PREVIOUS_CLS_PRICE")),
                last=number(row.get("CH_LAST_TRADED_PRICE")),
                delivered_quantity=quantity(row.get("COP_DELIV_QTY")),
                delivered_percent=number(row.get("COP_DELIV_PERC")),
            )
        )
    return tuple(rows)


@dataclass(frozen=True)
class JsonPage:
    body: bytes
    start: date
    end: date
    ordinal: int
    terminal: bool
    snapshot_id: str
    expected_records: int | None


@dataclass(frozen=True)
class JsonPages:
    rows: tuple[SourcePrice, ...]
    evidence: tuple[SourcePrice, ...]
    complete: bool


def merge_pages(pages: tuple[JsonPage, ...], *, source_id: str, max_pages: int = 128) -> JsonPages:
    if not pages or len(pages) > max_pages:
        raise MarketDataFailure("page_limit")
    rows: dict[tuple[str, str, date], SourcePrice] = {}
    evidence = []
    first = pages[0]
    for index, page in enumerate(pages, 1):
        day(page.start)
        day(page.end)
        if page.start >= page.end or (page.end - page.start).days > 366:
            raise MarketDataFailure("invalid_window")
        if page.ordinal != index or any(p.terminal for p in pages[: index - 1]):
            raise MarketDataFailure("page_order")
        if (page.start, page.end, page.snapshot_id, page.expected_records) != (
            first.start,
            first.end,
            first.snapshot_id,
            first.expected_records,
        ):
            raise MarketDataFailure("source_changed")
        for row in decode_equity_json(page.body, source_id=source_id, locator=f"page:{index}"):
            if not page.start <= row.session_date < page.end:
                raise MarketDataFailure("row_outside_window")
            if row.key in rows and rows[row.key].values != row.values:
                raise MarketDataFailure("conflicting_duplicate")
            evidence.append(row)
            rows.setdefault(row.key, row)
    complete = (
        pages[-1].terminal
        and bool(first.snapshot_id)
        and first.expected_records is not None
        and first.expected_records == len(rows)
    )
    return JsonPages(tuple(rows.values()), tuple(evidence), complete)


def windows(
    start: date, end: date, *, max_days: int = 31, max_windows: int = 512
) -> tuple[tuple[date, date], ...]:
    day(start)
    day(end)
    if start >= end or not 1 <= max_days <= 366 or max_windows <= 0:
        raise MarketDataFailure("invalid_window")
    if ((end - start).days + max_days - 1) // max_days > max_windows:
        raise MarketDataFailure("window_limit")
    return tuple(
        (start + timedelta(days=n), min(start + timedelta(days=n + max_days), end))
        for n in range(0, (end - start).days, max_days)
    )


@dataclass(frozen=True)
class EquityWindow:
    start: date
    end: date
    url: str
    body: bytes | None
    rows: tuple[SourcePrice, ...]
    failure: str | None


async def fetch_equity_windows(
    transport: DirectTransport,
    symbol: str,
    start: date,
    end: date,
    *,
    max_days: int = 31,
    max_windows: int = 512,
) -> tuple[EquityWindow, ...]:
    """Explicit acquisition only; failed windows retain typed outcomes and raw.

    The observed endpoint has a data-only envelope, no verified cursor contract.
    Bounded requests and a supplied expected session grid detect missing rows;
    HTTP success alone never establishes full requested-session coverage.
    """
    text(symbol)
    result = []
    for left, right in windows(start, end, max_days=max_days, max_windows=max_windows):
        params = {
            "from": left.strftime("%d-%m-%Y"),
            "to": (right - timedelta(days=1)).strftime("%d-%m-%Y"),
            "symbol": symbol,
            "type": "priceVolumeDeliverable",
            "series": "ALL",
        }
        url = (
            "https://www.nseindia.com/api/historicalOR/generateSecurityWiseHistoricalData?"
            + urlencode(params)
        )
        body = None
        try:
            response = await transport.get(url)
            body = response.body
            rows = decode_equity_json(body, source_id="nse-equity-json", locator=url)
            if any(r.symbol != symbol or not left <= r.session_date < right for r in rows):
                raise MarketDataFailure("request_scope_mismatch")
            result.append(EquityWindow(left, right, url, body, rows, None))
        except (MarketDataFailure, TransportFailure) as error:
            result.append(EquityWindow(left, right, url, body, (), error.code))
    return tuple(result)
