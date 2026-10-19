"""Local synthetic ingest and two query-shape baselines; never a market benchmark.

Use a local non-synchronized --output directory. First-open means a new DuckDB
connection, not an OS cache flush. JSON profiler bytes/memory are engine metrics.
"""

import argparse
import json
import sys
import time
import tracemalloc
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from niftyverse.batches import Capture, Partition, ValidatedBatch
from niftyverse.storage.catalog import Store
from niftyverse.storage.publication import publish
from niftyverse.storage.schemas import SCHEMAS
from niftyverse.storage.snapshots import history_bundle


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    start = date(2024, 1, 1)
    ids = tuple(f"L{i:04}" for i in range(200))
    rows = [
        {
            "listing_id": listing,
            "series": "EQ",
            "session_date": start + timedelta(days=day),
            "open": None,
            "high": None,
            "low": None,
            "close": Decimal(day + 1),
            "quantity": 1,
            "quantity_unit": "shares",
            "turnover": None,
            "currency": "INR",
            "locator": f"synthetic:{listing}:{day}",
            "missing_reason": None,
        }
        for listing in ids
        for day in range(500)
    ]
    table = pa.Table.from_pylist(rows, schema=SCHEMAS["equity_daily"])
    del rows
    batch = ValidatedBatch(
        Partition(
            "equity_daily",
            start,
            start + timedelta(days=500),
            ids,
            ("close",),
            "raw",
            "owned-synthetic-v1",
            "stable-listing-v1",
            "synthetic-v1",
            "200 generated listings x 500 synthetic calendar dates",
        ),
        Capture(
            b"owned deterministic 200x500 synthetic generator v1",
            "direct_raw",
            "owned",
            "local:synthetic",
        ),
        "baseline",
        datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 1, 1, tzinfo=UTC),
        None,
        "active",
        None,
        (("equity_daily", table),),
        "complete",
        "schema-v1",
        "normalizer-v1",
    )
    tracemalloc.start()
    begin = time.perf_counter()
    with Store(args.output / "store") as store:
        publish(store, batch)
        ingest = time.perf_counter() - begin
        begin = time.perf_counter()
        snapshot = history_bundle(
            store, "benchmark", recipe="synthetic-200x500-v1", policy="retained-at-cutoff-v1"
        )
        export = time.perf_counter() - begin
    _, python_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    # Compare two coarse small-table physical orders; no symbol/day explosion.
    source = snapshot.table("equity_daily").drop(["occurrence_id"])
    layouts = {}
    shapes = {
        "single_listing_history": ("listing_id = 'L0001'", 500),
        "cross_section_date": ("session_date = DATE '2024-09-01'", 200),
    }
    for layout, keys in {
        "listing_date": ["listing_id", "session_date"],
        "date_listing": ["session_date", "listing_id"],
    }.items():
        path = args.output / f"{layout}.parquet"
        pq.write_table(
            source.sort_by([(key, "ascending") for key in keys]),
            path,
            compression="zstd",
            row_group_size=16_384,
        )
        filemeta = pq.ParquetFile(path).metadata
        results = {}
        for shape, (predicate, expected) in shapes.items():
            with duckdb.connect(config={"memory_limit": "256MB", "threads": "2"}) as conn:
                measurements = []
                for run in ("first_open", "warm"):
                    profile = args.output / f"{layout}-{shape}-{run}.json"
                    conn.execute("SET enable_profiling = 'json'")
                    conn.execute("SET profiling_output = ?", [str(profile)])
                    begin = time.perf_counter()
                    result = conn.execute(
                        "SELECT listing_id, session_date, close FROM read_parquet(?) "
                        f"WHERE {predicate}",
                        [str(path)],
                    ).to_arrow_table()
                    elapsed = time.perf_counter() - begin
                    conn.execute("SET enable_profiling = 'no_output'")
                    assert result.num_rows == expected
                    assert all(
                        row["close"] == Decimal((row["session_date"] - start).days + 1)
                        for row in result.to_pylist()
                    )
                    metrics = json.loads(profile.read_text())
                    measurements.append(
                        {
                            "run": run,
                            "seconds": elapsed,
                            "rows": result.num_rows,
                            **{
                                key: metrics[key]
                                for key in (
                                    "total_bytes_read",
                                    "cumulative_rows_scanned",
                                    "system_peak_buffer_memory",
                                    "system_peak_temp_dir_size",
                                )
                            },
                        }
                    )
                results[shape] = measurements
        layouts[layout] = {
            "files": 1,
            "bytes": path.stat().st_size,
            "row_groups": filemeta.num_row_groups,
            "queries": results,
        }
    report = {
        "python": sys.version,
        "duckdb": duckdb.__version__,
        "pyarrow": pa.__version__,
        "rows": table.num_rows,
        "ingest_seconds": ingest,
        "history_export_seconds": export,
        "python_traced_peak_bytes": python_peak,
        "arrow_pool_peak_bytes": pa.default_memory_pool().max_memory(),
        "active_spill_bytes": sum(
            p.stat().st_size for p in (args.output / "store/spill").rglob("*") if p.is_file()
        ),
        "layouts": layouts,
        "cold_scope": "first new connection; OS caches not flushed",
        "logical_oracle": "500 rows for one listing; "
        "200 for one synthetic date; exact decimal values",
    }
    (args.output / "baseline.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
