# Phase 01 - shared research display, 18 October 2026

Historical observations; current status belongs in [STATE](../../STATE.md).
The owner requested a three-zone terminal card and four-zone notebook dashboard,
including a Rich protocol, shared value semantics and executable checks. This
supersedes the appearance reviewed in the [previous record](01-20261018-terminal-hierarchy.md).
The object is `SliceResult`, the existing offline slice result. Tested source is
this record's containing commit; display source SHA-256 is
`1855bdd659e3bfb498d0e1fa3b8634fd3d4a3c58ef4d300dc28b61a94f2168d7`,
and result source SHA-256 is
`590b20f3ba84aa501321356ff443d40c54fc4075d0d47c99ae32bfd40f3621f8`.

## Behavior and scope

- `SliceResult.__rich_console__` and the CLI summary share a single rounded
  three-zone card, with joined horizontal rules, a saved pill/title, right-aligned
  counts/type, fixed-key provenance grid, underlined data table and preview footer.
  At 60 columns the table is omitted and the footer honestly reports zero previewed
  rows with a widening hint; 100/160 columns show up to five prepared rows.
- Notebook HTML has a 780px maximum width, sans-serif UI chrome, local monospace
  font stacks for values/pills, four provenance KPIs, inline dtype badges and a
  shaded integrity footer. Data cells use 18px vertical / 28px horizontal padding.
  The full hash is available in the hash tooltip. Synthetic-fixture and preview-date
  wording avoids claiming a research snapshot or full-result date coverage.
- Both surfaces preserve leading-zero IDs, exact four-place decimals, nulls,
  empty strings and literal `__NULL__`. Nulls are amber; notebook null pills are
  italic and empty strings have a separate slate pill. Numeric zero is slate,
  nonzero figures are foreground, identifiers teal, dates slate and labels muted.
  Numeric values remain right-aligned and unwrapped, with generous column gaps.
- Source strings cross explicit Rich-markup or HTML escaping boundaries. HTML is
  scoped, bounded and self-contained with no scripts, remote fonts or assets.
  Rendering consumes only the existing immutable bounded snapshot. No data,
  schema, persistence, dependencies, lockfile or later phase changed.
- Native terminals retain their configured ANSI palette. The review capture uses
  the existing coordinated navy/mint/teal/sage/amber reference palette. No-color
  and legacy-console paths use ASCII structure and a useful summary.

## Verification observed

Tests were written and run before implementation: four new cases failed for the
missing Rich protocol/card structure, zero styling and dashboard layout, while the
ten existing display cases passed. Tests subsequently cover literal
`<script>[red]x[/red]</script>`, null/empty/literal-null distinctions, zero style,
`99,999,999,999.9999` and the fixture's larger maximum decimal, and 60/100-column
card zones, exact width and protocol/CLI agreement. Existing I/O spies now also
exercise `Console.print(result)`; no render query, read or full conversion occurs.

A boundary check additionally exposed metadata clipping/Unicode ellipses at the
already-supported 20-column minimum; adaptive key width and folding preserve the
ASCII fallback. Legacy Windows consoles reserve one column within Rich itself;
tests enforce the available-width bound there and exact width on modern consoles.
Installed Rich signatures/source were inspected before using the rendering APIs.

All following checks exited zero on the final display source:

| Procedure | Observation |
|---|---|
| `uv run --frozen ruff format --check src tests` and `ruff check src tests` | Pass, 19 formatted files |
| `uv run --frozen mypy src tests` | Pass, 19 source files |
| `uv run --frozen pytest -q` | 41 pass on Windows CPython 3.14.7 |
| `wsl -d Ubuntu -- python3 .../tools/check_linux.py` | Format/lint/types and 41 tests pass on Linux CPython 3.14.4; fresh core wheel passes |
| `uv run --frozen python tools/check_wheel.py --lane core` | Fresh Windows core wheel passes, optional imports isolated |
| Same wheel command with `--lane notebook` | Fresh Windows notebook-extra wheel passes, including actual IPython DisplayFormatter |
| `uv run --frozen python tools/capture_previews.py` | Actual result MIME and 60/100/160-column plain/ANSI captures saved |
| Offline headless Edge through Playwright 1.64.0 | Light/dark/420px layout checks and screenshots pass |

The fresh wheel smoke also exercises the new Rich protocol after denying DB
connections/full materialization. Socket and process-launch negative controls pass;
these are Python audit guards, not an OS firewall. Wheel SHA-256: Windows core and
notebook `885e20fc7c965cf28986f2e515f1a682d361092eb38b539d7425441dc381b7e7`;
Linux core `76ddcea57e72813e592fb0a809c89d7ae3a3175895ae7b0b6b6a42200cbab9cc`.
Lock SHA-256 stays
`569bbd9a2d4daea3d86f55690014f8cb965aff95ac3eddd0303b453ab0672724`.

Browser measurements: outer card 780px, table and scroll viewport both 778px
(no horizontal drift at desktop width), cell padding `18px 28px`, numeric zero
right-aligned in monospace with slate `rgb(100, 118, 128)`, null style italic.
At 420px, KPIs use two columns and the document has no page overflow; the table
scrolls within the card. Light/dark notebook and 60/100-column terminal screenshots
were inspected. Notebook output is captured MIME, not a kernel execution claim.

An exploratory `ruff check .` reported eight pre-existing E501 lines in the
immutable baseline `tools/check_docs.py`. The configured lint targets pass; that
baseline file was preserved. Documentation validation and static fingerprints
pass separately with `tools/check_docs.py --baseline --self-test`, including a
clean tracked-source copy (59 project Markdown files). The two changed tool files
also pass targeted Ruff format/check. Staged bytes match tested source and lock
hashes; the staged whitespace check passes.

## Review artifacts and remaining verification

`docs/evidence/artifacts/phase01-research-card/` contains `review.html`,
`preview.ipynb`, `terminal-{60,100,160}.{txt,ansi}`, `terminal-60.png`,
`terminal-100.png`, and `notebook-{light,dark,narrow}.png`. Earlier captures remain
historical. The owned input fixture is unchanged, SHA-256
`277226b740ac2ce6b1b3a4659c8cc18378358989bdaed20f4c8a5774c8c250fa`.

This newly requested notebook/terminal design awaits owner visual review.
Hosted CI/macOS smoke and authorized remote Phase 01 delivery remain pending
that review. PH-01-GATE is open; no Phase 02 work or market-source readiness claim.
