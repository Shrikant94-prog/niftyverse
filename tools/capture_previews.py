"""Capture actual slice MIME and terminal output for the Phase 01 owner review."""

import html
import io
import tempfile
from pathlib import Path

import nbformat
from rich.console import Console
from rich.terminal_theme import MONOKAI
from rich.text import Text

from niftyverse import extract_fixture
from niftyverse.display import terminal_summary

ROOT = Path(__file__).resolve().parents[1]

_REVIEW_CSS = """
*{box-sizing:border-box}body{margin:0;background:#eff4f5;color:#19313d;
 font:14px/1.6 system-ui,sans-serif}main{max-width:1120px;margin:auto;padding:48px 32px 64px}
.eyebrow{font-size:11px;letter-spacing:.14em;font-weight:700;color:#087f75;text-transform:uppercase}
h1{font-size:34px;line-height:1.2;letter-spacing:-.04em;margin:10px 0 12px;font-weight:650}
.intro{color:#637983;max-width:640px;margin:0;font-size:15px}
.review-header{border-bottom:1px solid #d8e4e8;padding-bottom:30px;margin-bottom:36px}
.review-section{margin-top:36px}.section-heading{display:flex;gap:14px;align-items:baseline;
 margin-bottom:18px}.section-number{font-size:11px;color:#7d919a;letter-spacing:.06em}
h2{font-size:17px;letter-spacing:-.015em;margin:0;font-weight:650}
.section-note{margin:3px 0 0;color:#71848e;font-size:12px}
.terminal-window{border-radius:12px;overflow:hidden;background:#111b24;
 box-shadow:0 4px 18px #1b3b4912;
 border:1px solid #24343f;margin-top:12px}.window-bar{display:flex;align-items:center;gap:6px;
 padding:12px 16px;background:#1a2833;border-bottom:1px solid #283946;color:#9eafb9;font-size:11px}
.window-dot{width:7px;height:7px;border-radius:50%;background:#49606c}
.window-label{margin-left:9px}pre{font:13px/1.65 ui-monospace,SFMono-Regular,Consolas,monospace;
 margin:0;padding:20px;overflow-x:auto;tab-size:4}.terminal-window pre{color:#e2eaf0}
.review-details{margin-top:12px;border:1px solid #d7e2e7;border-radius:9px;background:#f7fafb}
.review-details>summary{padding:12px 16px;cursor:pointer;color:#4b6571;
 font-size:12px;font-weight:550}
.review-details .terminal-window{margin:0 12px 12px}
.review-details>pre{border-top:1px solid #e0e9ed;font-size:11px}
.review-footer{margin-top:36px;font-size:11px;color:#80949d;
 border-top:1px solid #d8e4e8;padding-top:18px}
@media(max-width:600px){main{padding:28px 16px}h1{font-size:28px}pre{font-size:11px;padding:14px}}
@media(prefers-color-scheme:dark){body{background:#0d171e;color:#dce8ee}.intro,.section-note{
 color:#9cafba}.review-header,.review-footer{border-color:#2c3d47}.review-details{
 background:#15232c;border-color:#2c3d47}.review-details>summary{color:#b2c5cf}}
"""


def _terminal_window(contents: str, label: str) -> str:
    return (
        '<div class="terminal-window"><div class="window-bar">'
        '<span class="window-dot"></span><span class="window-dot"></span>'
        '<span class="window-dot"></span><span class="window-label">'
        + label
        + "</span></div><pre>"
        + contents
        + "</pre></div>"
    )


def main() -> None:
    output = ROOT / "docs/evidence/artifacts/phase01-polished"
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="niftyverse-preview-") as folder:
        result = extract_fixture(
            (ROOT / "tests/fixtures/observations.json").read_bytes(), Path(folder) / "bundle"
        )
    mime = result._repr_mimebundle_()
    blocks = [
        "<!doctype html><html lang='en'><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1'>",
        "<title>niftyverse Phase 01 previews</title>",
        f"<style>{_REVIEW_CSS}</style><body><main>",
        '<header class="review-header"><div class="eyebrow">niftyverse / design review</div>',
        "<h1>Notebook &amp; terminal previews</h1>",
        '<p class="intro">The same saved fixture, with clear hierarchy, aligned values '
        "and details when you need them.</p></header>",
        '<section class="review-section"><div class="section-heading">'
        '<span class="section-number">01</span><div><h2>Notebook card</h2>'
        '<p class="section-note">Light and dark themes follow your system. '
        "Null and empty text remain distinct.</p></div></div>",
        mime["text/html"],
        '<details class="review-details"><summary>Plain-text notebook fallback</summary><pre>'
        + html.escape(mime["text/plain"]).replace(" \n", "&#32;\n")
        + "</pre></details></section>",
        '<section class="review-section"><div class="section-heading">'
        '<span class="section-number">02</span><div><h2>Terminal summary</h2>'
        '<p class="section-note">Compact at 60 columns. A data preview at 100 and 160.'
        "</p></div></div>",
    ]
    for width in (100, 60, 160):
        for capable in (False, True):
            text = terminal_summary(result, width=width, capable=capable)
            suffix = "ansi" if capable else "txt"
            (output / f"terminal-{width}.{suffix}").write_text(text, encoding="utf-8")
        console = Console(
            file=io.StringIO(),
            record=True,
            width=width,
            height=25,
            force_terminal=True,
            no_color=False,
            legacy_windows=False,
        )
        console.print(Text.from_ansi(terminal_summary(result, width=width, capable=True)), end="")
        capable_html = console.export_html(
            code_format="{code}",
            inline_styles=True,
            theme=MONOKAI,
        )
        if width != 100:
            blocks.append(
                f'<details class="review-details"><summary>{width}-column layout</summary>'
            )
        blocks.append(_terminal_window(capable_html, f"niftyverse &middot; {width} columns"))
        blocks += [
            '<details class="review-details"><summary>Plain / no-color fallback</summary>',
            _terminal_window(
                html.escape(terminal_summary(result, width=width)),
                f"plain text &middot; {width} columns",
            ),
            "</details>",
        ]
        if width != 100:
            blocks.append("</details>")
    blocks.append(
        '</section><footer class="review-footer">'
        "Owned offline fixture &middot; Actual saved result &middot; Phase 01 review"
        "</footer></main></body></html>"
    )
    (output / "review.html").write_text("\n".join(blocks), encoding="utf-8")
    notebook = nbformat.v4.new_notebook(
        cells=[
            nbformat.v4.new_markdown_cell(
                "# niftyverse Phase 01 preview\n"
                "Saved MIME output captured from the actual owned offline fixture result. "
                "No market data, snapshot or source-support claim. Reproduce with "
                "`uv run --frozen python tools/capture_previews.py`.",
                id="phase01-preview-context",
            ),
            nbformat.v4.new_code_cell(
                "# Captured result display (not a kernel execution claim)",
                outputs=[nbformat.v4.new_output("display_data", data=mime)],
                id="phase01-captured-mime",
            ),
        ]
    )
    nbformat.write(notebook, output / "preview.ipynb")
    print(output / "review.html")
    print("Saved actual MIME output and 60/100/160-column plain and ANSI terminal captures.")


if __name__ == "__main__":
    main()
