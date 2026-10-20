"""Delayed synthetic DAGs through real publication sinks, with independent counts."""

import asyncio
import hashlib
from collections.abc import Awaitable, Callable, Iterator
from dataclasses import replace
from functools import wraps
from pathlib import Path

import pyarrow as pa
import pytest
from test_planning import D1, D2, calendar, capability, plan
from test_store_schema import example

from niftyverse.batches import ValidatedBatch
from niftyverse.core import ValidationError
from niftyverse.execution import Acquired, AcquisitionFailure, Event, execute
from niftyverse.planning import DatasetRequest, Job, WorkGraph, compile_plan
from niftyverse.storage.bundles import read_bundle
from niftyverse.storage.catalog import Store
from niftyverse.storage.schemas import SCHEMAS

_loop: asyncio.AbstractEventLoop


@pytest.fixture(scope="module", autouse=True)
def execution_loop() -> Iterator[None]:
    # Match existing transport tests: create Windows' internal wakeup socket
    # before the function-scoped network denial, without relaxing that denial.
    global _loop
    _loop = asyncio.new_event_loop()
    yield
    _loop.close()


def offline_async[**P](check: Callable[P, Awaitable[None]]) -> Callable[P, None]:
    @wraps(check)
    def run(*args: P.args, **kwargs: P.kwargs) -> None:
        _loop.run_until_complete(check(*args, **kwargs))

    return run


def batch_for(job: Job, attempt: int = 1) -> ValidatedBatch:
    base = example(check=f"{job.id}-{attempt}")
    row = base.tables[0][1].to_pylist()[0]
    row["session_date"] = job.partition.start
    dataset = job.partition.dataset
    if dataset == "etf_daily":
        row["quantity_unit"] = "fund_units"
    return replace(
        base,
        partition=replace(job.partition, completeness_evidence="owned count/grid"),
        tables=((dataset, pa.Table.from_pylist([row], schema=SCHEMAS[dataset])),),
    )


class Provider:
    offline_capable = True

    def __init__(self, *, fail: set[tuple[str, object]] | None = None) -> None:
        self.fail = fail or set()
        self.active = self.peak = self.calls = 0

    async def acquire(self, job: Job, *, attempt: int, offline: bool) -> Acquired:
        self.active += 1
        self.calls += 1
        self.peak = max(self.peak, self.active)
        try:
            await asyncio.sleep(0.005)
            if (job.partition.dataset, job.partition.start) in self.fail:
                raise AcquisitionFailure("owned_failure")
            return Acquired(batch_for(job, attempt))
        finally:
            self.active -= 1


def graph_for(tmp_path: Path, mode: str = "build", **changes: object) -> WorkGraph:
    values: dict[str, object] = dict(mode=mode, workers=2, queue_limit=1, max_attempts=1)
    if mode != "build":
        values["store"] = None
    if mode == "files":
        values["destination"] = str(tmp_path / "output")
    values.update(changes)
    p = plan(tmp_path, **values)
    return compile_plan(p, (capability(), capability("etf_daily")), calendar=calendar())


@offline_async
async def test_bounded_executor_commit_events_and_real_fact_counts(tmp_path: Path) -> None:
    graph = graph_for(tmp_path)
    provider = Provider()
    events: list[Event] = []
    with Store(graph.plan.store) as store:

        def observe(event: Event) -> None:
            events.append(event)
            if event.state == "committed":
                count = store.connection.execute("SELECT count(*) FROM coverage").fetchone()
                assert count == (event.committed_partitions,)

        result = await execute(graph, {"owned": provider}, store=store, on_event=observe)
        assert result.status == "complete"
        assert result.committed_partitions == 2 and result.committed_rows == 2
        assert provider.peak <= 2 and result.peak_pending <= 1
        assert store.connection.execute("SELECT count(*) FROM equity_daily").fetchone() == (2,)
        assert store.connection.execute("SELECT count(*) FROM coverage").fetchone() == (2,)
    for job in graph.jobs:
        states = [e.state for e in events if e.job_id == job.id]
        assert states == ["ready", "fetching", "staged", "validating", "committed"]


@offline_async
async def test_required_poison_blocks_only_dependants_and_optional_failure_warns(
    tmp_path: Path,
) -> None:
    requests = (
        DatasetRequest("equity_daily", ("close",)),
        DatasetRequest("etf_daily", ("close",), depends_on=("equity_daily",)),
    )
    graph = graph_for(
        tmp_path,
        datasets=[
            dict(dataset=r.dataset, fields=list(r.fields), depends_on=list(r.depends_on))
            for r in requests
        ],
    )
    provider = Provider(fail={("equity_daily", D1)})
    with Store(graph.plan.store) as store:
        result = await execute(graph, {"owned": provider}, store=store)
        assert result.status == "failed"
        assert sorted(result.states.values()) == ["blocked", "committed", "committed", "failed"]
        assert result.committed_partitions == 2
        assert store.connection.execute("SELECT count(*) FROM coverage").fetchone() == (2,)
    optional = graph_for(
        tmp_path,
        "memory",
        datasets=[
            {"dataset": "equity_daily", "fields": ["close"]},
            {"dataset": "etf_daily", "fields": ["close"], "required": False},
        ],
    )
    result = await execute(optional, {"owned": Provider(fail={("etf_daily", D1)})})
    assert result.status == "partial" and result.warnings
    assert result.committed_partitions == 3


@offline_async
@pytest.mark.parametrize("mode", ["memory", "files"])
async def test_direct_shared_facts_no_store_and_honest_publication(
    tmp_path: Path,
    mode: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def denied(*args: object, **kwargs: object) -> None:
        raise AssertionError("direct extraction opened store")

    monkeypatch.setattr(Store, "__enter__", denied)
    graph = graph_for(tmp_path, mode)
    events: list[Event] = []

    def observe(event: Event) -> None:
        events.append(event)
        if mode == "files" and event.state == "committed":
            assert read_bundle(tmp_path / "output").manifest["status"] == "complete"

    result = await execute(graph, {"owned": Provider()}, on_event=observe)
    assert result.status == "complete" and result.run_id is None
    assert result.retry_limit == 1 and "re-extract" in result.resume_limit
    assert result.committed_rows == 2
    if mode == "memory":
        assert [b.tables[0][1].to_pylist()[0]["session_date"] for b in result.batches] == [D1, D2]
    else:
        bundle = read_bundle(tmp_path / "output")
        assert bundle.manifest["kind"] == "direct_extract_run"
        for job in graph.jobs:
            child = read_bundle(tmp_path / "output" / "partitions" / job.id)
            assert (
                child.table("equity_daily").to_pylist() == batch_for(job).tables[0][1].to_pylist()
            )
    assert not (tmp_path / "store").exists()


@offline_async
async def test_file_required_failure_no_destination_or_explicit_partial(tmp_path: Path) -> None:
    graph = graph_for(tmp_path, "files")
    result = await execute(graph, {"owned": Provider(fail={("equity_daily", D2)})})
    assert result.status == "failed" and result.committed_partitions == 0
    assert not graph.plan.destination.exists()  # type: ignore[union-attr]
    partial = graph_for(tmp_path, "files", allow_partial=True)
    result = await execute(partial, {"owned": Provider(fail={("equity_daily", D2)})})
    assert result.status == "partial" and result.committed_partitions == 1
    assert read_bundle(tmp_path / "output").manifest["status"] == "partial"


@offline_async
async def test_memory_and_batch_budgets_do_not_publish_failed_unit(tmp_path: Path) -> None:
    graph = graph_for(tmp_path, "memory", batch_bytes=8, memory_bytes=16)
    result = await execute(graph, {"owned": Provider()})
    assert result.status == "failed" and result.committed_partitions == 0
    assert set(result.reasons.values()) == {"batch_budget_exceeded"}


@offline_async
async def test_retries_are_bounded_and_source_wide_failure_stops_capability(
    tmp_path: Path,
) -> None:
    class Transient(Provider):
        async def acquire(self, job: Job, *, attempt: int, offline: bool) -> Acquired:
            self.calls += 1
            raise AcquisitionFailure("temporary", retryable=True)

    graph = graph_for(tmp_path, "memory", max_attempts=2)
    provider = Transient()
    result = await execute(graph, {"owned": provider})
    assert result.status == "failed" and provider.calls == 4
    assert result.attempts == {j.id: 2 for j in graph.jobs}

    class Broken(Transient):
        async def acquire(self, job: Job, *, attempt: int, offline: bool) -> Acquired:
            self.calls += 1
            raise AcquisitionFailure("contract_break", source_wide=True)

    broken = Broken()
    result = await execute(graph, {"owned": broken})
    assert broken.calls == 1
    assert sorted(result.states.values()) == ["blocked", "failed"]


@offline_async
async def test_poisoned_batch_quarantines_raw_and_other_day_commits(tmp_path: Path) -> None:
    class Poison(Provider):
        async def acquire(self, job: Job, *, attempt: int, offline: bool) -> Acquired:
            batch = batch_for(job)
            if job.partition.start == D1:
                batch = replace(
                    batch, capture=replace(batch.capture, body=b"poisoned-owned-source")
                )
                object.__setattr__(
                    batch, "partition", replace(batch.partition, universe=("wrong",))
                )
            return Acquired(batch)

    graph = graph_for(tmp_path)
    with Store(graph.plan.store) as store:
        result = await execute(graph, {"owned": Poison()}, store=store)
        assert result.status == "failed" and result.committed_partitions == 1
        assert sorted(result.states.values()) == ["committed", "quarantined"]
        assert store.connection.execute("SELECT count(*) FROM coverage").fetchone() == (1,)
        quarantine = store.connection.execute(
            "SELECT raw_sha256, reason FROM build_work WHERE status='quarantined'"
        ).fetchone()
        assert quarantine and quarantine[0] == hashlib.sha256(b"poisoned-owned-source").hexdigest()
        assert (store.location.paths["raw"] / quarantine[0][:2] / quarantine[0]).is_file()
        from niftyverse.storage.snapshots import backup, restore

        saved = backup(store, tmp_path / "backup")
        assert f"raw/sha256/{quarantine[0][:2]}/{quarantine[0]}" in saved.manifest["artifacts"]
    restore(tmp_path / "backup", tmp_path / "restored")
    with Store(tmp_path / "restored") as restored:
        assert restored.connection.execute(
            "SELECT count(*) FROM build_work WHERE status='quarantined'"
        ).fetchone() == (1,)


@offline_async
async def test_decoder_value_error_isolated_and_sanitized(tmp_path: Path) -> None:
    class DecodeFailure(Provider):
        async def acquire(self, job: Job, *, attempt: int, offline: bool) -> Acquired:
            if job.partition.start == D1:
                raise ValueError("source secret must not enter diagnostics")
            return Acquired(batch_for(job))

    result = await execute(graph_for(tmp_path, "memory"), {"owned": DecodeFailure()})
    assert result.status == "failed" and result.committed_partitions == 1
    assert set(result.reasons.values()) == {"validation_failed"}


@offline_async
@pytest.mark.parametrize("boundary", ["fetching", "staged", "validating"])
async def test_cancel_at_prepublication_boundaries_preserves_no_coverage(
    tmp_path: Path,
    boundary: str,
) -> None:
    cancel = asyncio.Event()
    graph = graph_for(tmp_path)

    def observe(event: Event) -> None:
        if event.state == boundary:
            cancel.set()

    with Store(graph.plan.store) as store:
        result = await execute(
            graph, {"owned": Provider()}, store=store, cancel=cancel, on_event=observe
        )
        assert result.status == "cancelled" and result.committed_partitions == 0
        assert store.connection.execute("SELECT count(*) FROM coverage").fetchone() == (0,)


@offline_async
async def test_concurrent_admission_and_open_store_preflight(tmp_path: Path) -> None:
    graph = graph_for(tmp_path, "memory", workers=2, queue_limit=2)
    provider = Provider()
    result = await execute(graph, {"owned": provider})
    assert provider.peak == 2 and result.peak_active == 2 and result.peak_pending == 2
    assert result.status == "complete"
    with pytest.raises(ValidationError, match="store"):
        await execute(graph_for(tmp_path), {"owned": provider})
    with pytest.raises(ValidationError, match="resume"):
        await execute(graph, {"owned": provider}, resume="invented")


def test_v5_migration_rollback_and_retained_backup(tmp_path: Path) -> None:
    import duckdb

    from niftyverse.storage.catalog import migrate

    root = tmp_path / "store"
    root.mkdir()
    with duckdb.connect(str(root / "catalog.duckdb")) as conn:
        migrate(conn, target=5)
        conn.execute("CREATE TABLE owner_marker AS SELECT 31 AS value")

        def fail() -> None:
            raise OSError("injected v6 failure")

        with pytest.raises(OSError, match="injected v6"):
            migrate(conn, fault=fail)
        assert conn.execute("SELECT max(version) FROM schema_migrations").fetchone() == (5,)
        assert conn.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_name='build_runs'"
        ).fetchone() == (0,)
    with Store(root) as store:
        assert store.connection.execute(
            "SELECT max(version) FROM schema_migrations"
        ).fetchone() == (6,)
        assert store.connection.execute("SELECT value FROM owner_marker").fetchone() == (31,)
        backups = list(store.location.paths["backups"].glob("pre-migration-v5-*.duckdb"))
        assert len(backups) == 1
    with duckdb.connect(str(backups[0]), read_only=True) as conn:
        assert conn.execute("SELECT max(version) FROM schema_migrations").fetchone() == (5,)
        assert conn.execute("SELECT value FROM owner_marker").fetchone() == (31,)
