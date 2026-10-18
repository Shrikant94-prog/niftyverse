# Phase 01 - display and integration observations, 18 October 2026

Historical observations only; current progress belongs in [STATE](../../STATE.md).
This record does **not** claim PH-01-GATE is closed.

## Source, input and environment identities

- Previous checkpoints: package `644c11e`; offline slice `0bfce43`. Display,
  tests, helpers, ADR and preview artifacts are identified by the checkpoint
  commit containing this record. No source/topic specification/checker baseline
  bytes or uv.lock were changed by this checkpoint.
- Owned JSON SHA-256:
  `277226b740ac2ce6b1b3a4659c8cc18378358989bdaed20f4c8a5774c8c250fa`.
  [Slice evidence](01-20261018-slice.md) defines its independent expected values.
- Windows CPython 3.14.7 and uv 0.12.9 as in
  [package evidence](01-20261018-package.md); lock SHA-256 remains
  `569bbd9a2d4daea3d86f55690014f8cb965aff95ac3eddd0303b453ab0672724`.
- Actual Linux execution: Ubuntu WSL,
  `Linux-6.18.33.2-microsoft-standard-WSL2-x86_64-with-glibc2.43`,
  CPython `3.14.4 (main, Apr 8 2026, 04:02:31) [GCC 15.2.0]`, uv 0.12.9.
  Different Python patch/build is recorded explicitly, not represented as the
  Windows environment. The same frozen dependency versions apply except the
  platform-marked Windows tzdata dependency.
- Final runtime-source wheel SHA-256 on Windows:
  `c8ef5178c75befd7db70377028a51b5cff7ee747f4b6e6dc6bee5623d1128e2b`;
  on Linux: `aafd09eb51e0367fd33964144b8f5a11ce62e7f4db9ad29829e0c9f3eab45177`.
  Each packaging run built a fresh artifact. Cross-platform byte identity is
  neither assumed nor required; exact fixture values are checked on both.

## Acceptance and integration observations

| Criterion | Independent expectation / actual procedure | Observed result |
|---|---|---|
| NV-01-03-AC1 | Actual slice MIME and committed event; `uv run --frozen pytest -q`; `uv run --frozen python tools/capture_previews.py` | 33 tests pass. Static HTML and text display the fixture, 4 actual committed rows, direct mode, bounded table and input hash. Success event created only after sink return. Machine CLI output is JSON only; human output is stderr. |
| NV-01-03-AC2 | Disable Path.open, socket calls, DuckDB connect, SliceResult.to_polars, frame conversion/clone and LazyFrame.collect after result construction; render normal/empty/large-metadata cases | Passes with no I/O/materialization. Malicious labels/mode strings escaped; terminal control characters removed. Snapshot captures at most 10 frozen rows and 4 known columns; cells capped at 120 characters and HTML below 64 KiB. Empty display reports zero without constructing an empty successful build. |
| NV-01-03-AC2 | Minimal installed-wheel lane has no display extras; render MIME; separate notebook lane calls actual IPython DisplayFormatter | Both pass. Plain/HTML fallback needs no notebook extra. Notebook lane also imports its declared widgets/Plotly/anywidget; no interactive explorer is implied. |
| NV-01-03-AC3 | `uv run --frozen ruff format --check src tests`; `ruff check src tests`; `mypy src tests`; capture widths 60/100/160 and explicit capable/plain modes | All local checks pass; 19 typed source/test files. Public names/configuration fixed in [ADR 0001](../decisions/0001-phase01-api.md) and tests/type_smoke.py. Captures are linked below. **Owner visual feedback has been requested but not received.** |
| PH-01-GATE software portions | Fresh core wheel installs outside source under Python 3.14; compare hand-authored rows through real msgspec/Arrow/DuckDB/CSV/Polars; verify CLI entry point/help and JSON; render without DB/materialization | Windows and actual Linux wheel smoke pass. Core optional imports absent; DB/direct exact values/schema agree; no legacy imports or source acquisition. Runtime smoke child socket and process-launch negative controls both deny operations before package import. |
| PH-01-GATE extras portions | Repeat fresh builds and separate frozen lanes core/yahoo/notebook/pandas/filings; resolve yahoo-consumer separately | All Windows lanes pass. Yahoo 1.7.0 and its complete tree are locked; consumer result currently matches locked versions. Actual result-to-pandas conversion and IPython formatting pass. Filings parser remains intentionally unselected and unavailable, with candidate Python 3.14 evidence in package record. |
| NV-01-01 verification design / platform matrix | Windows/Linux behavior and macOS install smoke; distinguish configured CI from executed checks | Local Windows and WSL Linux behavior/wheel checks pass. GitHub workflow is configured. **macOS install smoke and hosted CI have not run.** `git remote` is empty; no push/publication is authorized or performed. These required checks are not converted into passes. |

## Executed procedures and test ordering

Display negative/boundary tests were written and run first; initial collection
failed because niftyverse.cli did not exist. This is a missing-interface result,
not a claimed behavioral red test. The implemented display then passed all its
normal/adversarial cases. One strict-type error exposed deprecated Click
get_text_stream in installed Click 8.5.0; inspecting its source/signature led to
using sys.stderr.isatty directly. No blanket type/lint suppression was added.

Windows commands actually run:

```text
uv run --frozen ruff format --check src tests
uv run --frozen ruff check src tests
uv run --frozen mypy src tests
uv run --frozen pytest -q
uv run --frozen niftyverse --help
uv run --frozen niftyverse fixture --help
uv run --frozen python tools/capture_previews.py
python tools/check_wheel.py --lane core
python tools/check_wheel.py --lane yahoo
python tools/check_wheel.py --lane yahoo-consumer
python tools/check_wheel.py --lane notebook
python tools/check_wheel.py --lane pandas
python tools/check_wheel.py --lane filings
```

All exited 0. The final strengthened core helper also invokes the installed CLI
with an actual input file and asserts 3 committed rows on clean JSON stdout.
No live provider probe exists or was executed; default pytest excludes live.
After adding one materialization-limit test the Windows/Linux suites both report
33 tests. Earlier full extras checks used the same final runtime-source wheel
and exercised real slice/MIME; later helper-only strengthening does not change
that wheel's source identity.

Linux command: `wsl -d Ubuntu -- python3 <selected-project-linux-path>/tools/check_linux.py`.
The first attempt failed because Ubuntu lacks ensurepip. Instead of changing
system Python or installing OS packages, the helper downloads the official uv
0.12.9 Linux wheel, checks SHA-256
`5badfd805fd88bf99b4b4f044f6e8f762f1892cab27477f4427bb473e93dd049`,
and extracts its uv executable into a temporary directory. It freezes the project
environment separately in /tmp, then runs format/lint/mypy, all 33 tests and the
fresh core wheel helper. Exit 0; temporary tools/project/wheel environments
removed on completion. Windows .venv and interpreter pin remain intact.

New verification helpers also pass Ruff check/format. Baseline documentation
checks pass; the original checker scans ignored local environments, so Markdown
counts in the development workspace include dependency documents. A clean
checkout is the authoritative document-only inventory; no checker or historical
manifest was silently rewritten to hide that behavior. Its link inventory supports only .md/.json/.py, so HTML/notebook/text/ANSI artifacts below use explicit paths rather than unsupported Markdown link targets.

A clean staged-source snapshot was also tested: enumerate `git ls-files --cached`,
copy those 96 paths into a new temporary directory with byte-equality assertions,
then run `python tools/check_docs.py --baseline --self-test` there. Exit 0;
55 project Markdown files, unchanged stable-ID counts and all static fingerprints
match. Temporary snapshot removed. Generated HTML preserves the plain fallback's
meaningful empty-label space with an HTML entity, so whitespace checking passes
without changing the displayed fixture value.

## Concrete review artifacts and outstanding checks

- Notebook and terminal appearance review (`docs/evidence/artifacts/phase01/review.html`)
- Saved notebook MIME output (`docs/evidence/artifacts/phase01/preview.ipynb`) (captured actual
  result output, not a claim of notebook-kernel execution)
- Plain terminal captures: 60 (`docs/evidence/artifacts/phase01/terminal-60.txt`),
  100 (`docs/evidence/artifacts/phase01/terminal-100.txt`), 160 (`docs/evidence/artifacts/phase01/terminal-160.txt`)
- Capable-terminal ANSI captures: 60 (`docs/evidence/artifacts/phase01/terminal-60.ansi`),
  100 (`docs/evidence/artifacts/phase01/terminal-100.ansi`), 160 (`docs/evidence/artifacts/phase01/terminal-160.ansi`)

Owner was asked to accept or request changes to the concrete appearance review;
the question remains unanswered. Artifact presence is not human acceptance.
Required macOS smoke/hosted CI also remain unverified. PH-01-GATE remains open;
Phase 02 has not begun and is eligible only after Phase 01 closure and separate
authorization. No further source implementation is required by the currently
observed tests, but these missing acceptance checks prevent phase completion.
Source/dataset readiness, production adapters, durable publication and a full
CLI/explorer remain later work. Audit hooks cover Python runtime subprocess
boundaries, not an OS firewall for native libraries.
