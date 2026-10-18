"""Thin local DuckDB proof; crash durability is deferred to Phase 04."""

from pathlib import Path

import duckdb
import pyarrow as pa


def store_fixture(batch: pa.RecordBatch, destination: Path, raw_sha256: str) -> pa.Table:
    """Store a validated fixture in a new DB and query its typed values."""
    if destination.exists():
        raise FileExistsError(destination)
    with duckdb.connect(str(destination), config={"enable_external_access": False}) as connection:
        connection.register("fixture_input", batch)
        connection.execute("CREATE TABLE observations AS SELECT * FROM fixture_input")
        connection.execute(
            "CREATE TABLE fixture_provenance AS SELECT ? AS raw_sha256, "
            "'owned-fixture-json' AS capture_kind, 'fixture-v1' AS schema_version",
            [raw_sha256],
        )
        return connection.execute(
            "SELECT instrument_id, session_date, close, label FROM observations "
            "ORDER BY session_date, instrument_id"
        ).to_arrow_table()
