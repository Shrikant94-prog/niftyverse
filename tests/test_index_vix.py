"""Historical VIX capability must be source/window verified; current never substitutes."""

import json
from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from test_indices import D1, D2, KNOWN, PRICE, calendar, catalogue

from niftyverse.adapters.index_history import assess_vix_capability, decode_vix_history
from niftyverse.core import ValidationError
from niftyverse.indices import IndexAlias, IndexCatalogue, IndexPrice, IndexVariant

VIX = IndexVariant("india-vix", "india-vix", "volatility")


def vix_catalogue() -> IndexCatalogue:
    evidence = catalogue().aliases[0].evidence
    return IndexCatalogue(
        "vix-v1", (VIX,), (IndexAlias("owned", "INDIA VIX", VIX.variant_id, evidence),)
    )


def wire(**changes: object) -> bytes:
    row: dict[str, Any] = {
        "EOD_TIMESTAMP": "14-OCT-2026",
        "EOD_INDEX_NAME": "INDIA VIX",
        "EOD_OPEN_INDEX_VAL": "14.12",
        "EOD_HIGH_INDEX_VAL": "15.015",
        "EOD_LOW_INDEX_VAL": "13.795",
        "EOD_CLOSE_INDEX_VAL": "14.63",
        "HI_TIMESTAMP_ORDER": "2026-10-13T18:30:00.000Z",
        "VIX_PTS_CHG": "-0.4",
    }
    row.update(changes)
    return json.dumps({"data": [row]}).encode()


def decode(body: bytes) -> tuple[IndexPrice, ...]:
    return decode_vix_history(
        body,
        catalogue=vix_catalogue(),
        variant=VIX,
        source_id="owned",
        locator="vix",
        start=D1,
        end=D2,
        known_at=KNOWN,
    )


def test_actual_source_date_and_exact_numeric_volatility_levels() -> None:
    body = wire().replace(b'"15.015"', b"15.0150")
    row = decode(body)[0]
    assert row.session_date == D1 and row.variant == VIX
    assert row.high is not None and row.high.as_tuple().exponent == -4
    assert row.close == Decimal("14.63")
    assert row.unit == "volatility_percent_annualised"
    assert dict(row.lineage.raw_fields)["HI_TIMESTAMP_ORDER"] == "2026-10-13T18:30:00.000Z"
    capability = assess_vix_capability(
        body,
        catalogue=vix_catalogue(),
        variant=VIX,
        source_id="owned",
        locator="vix",
        start=D1,
        end=D2,
        observed_at=KNOWN,
        calendar=calendar(),
    )
    assert capability.status == "experimental" and capability.verified_sessions == (D1,)
    assert capability.start == D1 and capability.end == D2 and capability.reason is None


@pytest.mark.parametrize(
    "body,reason",
    [
        (b'{"data":[{"index":"INDIA VIX","last":14.63}]}', "current_only_capability"),
        (b'{"data":[]}', "incomplete_historical_window"),
        (b'{"error":"unavailable"}', "schema"),
        (wire(EOD_INDEX_NAME="NIFTY 50"), "unresolved"),
        (wire(EOD_TIMESTAMP="15-OCT-2026"), "outside"),
        (wire(EOD_CLOSE_INDEX_VAL="NaN"), "number"),
        (wire(EOD_LOW_INDEX_VAL="20"), "OHLC"),
    ],
)
def test_unverified_current_empty_or_bad_history_is_explicitly_blocked(
    body: bytes, reason: str
) -> None:
    result = assess_vix_capability(
        body,
        catalogue=vix_catalogue(),
        variant=VIX,
        source_id="owned",
        locator="vix",
        start=D1,
        end=D2,
        observed_at=KNOWN,
        calendar=calendar(),
    )
    assert result.status == "blocked" and result.reason is not None and reason in result.reason
    assert result.verified_sessions == () and result.raw_sha256


def test_capability_cannot_claim_an_unobserved_interval_or_wrong_variant() -> None:
    result = assess_vix_capability(
        wire(),
        catalogue=vix_catalogue(),
        variant=VIX,
        source_id="owned",
        locator="vix",
        start=D1,
        end=date(2026, 10, 16),
        observed_at=KNOWN,
        calendar=calendar(),
    )
    assert result.status == "blocked" and result.verified_sessions == ()
    with pytest.raises(ValidationError, match="variant"):
        decode_vix_history(
            wire(),
            catalogue=vix_catalogue(),
            variant=PRICE,
            source_id="owned",
            locator="vix",
            start=D1,
            end=D2,
            known_at=KNOWN,
        )
    unknown = replace(calendar(), sessions=())
    result = assess_vix_capability(
        wire(),
        catalogue=vix_catalogue(),
        variant=VIX,
        source_id="owned",
        locator="vix",
        start=D1,
        end=D2,
        observed_at=KNOWN,
        calendar=unknown,
    )
    assert result.status == "blocked"
