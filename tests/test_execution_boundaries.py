"""Scoped final review reproducers for data/cache/acknowledgement boundaries."""

import asyncio
from dataclasses import replace
from pathlib import Path

import pytest
from test_execution import Provider, batch_for, execution_loop, graph_for, offline_async
from test_planning import D1, calendar, capability

from niftyverse.core import ValidationError
from niftyverse.execution import Acquired, AcquisitionFailure, Event, execute
from niftyverse.planning import DatasetRequest, Job, compile_plan
from niftyverse.storage.catalog import Store
from niftyverse.storage.snapshots import backup

__all__ = ["execution_loop"]


@offline_async
async def test_cached_dependant_does_not_bypass_failed_refreshed_dependency(
    tmp_path: Path,
) -> None:
    p = graph_for(tmp_path).plan
    requests = (
        DatasetRequest("equity_daily", ("close",)),
        DatasetRequest("etf_daily", ("close",), depends_on=("equity_daily",)),
    )
    graph = compile_plan(
        replace(p, datasets=requests), (capability(), capability("etf_daily")), calendar=calendar()
    )
    with Store(p.store) as store:
        await execute(graph, {"owned": Provider()}, store=store)
        repair = compile_plan(
            replace(
                p,
                datasets=requests,
                operation="repair",
                repair_partitions=(graph.jobs[0].partition.identity,),
            ),
            (capability(), capability("etf_daily")),
            calendar=calendar(),
        )
        result = await execute(
            repair, {"owned": Provider(fail={("equity_daily", D1)})}, store=store
        )
        dependent = next(
            j
            for j in repair.jobs
            if j.partition.dataset == "etf_daily" and j.partition.start == D1
        )
        assert result.status == "failed" and result.states[dependent.id] == "blocked"
        assert result.reasons[dependent.id] == "dependency_failed"
        assert store.connection.execute("SELECT count(*) FROM coverage").fetchone() == (4,)


@offline_async
async def test_source_wide_break_cancels_admitted_same_source_before_publication(
    tmp_path: Path,
) -> None:
    started = asyncio.Event()
    stopped = asyncio.Event()

    class Broken(Provider):
        async def acquire(self, job: Job, *, attempt: int, offline: bool) -> Acquired:
            if job.partition.start == D1:
                await started.wait()
                raise AcquisitionFailure("source_contract_break", source_wide=True)
            started.set()
            try:
                await asyncio.sleep(0.03)
                return Acquired(batch_for(job))
            finally:
                stopped.set()

    result = await execute(
        graph_for(tmp_path, "memory", workers=2, queue_limit=2), {"owned": Broken()}
    )
    assert stopped.is_set()
    assert result.committed_partitions == 0
    assert sorted(result.states.values()) == ["blocked", "failed"]


@offline_async
async def test_validation_error_from_progress_consumer_is_not_quarantined_data(
    tmp_path: Path,
) -> None:
    graph = graph_for(tmp_path)

    def observer(event: Event) -> None:
        if event.state == "committed":
            raise ValidationError("observer rejected acknowledgement")

    with Store(graph.plan.store) as store:
        with pytest.raises(ValidationError, match="observer rejected"):
            await execute(graph, {"owned": Provider()}, store=store, on_event=observer)
        assert store.connection.execute("SELECT status FROM build_work").fetchone() == (
            "committed",
        )
        assert store.connection.execute("SELECT count(*) FROM coverage").fetchone() == (1,)
        run = store.connection.execute("SELECT run_id FROM build_runs").fetchone()
    with Store(graph.plan.store) as store:
        assert run
        resumed = await execute(graph, {"owned": Provider()}, store=store, resume=run[0])
        assert resumed.status == "complete" and resumed.reused_partitions == 1
        assert store.connection.execute("SELECT count(*) FROM equity_daily").fetchone() == (2,)


@offline_async
async def test_actual_task_cancellation_reopens_and_resumes(tmp_path: Path) -> None:
    started = asyncio.Event()
    stopped = asyncio.Event()

    class Hanging(Provider):
        async def acquire(self, job: Job, *, attempt: int, offline: bool) -> Acquired:
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                stopped.set()
            raise AssertionError("unreachable")

    graph = graph_for(tmp_path)
    with Store(graph.plan.store) as store:
        task = asyncio.create_task(execute(graph, {"owned": Hanging()}, store=store))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert stopped.is_set()
        assert store.connection.execute("SELECT status FROM build_runs").fetchone() == (
            "interrupted",
        )
        run = store.connection.execute("SELECT run_id FROM build_runs").fetchone()
        assert store.connection.execute("SELECT count(*) FROM coverage").fetchone() == (0,)
        backup(store, tmp_path / "backup")
    with Store(graph.plan.store) as store:
        assert run
        resumed = await execute(graph, {"owned": Provider()}, store=store, resume=run[0])
        assert resumed.status == "complete" and resumed.committed_partitions == 2


@offline_async
async def test_readiness_exposes_requested_scope_nulls_and_unknown_inputs(tmp_path: Path) -> None:
    graph = graph_for(tmp_path, "memory")
    result = await execute(graph, {"owned": Provider()})
    assert result.quality["requested_interval"] == ["2026-01-01", "2026-01-03"]
    assert result.quality["universe"] == ["0001"]
    for job in graph.jobs:
        detail = result.quality["partitions"][job.id]
        assert detail["expected_sessions"] == 1 and detail["observed_sessions"] == 1
        assert detail["null_counts"] == {"close": 0}
        assert detail["coverage"] == "complete"
        assert detail["parser_version"] == "normalizer-v1"
    blocked = compile_plan(graph.plan, (capability(),))
    result = await execute(blocked, {"owned": Provider()})
    assert result.status == "failed"
    assert all(
        d["expected_sessions"] is None and d["coverage"] == "unavailable"
        for d in result.quality["partitions"].values()
    )


@offline_async
@pytest.mark.parametrize("interrupt", [False, True])
async def test_repaired_revision_invalidates_only_affected_dependants_including_resume(
    tmp_path: Path,
    interrupt: bool,
) -> None:
    from datetime import timedelta
    from decimal import Decimal

    import pyarrow as pa
    from test_store_schema import NOW

    class Revision(Provider):
        async def acquire(self, job: Job, *, attempt: int, offline: bool) -> Acquired:
            self.calls += 1
            batch = batch_for(job)
            table = batch.tables[0][1]
            rows = table.to_pylist()
            rows[0]["close"] = Decimal("2.5")
            return Acquired(
                replace(
                    batch,
                    capture=replace(batch.capture, body=b"revised close 2.5"),
                    tables=(
                        (job.partition.dataset, pa.Table.from_pylist(rows, schema=table.schema)),
                    ),
                    known_at=NOW + timedelta(days=1),
                    checked_at=NOW + timedelta(days=1),
                )
            )

    p = graph_for(tmp_path).plan
    p = replace(
        p,
        datasets=(
            DatasetRequest("equity_daily", ("close",)),
            DatasetRequest("etf_daily", ("close",), depends_on=("equity_daily",)),
        ),
    )
    caps = (capability(), capability("etf_daily"))
    graph = compile_plan(p, caps, calendar=calendar())
    stop = asyncio.Event()

    def observe(event: Event) -> None:
        if interrupt and event.state == "committed":
            stop.set()

    revision = Revision()
    with Store(p.store) as store:
        await execute(graph, {"owned": Provider()}, store=store)
        repair = compile_plan(
            replace(p, operation="repair", repair_partitions=(graph.jobs[0].partition.identity,)),
            caps,
            calendar=calendar(),
        )
        result = await execute(
            repair, {"owned": revision}, store=store, cancel=stop, on_event=observe
        )
        if interrupt:
            assert result.status == "cancelled" and result.run_id
            result = await execute(repair, {"owned": revision}, store=store, resume=result.run_id)
        assert result.status == "complete" and revision.calls == 2
        expected_changed = {j.partition.identity for j in graph.jobs if j.partition.start == D1}
        assert set(result.changed_partitions) == expected_changed
        assert store.connection.execute("SELECT count(*) FROM equity_daily").fetchone() == (3,)
        assert store.connection.execute("SELECT count(*) FROM etf_daily").fetchone() == (3,)
        if interrupt:
            again = await execute(repair, {"owned": revision}, store=store, resume=result.run_id)
            assert again.status == "complete" and revision.calls == 2
