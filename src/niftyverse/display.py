"""Pure bounded preview rendering; never queries or materializes result data."""

import html
import io
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING

from rich.console import Console
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
    raw = "<null>" if value is None else str(value)
    truncated = len(raw) > limit
    clipped = raw[: max(0, limit - 3)] if truncated else raw[:limit]
    safe = "".join(" " if unicodedata.category(c).startswith("C") else c for c in clipped)
    return safe + ("." * min(3, limit) if truncated else "")


def _rows(result: SliceResult, config: PreviewConfig) -> list[list[str]]:
    return [
        [
            _text(value, config.max_cell_chars)
            for value in (row.instrument_id, row.session_date, row.close, row.label)
        ]
        for row in result.preview_rows[: config.max_rows]
    ]


_DEFAULT_PREVIEW = PreviewConfig()


def render_text(result: SliceResult, config: PreviewConfig = _DEFAULT_PREVIEW) -> str:
    """Return a plain-text fallback from the prepared immutable snapshot."""
    rows = _rows(result, config)
    lines = [
        f"niftyverse | {result.committed_rows} committed rows | {_text(result.mode, 40)}",
        "Owned offline fixture; provider support and snapshot pinning not implied.",
        "instrument_id | session_date | close | label",
    ]
    lines.extend(" | ".join(row) for row in rows)
    if not rows:
        lines.append("No rows")
    lines.append(f"Preview only: {len(rows)} of {result.committed_rows} rows")
    return "\n".join(lines)


def render_html(result: SliceResult, config: PreviewConfig = _DEFAULT_PREVIEW) -> str:
    """Return self-contained escaped HTML, capped below 64 KiB."""
    rows = _rows(result, config)
    esc = html.escape
    header = "".join(
        f"<th scope='col'>{name}</th>" for name in ("Instrument", "Session", "Close", "Label")
    )
    body = "".join(
        "<tr>" + "".join(f"<td>{esc(cell)}</td>" for cell in row) + "</tr>" for row in rows
    )
    if not rows:
        body = "<tr><td colspan='4'>No rows</td></tr>"
    rendered = (
        "<section class='niftyverse-card' style='font:14px system-ui,sans-serif;"
        "border:1px solid #cbd5e1;border-radius:8px;padding:16px;max-width:960px'>"
        "<h3 style='margin:0 0 8px;color:#0f766e'>niftyverse - offline fixture</h3>"
        f"<p><strong>{result.committed_rows} committed rows</strong> | "
        f"{esc(_text(result.mode, 40))}</p>"
        "<p>Owned fixture only. Provider support, raw replay and snapshot pinning "
        "are not implied.</p>"
        "<div style='overflow-x:auto'><table class='niftyverse-preview' "
        "style='border-collapse:separate;border-spacing:12px 6px;text-align:left'>"
        f"<thead><tr>{header}</tr></thead><tbody>{body}</tbody></table></div>"
        f"<p>Preview only: {len(rows)} of {result.committed_rows} rows. "
        f"Input SHA-256: {esc(_text(result.raw_sha256, 12))}</p></section>"
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
        force_terminal=capable,
        color_system="standard" if capable else None,
        highlight=False,
    )
    console.print(Text("niftyverse | fixture complete", style="bold cyan" if capable else ""))
    console.print(Text(f"{result.event.committed_rows} committed rows | {_text(result.mode, 40)}"))
    console.print(Text("Owned offline fixture; no provider readiness claimed."))
    return stream.getvalue()
