"""Small explicit fixture command; complete CLI/explorer comes in later phases."""

import asyncio
import json
import os
import sys
from collections.abc import Coroutine
from dataclasses import fields, replace
from pathlib import Path
from typing import Any

import click

from niftyverse import __version__, build_fixture, extract_fixture
from niftyverse.core import ValidationError
from niftyverse.display import terminal_summary
from niftyverse.execution import AcquisitionFailure, Event, ExecutionResult, Provider
from niftyverse.planning import DataPlan, WorkGraph, compile_plan


@click.group()
@click.version_option(__version__, prog_name="niftyverse")
def main() -> None:
    """niftyverse: explicit local research-data operations."""


@main.command("doctor")
@click.option("--store", type=click.Path(path_type=Path), default=None)
def doctor(store: Path | None) -> None:
    """Report resolved local store paths and best-effort location risks; no I/O."""
    from niftyverse.storage.paths import diagnose_store

    location = diagnose_store(store)
    click.echo(f"Store: {location.root}")
    for name, path in location.paths.items():
        click.echo(f"{name}: {path}")
    for risk in location.risks:
        click.echo(f"WARNING: {risk}")


@main.command("fixture")
@click.option(
    "--input",
    "input_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
    help="Owned JSON fixture; no network acquisition.",
)
@click.option("--output", type=click.Path(path_type=Path), required=True)
@click.option("--mode", type=click.Choice(["direct-csv", "database"]), default="direct-csv")
@click.option(
    "--json", "as_json", is_flag=True, help="Machine-readable committed summary on stdout."
)
@click.option("--plain", is_flag=True, help="Disable terminal color.")
@click.option("--width", type=click.IntRange(20, 240), default=80)
def fixture(
    input_path: Path, output: Path, mode: str, as_json: bool, plain: bool, width: int
) -> None:
    """Run the thin Phase 01 offline fixture slice into a new destination."""
    try:
        payload = input_path.read_bytes()
        result = (build_fixture if mode == "database" else extract_fixture)(payload, output)
    except ValidationError as error:
        raise click.UsageError(f"fixture: {error}; correct the supplied JSON") from error
    except OSError as error:
        raise click.ClickException(
            f"fixture output failed: {error}; choose a new writable path"
        ) from error
    if as_json:
        click.echo(
            json.dumps(
                {
                    "name": "niftyverse",
                    "status": "committed",
                    "mode": result.mode,
                    "committed_rows": result.committed_rows,
                    "raw_sha256": result.raw_sha256,
                }
            )
        )
    else:
        capable = (
            not plain
            and "NO_COLOR" not in os.environ
            and os.environ.get("TERM") != "dumb"
            and sys.stderr.isatty()
        )
        click.echo(terminal_summary(result, width=width, capable=capable), err=True, nl=False)


def _compile(plan_path: Path, context_path: Path, bundles: tuple[Path, ...] = ()) -> WorkGraph:
    from niftyverse.acquisition_inputs import PlanningContext

    if plan_path.stat().st_size > 1024 * 1024 or context_path.stat().st_size > 8 * 1024 * 1024:
        raise ValidationError("plan/context byte limit")
    plan = DataPlan.from_toml(plan_path.read_text(encoding="utf-8"))
    context = PlanningContext.from_json(context_path.read_bytes())
    plan = replace(
        plan,
        local_files=tuple(
            sorted(
                set(plan.local_files)
                | {
                    plan_path.resolve(),
                    context_path.resolve(),
                    *((p / "manifest.json").resolve() for p in bundles),
                },
                key=str,
            )
        ),
    )
    return compile_plan(plan, context.capabilities, calendar=context.calendar)


@main.command("explain")
@click.option("--plan", "plan_path", type=click.Path(exists=True, path_type=Path), required=True)
@click.option(
    "--context", "context_path", type=click.Path(exists=True, path_type=Path), required=True
)
def explain(plan_path: Path, context_path: Path) -> None:
    """Compile only local TOML/context; never acquire data or open a store."""
    try:
        click.echo(json.dumps(_compile(plan_path, context_path).explain()))
    except (ValidationError, OSError) as error:
        raise click.ClickException(str(error)) from error


def _run(coroutine: Coroutine[Any, Any, ExecutionResult]) -> ExecutionResult:
    return asyncio.run(coroutine)


def _acquire_command(
    command: str,
    plan_path: Path,
    context_path: Path,
    inputs: tuple[Path, ...],
    as_json: bool,
    resume: str | None = None,
) -> None:
    from niftyverse import build, extract
    from niftyverse.acquisition_inputs import BundleProvider

    def progress(event: Event) -> None:
        click.echo(
            f"{event.job_id[:12]} {event.state} partitions={event.committed_partitions} "
            f"rows={event.committed_rows} reason={event.reason or ''}",
            err=True,
        )

    try:
        graph = _compile(plan_path, context_path, inputs)
        if (command == "build") != (graph.plan.mode == "build"):
            raise ValidationError("command does not match plan output mode")
        provider = BundleProvider(inputs)
        providers: dict[str, Provider] = {
            j.capability.source_id: provider for j in graph.jobs if j.capability
        }
        result = _run(
            build(graph, providers, resume=resume, on_event=progress)
            if command == "build"
            else extract(graph, providers, on_event=progress)
        )
    except (ValidationError, AcquisitionFailure, OSError) as error:
        raise click.ClickException(str(error)) from error
    summary = {f.name: getattr(result, f.name) for f in fields(result) if f.name != "batches"}
    if as_json:
        click.echo(json.dumps(summary))
    else:
        click.echo(
            f"{result.status}: {result.committed_partitions} published partitions, "
            f"{result.reused_partitions} cached; {result.resume_limit}",
            err=True,
        )
    if result.status != "complete":
        raise click.exceptions.Exit(1)


@main.command("build")
@click.option("--plan", "plan_path", type=click.Path(exists=True, path_type=Path), required=True)
@click.option(
    "--context", "context_path", type=click.Path(exists=True, path_type=Path), required=True
)
@click.option(
    "--input-bundle",
    "inputs",
    multiple=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option("--resume", default=None, help="Compatible persistent run ID.")
@click.option("--json", "as_json", is_flag=True)
def build_command(
    plan_path: Path,
    context_path: Path,
    inputs: tuple[Path, ...],
    resume: str | None,
    as_json: bool,
) -> None:
    """Build from explicit local partition bundles with durable incremental state."""
    _acquire_command("build", plan_path, context_path, inputs, as_json, resume)


@main.command("extract")
@click.option("--plan", "plan_path", type=click.Path(exists=True, path_type=Path), required=True)
@click.option(
    "--context", "context_path", type=click.Path(exists=True, path_type=Path), required=True
)
@click.option(
    "--input-bundle",
    "inputs",
    multiple=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option("--json", "as_json", is_flag=True)
def extract_command(
    plan_path: Path,
    context_path: Path,
    inputs: tuple[Path, ...],
    as_json: bool,
) -> None:
    """Extract bounded memory/files from explicit bundles without creating a store."""
    _acquire_command("extract", plan_path, context_path, inputs, as_json)
