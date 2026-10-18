"""Pure bounded preview rendering; never queries or materializes result data."""

import html
import io
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING

from rich import box
from rich.console import Console, Group
from rich.markup import escape as markup_escape
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
_ASCII_HEAD = box.Box(str(box.SIMPLE_HEAD).replace("─", "-"), ascii=True)


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
    return f"{first:%d %b %Y} → {last:%d %b %Y}"


def _literal(value: str, style: str = "") -> Text:
    """Escape source text at the markup boundary, including Rich-like payloads."""
    return Text.from_markup(markup_escape(value), style=style, emoji=False)


def _table(result: SliceResult, config: PreviewConfig, *, capable: bool) -> Table:
    table = Table(
        box=box.SIMPLE_HEAD if capable else _ASCII_HEAD,
        show_edge=False,
        padding=(0, 2),
        pad_edge=False,
        header_style="bold bright_cyan" if capable else "",
        expand=False,
    )
    table.add_column("Instrument", no_wrap=True, max_width=16)
    table.add_column("Session date", no_wrap=True)
    table.add_column("Close", justify="right", no_wrap=True)
    table.add_column("Label", overflow="ellipsis", max_width=40)
    for row, cells in zip(
        result.preview_rows[: config.max_rows], _rows(result, config), strict=True
    ):
        values = (row.instrument_id, row.session_date, row.close, row.label)
        styles = ["cyan", "bright_black", "bold", ""] if capable else [""] * 4
        if capable:
            for index, value in enumerate(values):
                if value is None:
                    styles[index] = "yellow"
                elif value == "" or (index == 2 and value == 0):
                    styles[index] = "bright_black"
        table.add_row(*[_literal(cell, styles[index]) for index, cell in enumerate(cells)])
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
.niftyverse-card{--nv-bg:#fff;--nv-ink:#182b36;--nv-muted:#647680;--nv-line:#e2e9ed;
 --nv-tint:#f4f7f9;--nv-accent:#087f75;--nv-good:#e5f5ed;--nv-green:#16734b;
 --nv-amber:#865400;--nv-amber-bg:#fff4dc;--nv-slate-bg:#eaf0f4;
 --nv-ui:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
 --nv-mono:"Geist Mono","JetBrains Mono",ui-monospace,SFMono-Regular,Consolas,monospace;
 color:var(--nv-ink);background:var(--nv-bg);border:1px solid var(--nv-line);
 border-radius:14px;max-width:780px;overflow:hidden;font:13px/1.5 var(--nv-ui);
 box-shadow:0 4px 20px #14343c0a;text-align:left;color-scheme:light dark}
.niftyverse-card *{box-sizing:border-box}
.niftyverse-card .nv-top{padding:24px 28px;display:flex;justify-content:space-between;
 gap:16px;flex-wrap:wrap;border-bottom:1px solid var(--nv-line)}
.niftyverse-card .nv-brand{color:var(--nv-accent);font-size:10px;font-weight:700;
 letter-spacing:.12em;margin:0 0 8px}
.niftyverse-card .nv-title{font:650 22px/1.25 var(--nv-ui);color:var(--nv-ink);
 margin:0 0 6px;letter-spacing:-.025em}
.niftyverse-card .nv-sub{margin:0;color:var(--nv-muted);font:12px/1.6 var(--nv-ui)}
.niftyverse-card .nv-status{align-self:flex-start;background:var(--nv-good);
 color:var(--nv-green);border:1px solid color-mix(in srgb,var(--nv-green) 14%,transparent);
 border-radius:20px;padding:5px 10px;font:600 11px/1.5 var(--nv-mono);white-space:nowrap}
.niftyverse-card .nv-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));
 gap:20px;padding:18px 28px;
 background:var(--nv-tint);border-bottom:1px solid var(--nv-line)}
.niftyverse-card .nv-stat{min-width:0}
.niftyverse-card .nv-stat-label{display:block;color:var(--nv-muted);font-size:10px;
 text-transform:uppercase;letter-spacing:.08em;margin-bottom:3px}
.niftyverse-card .nv-stat-value{font:500 12px/1.65 var(--nv-mono);
 font-variant-numeric:tabular-nums slashed-zero;overflow-wrap:anywhere}
.niftyverse-card .nv-dates{color:var(--nv-muted)}
.niftyverse-card .nv-scroll{overflow-x:auto;overscroll-behavior-x:contain}
.niftyverse-card .nv-table{width:100%;border-collapse:collapse;margin:0;
 background:var(--nv-bg);font:12px/1.6 var(--nv-mono);color:var(--nv-ink)}
.niftyverse-card .nv-table th{padding:14px 28px;font:600 11px/1.5 var(--nv-ui);
 color:var(--nv-muted);
 border-bottom:1px solid var(--nv-line);white-space:nowrap;text-align:left}
.niftyverse-card .nv-dtype{font:400 9px/1.5 var(--nv-mono);color:var(--nv-muted);
 background:var(--nv-tint);border:1px solid var(--nv-line);border-radius:4px;
 padding:1px 4px;margin-left:5px}
.niftyverse-card .nv-table td{padding:18px 28px;border-bottom:1px solid var(--nv-line);
 font:12px/1.6 var(--nv-mono);font-variant-numeric:tabular-nums slashed-zero;
 vertical-align:middle;text-align:left;max-width:230px;overflow-wrap:anywhere}
.niftyverse-card .nv-table tbody tr:last-child td{border-bottom:none}
.niftyverse-card .nv-table .nv-number{text-align:right;white-space:nowrap;overflow-wrap:normal}
.niftyverse-card .nv-table .nv-id{color:var(--nv-accent);font-weight:600;white-space:nowrap}
.niftyverse-card .nv-table .nv-date{color:var(--nv-muted);white-space:nowrap}
.niftyverse-card .nv-table .nv-zero{color:var(--nv-muted)}
.niftyverse-card .nv-null,.niftyverse-card .nv-empty{display:inline-block;
 padding:2px 7px;border-radius:5px;font:11px/1.5 var(--nv-mono);white-space:nowrap}
.niftyverse-card .nv-null{color:var(--nv-amber);background:var(--nv-amber-bg);font-style:italic}
.niftyverse-card .nv-empty{color:var(--nv-muted);background:var(--nv-slate-bg)}
.niftyverse-card .nv-footer{padding:14px 28px;border-top:1px solid var(--nv-line);
 background:var(--nv-tint);
 display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;
 color:var(--nv-muted);font:11px/1.5 var(--nv-ui)}
@media(max-width:600px){.niftyverse-card .nv-stats{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(prefers-color-scheme:dark){.niftyverse-card{--nv-bg:#15232c;--nv-ink:#e3edf2;
 --nv-muted:#9cafba;--nv-line:#2c3d47;--nv-tint:#1c2d36;--nv-accent:#7fc9be;
 --nv-good:#193d30;--nv-green:#94c8a8;--nv-amber:#e4c58b;--nv-amber-bg:#3b3020;
 --nv-slate-bg:#283a46}}
"""


def render_html(result: SliceResult, config: PreviewConfig = _DEFAULT_PREVIEW) -> str:
    """Return self-contained escaped HTML, capped below 64 KiB."""
    rows = _rows(result, config)
    esc = html.escape
    header = (
        "<th scope='col'>Instrument<span class='nv-dtype'>id</span></th>"
        "<th scope='col'>Session date<span class='nv-dtype'>date</span></th>"
        "<th scope='col' class='nv-number'>Close<span class='nv-dtype'>dec</span></th>"
        "<th scope='col'>Label<span class='nv-dtype'>str</span></th>"
    )
    body_rows = []
    for row, cells in zip(result.preview_rows[: config.max_rows], rows, strict=True):
        formatted = []
        for index, value in enumerate(cells):
            raw = (row.instrument_id, row.session_date, row.close, row.label)[index]
            if raw is None:
                value_html = '<span class="nv-null" aria-label="Null value">&lt;null&gt;</span>'
            elif raw == "":
                value_html = (
                    '<span class="nv-empty" aria-label="Empty text">&quot;&quot; (empty)</span>'
                )
            else:
                value_html = esc(value)
            cell_class = ("nv-id", "nv-date", "nv-number", "nv-cell")[index]
            if index == 2 and raw is not None and raw == 0:
                cell_class += " nv-zero"
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
        f"<p class='nv-sub'>Owned offline fixture &middot; {esc(_mode(result))}<br>"
        "Synthetic data &middot; No research snapshot</p></div>"
        "<span class='nv-status'>● Saved</span></header>"
        "<div class='nv-stats' aria-label='Provenance metrics'>"
        "<div class='nv-stat'><span class='nv-stat-label'>Rows</span>"
        f"<span class='nv-stat-value' aria-label='{result.committed_rows} committed rows'>"
        f"{result.committed_rows:,}</span></div>"
        "<div class='nv-stat'><span class='nv-stat-label'>Columns</span>"
        "<span class='nv-stat-value'>4</span></div>"
        "<div class='nv-stat'><span class='nv-stat-label'>Preview dates</span>"
        f"<span class='nv-stat-value nv-dates'>{esc(_dates(result))}</span></div>"
        "<div class='nv-stat'><span class='nv-stat-label'>Input hash</span>"
        f"<span class='nv-stat-value' title='Input SHA-256: {esc(_text(result.raw_sha256, 64))}'>"
        f"{esc(_text(result.raw_sha256, 15))}</span></div></div>"
        "<div class='nv-scroll'><table class='nv-table'>"
        f"<thead><tr>{header}</tr></thead><tbody>{body}</tbody></table></div>"
        "<footer class='nv-footer'>"
        f"<span>Preview only: {len(rows)} of {result.committed_rows} rows</span>"
        "<span>Exact decimals &middot; Nulls preserved</span></footer></section>"
    )
    if len(rendered.encode("utf-8")) > 65536:
        raise ValueError("static preview exceeds 64 KiB")
    return rendered


def render_terminal(result: SliceResult, *, width: int, capable: bool) -> Table:
    """Build one continuous three-zone card, shared by CLI and Rich display."""
    card = Table(
        box=box.ROUNDED if capable else box.ASCII,
        safe_box=not capable,
        show_header=False,
        show_lines=True,
        padding=(1, 2),
        expand=True,
        border_style="dim cyan" if capable else "",
    )
    card.add_column()
    title = Text()
    title.append(" SAVED ", style="bold black on green" if capable else "")
    title.append("  niftyverse / Observation preview", style="bold" if capable else "")
    counts = Text(f"{result.event.committed_rows} committed rows")
    counts.append(" · " if capable else " | ", style="bright_black" if capable else "")
    counts.append_text(_literal(_mode(result), "cyan" if capable else ""))
    header = Table.grid(expand=True, padding=(0, 2))
    header.add_column(ratio=1)
    if width >= 90:
        header.add_column(justify="right", no_wrap=True)
        header.add_row(title, counts)
    else:
        header.add_row(title)
        header.add_row(counts)
    card.add_row(header)

    detail = Table.grid(padding=(0, 2))
    detail.add_column(
        width=min(13, max(4, (width - 8) // 3)),
        style="bright_black" if capable else "",
        overflow="fold",
    )
    detail.add_column(overflow="fold")
    detail.add_row(Text("Source"), Text("Owned offline fixture"))
    detail.add_row(
        Text("Preview dates"),
        _literal(_dates(result) if capable else _dates(result).replace(" → ", " - ")),
    )
    detail.add_row(Text("Input hash"), _literal(_text(result.raw_sha256, 15)))
    card.add_row(detail)

    contents: list[Text | Table] = []
    count = 0
    if width >= 90:
        count = len(result.preview_rows[:5])
        contents.append(
            _table(result, PreviewConfig(max_rows=5, max_cell_chars=40), capable=capable)
        )
        if not count:
            contents.append(Text("No rows"))
        contents.append(Text(""))
    footer = f"Preview only: {count} of {result.committed_rows} rows"
    if width < 90:
        footer += " | Widen to 90+ columns"
    contents.append(Text(footer, style="bright_black" if capable else ""))
    card.add_row(Group(*contents))
    return card


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
    console.print(render_terminal(result, width=width, capable=capable))
    return stream.getvalue()
