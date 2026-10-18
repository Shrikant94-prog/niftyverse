"""Bounded representations are pure consumers of the prepared snapshot."""

import dataclasses
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import duckdb
import polars as pl
import pytest
from click.testing import CliRunner

from niftyverse import SliceResult, extract_fixture
from niftyverse.cli import main
from niftyverse.core import FixtureRow
from niftyverse.display import PreviewConfig, render_html, render_text, terminal_summary

PAYLOAD = Path(__file__).with_name("fixtures").joinpath("observations.json").read_bytes()


def test_snapshot_display_without_io(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    result = extract_fixture(PAYLOAD, tmp_path / "out")

    def denied(*args: object, **kwargs: object) -> None:
        raise AssertionError("display performed query, file read or materialization")

    monkeypatch.setattr(SliceResult, "to_polars", denied)
    monkeypatch.setattr(duckdb, "connect", denied)
    monkeypatch.setattr(Path, "open", denied)
    monkeypatch.setattr(pl.DataFrame, "to_dicts", denied)
    monkeypatch.setattr(pl.DataFrame, "to_arrow", denied)
    monkeypatch.setattr(pl.DataFrame, "clone", denied)
    monkeypatch.setattr(pl.LazyFrame, "collect", denied)
    html = result._repr_html_()
    assert "&lt;script&gt;" in html
    assert "<script>" not in html
    assert "4 committed rows" in html
    assert "fixture" in html
    assert "Snapshot pinned" not in html
    assert len(html.encode()) < 65536
    mime = result._repr_mimebundle_()
    assert set(mime) == {"text/plain", "text/html"}
    assert result._repr_mimebundle_(include={"text/plain"}) == {"text/plain": repr(result)}
    assert "niftyverse" in terminal_summary(result, width=60, capable=False)
    for variant in (
        dataclasses.replace(result, preview_rows=(), committed_rows=0),
        dataclasses.replace(result, mode="<script>" * 100000),
    ):
        assert "<script>" not in variant._repr_html_()
        assert "niftyverse" in repr(variant)
        assert "niftyverse" in terminal_summary(variant)


def test_bounds_empty_and_malicious_metadata(tmp_path: Path) -> None:
    result = extract_fixture(PAYLOAD, tmp_path / "out")
    row = FixtureRow(
        "<img src=x onerror=alert(1)>" * 1000,
        date(2026, 9, 1),
        Decimal("1"),
        "\x1b[31m" + "<&\"'" * 10000,
    )
    huge = dataclasses.replace(
        result, preview_rows=(row,) * 10, committed_rows=1000000, mode="</style>" * 100000
    )
    html = render_html(huge)
    assert len(html.encode()) < 65536
    assert "<img" not in html and "</style>" not in html
    assert "1000000 committed rows" in html
    assert "10 of 1000000" in html
    assert "\x1b" not in render_text(huge)
    empty = dataclasses.replace(result, preview_rows=(), committed_rows=0)
    assert "0 committed rows" in render_html(empty)
    assert "No rows" in render_text(empty)
    assert render_html(result, PreviewConfig(max_rows=1)).count("<tr>") == 2


def test_plain_and_capable_terminals(tmp_path: Path) -> None:
    result = extract_fixture(PAYLOAD, tmp_path / "out")
    for width in (60, 100, 160):
        plain = terminal_summary(result, width=width, capable=False)
        capable = terminal_summary(result, width=width, capable=True)
        assert "\x1b[" not in plain
        assert "\x1b[" in capable
        assert all(len(line) <= width for line in plain.splitlines())
        assert "4 committed rows" in plain


def test_cli_json_and_failure_are_honest(tmp_path: Path) -> None:
    runner = CliRunner()
    payload = tmp_path / "input.json"
    payload.write_bytes(PAYLOAD)
    args = ["fixture", "--input", str(payload), "--output", str(tmp_path / "out"), "--json"]
    result = runner.invoke(main, args, env={"TERM": "dumb", "NO_COLOR": "1"})
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["committed_rows"] == 4
    assert "\x1b" not in result.stdout
    assert result.stderr == ""
    repeated = runner.invoke(main, args)
    assert repeated.exit_code != 0
    assert "committed" not in repeated.stdout
    payload.write_text('[{"bad":true}]')
    invalid = runner.invoke(
        main, ["fixture", "--input", str(payload), "--output", str(tmp_path / "invalid")]
    )
    assert invalid.exit_code == 2
    assert not (tmp_path / "invalid").exists()


@pytest.mark.parametrize("config", [{"max_rows": 21}, {"max_cell_chars": 121}, {"max_rows": -1}])
def test_preview_config_rejects_unbounded_values(config: dict[str, int]) -> None:
    with pytest.raises(ValueError):
        PreviewConfig(**config)


def test_explicit_materialization_limit(tmp_path: Path) -> None:
    result = extract_fixture(PAYLOAD, tmp_path / "out")
    with pytest.raises(ValueError, match="max_rows=3"):
        result.to_polars(max_rows=3)
    assert result.to_polars(max_rows=4).height == 4
