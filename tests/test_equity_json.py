"""Independent JSON contracts, exact source decimals and bounded page evidence."""

import asyncio
import json
from collections.abc import Iterator
from datetime import date
from decimal import Decimal

import pytest

from niftyverse.adapters.equity_json import JsonPage, decode_equity_json, merge_pages, windows
from niftyverse.market_prices import MarketDataFailure

D1, D2, D3 = (date(2026, 10, d) for d in (14, 15, 16))
_loop: asyncio.AbstractEventLoop


@pytest.fixture(scope="module", autouse=True)
def transport_loop() -> Iterator[None]:
    # Windows needs its socketpair before the per-test offline guard, matching
    # the transport test boundary. All actual request handling remains mocked.
    global _loop
    _loop = asyncio.new_event_loop()
    yield
    _loop.close()


def wire(on: str = "14-Oct-2026", series: str = "EQ", **changes: object) -> bytes:
    row = {
        "CH_SYMBOL": "ALPHA",
        "CH_SERIES": series,
        "mTIMESTAMP": on,
        "CH_OPENING_PRICE": "100.125",
        "CH_TRADE_HIGH_PRICE": "102.25",
        "CH_TRADE_LOW_PRICE": "99.50",
        "CH_CLOSING_PRICE": "101.2500",
        "CH_TOT_TRADED_QTY": 10,
        "CH_TOT_TRADED_VAL": "1012.5000",
        "CH_TOTAL_TRADES": 3,
        "CH_PREVIOUS_CLS_PRICE": "100.00",
        "CH_LAST_TRADED_PRICE": "101.20",
        "COP_DELIV_QTY": 4,
        "COP_DELIV_PERC": "40.00",
    }
    row.update(changes)
    return json.dumps({"data": [row]}).encode()


def test_exact_decimals_and_independent_schema() -> None:
    rows = decode_equity_json(wire(), source_id="owned-json", locator="page:1")
    row = rows[0]
    assert row.close == Decimal("101.2500") and row.quantity == 10
    assert row.turnover == Decimal("1012.5000") and row.trades == 3
    assert row.session_date == D1 and row.series == "EQ"
    assert row.delivered_quantity == 4 and row.delivered_percent == Decimal("40.00")
    assert dict(row.raw_fields)["CH_CLOSING_PRICE"] == "101.2500"
    assert row.representation == "nse_equity_json_v1" and len(row.raw_sha256) == 64
    numeric = wire().replace(b'"101.2500"', b"101.2500")
    numeric_close = decode_equity_json(numeric, source_id="owned", locator="p")[0].close
    assert numeric_close is not None and numeric_close.as_tuple().exponent == -4


@pytest.mark.parametrize(
    "body,code",
    [
        (b'{"data":', "invalid_json"),
        (b'{"data":[],"data":[]}', "duplicate_json_key"),
        (b'{"error":true,"data":[]}', "source_error"),
        (b'{"data":[{"SLBMH_SYMBOL":"ALPHA"}]}', "schema_drift"),
        (wire(CH_OPENING_PRICE="NaN"), "invalid_number"),
        (wire(CH_TOT_TRADED_QTY=True), "invalid_quantity"),
        (wire(CH_TRADE_LOW_PRICE="105"), "invalid_ohlc"),
        (wire(CH_TOT_TRADED_VAL="-1"), "invalid_number"),
    ],
)
def test_invalid_json_is_atomic(body: bytes, code: str) -> None:
    before = bytes(body)
    with pytest.raises(MarketDataFailure) as error:
        decode_equity_json(body, source_id="owned", locator="page")
    assert error.value.code == code and body == before


def test_changed_required_fields_and_limits() -> None:
    data = json.loads(wire())
    del data["data"][0]["CH_CLOSING_PRICE"]
    with pytest.raises(MarketDataFailure, match="schema_drift"):
        decode_equity_json(json.dumps(data).encode(), source_id="owned", locator="p")
    with pytest.raises(MarketDataFailure, match="byte_limit"):
        decode_equity_json(wire(), source_id="owned", locator="p", max_bytes=5)
    assert decode_equity_json(b'{"data":[]}', source_id="owned", locator="p") == ()


def test_pages_overlaps_truncation_and_nonadvancing_cursor() -> None:
    first = JsonPage(wire(), D1, D3, 1, False, "snapshot-a", 2)
    second = JsonPage(wire("15-Oct-2026"), D1, D3, 2, True, "snapshot-a", 2)
    merged = merge_pages((first, second), source_id="owned")
    assert [r.session_date for r in merged.rows] == [D1, D2] and merged.complete
    assert not merge_pages((first,), source_id="owned").complete
    with pytest.raises(MarketDataFailure, match="page_order"):
        merge_pages((first, first), source_id="owned")
    with pytest.raises(MarketDataFailure, match="source_changed"):
        merge_pages(
            (first, JsonPage(second.body, D1, D3, 2, True, "snapshot-b", 2)), source_id="owned"
        )
    # Identical overlap is retained as evidence, never added to volume/turnover.
    overlap = merge_pages(
        (JsonPage(wire(), D1, D3, 1, False, "a", 1), JsonPage(wire(), D1, D3, 2, True, "a", 1)),
        source_id="owned",
    )
    assert len(overlap.rows) == 1 and len(overlap.evidence) == 2
    with pytest.raises(MarketDataFailure, match="conflicting_duplicate"):
        merge_pages(
            (
                JsonPage(wire(), D1, D3, 1, False, "a", 1),
                JsonPage(wire(CH_TOT_TRADED_QTY=11), D1, D3, 2, True, "a", 1),
            ),
            source_id="owned",
        )


def test_windows_are_half_open_bounded_and_do_not_skip_boundaries() -> None:
    assert windows(D1, date(2026, 10, 19), max_days=2) == (
        (D1, date(2026, 10, 16)),
        (date(2026, 10, 16), date(2026, 10, 18)),
        (date(2026, 10, 18), date(2026, 10, 19)),
    )
    with pytest.raises(MarketDataFailure, match="window_limit"):
        windows(D1, date(2036, 10, 19), max_days=1, max_windows=2)


def test_explicit_acquisition_uses_owned_transport_and_preserves_failed_window() -> None:
    import httpx

    from niftyverse.adapters.equity_json import fetch_equity_windows
    from niftyverse.transport import DirectTransport, FamilyPolicy

    seen = []

    def respond(request: httpx.Request) -> httpx.Response:
        seen.append(dict(request.url.params))
        if request.url.params["from"] == "15-10-2026":
            return httpx.Response(503)
        return httpx.Response(200, content=wire(), headers={"Content-Type": "application/json"})

    async def check() -> None:
        async with DirectTransport(
            FamilyPolicy(spacing=0, attempts=1), transport=httpx.MockTransport(respond)
        ) as transport:
            results = await fetch_equity_windows(transport, "ALPHA", D1, D3, max_days=1)
        assert results[0].rows[0].quantity == 10 and results[0].failure is None
        assert results[1].failure is not None and results[1].rows == ()
        assert seen == [
            {
                "from": "14-10-2026",
                "to": "14-10-2026",
                "symbol": "ALPHA",
                "type": "priceVolumeDeliverable",
                "series": "ALL",
            },
            {
                "from": "15-10-2026",
                "to": "15-10-2026",
                "symbol": "ALPHA",
                "type": "priceVolumeDeliverable",
                "series": "ALL",
            },
        ]

    _loop.run_until_complete(check())
