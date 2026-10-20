"""Pure delivery quantities and explicitly comparable, rounded derived fractions."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import Literal

from niftyverse.calendars import Calendar
from niftyverse.identity import Catalogue, ListingSelectionPolicy
from niftyverse.market_prices import (
    EquityResult,
    MarketDataFailure,
    SourcePrice,
    normalize_equities,
    number,
)
from niftyverse.temporal import day, text


@dataclass(frozen=True)
class SourceDelivery:
    symbol: str
    series: str
    session_date: date
    traded_quantity: int | None
    delivered_quantity: int | None
    published_percent: Decimal | None
    source_id: str
    representation: str
    raw_sha256: str
    locator: str
    raw_fields: tuple[tuple[str, str | None], ...]
    source_turnover: Decimal | None = None
    source_turnover_unit: str | None = None
    quantity_definition: str = "traded_security_units"

    def __post_init__(self) -> None:
        text(
            self.symbol,
            self.series,
            self.source_id,
            self.representation,
            self.raw_sha256,
            self.locator,
            self.quantity_definition,
        )
        day(self.session_date)
        for value in (self.traded_quantity, self.delivered_quantity):
            if value is not None:
                number(value, integer=True)
        for amount in (self.published_percent, self.source_turnover):
            if amount is not None:
                number(amount)
        if self.published_percent is not None and self.published_percent > 100:
            raise MarketDataFailure("invalid_delivery_percent")
        if self.source_turnover_unit not in {None, "INR_lakh", "INR"}:
            raise MarketDataFailure("incompatible_turnover_unit")
        if self.source_turnover is not None and self.source_turnover_unit is None:
            raise MarketDataFailure("unknown_turnover_unit")

    @property
    def key(self) -> tuple[str, str, date]:
        return self.symbol, self.series, self.session_date

    @property
    def turnover_inr(self) -> Decimal | None:
        if self.source_turnover is None:
            return None
        with localcontext() as context:
            context.prec = 50
            converted = self.source_turnover * (
                100000 if self.source_turnover_unit == "INR_lakh" else 1
            )
        return number(converted)


@dataclass(frozen=True)
class DeliveryFraction:
    value: Decimal | None
    reason: str | None
    published_percent: Decimal | None
    policy_version: str = "comparable-units-half-even-12dp-v1"


def delivery_fraction(
    delivery: SourceDelivery, price: SourcePrice | None = None
) -> DeliveryFraction:
    delivery.__post_init__()
    total = delivery.traded_quantity
    reason = (
        "incompatible_quantity_definition"
        if delivery.quantity_definition != "traded_security_units"
        else None
    )
    if price is not None:
        price.__post_init__()
        if price.key != delivery.key:
            reason = "incompatible_listing_series_session"
        elif price.quantity_definition != delivery.quantity_definition:
            reason = "incompatible_quantity_definition"
        elif total is not None and price.quantity is not None and total != price.quantity:
            reason = "comparable_total_conflict"
        total = price.quantity
    if delivery.delivered_quantity is None:
        reason = reason or "delivery_absent"
    elif total is None:
        reason = reason or "unknown_comparable_total"
    elif total == 0:
        reason = reason or "zero_comparable_total"
    elif delivery.delivered_quantity > total:
        reason = reason or "delivery_exceeds_total"
    if reason:
        return DeliveryFraction(None, reason, delivery.published_percent)
    assert total is not None and delivery.delivered_quantity is not None
    with localcontext() as context:
        context.prec = 50
        exact = Decimal(delivery.delivered_quantity) / Decimal(total)
        if delivery.published_percent is not None and abs(
            exact * 100 - delivery.published_percent
        ) > Decimal("0.005"):
            return DeliveryFraction(
                None, "published_fraction_conflict", delivery.published_percent
            )
        rounded = exact.quantize(Decimal("0.000000000001"), rounding=ROUND_HALF_EVEN)
    return DeliveryFraction(rounded, None, delivery.published_percent)


def normalize_deliveries(
    rows: tuple[SourceDelivery, ...],
    *,
    catalogue: Catalogue,
    calendar: Calendar,
    instrument_ids: tuple[str, ...],
    start: date,
    end: date,
    known_at: datetime,
    policy: ListingSelectionPolicy,
    source_complete: bool,
    asset_type: Literal["equity", "etf"] = "equity",
) -> EquityResult:
    """Reuse dated identity/session selection for quantity-only source records.

    OHLC remains null and is never published as a price observation. Feed this
    result only to a security_daily_details partition, retaining delivery gaps.
    """
    source = []
    for row in rows:
        row.__post_init__()
        source.append(
            SourcePrice(
                row.symbol,
                row.series,
                row.session_date,
                None,
                None,
                None,
                None,
                row.traded_quantity,
                row.turnover_inr,
                row.source_id,
                row.representation,
                row.raw_sha256,
                row.locator,
                row.raw_fields,
                delivered_quantity=row.delivered_quantity,
                delivered_percent=row.published_percent,
                quantity_definition=row.quantity_definition,
            )
        )
    return normalize_equities(
        tuple(source),
        catalogue=catalogue,
        calendar=calendar,
        instrument_ids=instrument_ids,
        start=start,
        end=end,
        known_at=known_at,
        policy=policy,
        source_complete=source_complete,
        asset_type=asset_type,
        required_fields=(),
    )
