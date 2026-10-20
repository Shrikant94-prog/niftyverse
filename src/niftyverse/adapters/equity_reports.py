"""Independent source-generation mappings after bounded whole-report decoding."""

import csv
import hashlib
import io
import re
from dataclasses import dataclass
from datetime import date

from niftyverse.delivery import SourceDelivery
from niftyverse.ingestion import IngestionLimits, _source_date, read_report
from niftyverse.market_prices import MarketDataFailure, SourcePrice, number, quantity
from niftyverse.temporal import day, text

DELIVERY_HEADER = tuple(
    (
        "SYMBOL SERIES DATE1 PREV_CLOSE OPEN_PRICE HIGH_PRICE LOW_PRICE LAST_PRICE CLOSE_PRICE "
        "AVG_PRICE TTL_TRD_QNTY TURNOVER_LACS NO_OF_TRADES DELIV_QTY DELIV_PER"
    ).split()
)
MTO_HEADER = (
    "Record Type",
    "Sr No",
    "Name of Security",
    "Quantity Traded",
    "Deliverable Quantity(gross across client level)",
    "% of Deliverable Quantity to Traded Quantity",
)


def decode_cm_prices(
    body: bytes,
    *,
    session: date,
    source_id: str,
    limits: IngestionLimits | None = None,
) -> tuple[SourcePrice, ...]:
    """Validate every source row before returning any selected-universe input."""
    text(source_id)
    report = read_report(body, dataset="cm", session=session, source=source_id, limits=limits)
    fields = (
        (
            "SYMBOL SERIES OPEN HIGH LOW CLOSE TOTTRDQTY TOTTRDVAL TOTALTRADES PREVCLOSE LAST ISIN"
        ).split()
        if report.generation == "cm_legacy"
        else (
            "TckrSymb SctySrs OpnPric HghPric LwPric ClsPric TtlTradgVol TtlTrfVal "
            "TtlNbOfTxsExctd PrvsClsgPric LastPric ISIN"
        ).split()
    )
    result = []
    for row in report.rows:
        raw = dict(zip(report.headers, row.values, strict=True))
        symbol, series, op, high, low, close, qty, turnover, trades, previous, last, isin = fields
        result.append(
            SourcePrice(
                raw[symbol],
                raw[series],
                session,
                number(raw[op]),
                number(raw[high]),
                number(raw[low]),
                number(raw[close]),
                quantity(raw[qty]),
                number(raw[turnover]),
                source_id,
                report.generation,
                report.sha256,
                f"{report.member}:{row.line}",
                tuple(raw.items()),
                trades=quantity(raw[trades]),
                settlement=number(raw.get("SttlmPric")),
                previous_close=number(raw[previous]),
                last=number(raw[last]),
                isin=raw[isin] or None,
            )
        )
    return tuple(result)


@dataclass(frozen=True)
class DeliveryReport:
    rows: tuple[SourceDelivery, ...]
    generation: str
    complete: bool
    raw_sha256: str


def decode_delivery(
    body: bytes,
    *,
    session: date,
    source_id: str,
    expected_rows: int | None = None,
    max_bytes: int = 8 * 1024 * 1024,
    max_rows: int = 100_000,
) -> DeliveryReport:
    day(session)
    text(source_id)
    if not isinstance(body, bytes) or len(body) > max_bytes:
        raise MarketDataFailure("byte_limit")
    try:
        reader = csv.reader(io.StringIO(body.decode("utf-8-sig"), newline=""), strict=True)
        first = next(reader, [])
        sha = hashlib.sha256(body).hexdigest()
        headers: tuple[str, ...]
        declared_count = None
        declared_delivery = None
        if first == ["Security Wise Delivery Position - Compulsory Rolling Settlement"]:
            generation = "mto_v1"
            metadata = next(reader, [])
            if len(metadata) != 5 or metadata[:2] != ["10", "MTO"]:
                raise MarketDataFailure("invalid_metadata")
            if metadata[2] != session.strftime("%d%m%Y"):
                raise MarketDataFailure("session_mismatch")
            declared_delivery = quantity(metadata[3])
            declared_count = quantity(metadata[4])
            timing = ",".join(next(reader, []))
            match = re.match(
                r"Trade Date <([^>]+)>,Settlement Type <[^>]+>,"
                r"Settlement No <[^>]+>,Settlement Date <[^>]+>$",
                timing,
            )
            if match is None or _source_date(match[1], True) != session:
                raise MarketDataFailure("session_mismatch")
            if tuple(next(reader, [])) != MTO_HEADER:
                raise MarketDataFailure("unsupported_generation")
            headers = (
                "record_type",
                "serial",
                "symbol",
                "series",
                "traded_quantity",
                "delivered_quantity",
                "published_percent",
            )
        elif tuple(v.strip() for v in first) == DELIVERY_HEADER:
            generation = "delivery_csv_v1"
            headers = DELIVERY_HEADER
        else:
            raise MarketDataFailure("unsupported_generation")
        result = []
        keys = set()
        for index, values in enumerate(reader, 1):
            if index > max_rows:
                raise MarketDataFailure("row_limit")
            if len(values) != len(headers):
                raise MarketDataFailure("row_width")
            raw = dict(zip(headers, (v.strip() for v in values), strict=True))
            if generation == "mto_v1":
                if raw["record_type"] != "20":
                    raise MarketDataFailure("unsupported_record")
                if quantity(raw["serial"]) != index:
                    raise MarketDataFailure("record_sequence")
                row = SourceDelivery(
                    raw["symbol"],
                    raw["series"],
                    session,
                    quantity(raw["traded_quantity"]),
                    quantity(raw["delivered_quantity"]),
                    number(raw["published_percent"]),
                    source_id,
                    generation,
                    sha,
                    f"record:{index}",
                    tuple(raw.items()),
                )
            else:
                if _source_date(raw["DATE1"], True) != session:
                    raise MarketDataFailure("session_mismatch")
                # The combined report includes prices: poisoned unselected rows
                # cannot escape whole-source validation by projecting delivery.
                SourcePrice(
                    raw["SYMBOL"],
                    raw["SERIES"],
                    session,
                    number(raw["OPEN_PRICE"]),
                    number(raw["HIGH_PRICE"]),
                    number(raw["LOW_PRICE"]),
                    number(raw["CLOSE_PRICE"]),
                    quantity(raw["TTL_TRD_QNTY"]),
                    number(raw["TURNOVER_LACS"]),
                    source_id,
                    generation,
                    sha,
                    f"row:{index}",
                    tuple(raw.items()),
                    trades=quantity(raw["NO_OF_TRADES"]),
                    previous_close=number(raw["PREV_CLOSE"]),
                    last=number(raw["LAST_PRICE"]),
                    turnover_unit="INR_lakh",
                )
                row = SourceDelivery(
                    raw["SYMBOL"],
                    raw["SERIES"],
                    session,
                    quantity(raw["TTL_TRD_QNTY"]),
                    quantity(raw["DELIV_QTY"]),
                    number(raw["DELIV_PER"]),
                    source_id,
                    generation,
                    sha,
                    f"row:{index}",
                    tuple(raw.items()),
                    number(raw["TURNOVER_LACS"]),
                    "INR_lakh",
                )
            if row.key in keys:
                raise MarketDataFailure("duplicate_key")
            keys.add(row.key)
            result.append(row)
        if (
            not result
            or (declared_count is not None and declared_count != len(result))
            or (expected_rows is not None and expected_rows != len(result))
        ):
            raise MarketDataFailure("incomplete_report")
        if declared_delivery is not None and (
            any(r.delivered_quantity is None for r in result)
            or sum(r.delivered_quantity or 0 for r in result) != declared_delivery
        ):
            raise MarketDataFailure("delivery_total_mismatch")
        return DeliveryReport(
            tuple(result), generation, declared_count is not None or expected_rows is not None, sha
        )
    except UnicodeError, csv.Error:
        raise MarketDataFailure("invalid_csv") from None
