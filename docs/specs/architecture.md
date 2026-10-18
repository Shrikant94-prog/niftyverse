# Architecture and dependencies

**Read when:** Changing module ownership, shared interfaces, packaging, or dependencies.

**Authority:** detailed product contract, revision 18 October 2026. Implementation and dataset support are not claimed. Progress belongs only in root STATE.

## Section lookup

- [6.1 End-to-end flow](#s6-1)
- [6.2 Module ownership](#s6-2)
- [6.3 Project layout and growth](#s6-3)
- [6.4 Core abstractions](#s6-4)
- [6.5 Dependencies and compatibility](#s6-5)
- [6.6 Implementation conventions](#s6-6)

Read the selected section and its necessary dependencies; this lookup is not a full-file reading checklist. Original section numbers are retained as stable references.

<a id="s6"></a>
## 6. Architecture and package boundaries

<a id="s6-1"></a>
### 6.1 End-to-end flow

```text
DataPlan / fluent request       Explicit local filing
           |                            |
compiler + identity/calendar             |
           |                            |
bounded acquisition -> immutable capture/hash
           |                            |
           +--- format decoder + economic mapper ---+
                               |
                    canonical Arrow batches
                               |
               shared schema/financial/time validation
                               |
          +--------------------+--------------------+
          |                    |                    |
   DuckDB publication    Direct CSV/Parquet    Arrow/Polars result
   versions/coverage     bundle + manifest    bounded materialization
          |
   history bundle -> ResearchPlan -> immutable research snapshot
          |
   SQL / Polars / export / CLI / Jupyter
```

Direct-source bytes are captured before parsing. Yahoo enters at its retained `sdk_result` boundary ([§5.6](sources.md#s5-6)), not fictitious raw HTTP bytes. Local files use the same decoder/mapper with origin `local_file`; no hidden fetch or automatic source certification. Storage selection occurs after shared normalization/validation; direct extraction does not instantiate a DuckDB store. [§11.6](storage.md#s11-6) defines its narrower persistence/replay guarantees. JSON/XML decoding is not an Arrow zero-copy operation; measure copying where performance matters.

<a id="s6-2"></a>
### 6.2 Module ownership

| Layer | Owns | Must not own |
|---|---|---|
| `core` | Domain IDs, time policies, config, errors, protocols | Network sessions, SQL, terminal rendering |
| `transport` | HTTP, timeouts, budgets, cookie refresh, retries | Financial normalization or dataset completeness |
| `adapters` | Verified provider contracts and economic mapping; shared pure filing decoders in `adapters/filings` | Hidden decoder network/file I/O, global orchestration, direct DB writes, UI |
| `builder` | Planning, dependencies, incremental scheduling, cancellation/resume | Endpoint-specific JSON keys or display formatting |
| `quality` | Validators, readiness, reconciliation, correction evidence | Silent repair of business facts |
| `storage` | Raw objects, DB/file sinks, transactions, schema migration, versions, snapshots | Download scheduling or investment calculations |
| `research` | Availability joins, recipe dependency graphs, research panels | Source acquisition hidden inside dataframe expressions |
| `analytics` | Pure versioned adjustment/indicator operations | Network calls, invented missing data |
| `display` / `cli` | Render events and bounded results; explicit user controls | Trading decisions, source retries, hidden fetch-on-display |

<a id="s6-3"></a>
### 6.3 Project layout and growth

```text
niftyverse/
  AGENTS.md                 # Small always-on working rules
  STATE.md                  # Only current execution status
  PLAN.md                   # Short scope/roadmap/reading router
  docs/specs/               # Topic contracts, selectively read
  docs/phases/              # Static acceptance briefs
  docs/WORKFLOW.md          # One execution/evidence procedure
  docs/evidence/            # Historical observed evidence, created when needed
  tools/check_docs.py       # Standard-library documentation validation
  pyproject.toml            # Created in Phase 01
  uv.lock                   # Created and tested in Phase 01
  src/niftyverse/           # Production modules created only when needed
  tests/                    # Independent behavior and contract checks
```

Create packages/modules only for demonstrated behavior. Do not build empty future-phase scaffolds, copy the earlier implementation, or add a second planning/state system. Core, adapter, transport, storage, builder, research, analytics and display ownership is defined above. Explicit external input identities are recorded in [INPUTS](../INPUTS.md); missing data blocks its dependent evidence tasks, not bootstrap.

<a id="s6-4"></a>
### 6.4 Core abstractions

| Abstraction | Contract |
|---|---|
| `DataSource` | Declares provider identity and dataset capabilities; expands bounded requests; asynchronously returns acquisition envelopes (direct raw bytes or declared SDK captures); normalizes into typed batches. No DB/UI responsibility. |
| `DatasetCapability` | Dataset/field/format support, actual date bounds, units, temporal semantics, limitations, contract version, verification status. |
| `FetchRequest` | Stable request fingerprint, dataset, instrument/contract/date filters, source choice, schema generation, page/checkpoint token. |
| `RawEnvelope` | Origin (`provider` or `local_file`) and acquisition artifact hash, sanitized request metadata, retrieval time, parser/SDK contract and immutable object reference; `capture_kind` is `provider_raw` or `sdk_result`. Wire status/content type may be unknown for SDK captures; never invent them. |
| `NormalizedBatch` | Arrow batch plus source row locators, canonical schema version, diagnostics and coverage candidate. |
| `DataPlan` | Immutable acquisition intent, universe, windows, datasets, source-format policy and quality rules; a store is required by `build`, optional for direct `extract`. |
| `FilingDocument` / `SourceAssertion` | Immutable document identity plus lossless fact/context/unit/dimension/locator data before versioned economic mapping. |
| `OutputTarget` / `ExtractionReport` | Memory or CSV/Parquet destination, raw-retention policy, shared validation/coverage/failures and completion manifest; no fabricated database snapshot/resume ID. |
| `CompiledPlan` | Deterministic dependency graph, work estimates/bounds, blockers, required capabilities and input hashes. |
| `BuildHandle` / `BuildReport` | Observable progress/cancellation and durable final statuses, coverage, failures, snapshot references. |
| `DataResult` | Immutable result metadata, prepared bounded preview, explicit Arrow/Polars/export/explorer methods. |
| `ResearchPlan` | Universe, decision schedule, feature recipes, availability mode, output contract. |
| `FeatureRecipe` | Pure versioned transform shared by standalone and ResearchPlan use; declares input schema/units/basis, parameters, session/availability/null policies, warmup and dependency influence, output schema and implementation identity. Registration is explicit trusted code; no implicit acquisition. |
| `DatasetSnapshot` | Explicit `history_bundle` or `resolved_result` kind; pinned fact/version/partition selections, recipe/code/schema versions, artifacts and hashes. |
| `QualityIssue` | Stable code, severity, affected keys, source evidence, remediation, scope of impact. |

Prefer explicit provider registration at first. Optional entry-point plugins are loaded only when selected, with declared capability/schema versions. Never import arbitrary modules named in an untrusted data file. The source protocol makes future providers possible without claiming failover exists today.

<a id="s6-5"></a>
### 6.5 Dependencies and compatibility

Core: `httpx[http2]`, `msgspec`, `polars`, `pyarrow`, `duckdb`, `click`, `rich`, a small cross-platform lock package such as `filelock`, `platformdirs`, and `tzdata` where system timezone data is absent. Final versions are selected and locked during phase 1 after wheel/import checks; do not guess future compatible versions here.

Optional extras: `notebook` = ipywidgets/Plotly/anywidget/IPython as required by the tested rendering path; `pandas` = conversion only. Development groups: pytest, pytest-asyncio, Hypothesis, mypy, Ruff, coverage, notebook execution tooling and build validation. Keep documentation tooling in its own group. No requests, pandas, SciPy, Excel reader, Selenium, or legacy wrapper in core.

Add optional `yahoo` = the tested exact yfinance release and its resolved dependency tree. Its upstream dependencies include pandas and its own HTTP backend; those are confined to the Yahoo worker/adapter boundary, with Arrow/Polars everywhere downstream. Installing `yahoo` does not make it a core dependency or authorize pandas computation in research/analytics; `pandas` remains the separate user-facing conversion extra. Do not strip transitive dependencies by hand, install yfinance's optional repair extras or pass an HTTPX client into its session argument. [Upstream dependency declaration](https://github.com/ranaroussi/yfinance/blob/main/pyproject.toml), [upstream HTTP backend](https://github.com/ranaroussi/yfinance/blob/main/yfinance/_http.py).

**Python pin:** CPython **3.14.x only** for this release, with `.python-version` containing `3.14`, `requires-python = ">=3.14,<3.15"`, Python 3.14 Windows/Linux behavior lanes and a Python 3.14 macOS installation smoke check. Phase 01 records the exact patch/build used and tests both minimal core and the Yahoo extra; lock resolved dependencies with uv. Interpreter patch updates rerun compatibility checks and produce a new environment identity. No automatic 3.15 lane/promotion or silent downgrade to 3.12. Do not promise free-threaded/interpreter-specific behavior without testing. Use `uv sync --frozen`, `uv run`, and `uv build` once implementation exists.

An optional `filings` extra isolates any standards-aware XBRL/inline-XBRL and HTML dependencies. Evaluate Arelle and py-xbrl as candidates against representative NSE filings, licensing, exact Python 3.14 compatibility, offline taxonomy resolution and resource limits; neither is selected or certified by this plan. Phase 01 establishes the optional boundary; after Phase 02 evidence, lock/test the selected implementation before NV-03-04 closes. Do not implement financial semantics with generic XML tag scraping or allow a processor's default taxonomy downloads. Core import and reading already normalized facts must work without this extra; decoding/replaying structured filings needs the exact pinned parser/taxonomy artifacts. [Arelle documentation](https://arelle.readthedocs.io/en/latest/), [py-xbrl source](https://github.com/manusimidt/py-xbrl).

<a id="s6-6"></a>
### 6.6 Implementation conventions

- Follow [§6.2](architecture.md#s6-2) boundaries. Public entry points orchestrate small typed operations; decoding and economic mapping are separate. Share validation/recipes between persistent and direct paths. Add a protocol only for an actual boundary; do not create unused providers, empty package trees or parallel frameworks.
- Use Python 3.14 typing, `snake_case` functions/modules, `PascalCase` types and `UPPER_CASE` constants. Type public APIs and boundary records explicitly; contain untyped provider dictionaries at wire-decoding boundaries. Use the existing chosen domain models rather than passing arbitrary dictionaries through the system. Ruff and strict mypy configuration established in Phase 01 is authoritative for mechanical style.
- Preserve decimal source numbers, nullable facts, stable IDs and timezone-aware instants per [§7.2](data-model.md#s7-2). Do not use binary floats for source money, symbol-only joins, catch-all empty results or silent coercion. Typed errors carry affected scope and actionable context without secrets.
- No import-time acquisition, writes, worker launch or configuration mutation. Own clients, transactions, streams and workers explicitly; close them on success/error/cancellation. Async entry points must not block the event loop or create nested loops. Constrain synchronous parser/SDK work with the tested resource boundary.
- Before using an unfamiliar API, inspect the installed/pinned version's signature, source or official documentation and prove the smallest relevant behavior. Do not guess endpoints, response fields, framework keys or dependency compatibility. Label proposals and unverified source claims; stop only the dependent operation when a contract is unresolved.
- Inspect callers, schemas and acceptance before edits. Test observable outcomes using independent expected values and adversarial boundaries; no tests that merely restate implementation. Keep offline fixtures deterministic and live probes opt-in. Preserve a regression reproducer for substantive bugs; measure a suspected bottleneck before introducing caching/concurrency.
- Prefer explicit names and short functions with one purpose, concise docstrings for public units/side effects/errors, and comments explaining non-obvious constraints. Reuse existing conventions; avoid speculative abstractions and repetitive boilerplate.
