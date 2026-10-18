# Phase 01 - terminal color refinement, 18 October 2026

Historical observations only; current status is [STATE](../../STATE.md).
Owner accepted the notebook and terminal layout from `40a5f2a`, then requested a
few subtle terminal colors for readability. Notebook appearance is accepted;
the terminal color refinement is presented for review.

Changes are limited to capable-terminal styles in display.py and the capture
helper's new artifact destination. Cyan distinguishes labels/identifiers/mode,
a date accent separates time values, amber identifies nulls, and neutral bold
numbers remain easy to scan. Green remains the saved-status color. Text,
widths, layout, source values, notebook CSS and plain/no-color behavior are
unchanged. No new style-only tests were added; existing display boundaries and
explicit capability/width tests exercise the changed path.

Source identity: this record's containing checkpoint, based on `40a5f2a`.
Python/uv/dependency builds are unchanged from [polish evidence](01-20261018-preview-polish.md).
Lock SHA-256 remains `569bbd9a2d4daea3d86f55690014f8cb965aff95ac3eddd0303b453ab0672724`.
Fresh core wheel SHA-256: Windows
`aa98ef4ba10cedf15b2cfd64f4846f478da5852a2f11258471e009e74a2b2551`;
Linux `197ec62f84754524d62e4fb4f6f3abdd48662090e64d0e9113090660a147dc85`.

NV-01-03-AC1/AC2/AC3 checks actually run: Ruff format/check, strict mypy,
`uv run --frozen pytest -q` (35 passed), fresh installed core wheel smoke, and
the Linux helper's full behavior/wheel checks. All exit 0 on Windows and Linux.
The renderer remains bounded and escaped, with no query/network/materialization
and correct committed counts. No dependency or canonical-data change occurred.

`uv run --frozen python tools/capture_previews.py` captured the actual result
under `docs/evidence/artifacts/phase01-terminal-colors/`. The 60/100/160-column
plain `.txt` files were compared byte-for-byte with the accepted layout; all
match. ANSI-stripped capable output also matches at every width. Both notebook
MIME outputs match the accepted polished notebook outputs exactly.

Isolated Playwright 1.64.0 and offline headless Edge 155.0.4283.62 captured and
visually inspected `terminal-100.png` and `terminal-60.png`. `review.html` holds
all widths, plain fallbacks and the unchanged notebook. Earlier review artifacts
are retained. These captures establish appearance observations, not human
acceptance of the final colors or data correctness by screenshot.

PH-01-GATE remains open for final terminal-color feedback and hosted platform
CI/macOS smoke. The authorized origin is configured; no remote push occurred
during this refinement. Phase 02 remains unstarted.
