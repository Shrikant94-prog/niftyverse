"""Observation-dated ETF metadata through the shared publication boundary."""

import json
from dataclasses import asdict, replace
from datetime import datetime, timedelta

import pyarrow as pa

from niftyverse.batches import Capture, Partition, ValidatedBatch
from niftyverse.etfs import EtfSnapshot
from niftyverse.identity import Catalogue
from niftyverse.market_prices import MarketDataFailure
from niftyverse.storage.schemas import SCHEMAS


def make_metadata_batch(
    snapshot: EtfSnapshot,
    *,
    catalogue: Catalogue,
    partition: Partition,
    capture: Capture,
    check_id: str,
    checked_at: datetime,
    known_at: datetime,
) -> ValidatedBatch:
    on = snapshot.observed_at.date()
    if (
        partition.dataset != "etf_metadata"
        or partition.start != on
        or partition.end != on + timedelta(days=1)
        or set(partition.fields) - {"scheme_name", "classification"}
    ):
        raise MarketDataFailure("unsupported_metadata_scope_or_fields")
    if snapshot.raw_sha256 != capture.sha256 or snapshot.source_id != capture.source_id:
        raise MarketDataFailure("source_capture_mismatch")
    if known_at < snapshot.observed_at or catalogue.collected_at > known_at:
        raise MarketDataFailure("evidence_not_known")
    if not partition.completeness_evidence.strip():
        raise MarketDataFailure("completeness_evidence_required")
    rows = []
    by_isin = {r.isin: r for r in snapshot.rows}
    for listing_id in partition.universe:
        listings = [
            r
            for r in catalogue.listings
            if r.listing_id == listing_id and r.evidence.admits(on, known_at)
        ]
        isins = {
            a.identifier
            for a in catalogue.aliases
            if a.listing_id == listing_id
            and a.namespace == "isin"
            and a.evidence.admits(on, known_at)
        }
        if len(listings) != 1 or len(isins) != 1 or next(iter(isins)) not in by_isin:
            raise MarketDataFailure("metadata_identity_unresolved")
        instrument = next(
            i for i in catalogue.instruments if i.instrument_id == listings[0].instrument_id
        )
        if instrument.asset_type != "etf":
            raise MarketDataFailure("metadata_identity_unresolved")
        row = by_isin[next(iter(isins))]
        rows.append(
            dict(
                listing_id=listing_id,
                valid_from=on,
                valid_to=partition.end,
                scheme_name=row.scheme_name,
                classification=row.classification,
                locator=row.evidence.locator,
            )
        )
    complete = bool(rows) and all(
        row[field] is not None for row in rows for field in partition.fields
    )
    metadata = {
        "source_evidence": partition.completeness_evidence,
        "catalogue_version": catalogue.version_id,
        "validity": "observation day only; listing date does not date current attributes",
        "source_attributes": [asdict(r) for r in snapshot.rows],
    }
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
        (("etf_metadata", pa.Table.from_pylist(rows, schema=SCHEMAS["etf_metadata"])),),
        "complete" if complete else "partial",
        "etf-catalogue-v1",
        "etf-metadata-v1",
    )
