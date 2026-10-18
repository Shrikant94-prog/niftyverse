"""Capture actual slice MIME and terminal output for the Phase 01 owner review."""

import html
import io
import tempfile
from pathlib import Path

import nbformat
from rich.console import Console
from rich.text import Text

from niftyverse import extract_fixture
from niftyverse.display import terminal_summary

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    output = ROOT / "docs/evidence/artifacts/phase01"
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
        "<body style='margin:24px;color:#172033;background:#f8fafc'>",
        "<h1>Phase 01 appearance review</h1>",
        "<h2>Notebook static MIME card</h2>",
        mime["text/html"],
        "<h2>Plain-text fallback</h2>",
        "<pre style='overflow-x:auto'>"
        + html.escape(mime["text/plain"]).replace(" \n", "&#32;\n")
        + "</pre>",
    ]
    for width in (60, 100, 160):
        for capable in (False, True):
            text = terminal_summary(result, width=width, capable=capable)
            suffix = "ansi" if capable else "txt"
            (output / f"terminal-{width}.{suffix}").write_text(text, encoding="utf-8")
        blocks += [
            f"<h2>Terminal - {width} columns (plain)</h2>",
            "<pre style='background:#111827;color:#f1f5f9;padding:16px;overflow-x:auto'>"
            + html.escape(terminal_summary(result, width=width))
            + "</pre>",
        ]
        console = Console(file=io.StringIO(), record=True, width=width, force_terminal=True)
        console.print(Text.from_ansi(terminal_summary(result, width=width, capable=True)), end="")
        blocks += [
            f"<h2>Terminal - {width} columns (capable/color)</h2>",
            "<pre style='padding:16px;overflow-x:auto'>"
            + console.export_html(code_format="{code}", inline_styles=True)
            + "</pre>",
        ]
    blocks.append("</body></html>")
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
