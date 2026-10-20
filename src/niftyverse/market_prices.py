"""Pure raw-traded price contracts and dated listing/session selection."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal

from niftyverse.calendars import Calendar
from niftyverse.core import ValidationError
from niftyverse.identity import Catalogue, ListingSelectionPolicy, select_listing
from niftyverse.temporal import day, text, utc


class MarketDataFailure(ValidationError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def number(value: object, *, integer: bool = False) -> Decimal | None:
    if value is None or value in ("", "-", "--"):
        return None
    if isinstance(value, (bool, float)) or not isinstance(value, (str, int, Decimal)):
        raise MarketDataFailure("invalid_quantity" if integer else "invalid_number")
    try:
        result = Decimal(value)
    except InvalidOperation:
        raise MarketDataFailure("invalid_number") from None
    if not result.is_finite() or result < 0:
        raise MarketDataFailure("invalid_number")
    if integer and (result != result.to_integral_value() or result > 2**63 - 1):
        raise MarketDataFailure("invalid_quantity")
    exponent = result.as_tuple().exponent
    if (
        len(result.as_tuple().digits) > 38
        or not isinstance(exponent, int)
        or exponent < -8
        or result.adjusted() >= 30
    ):
        raise MarketDataFailure("numeric_precision")
    return result


def quantity(value: object) -> int | None:
    result = number(value, integer=True)
    return int(result) if result is not None else None


def validate_price_fields(
    *,
    open: Decimal | None,
    high: Decimal | None,
    low: Decimal | None,
    close: Decimal | None,
    quantity: int | None,
    turnover: Decimal | None,
) -> None:
    for value in (open, high, low, close, turnover):
        if value is not None:
            if not isinstance(value, Decimal):
                raise MarketDataFailure("invalid_number")
            number(value)
    if quantity is not None:
        number(quantity, integer=True)
    if high is not None and low is not None:
        if high < low:
            raise MarketDataFailure("invalid_ohlc")
        # No-trade source rows may retain an earlier close outside zero OHLC.
        # Statistical size of a valid move is never a deterministic failure.
        if (
            quantity is not None
            and quantity > 0
            and any(v is not None and not low <= v <= high for v in (open, close))
        ):
            raise MarketDataFailure("invalid_ohlc")


@dataclass(frozen=True)
class SourcePrice:
    symbol: str
    series: str
    session_date: date
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    close: Decimal | None
    quantity: int | None
    turnover: Decimal | None
    source_id: str
    representation: str
    raw_sha256: str
    locator: str
    raw_fields: tuple[tuple[str, str | None], ...]
    trades: int | None = None
    settlement: Decimal | None = None
    previous_close: Decimal | None = None
    last: Decimal | None = None
    delivered_quantity: int | None = None
    delivered_percent: Decimal | None = None
    turnover_unit: str = "INR"
    quantity_definition: str = "traded_security_units"
    isin: str | None = None
    price_basis: str = "raw_traded"

    def __post_init__(self) -> None:
        text(
            self.symbol,
            self.series,
            self.source_id,
            self.representation,
            self.raw_sha256,
            self.locator,
            self.turnover_unit,
            self.quantity_definition,
        )
        day(self.session_date)
        text(self.price_basis)
        if not isinstance(self.raw_fields, tuple) or len(dict(self.raw_fields)) != len(
            self.raw_fields
        ):
            raise MarketDataFailure("invalid_raw_fields")
        validate_price_fields(
            open=self.open,
            high=self.high,
            low=self.low,
            close=self.close,
            quantity=self.quantity,
            turnover=self.turnover,
        )
        for value in (self.settlement, self.previous_close, self.last, self.delivered_percent):
            if value is not None:
                number(value)
        for count in (self.trades, self.delivered_quantity):
            if count is not None:
                number(count, integer=True)
        if self.delivered_percent is not None and self.delivered_percent > 100:
            raise MarketDataFailure("invalid_delivery_percent")

    @property
    def key(self) -> tuple[str, str, date]:
        return self.symbol, self.series, self.session_date

    @property
    def values(self) -> tuple[object, ...]:
        return (
            self.open,
            self.high,
            self.low,
            self.close,
            self.quantity,
            self.turnover,
            self.trades,
            self.settlement,
            self.previous_close,
            self.last,
            self.delivered_quantity,
            self.delivered_percent,
            self.turnover_unit,
            self.quantity_definition,
            self.isin,
        )


@dataclass(frozen=True)
class NormalizedPrice:
    instrument_id: str
    listing_id: str
    quantity_unit: Literal["shares", "fund_units"]
    source: SourcePrice
    evidence: tuple[SourcePrice, ...]


@dataclass(frozen=True)
class RepresentationChoice:
    selected: SourcePrice | None
    evidence: tuple[SourcePrice, ...]
    reason: str | None
    differing_fields: tuple[str, ...] = ()


def choose_representation(
    candidates: tuple[SourcePrice, ...],
    *,
    preferred: tuple[str, ...],
    tolerances: tuple[tuple[str, Decimal], ...] = (),
) -> RepresentationChoice:
    """Exact conservative selection; competing material evidence never disappears."""
    if not preferred or len(set(preferred)) != len(preferred) or not candidates:
        raise MarketDataFailure("invalid_representation_policy")
    for row in candidates:
        row.__post_init__()
    first = candidates[0]
    if any(r.price_basis != first.price_basis for r in candidates):
        return RepresentationChoice(None, candidates, "incompatible_basis")
    if any(r.key != first.key for r in candidates):
        raise MarketDataFailure("incompatible_business_key")
    if any(
        (r.turnover_unit, r.quantity_definition)
        != (first.turnover_unit, first.quantity_definition)
        for r in candidates
    ):
        return RepresentationChoice(None, candidates, "incompatible_units")
    fields = (
        "open",
        "high",
        "low",
        "close",
        "quantity",
        "turnover",
        "trades",
        "settlement",
        "previous_close",
        "last",
        "delivered_quantity",
        "delivered_percent",
        "isin",
    )
    price_fields = {
        "open",
        "high",
        "low",
        "close",
        "turnover",
        "settlement",
        "previous_close",
        "last",
        "delivered_percent",
    }
    tolerance_map = dict(tolerances)
    if len(tolerance_map) != len(tolerances) or any(
        f not in price_fields or not isinstance(t, Decimal) or not t.is_finite() or t < 0
        for f, t in tolerances
    ):
        raise MarketDataFailure("invalid_tolerance_policy")
    differing = tuple(
        f
        for f in fields
        if len({getattr(r, f) for r in candidates if getattr(r, f) is not None}) > 1
        and not (
            f in tolerance_map
            and max(getattr(r, f) for r in candidates if getattr(r, f) is not None)
            - min(getattr(r, f) for r in candidates if getattr(r, f) is not None)
            <= tolerance_map[f]
        )
    )
    if differing:
        return RepresentationChoice(None, candidates, "representation_conflict", differing)
    ordered = [r for profile in preferred for r in candidates if r.representation == profile]
    if not ordered:
        return RepresentationChoice(None, candidates, "unsupported_representation")
    return RepresentationChoice(ordered[0], candidates, None)


@dataclass(frozen=True)
class PriceGap:
    instrument_id: str
    on: date
    reason: str
    evidence: tuple[SourcePrice, ...] = ()


@dataclass(frozen=True)
class EquityResult:
    rows: tuple[NormalizedPrice, ...]
    gaps: tuple[PriceGap, ...]
    coverage: Literal["complete", "partial", "quarantined"]
    catalogue_version: str
    calendar_version: str
    policy_version: str
    source_evidence: tuple[SourcePrice, ...] = ()


def normalize_equities(
    source: tuple[SourcePrice, ...],
    *,
    catalogue: Catalogue,
    calendar: Calendar,
    instrument_ids: tuple[str, ...],
    start: date,
    end: date,
    known_at: datetime,
    policy: ListingSelectionPolicy,
    source_complete: bool,
    source_failed: bool = False,
    asset_type: Literal["equity", "etf"] = "equity",
    preferred_representations: tuple[str, ...] = (),
    tolerances: tuple[tuple[str, Decimal], ...] = (),
    required_fields: tuple[str, ...] = ("close",),
) -> EquityResult:
    day(start)
    day(end)
    utc(known_at)
    policy.__post_init__()
    if (
        start >= end
        or (end - start).days > 3660
        or not instrument_ids
        or len(set(instrument_ids)) != len(instrument_ids)
    ):
        raise MarketDataFailure("invalid_selection_scope")
    if catalogue.collected_at > known_at or calendar.known_at > known_at:
        raise MarketDataFailure("evidence_not_known")
    instruments = {r.instrument_id: r for r in catalogue.instruments}
    if any(
        i not in instruments or instruments[i].asset_type != asset_type for i in instrument_ids
    ):
        raise MarketDataFailure("identity_unresolved")
    grouped: dict[tuple[str, date], dict[str, list[SourcePrice]]] = {}
    unresolved: set[tuple[str, date]] = set()
    for row in source:
        row.__post_init__()
        if not start <= row.session_date < end:
            raise MarketDataFailure("row_outside_window")
        matches = tuple(
            m
            for m in catalogue.search(
                row.symbol, on=row.session_date, known_at=known_at, namespace="symbol"
            ).matches
            if m.alias is not None
            and m.alias.identifier.casefold() == row.symbol.casefold()
            and m.listing.series == row.series
        )
        affected = {m.instrument.instrument_id for m in matches} & set(instrument_ids)
        if len(matches) != 1 or any(m.date_status != "dated" for m in matches):
            unresolved.update((i, row.session_date) for i in affected)
            continue
        match = matches[0]
        key = (match.instrument.instrument_id, row.session_date)
        if key[0] not in instrument_ids:
            continue
        if row.turnover_unit != "INR" or row.quantity_definition != "traded_security_units":
            raise MarketDataFailure("incompatible_units")
        grouped.setdefault(key, {}).setdefault(match.listing.listing_id, []).append(row)
    output = []
    gaps = []
    for session in calendar.sessions_between(start, end, require_complete=False):
        on = session.session_date
        for instrument_id in instrument_ids:
            reason = None
            available = grouped.get((instrument_id, on), {})
            if session.eligible is None:
                reason = "calendar_unknown"
            elif not session.eligible:
                reason = "closed_session"
            elif (instrument_id, on) in unresolved:
                reason = "identity_unresolved"
            else:
                dated = tuple(
                    r.listing_id
                    for r in catalogue.listings
                    if r.instrument_id == instrument_id and r.evidence.admits(on, known_at)
                )
                selection = select_listing(
                    catalogue,
                    instrument_id,
                    on,
                    known_at,
                    tuple(available) if available else dated,
                    policy,
                )
                if selection.status != "selected":
                    reason = selection.status
                    dated_states = {
                        r.status
                        for r in catalogue.listings
                        if r.instrument_id == instrument_id
                        and r.evidence.admits(on, known_at)
                        and r.role == "ordinary"
                    }
                    if not available and dated_states == {"delisted"}:
                        reason = "not_listed"
                    elif not available and dated_states == {"suspended"}:
                        reason = "suspended"
                elif selection.listing is not None:
                    candidates = available.get(selection.listing.listing_id, [])
                    if candidates:
                        profiles = tuple(dict.fromkeys(c.representation for c in candidates))
                        preferred = preferred_representations or (
                            profiles if len(profiles) == 1 else ()
                        )
                        if not preferred:
                            reason = "representation_policy_required"
                            continue_selection = None
                        else:
                            choice = choose_representation(
                                tuple(candidates), preferred=preferred, tolerances=tolerances
                            )
                            continue_selection = choice.selected
                            if choice.reason:
                                reason = choice.reason
                        if continue_selection is not None:
                            output.append(
                                NormalizedPrice(
                                    instrument_id,
                                    selection.listing.listing_id,
                                    "fund_units" if asset_type == "etf" else "shares",
                                    continue_selection,
                                    tuple(candidates),
                                )
                            )
                            if any(
                                getattr(continue_selection, field) is None
                                for field in required_fields
                            ):
                                reason = "source_null"
                    else:
                        reason = "source_unavailable" if source_failed else "missing_observation"
            if reason is not None:
                gaps.append(
                    PriceGap(
                        instrument_id,
                        on,
                        reason,
                        tuple(r for values in available.values() for r in values),
                    )
                )
    blocked = {
        "identity_unresolved",
        "collision",
        "conflicting_duplicate",
        "representation_conflict",
        "representation_policy_required",
        "incompatible_units",
        "incompatible_basis",
    }
    partial = any(g.reason not in {"closed_session", "policy_exclusion"} for g in gaps)
    coverage: Literal["complete", "partial", "quarantined"] = (
        "quarantined"
        if any(g.reason in blocked for g in gaps)
        else "partial"
        if partial or not source_complete or source_failed
        else "complete"
    )
    return EquityResult(
        tuple(output),
        tuple(gaps),
        coverage,
        catalogue.version_id,
        calendar.version_id,
        policy.version_id,
        source,
    )
