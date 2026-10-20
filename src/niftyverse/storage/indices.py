"""Map explicit historical index datasets through the shared publication contract."""

import json
from datetime import datetime
from typing import Any

import pyarrow as pa

from niftyverse.batches import Capture, Partition, ValidatedBatch
from niftyverse.core import ValidationError
from niftyverse.indices import IndexHistory, IndexObservation, IndexPrice, IndexTRI, IndexValuation
from niftyverse.storage.schemas import SCHEMAS


def make_index_batch[T: IndexObservation](
    history: IndexHistory[T],
    *,
    partition: Partition,
    capture: Capture,
    check_id: str,
    checked_at: datetime,
    known_at: datetime,
) -> ValidatedBatch:
    datasets = {
        "index_daily": IndexPrice,
        "index_tri": IndexTRI,
        "index_valuations": IndexValuation,
    }
    if partition.dataset not in datasets:
        raise ValidationError("incompatible index publication dataset")
    rows = []
    for observation in history.rows:
        observation.__post_init__()
        if not isinstance(observation, datasets[partition.dataset]):
            raise ValidationError("incompatible index publication dataset")
        if observation.variant != history.variant:
            raise ValidationError("index history variant mismatch")
        if (
            observation.lineage.raw_sha256 != capture.sha256
            or observation.lineage.source_id != capture.source_id
        ):
            raise ValidationError("index source capture mismatch")
        row: dict[str, Any] = dict(
            variant_id=observation.variant.variant_id,
            index_id=observation.variant.index_id,
            variant_kind=observation.variant.kind,
            session_date=observation.session_date,
            raw_sha256=observation.lineage.raw_sha256,
            locator=observation.lineage.locator,
        )
        if isinstance(observation, IndexPrice):
            row.update(
                open=observation.open,
                high=observation.high,
                low=observation.low,
                close=observation.close,
                unit="index_points",
                missing_reason="source_null" if observation.close is None else None,
            )
        elif isinstance(observation, IndexTRI):
            row.update(
                value=observation.value,
                unit="index_points",
                missing_reason="source_null" if observation.value is None else None,
            )
        else:
            row.update(
                pe=observation.pe,
                pb=observation.pb,
                dividend_yield=observation.dividend_yield,
                ratio_unit=observation.ratio_unit,
                yield_unit=observation.yield_unit,
            )
            row.update(
                {
                    f + "_reason": "source_null" if getattr(observation, f) is None else None
                    for f in ("pe", "pb", "dividend_yield")
                }
            )
        rows.append(row)
    metadata = json.dumps(
        {
            "source_evidence": partition.completeness_evidence,
            "calendar_version": history.calendar_version,
            "variant_id": history.variant.variant_id,
            "gaps": [(str(on), reason) for on, reason in history.gaps],
        },
        sort_keys=True,
    )
    if history.gaps and history.coverage != "partial":
        raise ValidationError("index gaps cannot be complete")
    return ValidatedBatch(
        partition,
        capture,
        check_id,
        checked_at,
        known_at,
        None,
        "active",
        metadata,
        ((partition.dataset, pa.Table.from_pylist(rows, schema=SCHEMAS[partition.dataset])),),
        history.coverage,
        "index-v1",
        "index-normalizer-v1",
    )
