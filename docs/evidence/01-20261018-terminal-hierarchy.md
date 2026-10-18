# Phase 01 - terminal hierarchy and palette, 18 October 2026

Historical observations; current status belongs in [STATE](../../STATE.md).
Owner requested more prominent, readable terminal headers and a cohesive palette
after the prior [color refinement](01-20261018-terminal-colors.md) at `a597727`.
Notebook appearance and terminal layout remain accepted; this header/palette
revision is presented for review. Source is this record's containing commit.

Changes are restricted to capable-terminal styles and capture rendering:
column headings/brand use bold bright cyan, metadata labels use bold cyan,
identifiers use ordinary cyan, dates/body use neutral foreground, saved status
uses green, and nulls use yellow. Dim headings and competing violet dates were
removed. Status color is confined to SAVED rather than the whole job title.
Plain/no-color styling and all data remain unchanged.

The review capture uses a coordinated reference ANSI palette: navy `#111B24`,
mint headers `#AEEBE0`, teal labels/IDs `#7FC9BE`, sage status `#94C8A8`, amber
nulls `#E4C58B`, and off-white foreground `#DCE7EF`. Native terminal hues follow
the user's configured ANSI palette; the application does not change it or force
unsupported truecolor escape sequences. Rich TerminalTheme's installed signature
was inspected before constructing the capture palette.

Actual checks: `uv run --frozen ruff format --check src tests tools/capture_previews.py`,
Ruff check, strict mypy, `uv run --frozen pytest -q` (35 pass), capture generation
and headless Edge inspection all exit 0 on Windows CPython 3.14.7. No additional
style-only tests were added. Existing bounds/escaping/no-I/O/explicit capability
checks pass. Linux and wheel observations in the preceding record are historical;
the latest source will undergo the configured platform/wheel CI after review.
No dependency, schema, persistence or package configuration changed.

Playwright 1.64.0 with offline headless Edge 155.0.4283.62 captured and inspected
60/100-column terminal images. Browser-computed column header style is
`rgb(174, 235, 224)` with weight 700. Relative-luminance contrast against the
reference navy background calculates to 13.07:1 for column headers and 9.12:1
for metadata labels; these describe this reference theme, not every user theme.
Plain terminal files match the accepted layout byte-for-byte at 60/100/160
columns; ANSI-stripped capable output also matches exactly. Both notebook MIME
outputs match the accepted notebook. No fixture value or display text changed.

New artifacts are in `docs/evidence/artifacts/phase01-terminal-hierarchy/`:
`review.html`, `preview.ipynb`, 60/100/160-column `.txt`/`.ansi` files, and
`terminal-60.png` / `terminal-100.png`. Earlier versions are preserved.
Owner review, hosted CI/macOS smoke and final authorized remote delivery remain
pending. PH-01-GATE remains open; Phase 02 has not begun.
