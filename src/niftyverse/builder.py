"""Explicit acquisition entry points and the retained Phase 01 fixture API."""

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import polars as pl

from niftyverse.adapters.fixture import decode_fixture
from niftyverse.result import SliceResult
from niftyverse.storage.arrow import to_arrow
from niftyverse.storage.csv import write_fixture_bundle

if TYPE_CHECKING:
    from niftyverse.execution import Event, ExecutionResult, Provider
    from niftyverse.planning import WorkGraph


async def build(
    graph: WorkGraph,
    providers: dict[str, Provider],
    *,
    resume: str | None = None,
    on_event: Callable[[Event], None] | None = None,
    cancel: asyncio.Event | None = None,
) -> ExecutionResult:
    """Own one persistent store; complete builds return a new immutable history bundle."""
    from niftyverse.core import ValidationError
    from niftyverse.execution import execute
    from niftyverse.storage.bundles import read_bundle
    from niftyverse.storage.catalog import Store
    from niftyverse.storage.snapshots import history_bundle

    if graph.plan.mode != "build":
        raise ValidationError("build requires persistent output mode")
    with Store(graph.plan.store) as store:
        result = await execute(
            graph, providers, store=store, resume=resume, on_event=on_event, cancel=cancel
        )
        if result.status == "complete":
            label = f"build-{result.run_id}"
            path = store.location.paths["snapshots"] / label
            snapshot = (
                read_bundle(path)
                if path.exists()
                else history_bundle(
                    store,
                    label,
                    recipe=graph.plan_hash,
                    policy="retained-at-cutoff-v1",
                )
            )
            if snapshot.manifest["recipe"] != graph.plan_hash:
                raise ValidationError("incompatible existing build snapshot")
            result.history_snapshot_id = snapshot.manifest["snapshot_id"]
        return result


async def extract(
    graph: WorkGraph,
    providers: dict[str, Provider],
    *,
    on_event: Callable[[Event], None] | None = None,
    cancel: asyncio.Event | None = None,
) -> ExecutionResult:
    """Bounded memory/file acquisition; no store or durable resume is created."""
    from niftyverse.core import ValidationError
    from niftyverse.execution import execute

    if graph.plan.mode == "build":
        raise ValidationError("extract requires memory or files output mode")
    return await execute(graph, providers, on_event=on_event, cancel=cancel)


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
