"""Map selected market observations to the shared DB/direct publication boundary."""

import json
from dataclasses import asdict, replace
from datetime import datetime

import pyarrow as pa

from niftyverse.batches import Capture, Partition, ValidatedBatch
from niftyverse.delivery import SourceDelivery, delivery_fraction
from niftyverse.equity_quality import MoveAssessment
from niftyverse.market_prices import EquityResult, MarketDataFailure, number
from niftyverse.storage.schemas import SCHEMAS


def make_price_batch(
    result: EquityResult,
    *,
    partition: Partition,
    capture: Capture,
    check_id: str,
    checked_at: datetime,
    known_at: datetime,
    assessments: tuple[MoveAssessment, ...] = (),
) -> ValidatedBatch:
    """One source capture per batch; counterparts remain explicit references.

    Retain/publish each competing capture separately for raw replay. A selected
    fact cannot be reassigned to another capture or silently averaged. Delivery
    only partitions publish details without manufacturing price observations.
    """
    if partition.dataset not in {"equity_daily", "etf_daily", "security_daily_details"}:
        raise MarketDataFailure("incompatible_dataset")
    if result.coverage == "complete" and not partition.completeness_evidence.strip():
        raise MarketDataFailure("completeness_evidence_required")
    metadata = {
        "source_evidence": partition.completeness_evidence,
        "catalogue_version": result.catalogue_version,
        "calendar_version": result.calendar_version,
        "listing_policy": result.policy_version,
        "gaps": [
            {"instrument_id": g.instrument_id, "on": str(g.on), "reason": g.reason}
            for g in result.gaps
        ],
        "competing_evidence": [
            {"raw_sha256": r.raw_sha256, "locator": r.locator, "representation": r.representation}
            for r in result.source_evidence
        ],
        "quality_assessments": [asdict(a) for a in assessments],
        "counterpart_retention": "references only; retain each source capture separately",
    }
    if any(a.known_at > checked_at for a in assessments):
        raise MarketDataFailure("quality_evidence_not_known")
    price_rows = []
    details = []
    for row in result.rows:
        source = row.source
        source.__post_init__()
        if source.raw_sha256 != capture.sha256 or source.source_id != capture.source_id:
            raise MarketDataFailure("source_capture_mismatch")
        if source.price_basis != "raw_traded" or source.turnover_unit != "INR":
            raise MarketDataFailure("incompatible_basis_or_units")
        if (
            source.close is None
            and partition.dataset != "security_daily_details"
            and result.coverage == "complete"
        ):
            raise MarketDataFailure("missing_price_cannot_be_complete")
        price_rows.append(
            dict(
                listing_id=row.listing_id,
                series=source.series,
                session_date=source.session_date,
                open=source.open,
                high=source.high,
                low=source.low,
                close=source.close,
                quantity=source.quantity,
                quantity_unit=row.quantity_unit,
                turnover=source.turnover,
                currency="INR",
                locator=source.locator,
                missing_reason="source_null" if source.close is None else None,
            )
        )
        turnover_unit: str | None
        if source.representation == "delivery_csv_v1":
            source_turnover = number(dict(source.raw_fields).get("TURNOVER_LACS"))
            turnover_unit = "INR_lakh"
        else:
            source_turnover = source.turnover
            turnover_unit = "INR" if source_turnover is not None else None
        delivery = SourceDelivery(
            source.symbol,
            source.series,
            source.session_date,
            source.quantity,
            source.delivered_quantity,
            source.delivered_percent,
            source.source_id,
            source.representation,
            source.raw_sha256,
            source.locator,
            source.raw_fields,
            source_turnover,
            turnover_unit,
            source.quantity_definition,
        )
        fraction = delivery_fraction(delivery)
        details.append(
            dict(
                listing_id=row.listing_id,
                series=source.series,
                session_date=source.session_date,
                quantity_unit=row.quantity_unit,
                trades=source.trades,
                settlement_price=source.settlement,
                last_price=source.last,
                previous_close=source.previous_close,
                delivered_quantity=source.delivered_quantity,
                comparable_quantity=source.quantity,
                delivery_fraction=fraction.value,
                published_delivery_percent=source.delivered_percent,
                delivery_reason=fraction.reason,
                source_turnover=source_turnover,
                source_turnover_unit=turnover_unit,
                quantity_definition=source.quantity_definition,
                price_basis=source.price_basis,
                representation=source.representation,
                raw_sha256=source.raw_sha256,
                locator=source.locator,
            )
        )
    tables = []
    if partition.dataset != "security_daily_details":
        tables.append(
            (
                partition.dataset,
                pa.Table.from_pylist(price_rows, schema=SCHEMAS[partition.dataset]),
            )
        )
    tables.append(
        (
            "security_daily_details",
            pa.Table.from_pylist(details, schema=SCHEMAS["security_daily_details"]),
        )
    )
    return ValidatedBatch(
        replace(
            partition, completeness_evidence=json.dumps(metadata, default=str, sort_keys=True)
        ),
        capture,
        check_id,
        checked_at,
        known_at,
        None,
        "active",
        None,
        tuple(tables),
        result.coverage,
        "security-eod-v1",
        "security-eod-normalizer-v1",
    )
