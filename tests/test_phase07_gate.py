"""PH-07-GATE: independent source decoding through dated, scoped selection."""

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from typing import Literal

import pytest
from test_equity_json import D1, D2, D3, wire
from test_equity_selection import KNOWN, calendar, catalogue
from test_ingestion import CM, archive

from niftyverse.adapters.equity_json import decode_equity_json
from niftyverse.adapters.equity_reports import decode_cm_prices
from niftyverse.equity_quality import QualityPolicy
from niftyverse.identity import Alias, Instrument, ListingSelectionPolicy
from niftyverse.market_prices import EquityResult, SourcePrice, normalize_equities


@pytest.mark.parametrize("asset_type,unit", [("equity", "shares"), ("etf", "fund_units")])
def test_phase07_integrated_gate(asset_type: Literal["equity", "etf"], unit: str) -> None:
    cat = catalogue()
    cat = replace(
        cat,
        instruments=(
            Instrument("a", None, asset_type, "Fund or company"),
            Instrument("dead", None, asset_type, "Dead security"),
        ),
        aliases=tuple(
            replace(a, identifier="NEW" if a.evidence.valid_from == D3 else "OLD")
            for a in cat.aliases
        ),
    )
    dead = replace(
        cat.listings[0],
        listing_id="dead",
        instrument_id="dead",
        status="delisted",
        evidence=replace(cat.listings[0].evidence, valid_to=None),
    )
    cat = replace(
        cat,
        listings=cat.listings + (dead,),
        aliases=cat.aliases
        + tuple(Alias("INF000000001", "isin", r.listing_id, r.evidence) for r in cat.listings),
    )
    source: list[SourcePrice] = []
    for on, label, series, symbol in [
        (D1, "14-Oct-2026", "EQ", "OLD"),
        (D2, "15-Oct-2026", "BE", "OLD"),
        (D3, "16-Oct-2026", "EQ", "NEW"),
        (D2, "15-Oct-2026", "BL", "OLD"),
    ]:
        source.extend(
            decode_equity_json(
                wire(label, series).replace(b"ALPHA", symbol.encode()),
                source_id="json",
                locator=label + series,
            )
        )
        csv = (
            CM
            + (
                f"{symbol},{series},100.125,102.25,99.50,101.25,101.20,100,10,1012.5000,"
                f"{on.strftime('%d-%b-%Y').upper()},3,INF000000001,\n"
            ).encode()
        )
        source.extend(decode_cm_prices(archive(("cm.csv", csv)), session=on, source_id="archive"))

    def normalize(rows: tuple[SourcePrice, ...], policy: ListingSelectionPolicy) -> EquityResult:
        return normalize_equities(
            rows,
            catalogue=cat,
            calendar=calendar(),
            instrument_ids=("a", "dead"),
            start=D1,
            end=D3 + timedelta(days=1),
            known_at=KNOWN,
            policy=policy,
            source_complete=True,
            asset_type=asset_type,
            preferred_representations=("cm_legacy",),
            tolerances=QualityPolicy("gate-v1").tolerances,
        )

    result = normalize(tuple(source), ListingSelectionPolicy("ordinary"))
    assert [r.source.series for r in result.rows] == ["EQ", "BE", "EQ"]
    assert {r.quantity_unit for r in result.rows} == {unit}
    assert sum(r.source.quantity or 0 for r in result.rows) == 30
    assert sum(r.source.turnover or Decimal(0) for r in result.rows) == Decimal("3037.5000")
    assert [(g.instrument_id, g.reason) for g in result.gaps] == [("dead", "not_listed")] * 3
    assert all(len(r.evidence) == 2 and r.source.price_basis == "raw_traded" for r in result.rows)
    assert all(
        r.source.open == Decimal("100.125")
        and r.source.high == Decimal("102.25")
        and r.source.low == Decimal("99.50")
        and r.source.close == Decimal("101.25")
        for r in result.rows
    )
    eq_only = normalize(tuple(source), ListingSelectionPolicy("eq-only", ("EQ",)))
    assert len(eq_only.rows) == 2
    assert [(g.on, g.reason) for g in eq_only.gaps if g.instrument_id == "a"] == [
        (D2, "policy_exclusion")
    ]
    missing = normalize(
        tuple(r for r in source if r.session_date != D2), ListingSelectionPolicy("ordinary")
    )
    assert len(missing.rows) == 2 and any(
        g.on == D2 and g.reason == "missing_observation" for g in missing.gaps
    )
    conflict = normalize(
        tuple(
            replace(r, turnover=Decimal("2000"))
            if r.session_date == D3 and r.source_id == "archive"
            else r
            for r in source
        ),
        ListingSelectionPolicy("ordinary"),
    )
    assert len(conflict.rows) == 2 and conflict.coverage == "quarantined"
    gap = next(g for g in conflict.gaps if g.reason == "representation_conflict")
    assert gap.on == D3 and {r.source_id for r in gap.evidence} == {"json", "archive"}
