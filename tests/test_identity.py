"""Hand-authored dated identities; synthetic evidence, no provider claims."""

import socket
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from niftyverse.core import ValidationError
from niftyverse.identity import (
    Alias,
    Catalogue,
    Contract,
    ContractTerms,
    Instrument,
    Issuer,
    Listing,
    ListingSelectionPolicy,
    select_listing,
    select_terms,
)
from niftyverse.temporal import Evidence

KNOWN = datetime(2020, 1, 1, tzinfo=UTC)
CUTOFF = datetime(2026, 1, 1, tzinfo=UTC)


def ev(start: str | None, end: str | None = None) -> Evidence:
    return Evidence(
        date.fromisoformat(start) if start else None,
        date.fromisoformat(end) if end else None,
        KNOWN,
        "owned-fixture",
        "timeline:1",
    )


def catalogue() -> Catalogue:
    return Catalogue(
        "catalogue-v1",
        CUTOFF,
        date(2025, 12, 31),
        "historical",
        (Issuer("issuer-a", "Alpha"), Issuer("issuer-b", "Beta")),
        (
            Instrument("a", "issuer-a", "equity", "Alpha Industries"),
            Instrument("b", "issuer-b", "equity", "Beta Industries"),
            Instrument("fund", None, "etf", "Alpha Fund"),
        ),
        (
            Listing("a-eq", "a", "NSE", "EQ", "ordinary", "listed", ev("2020-01-01")),
            Listing("b-eq", "b", "NSE", "EQ", "ordinary", "listed", ev("2020-01-01")),
            Listing("fund-eq", "fund", "NSE", "EQ", "ordinary", "listed", ev("2020-01-01")),
        ),
        (
            Alias("OLD", "symbol", "a-eq", ev("2020-01-01", "2022-01-01")),
            Alias("NEW", "symbol", "a-eq", ev("2022-01-01")),
            Alias("OLD", "symbol", "b-eq", ev("2022-01-01")),
            Alias("INF000001", "isin", "fund-eq", ev("2020-01-01")),
        ),
    )


def test_rename_reuse_boundaries_and_known_at() -> None:
    cat = catalogue()
    assert (
        cat.resolve("OLD", "symbol", date(2021, 12, 31), CUTOFF)
        .matches[0]
        .instrument.instrument_id
        == "a"
    )
    assert (
        cat.resolve("OLD", "symbol", date(2022, 1, 1), CUTOFF).matches[0].instrument.instrument_id
        == "b"
    )
    assert cat.resolve("NEW", "symbol", date(2021, 12, 31), CUTOFF).status == "identity_unresolved"
    later = replace(cat.aliases[1], evidence=replace(cat.aliases[1].evidence, known_at=CUTOFF))
    cat = replace(cat, aliases=(later,))
    assert cat.resolve("NEW", "symbol", date(2023, 1, 1), KNOWN).status == "identity_unresolved"


def test_ambiguity_and_unknown_dates_never_choose_first() -> None:
    cat = catalogue()
    cat = replace(cat, aliases=cat.aliases + (Alias("NEW", "symbol", "b-eq", ev("2022-01-01")),))
    result = cat.resolve("NEW", "symbol", date(2023, 1, 1), CUTOFF)
    assert result.status == "ambiguous"
    assert {m.instrument.instrument_id for m in result.matches} == {"a", "b"}
    unknown = replace(cat, aliases=(Alias("MISSING", "symbol", "a-eq", ev(None)),))
    assert (
        unknown.resolve("MISSING", "symbol", date(2023, 1, 1), CUTOFF).status
        == "identity_unresolved"
    )
    assert (
        unknown.search("MISSING", on=date(2023, 1, 1), known_at=CUTOFF).matches[0].date_status
        == "unknown"
    )


def test_local_search_etf_ranking_staleness_and_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    def denied(*args: object, **kwargs: object) -> None:
        raise AssertionError("search attempted network")

    monkeypatch.setattr(socket, "socket", denied)
    cat = catalogue()
    result = cat.search("Alpha", on=date(2024, 1, 1), known_at=CUTOFF)
    assert {m.instrument.instrument_id for m in result.matches} == {"a", "fund"}
    assert (
        cat.search("INF000001", on=date(2024, 1, 1), known_at=CUTOFF)
        .matches[0]
        .instrument.asset_type
        == "etf"
    )
    assert (
        len(cat.search("Alpha", on=date(2024, 1, 1), known_at=CUTOFF, asset_type="etf").matches)
        == 1
    )
    current = replace(cat, coverage="current_only")
    result = current.search("Alpha", on=date(2018, 1, 1), known_at=CUTOFF)
    assert "current_only" in result.limitations
    assert "stale" in cat.search("Alpha", on=date(2026, 1, 1), known_at=CUTOFF).limitations


def test_listing_policy_eq_be_eq_with_bl_collision_and_unknown() -> None:
    cat = catalogue()
    cat = replace(
        cat,
        listings=(
            replace(cat.listings[0], evidence=ev("2020-01-01", "2021-01-01")),
            Listing(
                "a-be", "a", "NSE", "BE", "ordinary", "listed", ev("2021-01-01", "2022-01-01")
            ),
            replace(cat.listings[0], evidence=ev("2022-01-01")),
            Listing("a-bl", "a", "NSE", "BL", "block", "listed", ev("2020-01-01")),
        ),
        aliases=(),
    )
    policy = ListingSelectionPolicy("ordinary-v1")
    for day, expected in [("2020-12-31", "a-eq"), ("2021-01-01", "a-be"), ("2022-01-01", "a-eq")]:
        result = select_listing(
            cat, "a", date.fromisoformat(day), CUTOFF, ("a-eq", "a-be", "a-bl"), policy
        )
        assert result.status == "selected"
        assert result.listing is not None and result.listing.listing_id == expected
    eq_only = replace(policy, allowed_series=("EQ",))
    assert (
        select_listing(cat, "a", date(2021, 1, 1), CUTOFF, ("a-be",), eq_only).status
        == "policy_exclusion"
    )
    duplicate = replace(cat.listings[2], listing_id="other-eq")
    collision = replace(cat, listings=cat.listings + (duplicate,))
    assert (
        select_listing(
            collision, "a", date(2023, 1, 1), CUTOFF, ("a-eq", "other-eq"), policy
        ).status
        == "collision"
    )
    priority = replace(policy, listing_priority=("other-eq", "a-eq"))
    assert (
        select_listing(
            collision, "a", date(2023, 1, 1), CUTOFF, ("a-eq", "other-eq"), priority
        ).listing
        == duplicate
    )
    assert (
        select_listing(cat, "a", date(2019, 1, 1), CUTOFF, ("a-eq",), policy).status
        == "identity_unresolved"
    )


def test_invalid_identity_graph_and_evidence_fail_without_mutation() -> None:
    cat = catalogue()
    with pytest.raises(ValidationError, match="listing"):
        replace(cat, aliases=(replace(cat.aliases[0], listing_id="absent"),))
    with pytest.raises(ValidationError, match="duplicate"):
        replace(cat, instruments=cat.instruments + (cat.instruments[0],))
    with pytest.raises(ValidationError, match="interval"):
        ev("2021-01-01", "2021-01-01")
    with pytest.raises(ValidationError, match="UTC"):
        replace(ev(None), known_at=KNOWN.replace(tzinfo=None))
    assert cat == catalogue()


def test_unknown_competing_alias_and_overlapping_listing_states_are_unresolved() -> None:
    cat = catalogue()
    uncertain = replace(cat, aliases=cat.aliases + (Alias("NEW", "symbol", "b-eq", ev(None)),))
    result = uncertain.resolve("NEW", "symbol", date(2023, 1, 1), CUTOFF)
    assert result.status == "identity_unresolved"
    assert len(result.matches) == 2
    overlap = replace(cat, listings=cat.listings + (replace(cat.listings[0], status="suspended"),))
    assert overlap.resolve("NEW", "symbol", date(2023, 1, 1), CUTOFF).status == "ambiguous"
    assert "stale" in cat.resolve("NEW", "symbol", date(2026, 1, 1), CUTOFF).limitations


def test_derivative_stable_identity_and_full_terms_history() -> None:
    contract = Contract(
        "contract-1", "underlying-a", "option", "CE", "evidenced", None, "notice:1"
    )
    original = ContractTerms(
        "contract-1",
        "terms-1",
        ev("2020-01-01", "2021-01-01"),
        Decimal("100.125"),
        date(2021, 2, 1),
        100,
        Decimal("1"),
        "cash",
    )
    adjusted = replace(
        original,
        version_id="terms-2",
        evidence=ev("2021-01-01"),
        strike=Decimal("50.0625"),
        expiry=date(2021, 2, 2),
        lot=200,
    )
    assert select_terms(contract, (original, adjusted), date(2020, 12, 31), CUTOFF) == original
    assert select_terms(contract, (original, adjusted), date(2021, 1, 1), CUTOFF) == adjusted
    assert (
        select_terms(contract, (replace(original, evidence=ev(None)),), date(2020, 1, 1), CUTOFF)
        is None
    )
    with pytest.raises(ValidationError, match="ambiguous"):
        select_terms(
            contract,
            (adjusted, replace(adjusted, version_id="collision")),
            date(2021, 1, 1),
            CUTOFF,
        )
    with pytest.raises(ValidationError, match="decimal"):
        replace(original, strike=100.0)  # type: ignore[arg-type]
    assert original.strike == Decimal("100.125") and original.lot == 100
