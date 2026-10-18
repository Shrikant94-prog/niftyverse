# Development and the offline fixture

Use CPython 3.14 and uv 0.12.9. `.python-version` stays `3.14`; exact local
patch/build and environment checks are in [package evidence](evidence/01-20261018-package.md).

```text
uv sync --frozen
uv run --frozen ruff format --check src tests
uv run --frozen ruff check src tests
uv run --frozen mypy src tests
uv run --frozen pytest -q
uv run --frozen niftyverse --help
uv run --frozen niftyverse fixture --help
uv run --frozen niftyverse fixture --input tests/fixtures/observations.json --output .local/example-csv --json
uv run --frozen niftyverse fixture --input tests/fixtures/observations.json --output .local/example.duckdb --mode database --plain
uv run --frozen python tools/capture_previews.py
uv run --frozen python tools/check_wheel.py --lane core
```

Create `.local/` first; the output parent must exist. Choose a new output path
for each run; existing destinations fail. Inputs are
owned synthetic data, not market data. The DB and direct fixture output share
validation, schema and values. Direct CSV has explicit N/V null/value encoding
and schema/provenance in manifest.json; use
`niftyverse.storage.csv.read_fixture_bundle(Path(...))` for typed fixture replay.
See [slice evidence](evidence/01-20261018-slice.md) for exact encoding/limits and
[ADR 0001](decisions/0001-phase01-api.md) for public conventions.

The wheel checker always builds from current source into a new temporary
directory and installs outside the checkout. Repeat with `--lane yahoo`,
`yahoo-consumer`, `pandas`, `notebook` or `filings` for separate environments.
Frozen lanes install hashed exports of uv.lock; yahoo-consumer resolves normally
against package metadata. Build/install downloads are allowed; runtime smoke
children deny Python socket/child-process operations. This does not establish a
native-code OS firewall. Optional APIs are actually exercised in their own lane.

`uv pip` ignores Requires-Python upper bounds; pip 26.2.1 in the dev group tests
wheel rejection for both 3.12 and 3.15. No compatibility with those versions is
promised. Development notebook execution tooling is a dev dependency, not a
core/notebook-extra leak. Default pytest excludes `live` probes; none exist yet.
CI declares Windows/Linux behavior and macOS install smoke; local Windows
results do not prove hosted CI ran.
