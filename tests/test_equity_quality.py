"""Contract validity, source reconciliation and retrospective anomaly decisions."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from test_equity_json import wire

from niftyverse.adapters.equity_json import decode_equity_json
from niftyverse.equity_quality import QualityPolicy, assess_move, reconcile_prices

NOW = datetime(2026, 10, 20, tzinfo=UTC)


def test_comparable_tolerances_keep_values_and_competing_paths() -> None:
    a = decode_equity_json(wire(), source_id="owned", locator="p")[0]
    b = replace(a, representation="cm_udiff", raw_sha256="b" * 64, close=Decimal("101.254"))
    policy = QualityPolicy("quality-v1")
    equal = reconcile_prices((a, b), preferred=("cm_udiff", "nse_equity_json_v1"), policy=policy)
    assert equal.selected == b and equal.evidence == (a, b)
    assert equal.selected.close == Decimal("101.254")  # no averaging or value repair
    conflict = reconcile_prices(
        (a, replace(b, quantity=11)), preferred=("cm_udiff",), policy=policy
    )
    assert conflict.selected is None and conflict.differing_fields == ("quantity",)
    assert len(conflict.evidence) == 2
    units = reconcile_prices(
        (a, replace(b, quantity_definition="contracts")), preferred=("cm_udiff",), policy=policy
    )
    assert units.selected is None and units.reason == "incompatible_units"
    basis = reconcile_prices(
        (a, replace(b, price_basis="adjusted")), preferred=("cm_udiff",), policy=policy
    )
    assert basis.selected is None and basis.reason == "incompatible_basis"


def test_crash_and_split_sized_moves_remain_facts_with_known_time() -> None:
    current = decode_equity_json(
        wire(
            CH_OPENING_PRICE="10",
            CH_TRADE_HIGH_PRICE="11",
            CH_TRADE_LOW_PRICE="9",
            CH_CLOSING_PRICE="10",
        ),
        source_id="owned",
        locator="p",
    )[0]
    prior = replace(
        current,
        session_date=current.session_date - timedelta(days=1),
        close=Decimal("100"),
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("99"),
    )
    before = replace(current)
    assessment = assess_move(
        current,
        prior,
        policy=QualityPolicy("quality-v1"),
        known_at=NOW,
        prior_known_at=NOW,
        decision_at=NOW,
    )
    assert assessment.status == "anomaly_unresolved" and assessment.value == Decimal("-0.9")
    assert assessment.known_at == NOW and current == before
    future = assess_move(
        current,
        prior,
        policy=QualityPolicy("quality-v1"),
        known_at=NOW,
        prior_known_at=NOW,
        decision_at=NOW - timedelta(days=1),
    )
    assert future.status == "baseline_unavailable" and future.value is None
    future_current = assess_move(
        current,
        prior,
        policy=QualityPolicy("quality-v1"),
        known_at=NOW + timedelta(days=1),
        prior_known_at=NOW,
        decision_at=NOW,
    )
    assert future_current.value is None and future_current.status == "observation_unavailable"
    split = replace(
        current, open=Decimal("50"), high=Decimal("51"), low=Decimal("49"), close=Decimal("50")
    )
    assert (
        assess_move(
            split,
            prior,
            policy=QualityPolicy("warning-v2", move_warning=Decimal("0.4")),
            known_at=NOW,
            prior_known_at=NOW,
            decision_at=NOW,
        ).status
        == "anomaly_unresolved"
    )


def test_invalid_policy_never_weakens_contracts() -> None:
    with pytest.raises(ValueError, match="tolerance"):
        QualityPolicy("bad", price_tolerance=Decimal("-1"))


def test_optional_overlapping_states_and_band_touch_never_erase_volume() -> None:
    from test_market_state import observation

    from niftyverse.equity_quality import enrich_market_states
    from niftyverse.market_prices import NormalizedPrice
    from niftyverse.market_state import MarketStateObservation

    source = decode_equity_json(wire(), source_id="owned", locator="p")[0]
    price = NormalizedPrice("a", "a-eq", "shares", source, (source,))

    def state(kind: str) -> MarketStateObservation:
        return replace(
            observation(kind), listing_id="a-eq", observed_on=source.session_date, known_at=NOW
        )

    states = (
        state("ASM"),
        state("GSM"),
        replace(
            state("price_band"),
            value=None,
            lower=Decimal("99.50"),
            upper=Decimal("102.25"),
            basis="fixed_absolute_price",
        ),
    )
    enriched = enrich_market_states(
        price, states, known_at=NOW, requested=("ASM", "GSM", "price_band")
    )
    assert enriched.price == price and enriched.price.source.quantity == 10
    assert len(enriched.states) == 3 and enriched.band_touch is True
    assert enriched.execution_availability == "unknown"
    missing = enrich_market_states(
        price, (), known_at=NOW, requested=("ASM",), require_states=True
    )
    assert missing.unknown_kinds == ("ASM",) and missing.state_coverage == "partial"
    assert missing.price.source.quantity == 10
    price_only = enrich_market_states(price, (), known_at=NOW)
    assert price_only.state_coverage == "not_requested" and price_only.price == price
