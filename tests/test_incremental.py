"""Restart, overlap and honest source-completeness contracts using real stores."""

import asyncio
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest
from test_execution import Provider, batch_for, execution_loop, graph_for, offline_async
from test_planning import D1, D2, calendar, capability
from test_store_schema import NOW

from niftyverse.batches import identity
from niftyverse.core import ValidationError
from niftyverse.execution import Acquired, AcquisitionFailure, Event, PageEvidence, execute
from niftyverse.planning import Job, compile_plan
from niftyverse.storage.builds import committed_cache
from niftyverse.storage.catalog import Store

__all__ = ["execution_loop"]


@offline_async
async def test_cancel_reopen_resume_and_unchanged_rerun(tmp_path: Path) -> None:
    graph = graph_for(tmp_path)
    stop = asyncio.Event()

    def observe(event: Event) -> None:
        if event.state == "committed":
            stop.set()

    provider = Provider()
    with Store(graph.plan.store) as store:
        first = await execute(
            graph, {"owned": provider}, store=store, cancel=stop, on_event=observe
        )
        assert first.status == "cancelled" and first.committed_partitions == 1
        assert first.run_id
        preserved = store.read_table("equity_daily").to_pylist()
    with Store(graph.plan.store) as store:
        resumed = await execute(graph, {"owned": provider}, store=store, resume=first.run_id)
        assert resumed.status == "complete" and resumed.committed_partitions == 1
        assert resumed.reused_partitions == 1
        assert store.read_table("equity_daily").to_pylist()[:1] == preserved
        before = {
            name: store.connection.execute(f"SELECT count(*) FROM {name}").fetchone()
            for name in ("equity_daily", "occurrences", "source_checks", "coverage")
        }
        calls = provider.calls
        rerun = await execute(graph, {"owned": provider}, store=store)
        assert rerun.status == "complete" and rerun.reused_partitions == 2
        assert provider.calls == calls
        assert before == {
            name: store.connection.execute(f"SELECT count(*) FROM {name}").fetchone()
            for name in before
        }
        assert len(committed_cache(store)) == 2


@offline_async
@pytest.mark.parametrize("boundary", ["before_commit", "after_commit", "after_ack"])
async def test_commit_ack_interruption_reconciles_durable_state(
    tmp_path: Path,
    boundary: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import niftyverse.storage.publication as publication

    original = publication.publish

    def fault(point: str) -> None:
        if point == boundary:
            raise asyncio.CancelledError

    def interrupted(*args, **kwargs):  # type: ignore[no-untyped-def]
        return original(*args, **kwargs, fault=fault)

    graph = graph_for(tmp_path)
    provider = Provider()
    with Store(graph.plan.store) as store:
        with monkeypatch.context() as context:
            context.setattr(publication, "publish", interrupted)
            first = await execute(graph, {"owned": provider}, store=store)
        assert first.run_id
        count = 0 if boundary == "before_commit" else 2
        assert store.connection.execute("SELECT count(*) FROM coverage").fetchone() == (count,)
    with Store(graph.plan.store) as store:
        resumed = await execute(graph, {"owned": provider}, store=store, resume=first.run_id)
        assert resumed.status == "complete"
        assert store.connection.execute("SELECT count(*) FROM equity_daily").fetchone() == (2,)
        assert store.connection.execute("SELECT count(*) FROM occurrences").fetchone() == (2,)
        assert store.connection.execute("SELECT count(*) FROM coverage").fetchone() == (2,)


@offline_async
async def test_incompatible_checkpoint_and_changed_local_input_fail_before_acquisition(
    tmp_path: Path,
) -> None:
    graph = graph_for(tmp_path)
    provider = Provider()
    with Store(graph.plan.store) as store:
        first = await execute(graph, {"owned": provider}, store=store)
        changed = compile_plan(
            replace(graph.plan, universe=("0002",)), (capability(),), calendar=calendar()
        )
        calls = provider.calls
        with pytest.raises(ValidationError, match="incompatible checkpoint"):
            await execute(changed, {"owned": provider}, store=store, resume=first.run_id)
        assert provider.calls == calls
        assert store.connection.execute("SELECT count(*) FROM coverage").fetchone() == (2,)
    local = tmp_path / "input.txt"
    local.write_text("A", encoding="utf-8")
    local_graph = graph_for(tmp_path, "memory", local_files=[str(local)])
    local.write_text("B", encoding="utf-8")
    with pytest.raises(ValidationError, match="local input changed"):
        await execute(local_graph, {"owned": provider})
    assert provider.calls == calls


@offline_async
async def test_refresh_overlap_unchanged_poll_repair_and_wider_reconcile(tmp_path: Path) -> None:
    class Revised(Provider):
        async def acquire(self, job: Job, *, attempt: int, offline: bool) -> Acquired:
            self.calls += 1
            batch = batch_for(job)
            table = batch.tables[0][1]
            rows = table.to_pylist()
            from decimal import Decimal

            import pyarrow as pa

            rows[0]["close"] = Decimal("2.50")
            return Acquired(
                replace(
                    batch,
                    tables=(
                        (job.partition.dataset, pa.Table.from_pylist(rows, schema=table.schema)),
                    ),
                    capture=replace(batch.capture, body=b"owned revision"),
                    known_at=NOW + timedelta(days=1),
                    checked_at=NOW + timedelta(days=1),
                )
            )

    graph = graph_for(tmp_path)
    with Store(graph.plan.store) as store:
        await execute(graph, {"owned": Provider()}, store=store)
        refresh = compile_plan(
            replace(graph.plan, operation="refresh", overlap_sessions=1),
            (capability(),),
            calendar=calendar(),
            cache=committed_cache(store),
        )
        revised = Revised()
        result = await execute(refresh, {"owned": revised}, store=store)
        assert revised.calls == 1 and result.reused_partitions == 1
        assert store.connection.execute("SELECT count(*) FROM equity_daily").fetchone() == (3,)
        assert store.connection.execute("SELECT count(*) FROM source_checks").fetchone() == (3,)
        old = store.connection.execute(
            "SELECT close FROM equity_daily WHERE session_date=?", [D1]
        ).fetchall()
        assert len(old) == 1
        await execute(refresh, {"owned": revised}, store=store)
        assert store.connection.execute("SELECT count(*) FROM equity_daily").fetchone() == (3,)
        assert store.connection.execute("SELECT count(*) FROM source_checks").fetchone() == (4,)
        repair = compile_plan(
            replace(
                graph.plan,
                operation="repair",
                repair_partitions=(graph.jobs[0].partition.identity,),
            ),
            (capability(),),
            calendar=calendar(),
        )
        await execute(repair, {"owned": revised}, store=store)
        assert revised.calls == 3
        reconcile = compile_plan(
            replace(graph.plan, operation="reconcile"), (capability(),), calendar=calendar()
        )
        await execute(reconcile, {"owned": revised}, store=store)
        assert revised.calls == 5
        assert store.connection.execute("SELECT count(*) FROM equity_daily").fetchone() == (4,)


@offline_async
async def test_offline_missing_inputs_deferred_without_calling_network_provider(
    tmp_path: Path,
) -> None:
    provider = Provider()
    provider.offline_capable = False
    graph = graph_for(tmp_path, "memory", offline=True)
    result = await execute(graph, {"owned": provider})
    assert result.status == "failed" and provider.calls == 0
    assert set(result.states.values()) == {"deferred"}
    assert set(result.reasons.values()) == {"offline_missing_input"}


@offline_async
@pytest.mark.parametrize(
    "mutation", ["failed_page", "mutation", "repeat", "cursor", "count", "unstable"]
)
async def test_pagination_failures_never_advance_coverage_and_other_day_completes(
    tmp_path: Path,
    mutation: str,
) -> None:
    class Pages(Provider):
        async def acquire(self, job: Job, *, attempt: int, offline: bool) -> Acquired:
            if job.partition.start == D1 and mutation == "failed_page":
                raise AcquisitionFailure("failed_page")
            pages: tuple[PageEvidence, ...] = (
                PageEvidence("first", "second", identity("page1"), "generation1", 1),
                PageEvidence("second", None, identity("page2"), "generation1", 1),
            )
            expected = 2
            if job.partition.start == D1:
                if mutation == "mutation":
                    pages = (pages[0], replace(pages[1], snapshot_id="generation2"))
                if mutation == "repeat":
                    pages = (pages[0], replace(pages[1], content_sha256=pages[0].content_sha256))
                if mutation == "cursor":
                    pages = (pages[0], replace(pages[1], cursor="first"))
                if mutation == "count":
                    expected = 3
                if mutation == "unstable":
                    pages = tuple(replace(p, snapshot_id=None) for p in pages)
            return Acquired(batch_for(job), pages, expected)

    graph = compile_plan(
        graph_for(tmp_path).plan,
        (replace(capability(), paginated=True, requests_per_job=2),),
        calendar=calendar(),
    )
    with Store(graph.plan.store) as store:
        result = await execute(graph, {"owned": Pages()}, store=store)
        assert result.status == "failed" and result.committed_partitions == 1
        assert store.connection.execute("SELECT count(*) FROM coverage").fetchone() == (1,)
        assert store.connection.execute("SELECT session_date FROM equity_daily").fetchone() == (
            D2,
        )


@offline_async
async def test_direct_mode_reextracts_instead_of_trusting_persistent_cache(tmp_path: Path) -> None:
    graph = graph_for(tmp_path)
    with Store(graph.plan.store) as store:
        await execute(graph, {"owned": Provider()}, store=store)
        cache = committed_cache(store)
    direct = compile_plan(
        replace(graph.plan, mode="memory", store=None),
        (capability(),),
        calendar=calendar(),
        cache=cache,
    )
    assert all(j.reuse for j in direct.jobs)
    provider = Provider()
    result = await execute(direct, {"owned": provider})
    assert provider.calls == 2 and result.run_id is None and result.committed_partitions == 2


@offline_async
@pytest.mark.parametrize("mode", ["memory", "files"])
async def test_explicit_partial_batch_retains_facts_without_complete_progress(
    tmp_path: Path,
    mode: str,
) -> None:
    from niftyverse.storage.bundles import read_bundle

    class Partial(Provider):
        async def acquire(self, job: Job, *, attempt: int, offline: bool) -> Acquired:
            return Acquired(replace(batch_for(job), coverage="partial", reason="missing_page"))

    graph = graph_for(tmp_path, mode, allow_partial=True)
    result = await execute(graph, {"owned": Partial()})
    assert result.status == "partial" and result.committed_partitions == 0
    assert set(result.states.values()) == {"partial"}
    if mode == "memory":
        assert len(result.batches) == 2 and all(b.coverage == "partial" for b in result.batches)
    else:
        assert read_bundle(tmp_path / "output").manifest["status"] == "partial"
        for job in graph.jobs:
            child = read_bundle(tmp_path / "output" / "partitions" / job.id)
            assert child.manifest["status"] == "partial"
            assert child.table("equity_daily").num_rows == 1
