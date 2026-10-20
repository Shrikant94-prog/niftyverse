"""Separate source schemas, variants, null/zero and manually expected date joins."""

import json
from dataclasses import replace
from decimal import Decimal
from typing import Any

import pytest
from test_indices import D1, D2, D3, GROSS, KNOWN, LINEAGE, NET, PRICE, calendar, catalogue, price

from niftyverse.adapters.index_history import decode_index_tri, decode_index_valuations
from niftyverse.core import ValidationError
from niftyverse.indices import IndexTRI, IndexValuation, index_history, join_index_datasets


def valuation_wire(on: str = "14 Oct 2026", **changes: object) -> bytes:
    row: dict[str, Any] = {
        "Index Name": "Nifty 50",
        "DATE": on,
        "pe": "19.33",
        "pb": "2.78",
        "divYield": "1.52",
    }
    row.update(changes)
    return json.dumps([row]).encode()


def tri_wire(on: str = "15 Oct 2026", **changes: object) -> bytes:
    row: dict[str, Any] = {
        "Index Name": "Nifty 50",
        "Date": on,
        "TotalReturnsIndex": "34948.42",
        "NTR_Value": "30346.43",
    }
    row.update(changes)
    return json.dumps([row]).encode()


def values(body: bytes) -> tuple[IndexValuation, ...]:
    return decode_index_valuations(
        body,
        catalogue=catalogue(),
        variant=PRICE,
        source_id="owned",
        locator="v",
        start=D1,
        end=D3,
        known_at=KNOWN,
    )


def tris(body: bytes, variant: Any = GROSS) -> tuple[IndexTRI, ...]:
    return decode_index_tri(
        body,
        catalogue=catalogue(),
        variant=variant,
        source_id="owned",
        locator="t",
        start=D1,
        end=D3,
        known_at=KNOWN,
    )


def test_separate_source_schemas_and_true_null_zero() -> None:
    v = values(valuation_wire(pe=None, pb="0", divYield="0.0000"))[0]
    assert v.pe is None and v.pb == 0 and v.dividend_yield == Decimal("0.0000")
    assert v.missing_fields == ("pe",)
    assert v.assumptions == ("pe_unavailable", "pb_nonpositive")
    assert dict(v.lineage.raw_fields)["pe"] is None
    assert v.ratio_unit == "ratio" and v.yield_unit == "percent"
    gross, net = tris(tri_wire())[0], tris(tri_wire(), NET)[0]
    assert gross.value == Decimal("34948.42") and net.value == Decimal("30346.43")
    assert gross.variant == GROSS and net.variant == NET
    assert gross.lineage.raw_sha256 == net.lineage.raw_sha256
    assert tris(tri_wire(NTR_Value=None), NET)[0].value is None
    assert tris(tri_wire(TotalReturnsIndex="0"))[0].value == 0
    negative = values(valuation_wire(pe="-2.5"))[0]
    assert negative.pe == Decimal("-2.5") and "pe_nonpositive" in negative.assumptions


def test_outer_join_does_not_manufacture_valuation_dates_or_relabel_tri() -> None:
    result = join_index_datasets(
        variant=PRICE,
        prices=(price(), price(D3)),
        valuations=values(valuation_wire()),
        tri=tris(tri_wire()) + tris(tri_wire(), NET),
    )
    assert tuple(r.session_date for r in result) == (D1, D2, D3)
    assert result[0].price == price() and result[0].valuation == values(valuation_wire())[0]
    assert result[0].gross_tri is None and result[0].net_tri is None
    assert result[1].price is None and result[1].valuation is None
    assert result[1].gross_tri == tris(tri_wire())[0]
    assert result[1].net_tri == tris(tri_wire(), NET)[0]
    assert result[2].valuation is None and result[2].price == price(D3)


def test_nullable_dataset_coverage_is_independent() -> None:
    v = values(valuation_wire(pe=None))
    result = index_history(
        v,
        variant=PRICE,
        start=D1,
        end=D2,
        calendar=calendar(),
        known_at=KNOWN,
        source_complete=True,
    )
    assert result.coverage == "partial" and result.gaps == ((D1, "source_null:pe"),)
    gross = tris(tri_wire())
    result_tri = index_history(
        gross,
        variant=GROSS,
        start=D1,
        end=D3,
        calendar=calendar(),
        known_at=KNOWN,
        source_complete=True,
    )
    assert result_tri.gaps == ((D1, "missing_observation"),)
    assert result_tri.rows == gross


@pytest.mark.parametrize(
    "body,decoder,reason",
    [
        (valuation_wire(divYield="-1"), values, "yield"),
        (valuation_wire(pe="NaN"), values, "number"),
        (tri_wire(TotalReturnsIndex="-1"), tris, "number"),
        (valuation_wire(), tris, "schema"),
        (tri_wire(), values, "schema"),
    ],
)
def test_wrong_schema_and_invalid_values_fail(body: bytes, decoder: Any, reason: str) -> None:
    with pytest.raises(ValidationError, match=reason):
        decoder(body)


def test_wrong_variants_in_decoder_constructor_join_and_history() -> None:
    with pytest.raises(ValidationError, match="variant"):
        tris(tri_wire(), PRICE)
    with pytest.raises(ValidationError, match="variant"):
        IndexValuation(GROSS, D1, Decimal(1), Decimal(2), Decimal(3), LINEAGE)
    with pytest.raises(ValidationError, match="variant"):
        IndexTRI(PRICE, D1, Decimal(1), LINEAGE)
    with pytest.raises(ValidationError, match="duplicate"):
        join_index_datasets(variant=PRICE, prices=(price(), price()), valuations=(), tri=())
    with pytest.raises(ValidationError, match="index"):
        join_index_datasets(
            variant=PRICE,
            prices=(),
            valuations=(),
            tri=(replace(tris(tri_wire())[0], variant=replace(GROSS, index_id="other")),),
        )
    with pytest.raises(ValidationError, match="dataset"):
        index_history(
            (price(), values(valuation_wire())[0]),
            variant=PRICE,
            start=D1,
            end=D2,
            calendar=calendar(),
            known_at=KNOWN,
            source_complete=True,
        )
