"""Small explicit fixture command; complete CLI/explorer comes in later phases."""

import json
import os
import sys
from pathlib import Path

import click

from niftyverse import __version__, build_fixture, extract_fixture
from niftyverse.core import ValidationError
from niftyverse.display import terminal_summary


@click.group()
@click.version_option(__version__, prog_name="niftyverse")
def main() -> None:
    """niftyverse: explicit local research-data operations."""


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
