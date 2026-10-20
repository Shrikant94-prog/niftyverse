"""PH-09-GATE: integrated multi-dataset execution, explicit gaps and real CLI events."""

import asyncio
import json
from dataclasses import asdict, replace
from pathlib import Path

import pytest
from click.testing import CliRunner
from test_execution import Provider, batch_for, execution_loop, graph_for, offline_async
from test_planning import calendar, capability

from niftyverse import build, extract
from niftyverse.cli import main
from niftyverse.execution import Event
from niftyverse.planning import DatasetRequest, compile_plan
from niftyverse.storage.bundles import read_bundle, write_direct
from niftyverse.storage.catalog import Store

__all__ = ["execution_loop"]


@offline_async
async def test_integrated_build_cancel_resume_unchanged_and_direct_no_store(
    tmp_path: Path,
) -> None:
    p = graph_for(tmp_path).plan
    p = replace(
        p,
        datasets=(
            DatasetRequest("equity_daily", ("close",)),
            DatasetRequest("etf_daily", ("close",), depends_on=("equity_daily",)),
        ),
    )
    graph = compile_plan(p, (capability(), capability("etf_daily")), calendar=calendar())
    stop = asyncio.Event()

    def observe(event: Event) -> None:
        if event.state == "committed" and event.committed_partitions == 1:
            stop.set()

    provider = Provider()
    first = await build(graph, {"owned": provider}, cancel=stop, on_event=observe)
    assert first.status == "cancelled" and first.run_id and first.history_snapshot_id is None
    second = await build(graph, {"owned": provider}, resume=first.run_id)
    assert second.status == "complete" and second.reused_partitions == 1
    assert second.committed_partitions == 3 and second.history_snapshot_id
    before = provider.calls
    third = await build(graph, {"owned": provider})
    assert third.status == "complete" and third.reused_partitions == 4
    assert provider.calls == before
    with Store(p.store) as store:
        assert store.connection.execute("SELECT count(*) FROM equity_daily").fetchone() == (2,)
        assert store.connection.execute("SELECT count(*) FROM etf_daily").fetchone() == (2,)
        assert store.connection.execute("SELECT count(*) FROM source_checks").fetchone() == (4,)
        assert store.connection.execute("SELECT count(*) FROM coverage").fetchone() == (4,)
        history = read_bundle(store.location.paths["snapshots"] / f"build-{second.run_id}")
        assert history.manifest["kind"] == "history_bundle"
        assert history.manifest["snapshot_id"] == second.history_snapshot_id
    direct_graph = compile_plan(
        replace(p, mode="files", store=None, destination=tmp_path / "direct"),
        (capability(), capability("etf_daily")),
        calendar=calendar(),
    )
    direct = await extract(direct_graph, {"owned": Provider()})
    assert (
        direct.status == "complete"
        and direct.run_id is None
        and direct.history_snapshot_id is None
    )
    assert not (tmp_path / "direct" / "catalog.duckdb").exists()
    root = read_bundle(tmp_path / "direct")
    assert root.manifest["status"] == "complete"
    assert set(root.manifest["jobs"].values()) == {"committed"}
    for job in direct_graph.jobs:
        child = read_bundle(root.path / "partitions" / job.id)
        assert child.table(job.partition.dataset).equals(batch_for(job).tables[0][1])


@offline_async
async def test_unverified_membership_blocks_dependent_work_only(tmp_path: Path) -> None:
    p = graph_for(tmp_path, "memory").plan
    graph = compile_plan(
        replace(
            p,
            datasets=(
                DatasetRequest("equity_daily", ("close",)),
                DatasetRequest("etf_daily", ("close",), membership_scope="unverified-Nifty500"),
            ),
        ),
        (capability(), capability("etf_daily")),
        calendar=calendar(),
    )
    result = await extract(graph, {"owned": Provider()})
    assert result.status == "failed" and result.committed_partitions == 2
    assert list(result.states.values()).count("blocked") == 2
    assert set(result.reasons.values()) == {"membership_unverified:unverified-Nifty500"}
    assert not (tmp_path / "store").exists()


def cli_inputs(tmp_path: Path) -> tuple[Path, Path, list[Path]]:
    graph = graph_for(tmp_path)
    context = tmp_path / "context.json"
    context.write_text(
        json.dumps(
            {"capabilities": [asdict(capability())], "calendar": asdict(calendar())}, default=str
        ),
        encoding="utf-8",
    )
    config = tmp_path / "plan.toml"
    config.write_text(
        f"""version = 1
start = 2026-01-01
end = 2026-01-03
universe = ["0001"]
store = {str(tmp_path / "store")!r}
max_attempts = 1
[[datasets]]
dataset = "equity_daily"
fields = ["close"]
""",
        encoding="utf-8",
    )
    bundles = []
    for job in graph.jobs:
        path = tmp_path / f"input-{job.partition.start}"
        write_direct(batch_for(job), path)
        bundles.append(path)
    return config, context, bundles


def test_cli_explain_is_local_and_progress_uses_committed_events(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from test_execution import _loop

    import niftyverse.cli as cli

    monkeypatch.setattr(cli, "_run", _loop.run_until_complete)
    config, context, bundles = cli_inputs(tmp_path)
    args = ["--plan", str(config), "--context", str(context)]
    runner = CliRunner()
    explained = runner.invoke(main, ["explain", *args])
    assert explained.exit_code == 0, explained.output
    assert len(json.loads(explained.stdout)["jobs"]) == 2
    assert not (tmp_path / "store").exists()
    bundle_args = [arg for b in bundles for arg in ("--input-bundle", str(b))]
    result = runner.invoke(main, ["build", *args, *bundle_args, "--json"])
    assert result.exit_code == 0, result.output
    summary = json.loads(result.stdout)
    assert summary["status"] == "complete" and summary["committed_partitions"] == 2
    assert result.stderr.count(" committed ") == 2
    rerun = runner.invoke(main, ["build", *args, *bundle_args, "--json"])
    assert rerun.exit_code == 0 and json.loads(rerun.stdout)["reused_partitions"] == 2
    assert " committed " not in rerun.stderr


def test_cli_offline_missing_bundle_reports_failure_without_false_complete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from test_execution import _loop

    import niftyverse.cli as cli

    monkeypatch.setattr(cli, "_run", _loop.run_until_complete)
    config, context, _ = cli_inputs(tmp_path)
    config.write_text(
        config.read_text(encoding="utf-8").replace(
            f"store = {str(tmp_path / 'store')!r}", 'mode = "memory"\noffline = true'
        ),
        encoding="utf-8",
    )
    result = CliRunner().invoke(
        main, ["extract", "--plan", str(config), "--context", str(context), "--json"]
    )
    assert result.exit_code == 1
    summary = json.loads(result.stdout)
    assert summary["status"] == "failed" and summary["run_id"] is None
    assert summary["committed_partitions"] == 0
    assert set(summary["reasons"].values()) == {"offline_missing_input"}
    assert not (tmp_path / "store").exists()
