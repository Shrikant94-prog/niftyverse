"""Orchestrate only the explicitly requested Phase 01 offline fixture."""

from pathlib import Path

import polars as pl

from niftyverse.adapters.fixture import decode_fixture
from niftyverse.result import SliceResult
from niftyverse.storage.arrow import to_arrow
from niftyverse.storage.csv import write_fixture_bundle


def build_fixture(payload: bytes, destination: Path) -> SliceResult:
    """Validate owned JSON, store a new DB, and return its actual query result."""
    batch = decode_fixture(payload)
    arrow = to_arrow(batch)
    from niftyverse.storage.database import store_fixture

    frame = pl.from_arrow(store_fixture(arrow, destination, batch.raw_sha256))
    assert isinstance(frame, pl.DataFrame)
    return SliceResult(frame, batch.rows[:10], len(batch.rows), batch.raw_sha256, "database")


def extract_fixture(payload: bytes, destination: Path) -> SliceResult:
    """Validate the same JSON and write a new CSV bundle without a DuckDB store."""
    batch = decode_fixture(payload)
    frame = pl.from_arrow(to_arrow(batch))
    assert isinstance(frame, pl.DataFrame)
    write_fixture_bundle(batch, destination)
    return SliceResult(frame, batch.rows[:10], len(batch.rows), batch.raw_sha256, "direct-csv")
