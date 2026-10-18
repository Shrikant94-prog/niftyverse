"""Bounded representations are pure consumers of the prepared snapshot."""

import dataclasses
import io
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import duckdb
import polars as pl
import pytest
from click.testing import CliRunner
from rich.console import Console
from rich.text import Text

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
    console = Console(file=io.StringIO(), width=100, height=25, color_system=None)
    console.print(result)
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
    assert "<img" not in html and "&lt;/style&gt;" in html
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
        assert len(plain.splitlines()[0]) == width
        assert len(Text.from_ansi(capable).plain.splitlines()[0]) == width
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


def test_polished_preview_preserves_display_semantics(tmp_path: Path) -> None:
    result = extract_fixture(PAYLOAD, tmp_path / "out")
    html = result._repr_html_()
    text = repr(result)
    assert "Observation preview" in html
    assert "Owned offline fixture" in html
    assert "CSV bundle" in html
    assert "Provenance" in html
    assert "123.4500" in html and "99,999,999,999,999.9999" in html
    assert "0001" in html and "__NULL__" in html
    assert 'aria-label="Empty text"' in html
    assert 'aria-label="Null value"' in html
    assert '""' in text and "<null>" in text
    assert sum(len(value.encode()) for value in result._repr_mimebundle_().values()) <= 65536
    narrow = terminal_summary(result, width=60, capable=False)
    wide = terminal_summary(result, width=100, capable=False)
    assert "4 committed rows" in narrow
    assert "CSV bundle" in narrow
    assert "Instrument" in wide and "Session" in wide
    assert "0001" in wide and "__NULL__" in wide
    assert "123.4500" in wide


def test_explicit_terminal_capability_is_reproducible(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = extract_fixture(PAYLOAD, tmp_path / "out")
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("TERM", "dumb")
    colored = terminal_summary(result, width=100, capable=True)
    assert "36m" in colored
    assert len(Text.from_ansi(colored).plain.splitlines()[0]) == 100
    assert "\x1b" not in terminal_summary(result, width=100, capable=False)


@pytest.mark.parametrize("legacy_windows", [False, True])
def test_rich_protocol_respects_no_color_and_plain_encoding(
    tmp_path: Path,
    legacy_windows: bool,
) -> None:
    result = extract_fixture(PAYLOAD, tmp_path / "out")
    for width in (20, 60, 100, 160):
        stream = io.StringIO()
        console = Console(
            file=stream,
            width=width,
            height=25,
            force_terminal=True,
            color_system="standard",
            no_color=True,
            legacy_windows=legacy_windows,
        )
        console.print(result)
        plain = stream.getvalue()
        assert "\x1b" not in plain and plain.isascii()
        assert all(len(line) <= width for line in plain.splitlines())
        if not legacy_windows:
            assert all(len(line) == width for line in plain.splitlines())
        assert "fixture" in plain or width == 20  # Smallest layout wraps words.


@pytest.mark.parametrize("width", [60, 100])
def test_rich_protocol_card_zones_and_responsive_preview(tmp_path: Path, width: int) -> None:
    result = extract_fixture(PAYLOAD, tmp_path / "out")
    stream = io.StringIO()
    console = Console(
        file=stream,
        width=width,
        height=25,
        force_terminal=True,
        color_system="standard",
        no_color=False,
        legacy_windows=False,
    )
    console.print(result)
    rendered = stream.getvalue()
    assert rendered == terminal_summary(result, width=width, capable=True)
    lines = Text.from_ansi(rendered).plain.splitlines()
    assert lines[0].startswith("╭") and lines[-1].startswith("╰")
    assert sum(line.startswith("├") and line.endswith("┤") for line in lines) == 2
    assert all(len(line) == width for line in lines)
    assert "4 committed rows" in rendered and "CSV bundle" in rendered
    assert "Source" in rendered and "Preview dates" in rendered and "Input hash" in rendered
    assert ("Instrument" in rendered) == (width == 100)
    assert ("99,999,999,999,999.9999" in rendered) == (width == 100)
    assert f"Preview only: {4 if width == 100 else 0} of 4 rows" in rendered


def test_shared_value_semantics_and_literal_markup(tmp_path: Path) -> None:
    result = extract_fixture(PAYLOAD, tmp_path / "out")
    rows = (
        FixtureRow("0001", date(2026, 9, 1), None, None),
        FixtureRow("0002", date(2026, 9, 2), Decimal("0.0000"), ""),
        FixtureRow("0003", date(2026, 9, 3), Decimal("99999999999.9999"), "__NULL__"),
        FixtureRow("0004", date(2026, 9, 4), Decimal("123.4500"), "<script>[red]x[/red]</script>"),
    )
    result = dataclasses.replace(result, preview_rows=rows)
    output = terminal_summary(result, width=100, capable=True)
    styled = Text.from_ansi(output)
    assert "<null>" in styled.plain and '""' in styled.plain and "__NULL__" in styled.plain
    assert "<script>[red]x[/red]</script>" in styled.plain
    assert "99,999,999,999.9999" in styled.plain
    console = Console(color_system="standard")
    zero = styled.get_style_at_offset(console, styled.plain.index("0.0000"))
    nonzero = styled.get_style_at_offset(console, styled.plain.index("123.4500"))
    assert zero.color is not None and zero.color.number == 8  # ANSI muted slate
    assert nonzero != zero
    html = result._repr_html_()
    assert '<span class="nv-null" aria-label="Null value">&lt;null&gt;</span>' in html
    assert '<span class="nv-empty" aria-label="Empty text">&quot;&quot; (empty)</span>' in html
    assert '<td class="nv-number nv-zero">0.0000</td>' in html
    assert "__NULL__</td>" in html
    assert "&lt;script&gt;[red]x[/red]&lt;/script&gt;" in html and "<script>" not in html
    assert "99,999,999,999.9999" in html


def test_notebook_dashboard_is_scoped_and_self_contained(tmp_path: Path) -> None:
    result = extract_fixture(PAYLOAD, tmp_path / "out")
    html = result._repr_html_()
    assert "max-width:780px" in html and "padding:18px 28px" in html
    assert "tabular-nums slashed-zero" in html
    assert "grid-template-columns:repeat(4" in html
    assert "Geist Mono" in html and "JetBrains Mono" in html and "Inter" in html
    assert html.count("class='nv-dtype'") == 4
    assert "Input hash" in html and result.raw_sha256[:12] in html
    assert "Exact decimals &middot; Nulls preserved" in html
    assert "<details" not in html
    assert "<script" not in html and "@import" not in html and "https://" not in html
