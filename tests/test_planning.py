"""Contract-authored local compiler expectations; no acquisition is available here."""

from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from niftyverse.batches import Partition
from niftyverse.calendars import Calendar, Session
from niftyverse.core import ValidationError
from niftyverse.planning import (
    CacheEntry,
    Capability,
    DataPlan,
    DatasetRequest,
    ResearchDependency,
    compile_plan,
    research_preflight,
)

D1, D2, D3 = date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3)


def calendar() -> Calendar:
    return Calendar(
        "owned-calendar",
        "NSE",
        "CM",
        datetime(2025, 12, 31, tzinfo=UTC),
        tuple(
            Session(
                d,
                "trading",
                datetime(2026, 1, d.day, 4, tzinfo=UTC),
                datetime(2026, 1, d.day, 10, tzinfo=UTC),
                "Asia/Kolkata",
                "owned",
                "owned:session",
            )
            for d in (D1, D2)
        ),
    )


def capability(dataset: str = "equity_daily") -> Capability:
    return Capability(
        dataset,
        "owned",
        "synthetic-v1",
        "normalizer-v1",
        "schema-v1",
        ("json", "csv"),
        ("close", "open", "quantity"),
        ("raw",),
        D1,
        D3,
    )


def plan(tmp_path: Path, **changes: object) -> DataPlan:
    values: dict[str, object] = dict(
        version=1,
        start=D1,
        end=D3,
        universe=["0001"],
        datasets=[{"dataset": "equity_daily", "fields": ["close"]}],
        mode="build",
        store=str(tmp_path / "store"),
    )
    values.update(changes)
    return DataPlan.from_mapping(values)


def test_python_toml_determinism_and_local_preflight(tmp_path: Path) -> None:
    python = plan(tmp_path, universe=["0002", "0001"], source_formats=["csv", "json"])
    toml = DataPlan.from_toml(f"""
version = 1
start = 2026-01-01
end = 2026-01-03
universe = ["0001", "0002"]
mode = "build"
store = {str(tmp_path / "store")!r}
source_formats = ["json", "csv"]
[[datasets]]
dataset = "equity_daily"
fields = ["close"]
""")
    a = compile_plan(python, (capability(),), calendar=calendar())
    b = compile_plan(toml, (capability(),), calendar=calendar())
    assert a == b
    assert len(a.jobs) == a.request_estimate == 2
    assert a.jobs[0].partition.start == D1
    assert a.jobs[1].partition.start == D2
    assert a.explain()["plan_hash"] == a.plan_hash
    assert not (tmp_path / "store").exists()


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"version": 2}, "version"),
        ({"surprise": 1}, "unknown"),
        ({"start": "2026-01-03"}, "interval"),
        ({"workers": True}, "workers"),
        ({"timezone": "Mars/Test"}, "timezone"),
        ({"store": None}, "store"),
        ({"source_formats": ["pdf"]}, "source_formats"),
        ({"max_jobs": 1}, "budget"),
        ({"max_requests": 1}, "budget"),
    ],
)
def test_invalid_config_has_no_side_effects(
    tmp_path: Path,
    change: dict[str, object],
    reason: str,
) -> None:
    with pytest.raises(ValidationError, match=reason):
        compile_plan(plan(tmp_path, **change), (capability(),), calendar=calendar())
    assert list(tmp_path.iterdir()) == []


def test_direct_modes_need_no_store_and_policies_are_explicit(tmp_path: Path) -> None:
    for mode in ("memory", "files"):
        p = plan(
            tmp_path,
            mode=mode,
            store=None,
            destination=str(tmp_path / "output") if mode == "files" else None,
        )
        graph = compile_plan(p, (capability(),), calendar=calendar())
        assert graph.plan.mode == mode and graph.plan.store is None
        assert not graph.jobs[0].blocked
    blocked = compile_plan(
        plan(tmp_path), (replace(capability(), formats=("csv",)),), calendar=calendar()
    )
    assert blocked.jobs[0].blocked == ("source_format_unavailable",)
    assert list(tmp_path.iterdir()) == []


def test_cache_is_scope_parser_policy_and_history_aware(tmp_path: Path) -> None:
    p = plan(tmp_path)
    graph = compile_plan(p, (capability(),), calendar=calendar())
    job = graph.jobs[0]
    entry = CacheEntry(job.partition, "owned", "schema-v1", "normalizer-v1", "history_bundle")
    assert compile_plan(p, (capability(),), calendar=calendar(), cache=(entry,)).jobs[0].reuse
    mutations = [
        replace(entry, partition=replace(entry.partition, universe=("other",))),
        replace(entry, partition=replace(entry.partition, fields=("open",))),
        replace(entry, partition=replace(entry.partition, basis="adjusted")),
        replace(entry, partition=replace(entry.partition, quality_policy="other")),
        replace(entry, partition=replace(entry.partition, identity_policy="other")),
        replace(entry, partition=replace(entry.partition, source_generation="other")),
        replace(entry, parser_version="other"),
        replace(entry, schema_version="other"),
        replace(entry, snapshot_kind="resolved_result"),
    ]
    for mutated in mutations:
        assert (
            not compile_plan(p, (capability(),), calendar=calendar(), cache=(mutated,))
            .jobs[0]
            .reuse
        )
    larger = replace(p, universe=("0001", "0002"))
    assert (
        not compile_plan(larger, (capability(),), calendar=calendar(), cache=(entry,))
        .jobs[0]
        .reuse
    )


def test_dependencies_missing_calendar_membership_and_capability_are_local(tmp_path: Path) -> None:
    req = DatasetRequest(
        "security_daily_details", ("delivered_quantity",), membership_scope="Nifty500"
    )
    graph = compile_plan(replace(plan(tmp_path), datasets=(req,)), (), calendar=calendar())
    assert {j.partition.dataset for j in graph.jobs} == {"equity_daily", "security_daily_details"}
    details = next(j for j in graph.jobs if j.partition.dataset == "security_daily_details")
    assert len(details.dependencies) == 1
    assert "membership_unverified:Nifty500" in details.blocked
    assert "discovery_required" in details.blocked
    unknown = compile_plan(plan(tmp_path), (capability(),))
    assert all("calendar_unknown" in j.blocked for j in unknown.jobs)


def test_cycle_rejected_and_required_dependency_promoted(tmp_path: Path) -> None:
    a = DatasetRequest("equity_daily", ("close",), required=False)
    b = DatasetRequest("etf_daily", ("close",), depends_on=("equity_daily",))
    graph = compile_plan(
        replace(plan(tmp_path), datasets=(b, a)),
        (capability(), capability("etf_daily")),
        calendar=calendar(),
    )
    assert all(j.required for j in graph.jobs)
    with pytest.raises(ValidationError, match="cycle"):
        compile_plan(
            replace(plan(tmp_path), datasets=(replace(a, depends_on=("etf_daily",)), b)),
            (capability(), capability("etf_daily")),
            calendar=calendar(),
        )


def test_research_bridge_reports_actual_missing_scopes_without_acquisition(tmp_path: Path) -> None:
    p = plan(tmp_path)
    deps = tuple(
        ResearchDependency(kind, D1, D3, ("0001",), DatasetRequest("equity_daily", ("close",)))
        for kind in ("warmup", "prior_filings", "history")
    )
    result = research_preflight(p, deps, ())
    assert {d.kind for d in result.missing} == {"warmup", "prior_filings", "history"}
    assert result.acquisition is not None
    assert result.acquisition.start == D1 and result.acquisition.end == D3
    assert result.blocked
    partition = Partition(
        "equity_daily",
        D1,
        D3,
        ("0001",),
        ("close",),
        "raw",
        "synthetic-v1",
        "identity-v1",
        "quality-v1",
        "owned",
    )
    resolved = CacheEntry(partition, "owned", "schema-v1", "normalizer-v1", "resolved_result")
    assert len(research_preflight(p, deps, (resolved,)).missing) == 3
    pinned = tuple(replace(d, capability=capability()) for d in deps)
    history = replace(resolved, snapshot_kind="history_bundle")
    assert not research_preflight(p, pinned, (history,)).missing
    assert (
        len(research_preflight(p, pinned, (replace(history, parser_version="old"),)).missing) == 3
    )
    assert list(tmp_path.iterdir()) == []


def test_local_file_hashes_pin_graph_and_budget_before_expansion(tmp_path: Path) -> None:
    local = tmp_path / "identities.txt"
    local.write_text("A", encoding="utf-8")
    p = plan(tmp_path, local_files=[str(local)])
    a = compile_plan(p, (capability(),), calendar=calendar())
    local.write_text("B", encoding="utf-8")
    b = compile_plan(p, (capability(),), calendar=calendar())
    assert a.plan_hash != b.plan_hash
    with pytest.raises(ValidationError, match="budget"):
        compile_plan(replace(p, end=date(9999, 1, 1)), (capability(),))
