# Phase 01 - preview appearance revision, 18 October 2026

Historical observations only; current execution status belongs in [STATE](../../STATE.md).
The owner reviewed the earlier preview and requested cleaner, polished notebook
and terminal formatting. This is a change request, not visual acceptance.

## Scope and identity

Input source: `2535499`, followed by this record's containing checkpoint commit.
Changes are confined to display.py, its tests, the preview capture helper, new
review artifacts and STATE. Fixture values, wire decoding, schema, DB/CSV sinks,
package metadata, dependency versions and baseline documents are unchanged.
Earlier artifacts in `docs/evidence/artifacts/phase01/` remain unchanged.

The source fixture SHA-256 remains
`277226b740ac2ce6b1b3a4659c8cc18378358989bdaed20f4c8a5774c8c250fa`;
uv.lock SHA-256 remains
`569bbd9a2d4daea3d86f55690014f8cb965aff95ac3eddd0303b453ab0672724`.
Windows CPython 3.14.7, Linux CPython 3.14.4 and uv 0.12.9 are the exact builds
recorded in [prior integration evidence](01-20261018-integration.md).
Fresh Windows core/notebook wheel SHA-256:
`64a94badbec78b6ed24eddacd7a4e14e521eca084d8d94ac051b064e00d6c2db`.
Fresh Linux core wheel SHA-256:
`c2db471e0cb700ac6a7577d0c49a2561493e7cfe59e30f50854d0624d1180860`.

## Observed behavior and verification

| Acceptance | Independent expectation / procedure | Observation |
|---|---|---|
| NV-01-03-AC1 | Polished actual result; known count, identity, values and missing states; new semantic test written/run before implementation | Initial test failed on absent Observation preview title. Revised notebook card has clear title/status/summary/table/footer/provenance; light/dark colors, aligned exact decimal presentation, explicit null/empty-text markers. Leading zeros and literal `__NULL__` remain visible. No stored values changed. |
| NV-01-03-AC1 | Capture actual terminal summary at 60/100/160 columns with explicit capable/plain settings | Narrow panel contains source/count/mode/dates; wide panels include a bounded five-row table. Plain output uses ASCII borders; capable output uses color and rounded Unicode borders. Widths now match requested columns exactly in both conditions. Source labels are Rich Text, not markup. |
| NV-01-03-AC2 | Existing no-network/file/query/materialization spies and adversarial/empty/large cases; escaped source strings; combined MIME bound | All pass. Static HTML stays below 64 KiB; combined real-result MIME stays below 64 KiB. Preview row/cell budgets remain unchanged. CSS is namespaced, no remote font/script/assets; optional-display-free text/HTML remains useful. |
| NV-01-03-AC2 | `python tools/check_wheel.py --lane core` and `--lane notebook` | Both exit 0, each builds a fresh source wheel and installs outside checkout. Real DB/direct slice, MIME, CLI and subprocess socket/process-launch negative controls pass. Notebook lane exercises actual IPython formatting; minimal lane has no notebook extras. |
| NV-01-03-AC3 | `uv run --frozen ruff format --check src tests tools/capture_previews.py`; Ruff check, strict mypy, pytest; actual Linux helper | Windows and Linux: 35 tests pass, format/lint/types pass. New tests assert display semantics and explicit terminal color/width under NO_COLOR/TERM=dumb. No acceptance assertions weakened. |
| NV-01-03-AC3 visual evidence | `uv run --frozen python tools/capture_previews.py`; headless Edge screenshot inspection | New artifacts captured in phase01-polished. Actual card inspected in light, dark and 420px viewport; terminal panels inspected at 60/100 columns; page includes 160-column and plain alternatives. No page-wide overflow or HTTP requests. Owner review of these artifacts remains pending. |

Bounded dates are explicitly labeled Preview dates and derived only from the
prepared snapshot. They do not claim a full requested/observed historical span.
Formatting adds thousands separators and retains four decimal places; the typed
underlying frame and export data are unchanged. No market-support, snapshot or
new provenance claim is introduced.

## Demonstrated terminal repair

Inspection found inherited NO_COLOR removed color even in the explicitly
capable test condition, and inherited TERM=dumb made Rich size default to 80
columns despite the requested width. A new regression test reproduced each
failure before its repair. Installed Rich 15.0.0 Console signatures and size
property were inspected. The internal StringIO console now receives explicit
color/legacy/viewport conditions. The CLI still decides capability from the
real NO_COLOR/TERM/TTY settings, so normal dumb/plain operation remains plain.
No global environment setting was changed. All 60/100/160-column capable and
plain capture widths are asserted after stripping ANSI formatting.

## Visual inspection procedure and artifacts

Screenshots used an isolated Playwright 1.64.0 tool environment and the existing
Edge 155.0.4283.62 executable; neither is a project dependency. Browser launched
headless, offline, at 1280x1000 with light color scheme and opened the generated
local review.html. Screenshots captured the whole page, actual notebook card and
100/60-column terminal containers; dark mode and a 420x900 viewport were then
selected for additional card captures. Assertions checked four table rows, no
script element, no HTTP requests, and no document-wide horizontal overflow.
The narrow table scrolls inside its card; columns are not silently discarded.
Screenshots were inspected directly. This is browser appearance evidence, not
a claim of notebook-kernel execution or human approval.

All new review files are under `docs/evidence/artifacts/phase01-polished/`:
`review.html`, `review-light.png`, `preview.ipynb`, `notebook-light.png`,
`notebook-dark.png`, `notebook-narrow.png`, `terminal-60.png`, `terminal-100.png`,
and the 60/100/160-column `.txt`/`.ansi` captures. Paths are explicit because the
historical baseline checker supports only .md/.json/.py link targets.

## Delivery and remaining acceptance

Owner supplied `https://github.com/Shrikant94-prog/niftyverse.git` and authorized
Phase 01 local/remote delivery. `gh repo view Shrikant94-prog/niftyverse --json
nameWithOwner,isEmpty,defaultBranchRef,url` confirmed access and an empty repo.
Local origin now points to it. No remote write, license selection or Phase 02
work occurred. The polished preview is presented for owner review before the
remaining CI/macOS checks and final Phase 01 delivery. PH-01-GATE remains open.
