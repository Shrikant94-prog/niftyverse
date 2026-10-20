"""Owned report generations, whole-source validation and delivery definitions."""

from collections.abc import Callable
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from test_ingestion import CM, ROW, archive

from niftyverse.adapters.equity_reports import decode_cm_prices, decode_delivery
from niftyverse.delivery import delivery_fraction
from niftyverse.market_prices import MarketDataFailure, choose_representation

OLD = date(2016, 9, 1)
NEW = date(2026, 10, 16)
DELIVERY_HEADER = (
    b"SYMBOL, SERIES, DATE1, PREV_CLOSE, OPEN_PRICE, HIGH_PRICE, LOW_PRICE, "
    b"LAST_PRICE, CLOSE_PRICE, AVG_PRICE, TTL_TRD_QNTY, TURNOVER_LACS, "
    b"NO_OF_TRADES, DELIV_QTY, DELIV_PER\n"
)
DELIVERY_ROW = b"ABC, EQ, 16-Oct-2026, 1, 1, 2, 1, 1.5, 1.5, 1.5, 10, 0.00015, 3, 4, 40.00\n"
OLD_HEADER = (
    b"Security Wise Delivery Position - Compulsory Rolling Settlement\n"
    b"10,MTO,01092016,4,0000001\n"
    b"Trade Date <01-SEP-2016>,Settlement Type <N>,Settlement No <2016166>,"
    b"Settlement Date <06-SEP-2016>\n"
    b"Record Type,Sr No,Name of Security,Quantity Traded,"
    b"Deliverable Quantity(gross across client level),"
    b"% of Deliverable Quantity to Traded Quantity\n"
)


def test_bhavcopy_generation_values_and_raw_representation() -> None:
    legacy = decode_cm_prices(archive(("report.csv", CM + ROW)), session=OLD, source_id="owned")
    assert legacy[0].close == Decimal("1.50") and legacy[0].quantity == 10
    assert legacy[0].turnover == Decimal("15.00")
    assert legacy[0].representation == "cm_legacy"
    assert dict(legacy[0].raw_fields)["TOTTRDVAL"] == "15.00"
    payload = (Path(__file__).parent / "fixtures/reports/cm-udiff.csv").read_bytes()
    current = decode_cm_prices(archive(("report.csv", payload)), session=NEW, source_id="owned")
    assert current[0].close == Decimal("1211.20")
    assert current[0].settlement == Decimal("1211.19")
    assert current[0].trades == 247276 and current[0].quantity == 17225283
    assert current[0].turnover == Decimal("20794678894.30")
    assert current[0].representation == "cm_udiff"


def test_invalid_unselected_source_row_poison_is_atomic() -> None:
    poisoned = CM + ROW + ROW.replace(b"ABC", b"OTHER").replace(b",10,", b",-10,")
    with pytest.raises(MarketDataFailure, match="invalid_number"):
        decode_cm_prices(archive(("report.csv", poisoned)), session=OLD, source_id="owned")


def test_delivery_generations_totals_dates_and_fraction() -> None:
    old = decode_delivery(OLD_HEADER + b"20,1,ABC,EQ,10,4,40.00\n", session=OLD, source_id="owned")
    assert old.complete and old.generation == "mto_v1"
    assert old.rows[0].traded_quantity == 10 and old.rows[0].delivered_quantity == 4
    current = decode_delivery(
        DELIVERY_HEADER + DELIVERY_ROW, session=NEW, source_id="owned", expected_rows=1
    )
    assert current.complete and current.generation == "delivery_csv_v1"
    assert current.rows[0].source_turnover == Decimal("0.00015")
    assert current.rows[0].source_turnover_unit == "INR_lakh"
    assert current.rows[0].turnover_inr == Decimal("15.00000")
    fraction = delivery_fraction(current.rows[0])
    assert fraction.value == Decimal("0.400000000000") and fraction.reason is None
    assert fraction.published_percent == Decimal("40.00")
    unknown = replace(current.rows[0], quantity_definition="unknown")
    assert delivery_fraction(unknown).value is None
    assert delivery_fraction(unknown).reason == "incompatible_quantity_definition"


@pytest.mark.parametrize(
    "mutation,code",
    [
        (lambda b: b.replace(b"0000001", b"0000002"), "incomplete_report"),
        (lambda b: b.replace(b"01092016", b"02092016"), "session_mismatch"),
        (
            lambda b: b.replace(b"10,MTO,01092016,4", b"10,MTO,01092016,5"),
            "delivery_total_mismatch",
        ),
        (lambda b: b.replace(b"20,1,", b"30,1,"), "unsupported_record"),
    ],
)
def test_old_delivery_invalid_metadata_rejects(
    mutation: Callable[[bytes], bytes], code: str
) -> None:
    with pytest.raises(MarketDataFailure, match=code):
        decode_delivery(
            mutation(OLD_HEADER + b"20,1,ABC,EQ,10,4,40.00\n"), session=OLD, source_id="owned"
        )


def test_delivery_blank_zero_unknown_totals_and_incompatible_price() -> None:
    row = decode_delivery(DELIVERY_HEADER + DELIVERY_ROW, session=NEW, source_id="owned").rows[0]
    assert delivery_fraction(replace(row, delivered_quantity=None)).reason == "delivery_absent"
    assert (
        delivery_fraction(replace(row, traded_quantity=0, delivered_quantity=0)).reason
        == "zero_comparable_total"
    )
    assert (
        delivery_fraction(replace(row, traded_quantity=None)).reason == "unknown_comparable_total"
    )
    assert delivery_fraction(
        replace(row, delivered_quantity=0, published_percent=Decimal(0))
    ).value == Decimal(0)
    assert (
        delivery_fraction(replace(row, published_percent=Decimal("90"))).reason
        == "published_fraction_conflict"
    )
    price = decode_cm_prices(archive(("r.csv", CM + ROW)), session=OLD, source_id="owned")[0]
    assert delivery_fraction(row, price).reason == "incompatible_listing_series_session"
    price = replace(price, session_date=NEW)
    assert (
        delivery_fraction(row, replace(price, quantity_definition="contracts")).reason
        == "incompatible_quantity_definition"
    )
    assert (
        delivery_fraction(row, replace(price, quantity=11)).reason == "comparable_total_conflict"
    )


def test_delivery_truncation_generation_and_whole_source_validation() -> None:
    partial = decode_delivery(DELIVERY_HEADER + DELIVERY_ROW, session=NEW, source_id="owned")
    assert not partial.complete
    with pytest.raises(MarketDataFailure, match="incomplete_report"):
        decode_delivery(
            DELIVERY_HEADER + DELIVERY_ROW, session=NEW, source_id="owned", expected_rows=2
        )
    with pytest.raises(MarketDataFailure, match="unsupported_generation"):
        decode_delivery(b"Symbol,Total,NewColumn\nA,1,2\n", session=NEW, source_id="owned")
    with pytest.raises(MarketDataFailure, match="invalid_number"):
        decode_delivery(
            DELIVERY_HEADER
            + DELIVERY_ROW
            + DELIVERY_ROW.replace(b"ABC", b"OTHER").replace(b", 4,", b", -4,"),
            session=NEW,
            source_id="owned",
        )


def test_representation_selection_is_explicit_and_retains_competitors() -> None:
    original = decode_cm_prices(archive(("report.csv", CM + ROW)), session=OLD, source_id="owned")[
        0
    ]
    other = replace(original, representation="nse_equity_json_v1", raw_sha256="b" * 64)
    selected = choose_representation(
        (other, original), preferred=("cm_legacy", "nse_equity_json_v1")
    )
    assert selected.selected == original and selected.evidence == (other, original)
    conflict = choose_representation(
        (original, replace(other, quantity=11)), preferred=("cm_legacy",)
    )
    assert conflict.selected is None and conflict.reason == "representation_conflict"
    units = choose_representation(
        (original, replace(other, turnover_unit="INR_lakh")), preferred=("cm_legacy",)
    )
    assert units.selected is None and units.reason == "incompatible_units"


def test_turnover_unit_conversion_preserves_full_supported_precision() -> None:
    row = decode_delivery(DELIVERY_HEADER + DELIVERY_ROW, session=NEW, source_id="owned").rows[0]
    precise = replace(row, source_turnover=Decimal("1234567890123456789012345.12345678"))
    assert precise.turnover_inr == Decimal("123456789012345678901234512345.678")
