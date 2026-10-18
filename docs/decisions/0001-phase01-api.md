# ADR 0001 - Phase 01 public names and configuration

Accepted implementation convention for the thin offline fixture, not the
complete acquisition API. Product decisions and later phase contracts retain
their documented scope.

- Distribution/import/command: `niftyverse`; CPython 3.14 only. No user identity
  inferred for package metadata. Dependencies and optional trees are in uv.lock.
- Functions/modules use snake_case; public records use PascalCase; constants
  use UPPER_CASE. Public functions/records are typed; strict mypy and Ruff in
  pyproject.toml define the mechanical rules. tests/type_smoke.py checks names
  and return types. No configuration mutation or automatic acquisition on import.
- `build_fixture(payload: bytes, destination: Path) -> SliceResult` explicitly
  persists a new owned fixture DB; `extract_fixture` writes a new direct CSV
  bundle. These are Phase 01 proof interfaces, not production `build`/`extract`
  provider contracts. They share pure validation, exact schema and ordering.
- `SliceResult.to_polars(max_rows=100_000)` explicitly returns a frame clone and
  rejects an exceeded bound. It is an eager materialized fixture result that
  outlives the closed sink, not a streaming cursor or research snapshot.
- Display uses a precomputed tuple of at most 10 frozen rows, never a query or
  full-frame conversion. `PreviewConfig(max_rows=10, max_cell_chars=120)` accepts
  only 0..20 rows and 1..120 characters. Four known columns and a 64 KiB HTML
  bound apply; a larger configured row limit cannot fabricate uncaptured rows.
- MIME methods return escaped static HTML and plain text without requiring
  IPython/Plotly/widgets. No scripts, remote assets or automatic explorer opens.
- The frozen `BuildEvent` is created after successful sink return and contains
  actual committed fixture rows. Terminal summaries consume it; no download,
  attempt, ETA or snapshot counts are invented. CLI human output goes to stderr;
  `--json` returns only structured JSON on stdout. Explicit `--plain`, pipes,
  TERM=dumb and NO_COLOR select plain summaries. Color receives an explicit
  capable-terminal condition in tests/captures.
- Optional `yahoo`, `pandas`, `notebook` and `filings` extras are isolated. The
  filings extra is intentionally empty until source evidence selects a parser;
  requiring one now raises an actionable error. No generic XML financial parser
  or untested processor configuration is introduced.

This avoids a framework or unused provider tree while preserving the future
core/adapter/storage/builder/display boundaries. Full publication durability,
production adapters, complete CLI and notebook explorer remain later phases.
