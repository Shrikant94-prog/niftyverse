"""Owned index identity and coverage cases; no provider support inferred."""

from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest

from niftyverse.calendars import Calendar, Session
from niftyverse.core import ValidationError
from niftyverse.indices import (
    IndexAlias,
    IndexCatalogue,
    IndexHistory,
    IndexPrice,
    IndexVariant,
    SourceLineage,
    index_history,
)
from niftyverse.temporal import Evidence

D1, D2, D3 = (date(2026, 10, n) for n in (14, 15, 16))
KNOWN = datetime(2026, 10, 20, tzinfo=UTC)
PRICE = IndexVariant("n50-price", "n50", "price")
GROSS = IndexVariant("n50-gross", "n50", "gross_tri")
NET = IndexVariant("n50-net", "n50", "net_tri")
LINEAGE = SourceLineage("owned", "a" * 64, "p#0", "owned-v1", (("Close", "100.1250"),))


def catalogue() -> IndexCatalogue:
    evidence = Evidence(date(2016, 1, 1), None, KNOWN, "owned", "aliases")
    return IndexCatalogue(
        "owned-v1",
        (PRICE, GROSS, NET),
        tuple(
            IndexAlias("owned", "NIFTY 50", v.variant_id, evidence) for v in (PRICE, GROSS, NET)
        ),
    )


def calendar() -> Calendar:
    return Calendar(
        "owned-grid",
        "NSE",
        "index",
        KNOWN,
        tuple(
            Session(
                on,
                "trading",
                datetime(2026, 10, on.day, 4, tzinfo=UTC),
                datetime(2026, 10, on.day, 10, tzinfo=UTC),
                "Asia/Kolkata",
                "owned",
                "grid",
            )
            for on in (D1, D2, D3)
        ),
    )


def price(on: date = D1) -> IndexPrice:
    return IndexPrice(
        PRICE, on, Decimal("100"), Decimal("102"), Decimal("99"), Decimal("100.1250"), LINEAGE
    )


def test_variants_and_dated_source_aliases_are_explicit() -> None:
    cat = catalogue()
    assert cat.resolve("owned", "NIFTY 50", "price", D1, KNOWN) == PRICE
    assert cat.resolve("owned", "NIFTY 50", "gross_tri", D1, KNOWN) == GROSS
    assert cat.resolve("owned", "NIFTY 50", "net_tri", D1, KNOWN) == NET
    with pytest.raises(ValidationError, match="unresolved"):
        cat.resolve("owned", "NIFTYBEES", "price", D1, KNOWN)
    with pytest.raises(ValidationError, match="unresolved"):
        cat.resolve("owned", "NIFTY 50", "price", date(2015, 12, 31), KNOWN)
    with pytest.raises(ValidationError, match="unresolved"):
        cat.resolve("owned", "NIFTY 50", "price", D1, datetime(2026, 1, 1, tzinfo=UTC))
    other = IndexVariant("collision", "other", "price")
    collision = replace(
        cat,
        variants=(*cat.variants, other),
        aliases=(*cat.aliases, replace(cat.aliases[0], variant_id="collision")),
    )
    with pytest.raises(ValidationError, match="ambiguous"):
        collision.resolve("owned", "NIFTY 50", "price", D1, KNOWN)


def test_history_retains_true_dates_exact_values_and_missing_grid() -> None:
    result = index_history(
        (price(), price(D3)),
        variant=PRICE,
        start=D1,
        end=date(2026, 10, 17),
        calendar=calendar(),
        known_at=KNOWN,
        source_complete=True,
    )
    assert tuple(r.session_date for r in result.rows) == (D1, D3)
    assert result.rows[0].close == Decimal("100.1250")
    assert result.rows[0].lineage == LINEAGE
    assert result.gaps == ((D2, "missing_observation"),) and result.coverage == "partial"
    empty: IndexHistory[IndexPrice] = index_history(
        (),
        variant=PRICE,
        start=D1,
        end=D2,
        calendar=calendar(),
        known_at=KNOWN,
        source_complete=False,
    )
    assert empty.rows == () and empty.coverage == "partial"
    assert empty.gaps == ((D1, "source_unverified"),)


def test_wrong_variant_date_duplicates_and_unknown_calendar_never_fill() -> None:
    options: dict[str, Any] = dict(
        variant=PRICE, start=D1, end=D2, calendar=calendar(), known_at=KNOWN, source_complete=True
    )
    for rows, message in [
        ((replace(price(), variant=IndexVariant("vix", "vix", "volatility")),), "variant"),
        ((price(D2),), "outside"),
        ((price(), price()), "duplicate"),
    ]:
        with pytest.raises(ValidationError, match=message):
            index_history(rows, **options)
    unknown = replace(calendar(), sessions=())
    result: IndexHistory[IndexPrice] = index_history((), **{**options, "calendar": unknown})
    assert result.gaps == ((D1, "unknown_session"),)
    with pytest.raises(ValidationError, match="known"):
        index_history((price(),), **{**options, "known_at": datetime(2026, 1, 1, tzinfo=UTC)})


@pytest.mark.parametrize("change", [{"kind": "etf"}, {"kind": "current"}])
def test_no_substitute_identity(change: dict[str, Any]) -> None:
    with pytest.raises(ValidationError, match="variant"):
        replace(PRICE, **change)


def test_invalid_values_and_lineage_are_rejected() -> None:
    with pytest.raises(ValidationError, match="OHLC"):
        replace(price(), low=Decimal("101"))
    with pytest.raises(ValidationError, match="decimal"):
        replace(price(), close=Decimal("NaN"))
    with pytest.raises(ValidationError, match="hash"):
        replace(LINEAGE, raw_sha256="invalid")
    with pytest.raises(ValidationError, match="price variant"):
        replace(price(), variant=GROSS)
