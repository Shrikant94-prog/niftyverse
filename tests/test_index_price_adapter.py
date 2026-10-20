"""Independent manually specified historical price wire contract and negatives."""

import hashlib
import json
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from test_indices import D1, D2, KNOWN, PRICE, catalogue

from niftyverse.adapters.index_history import decode_index_prices
from niftyverse.core import ValidationError
from niftyverse.indices import IndexPrice


def wire(**changes: object) -> bytes:
    row: dict[str, Any] = {
        "INDEX_NAME": "Nifty 50",
        "HistoricalDate": "14 Oct 2026",
        "OPEN": "22715.75",
        "HIGH": "22757.95",
        "LOW": "22558.95",
        "CLOSE": "22622.70",
    }
    row.update(changes)
    return json.dumps([row]).encode()


def decode(body: bytes) -> tuple[IndexPrice, ...]:
    return decode_index_prices(
        body,
        catalogue=catalogue(),
        variant=PRICE,
        source_id="owned",
        locator="capture:p",
        start=D1,
        end=D2,
        known_at=KNOWN,
    )


def test_price_source_exact_decimal_actual_date_and_lineage() -> None:
    row = decode(wire())[0]
    assert row.variant == PRICE and row.session_date == D1
    assert (row.open, row.high, row.low, row.close) == tuple(
        map(Decimal, ("22715.75", "22757.95", "22558.95", "22622.70"))
    )
    assert row.lineage.raw_sha256 == hashlib.sha256(wire()).hexdigest()
    assert row.lineage.locator == "capture:p#0"
    assert dict(row.lineage.raw_fields)["CLOSE"] == "22622.70"
    assert decode(b"[]") == ()


@pytest.mark.parametrize(
    "body,reason",
    [
        (b'{"last":100,"index":"Nifty 50"}', "schema"),
        (wire(INDEX_NAME="NIFTYBEES"), "unresolved"),
        (wire(HistoricalDate="15 Oct 2026"), "outside"),
        (wire(HistoricalDate="31 Feb 2026"), "date"),
        (wire(CLOSE="NaN"), "number"),
        (wire(LOW="24000"), "OHLC"),
        (wire(CLOSE=True), "number"),
        (b'[{"INDEX_NAME":"a","INDEX_NAME":"b"}]', "duplicate"),
        (b'{"error":true}', "schema"),
        (wire().replace(b'"22622.70"', b"NaN"), "number"),
    ],
)
def test_bad_source_never_returns_success(body: bytes, reason: str) -> None:
    with pytest.raises(ValidationError, match=reason):
        decode(body)


def test_duplicate_dates_critical_fields_and_limits() -> None:
    body = json.loads(wire())
    with pytest.raises(ValidationError, match="duplicate"):
        decode(json.dumps(body + body).encode())
    del body[0]["CLOSE"]
    with pytest.raises(ValidationError, match="schema"):
        decode(json.dumps(body).encode())
    with pytest.raises(ValidationError, match="byte_limit"):
        decode_index_prices(
            wire(),
            catalogue=catalogue(),
            variant=PRICE,
            source_id="owned",
            locator="p",
            start=D1,
            end=D2,
            known_at=KNOWN,
            max_bytes=10,
        )
    with pytest.raises(ValidationError, match="window"):
        decode_index_prices(
            wire(),
            catalogue=catalogue(),
            variant=PRICE,
            source_id="owned",
            locator="p",
            start=D2,
            end=D1,
            known_at=KNOWN,
        )
    with pytest.raises(ValidationError, match="row_limit"):
        decode_index_prices(
            wire(),
            catalogue=catalogue(),
            variant=PRICE,
            source_id="owned",
            locator="p",
            start=D1,
            end=date(2026, 10, 16),
            known_at=KNOWN,
            max_rows=0,
        )
