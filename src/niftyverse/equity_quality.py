"""Versioned comparable-source tolerances and non-destructive move warnings."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from niftyverse.market_prices import (
    MarketDataFailure,
    NormalizedPrice,
    RepresentationChoice,
    SourcePrice,
    choose_representation,
)
from niftyverse.market_state import MarketStateObservation, state_on
from niftyverse.temporal import text, utc


@dataclass(frozen=True)
class QualityPolicy:
    version_id: str
    price_tolerance: Decimal = Decimal("0.005")
    turnover_tolerance: Decimal = Decimal("0.005")
    delivery_percent_tolerance: Decimal = Decimal("0.005")
    move_warning: Decimal = Decimal("0.5")

    def __post_init__(self) -> None:
        text(self.version_id)
        for value in (
            self.price_tolerance,
            self.turnover_tolerance,
            self.delivery_percent_tolerance,
            self.move_warning,
        ):
            if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
                raise MarketDataFailure("invalid_tolerance_policy")

    @property
    def tolerances(self) -> tuple[tuple[str, Decimal], ...]:
        return tuple(
            (f, self.price_tolerance)
            for f in ("open", "high", "low", "close", "last", "previous_close", "settlement")
        ) + (
            ("turnover", self.turnover_tolerance),
            ("delivered_percent", self.delivery_percent_tolerance),
        )


def reconcile_prices(
    candidates: tuple[SourcePrice, ...], *, preferred: tuple[str, ...], policy: QualityPolicy
) -> RepresentationChoice:
    policy.__post_init__()
    return choose_representation(candidates, preferred=preferred, tolerances=policy.tolerances)


@dataclass(frozen=True)
class MoveAssessment:
    status: str
    value: Decimal | None
    policy_version: str
    known_at: datetime
    baseline_known_at: datetime
    business_key: tuple[str, str, date]


def assess_move(
    current: SourcePrice,
    prior: SourcePrice,
    *,
    policy: QualityPolicy,
    known_at: datetime,
    prior_known_at: datetime,
    decision_at: datetime,
) -> MoveAssessment:
    current.__post_init__()
    prior.__post_init__()
    policy.__post_init__()
    for instant in (known_at, prior_known_at, decision_at):
        utc(instant)
    if (
        prior_known_at > decision_at
        or prior.session_date >= current.session_date
        or prior.symbol != current.symbol
        or prior.series != current.series
        or prior.close is None
        or prior.close == 0
        or current.close is None
        or prior.price_basis != current.price_basis
    ):
        return MoveAssessment(
            "baseline_unavailable", None, policy.version_id, known_at, prior_known_at, current.key
        )
    move = current.close / prior.close - 1
    return MoveAssessment(
        "anomaly_unresolved" if abs(move) > policy.move_warning else "no_move_warning",
        move,
        policy.version_id,
        known_at,
        prior_known_at,
        current.key,
    )


@dataclass(frozen=True)
class MarketStateView:
    price: NormalizedPrice
    states: tuple[MarketStateObservation, ...]
    unknown_kinds: tuple[str, ...]
    state_coverage: str
    band_touch: bool | None
    execution_availability: str = "unknown"


def enrich_market_states(
    price: NormalizedPrice,
    observations: tuple[MarketStateObservation, ...],
    *,
    known_at: datetime,
    requested: tuple[str, ...] = (),
    require_states: bool = False,
) -> MarketStateView:
    """Optional local observations only; no acquisition, trade/fill inference or price mutation.

    A source's percentage band change is not an absolute price bound. Touch is
    evaluated only for explicit absolute-price bases on the observed session.
    It is an EOD price/state coincidence, never evidence of continuous lock.
    """
    utc(known_at)
    if len(set(requested)) != len(requested):
        raise MarketDataFailure("duplicate_state_kind")
    if not requested:
        return MarketStateView(price, (), (), "not_requested", None)
    for observation in observations:
        observation.__post_init__()
    selected: list[MarketStateObservation] = []
    unknown = []
    for kind in requested:
        states = state_on(
            observations, price.listing_id, "CM", kind, price.source.session_date, known_at
        )
        selected.extend(states)
        if not states or any(r.state == "unknown" for r in states):
            unknown.append(kind)
    touch = None
    bands = [
        r
        for r in selected
        if r.state_kind == "price_band"
        and r.state == "present"
        and r.basis in {"fixed_absolute_price", "dynamic_absolute_price"}
    ]
    if bands and price.source.low is not None and price.source.high is not None:
        bounds = [bound for r in bands for bound in (r.lower, r.upper) if bound is not None]
        if bounds:
            touch = any(price.source.low <= bound <= price.source.high for bound in bounds)
    return MarketStateView(
        price,
        tuple(selected),
        tuple(unknown),
        "partial" if unknown and require_states else "unknown" if unknown else "complete",
        touch,
    )
