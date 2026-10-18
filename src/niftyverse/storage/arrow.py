"""Shared typed representation for both thin sinks."""

import pyarrow as pa

from niftyverse.core import FixtureBatch


def to_arrow(batch: FixtureBatch) -> pa.RecordBatch:
    """Create the fixture schema without inferring identifiers or decimals."""
    schema = pa.schema(
        [
            pa.field("instrument_id", pa.string(), nullable=False),
            pa.field("session_date", pa.date32(), nullable=False),
            pa.field("close", pa.decimal128(18, 4)),
            pa.field("label", pa.string()),
        ]
    )
    return pa.RecordBatch.from_pylist(
        [
            {
                "instrument_id": row.instrument_id,
                "session_date": row.session_date,
                "close": row.close,
                "label": row.label,
            }
            for row in batch.rows
        ],
        schema=schema,
    )
