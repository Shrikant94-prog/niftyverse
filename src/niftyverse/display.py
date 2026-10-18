"""Pure bounded preview rendering; never queries or materializes result data."""

import html
import io
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING

from rich import box
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from niftyverse.result import SliceResult


@dataclass(frozen=True, slots=True)
class PreviewConfig:
    """Static preview budgets within the initial public display limits."""

    max_rows: int = 10
    max_cell_chars: int = 120

    def __post_init__(self) -> None:
        if not 0 <= self.max_rows <= 20 or not 1 <= self.max_cell_chars <= 120:
            raise ValueError("preview requires 0..20 rows and 1..120 characters per cell")


def _text(value: object, limit: int = 120) -> str:
    raw = "<null>" if value is None else ('""' if value == "" else str(value))
    truncated = len(raw) > limit
    clipped = raw[: max(0, limit - 3)] if truncated else raw[:limit]
    safe = "".join(" " if unicodedata.category(c).startswith("C") else c for c in clipped)
    return safe + ("." * min(3, limit) if truncated else "")


def _rows(result: SliceResult, config: PreviewConfig) -> list[list[str]]:
    return [
        [
            _text(value, config.max_cell_chars)
            for value in (
                row.instrument_id,
                row.session_date,
                None if row.close is None else format(row.close, ",.4f"),
                row.label,
            )
        ]
        for row in result.preview_rows[: config.max_rows]
    ]


_DEFAULT_PREVIEW = PreviewConfig()


def _mode(result: SliceResult) -> str:
    return {"direct-csv": "CSV bundle", "database": "DuckDB database"}.get(
        result.mode, _text(result.mode, 40)
    )


def _dates(result: SliceResult) -> str:
    dates = [row.session_date for row in result.preview_rows[:10]]
    if not dates:
        return "No rows"
    first, last = min(dates), max(dates)
    if first == last:
        return first.strftime("%d %b %Y")
    return f"{first:%d %b %Y} - {last:%d %b %Y}"


def _table(result: SliceResult, config: PreviewConfig, *, capable: bool) -> Table:
    table = Table(
        box=None,
        padding=(0, 1),
        pad_edge=False,
        header_style="dim" if capable else "",
        expand=False,
    )
    table.add_column("Instrument", no_wrap=True, max_width=16)
    table.add_column("Session", no_wrap=True)
    table.add_column("Close", justify="right", no_wrap=True)
    table.add_column("Label", overflow="ellipsis", max_width=40)
    for cells in _rows(result, config):
        table.add_row(
            *[
                Text(cell, style="dim" if capable and cell in {"<null>", '""'} else "")
                for cell in cells
            ]
        )
    return table


def render_text(result: SliceResult, config: PreviewConfig = _DEFAULT_PREVIEW) -> str:
    """Return a plain-text fallback from the prepared immutable snapshot."""
    stream = io.StringIO()
    console = Console(file=stream, width=120, color_system=None, highlight=False)
    console.print(Text("niftyverse / Observation preview"))
    console.print(Text(f"{result.committed_rows} committed rows | {_mode(result)}"))
    console.print(Text("Owned offline fixture"))
    console.print()
    if result.preview_rows and config.max_rows:
        console.print(_table(result, config, capable=False))
    else:
        console.print("No rows")
    console.print()
    count = len(result.preview_rows[: config.max_rows])
    console.print(Text(f"Preview only: {count} of {result.committed_rows} rows | 4 columns"))
    return stream.getvalue().rstrip()


_CARD_CSS = """
.niftyverse-card{--nv-bg:#fff;--nv-ink:#182b36;--nv-muted:#647680;--nv-line:#e5ecef;
 --nv-tint:#f5f9fa;--nv-accent:#087f75;--nv-good:#e5f5ef;
 color:var(--nv-ink);background:var(--nv-bg);border:1px solid var(--nv-line);
 border-radius:14px;max-width:1040px;overflow:hidden;font:13px/1.5 system-ui,sans-serif;
 box-shadow:0 3px 16px #14343c08;text-align:left;color-scheme:light dark}
.niftyverse-card *{box-sizing:border-box}
.niftyverse-card .nv-top{padding:22px 24px 18px;display:flex;justify-content:space-between;
 gap:16px;flex-wrap:wrap;border-bottom:1px solid var(--nv-line)}
.niftyverse-card .nv-brand{color:var(--nv-accent);font-size:11px;font-weight:750;
 letter-spacing:.12em;margin:0 0 8px}
.niftyverse-card .nv-title{font:650 21px/1.25 system-ui,sans-serif;color:var(--nv-ink);
 margin:0 0 6px;letter-spacing:-.025em}
.niftyverse-card .nv-sub{margin:0;color:var(--nv-muted);font-size:12px}
.niftyverse-card .nv-status{align-self:flex-start;background:var(--nv-good);
 color:var(--nv-accent);border-radius:20px;padding:5px 10px;font-weight:650;font-size:11px}
.niftyverse-card .nv-stats{display:flex;flex-wrap:wrap;gap:24px;padding:14px 24px;
 background:var(--nv-tint);border-bottom:1px solid var(--nv-line)}
.niftyverse-card .nv-stat-label{display:block;color:var(--nv-muted);font-size:10px;
 text-transform:uppercase;letter-spacing:.08em;margin-bottom:3px}
.niftyverse-card .nv-stat-value{font-weight:600;font-variant-numeric:tabular-nums}
.niftyverse-card .nv-scroll{overflow-x:auto}
.niftyverse-card .nv-table{width:100%;border-collapse:collapse;margin:0;min-width:540px;
 background:var(--nv-bg);font-size:13px}
.niftyverse-card .nv-table th{padding:11px 24px;font-weight:550;color:var(--nv-muted);
 border-bottom:1px solid var(--nv-line);white-space:nowrap;text-align:left}
.niftyverse-card .nv-table td{padding:12px 24px;border-bottom:1px solid var(--nv-line);
 vertical-align:middle;text-align:left;max-width:300px;overflow-wrap:anywhere}
.niftyverse-card .nv-table tbody tr:last-child td{border-bottom:none}
.niftyverse-card .nv-table .nv-number{text-align:right;white-space:nowrap;
 font:13px ui-monospace,SFMono-Regular,Consolas,monospace;font-variant-numeric:tabular-nums}
.niftyverse-card .nv-id{font:600 13px ui-monospace,SFMono-Regular,Consolas,monospace}
.niftyverse-card .nv-null{color:var(--nv-muted);background:var(--nv-tint);
 border:1px solid var(--nv-line);padding:2px 6px;border-radius:4px;font-size:10px}
.niftyverse-card .nv-empty{color:var(--nv-muted);font-style:italic;font-size:11px}
.niftyverse-card .nv-footer{padding:12px 24px;border-top:1px solid var(--nv-line);
 display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;
 color:var(--nv-muted);font-size:11px}
.niftyverse-card .nv-provenance{padding:0 24px 14px;color:var(--nv-muted);font-size:11px}
.niftyverse-card .nv-provenance summary{cursor:pointer;width:fit-content}
.niftyverse-card .nv-provenance p{margin:8px 0 0;overflow-wrap:anywhere}
@media(prefers-color-scheme:dark){.niftyverse-card{--nv-bg:#15232c;--nv-ink:#e3edf2;
 --nv-muted:#9cafba;--nv-line:#2c3d47;--nv-tint:#1c2d36;--nv-accent:#6fd4be;--nv-good:#193d35}}
"""


def render_html(result: SliceResult, config: PreviewConfig = _DEFAULT_PREVIEW) -> str:
    """Return self-contained escaped HTML, capped below 64 KiB."""
    rows = _rows(result, config)
    esc = html.escape
    header = (
        "<th scope='col'>Instrument</th><th scope='col'>Session date</th>"
        "<th scope='col' class='nv-number'>Close</th><th scope='col'>Label</th>"
    )
    body_rows = []
    for row, cells in zip(result.preview_rows[: config.max_rows], rows, strict=True):
        formatted = []
        for index, value in enumerate(cells):
            raw = (row.instrument_id, row.session_date, row.close, row.label)[index]
            if raw is None:
                value_html = '<span class="nv-null" aria-label="Null value">null</span>'
            elif raw == "":
                value_html = '<span class="nv-empty" aria-label="Empty text">empty text</span>'
            else:
                value_html = esc(value)
            cell_class = "nv-number" if index == 2 else ("nv-id" if index == 0 else "nv-cell")
            formatted.append(f'<td class="{cell_class}">{value_html}</td>')
        body_rows.append("<tr>" + "".join(formatted) + "</tr>")
    body = "".join(body_rows)
    if not rows:
        body = "<tr><td colspan='4'>No rows</td></tr>"
    rendered = (
        f"<style>{_CARD_CSS}</style>"
        "<section class='niftyverse-card' aria-label='niftyverse observation preview'>"
        "<header class='nv-top'><div><p class='nv-brand'>NIFTYVERSE / RESEARCH DATA</p>"
        "<h3 class='nv-title'>Observation preview</h3>"
        f"<p class='nv-sub'>Owned offline fixture &middot; {esc(_mode(result))}</p></div>"
        "<span class='nv-status'>Saved</span></header>"
        "<div class='nv-stats'><div><span class='nv-stat-label'>Rows saved</span>"
        f"<span class='nv-stat-value'>{result.committed_rows} committed rows</span></div>"
        "<div><span class='nv-stat-label'>Columns</span><span class='nv-stat-value'>4</span></div>"
        "<div><span class='nv-stat-label'>Preview dates</span>"
        f"<span class='nv-stat-value'>{esc(_dates(result))}</span></div></div>"
        "<div class='nv-scroll'><table class='nv-table'>"
        f"<thead><tr>{header}</tr></thead><tbody>{body}</tbody></table></div>"
        "<footer class='nv-footer'>"
        f"<span>Preview only: {len(rows)} of {result.committed_rows} rows</span>"
        "<span>Exact decimals &middot; Nulls preserved</span></footer>"
        "<details class='nv-provenance'><summary>Provenance</summary>"
        f"<p>Input SHA-256: {esc(_text(result.raw_sha256, 64))}<br>"
        "Capture: owned fixture JSON &middot; Schema: fixture-v1<br>"
        "Synthetic data &middot; No research snapshot</p></details></section>"
    )
    if len(rendered.encode("utf-8")) > 65536:
        raise ValueError("static preview exceeds 64 KiB")
    return rendered


def terminal_summary(result: SliceResult, *, width: int = 80, capable: bool = False) -> str:
    """Render a committed event summary; the caller explicitly writes it."""
    if not 20 <= width <= 240:
        raise ValueError("terminal width must be 20..240 columns")
    stream = io.StringIO()
    console = Console(
        file=stream,
        width=width,
        height=25,
        force_terminal=capable,
        color_system="standard" if capable else None,
        no_color=not capable,
        legacy_windows=False,
        highlight=False,
    )
    detail = Table.grid(padding=(0, 2))
    detail.add_column(style="dim" if capable else "")
    detail.add_column()
    detail.add_row(Text("Source"), Text("Owned offline fixture"))
    detail.add_row(Text("Preview dates"), Text(_dates(result)))
    detail.add_row(Text("Input"), Text(_text(result.raw_sha256, 12)))
    contents: list[Text | Table] = [
        Text("SAVED  Observation fixture", style="bold green" if capable else ""),
        Text(f"{result.event.committed_rows} committed rows | {_mode(result)}"),
        Text(""),
        detail,
    ]
    if width >= 90:
        contents.extend(
            [
                Text(""),
                _table(result, PreviewConfig(max_rows=5, max_cell_chars=40), capable=capable),
                Text(
                    f"Preview only: {len(result.preview_rows[:5])} "
                    f"of {result.committed_rows} rows",
                    style="dim" if capable else "",
                ),
            ]
        )
    console.print(
        Panel(
            Group(*contents),
            title=Text("niftyverse", style="bold cyan" if capable else ""),
            title_align="left",
            box=box.ROUNDED if capable else box.ASCII,
            border_style="dim cyan" if capable else "",
            safe_box=not capable,
            padding=(1, 2),
        )
    )
    return stream.getvalue()
