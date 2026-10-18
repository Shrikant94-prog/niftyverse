# Requirements and acceptance ownership

**Read when:** Requirement mapping and release acceptance. Read only the IDs assigned to the current phase.

**Authority:** detailed product contract, revision 18 October 2026. Implementation and dataset support are not claimed. Progress belongs only in root STATE.

## Section lookup

- [2.1 Requirement register](#s2-1)
- [2.2 Two completion axes](#s2-2)
- [2.3 Explicit backlog](#s2-3)
- [18.2 Review amendment ownership — no phase renumbering](#s18-2)

Read the selected section and its necessary dependencies; this lookup is not a full-file reading checklist. Original section numbers are retained as stable references.

<a id="s2"></a>
## 2. Release requirements and ownership

<a id="s2-1"></a>
### 2.1 Requirement register

Every ID must map to static phase acceptance and observed evidence. Track execution progress only in STATE. Available coverage does not authorize silently dropping requested features.

| ID | First-release requirement | Completion evidence |
|---|---|---|
| CORE-01 | uv package, Python matrix, typed API, dependency boundaries | Wheel/import/type checks; `py.typed` included |
| CORE-02 | Provider protocols, capability registry, Python/TOML configs | Another fixture provider works without changing builder/storage |
| NET-01 | Async sessions, budgets, retries, cancellation, cookies | Deterministic fault tests and opt-in contract report |
| NET-02 | Official CSV/ZIP and scoped filing-document decoding across generations | Historical/current formats, bounded XML/HTML and malformed input rejection |
| STORE-01 | Raw retention, DuckDB migrations, atomic publication | Crash/restart, contention, migration, idempotency tests |
| STORE-02 | Snapshots, Parquet/CSV, backup/restore, replay | Reproduce pinned output without network |
| ID-01 | Dated identities, aliases, listing status, calendars | Renamed/reused symbols, delisted/non-tradable cases |
| UNI-01 | NIFTY 500 correction ledger, evidence, coverage | Supplied file fails honestly; verified subset publishes |
| UNI-02 | Historical membership and local delisted input | Dead/missing-price instruments remain visible |
| EQ-01 | Equity OHLCV, turnover/trades/delivery where supplied | JSON/report reconciliation; field coverage |
| IDX-01 | Index prices, valuations, total-return variants | Separate typed datasets and identities |
| DER-01 | Futures/options EOD and dated contract metadata | Expiry/strike/type/lot-size/unit tests |
| REP-01 | Equity/F&O bhavcopies, participant OI/volume | Verified archives and dated schema parsers |
| REP-02 | Bulk/block/short-selling and FII/DII where available | Segment/unit separation; unavailable history explicit |
| CORP-01 | Actions, announcement catalog, event calendar | Typed dates/revisions; announcement attachments remain metadata-only |
| FUND-01 | Catalogues and financial facts from JSON, XBRL XML, inline XBRL and verified legacy financial HTML; P&L, balance sheet, cash flow and segments | Period/unit/context/basis/revision tests; per-statement and per-family coverage |
| OWN-01 | Shareholding catalogues and JSON/XBRL/inline-XBRL ownership facts | Category/denominator/context/date/revision tests and measured coverage |
| GLOB-01 | Yahoo/yfinance S&P 500 and Nasdaq Composite EOD closes | Symbol/basis mapping, explicit SDK options, completed sessions, timing/coverage, cancellation and captured-result replay |
| BUILD-01 | DataPlan, explain/dry-run, incremental DAG | Multi-dataset build; unchanged rerun deduplicates |
| BUILD-02 | Resume, refresh, cancellation, repair, gaps | Failures never advance complete coverage |
| TIME-01 | Effective/publication/observation/revision semantics | Future-data fixtures cannot leak into strict panels |
| RES-01 | ResearchPlan, temporal joins, features, missingness | All eligible instruments retained with reason codes |
| RES-02 | Split/bonus adjustment and standard indicators | Hand-calculated fixtures; correction recomputation |
| RES-03 | Provenance, invalidation, snapshot comparison | Old snapshots persist after input corrections |
| API-01 | Fluent API, Arrow/Polars, SQL, optional pandas, direct extraction, local parsing and fact trace | Equivalent facts/diagnostics across applicable entry points and storage modes |
| UX-01 | Rich CLI, progress, diagnostics, machine output | Narrow/wide terminal and JSON tests |
| UX-02 | Notebook previews, tables/charts, async progress | Safe offline rendering; bounded payloads |
| QA-01 | Tests, CI, recovery, performance | Compatibility and verification reports |
| DOC-01 | Task-oriented docs and migration examples | Executable examples; visible capability limits |
| ETF-01 | NSE ETF catalogue, evidenced metadata and historical EOD | Dated identities, fund-unit semantics, field coverage and no index/NAV substitution |

<a id="s2-2"></a>
### 2.2 Two completion axes

The release includes historical derivatives and reports previously deferred. It cannot promise data absent from permitted sources.

1. **Software readiness:** schemas, adapters, APIs, validation, tests, and coverage reporting work.
2. **Dataset readiness:** a specific period/universe/field has sufficient source and timing evidence.

A module may be implemented while ten-year readiness is blocked. State both. An adapter that has never obtained a valid permitted-source response cannot be called supported because its fixtures pass. Mark it experimental/blocked; ask the owner before treating a mandatory blocked capability as release-complete.

Historical fundamental depth is measured incrementally during adapter development and broader Phase 22 testing, by issuer, period, statement, concept, basis and format. There is no universal earliest supported year: different fields and sectors can have different gaps. Successful retrieval, successful parsing and validated numerical coverage are separate statuses. A 15-year request may return explicitly incomplete coverage; it is not a promised release-wide guarantee. Existing fixed-workload readiness checks remain, separately from library software readiness.

<a id="s2-3"></a>
### 2.3 Explicit backlog

- All RBI ingestion and macro workflows. Quarterly RBI data remains excluded if this module returns.
- Live quotes/options chains, tick/intraday acquisition, streaming, polling, and trading alerts.
- Continuous futures, IV/Greeks, volatility surfaces, advanced derivatives valuation.
- Dividend total returns and rights/merger/demerger-aware return reconstruction; raw events remain included now.
- BSE, additional global markets, paid-vendor implementations, distributed/cloud/multi-tenant services.
- Broad TA-Lib replacement, portfolio/backtest engines, legacy function-name compatibility.

Terminal live progress is an interface feature, not live market data, and is included.

<a id="s18-2"></a>
### 18.2 Review amendment ownership — no phase renumbering

Fold these acceptance details into the existing slices; do not create a parallel platform project. No delivery estimate is adopted; measure source and storage work before estimating later implementation. Advanced backlog items add no current-release execution tasks. Acceptance identifiers below refine requirement contracts; the original 29 IDs remain and ETF-01 is the sole added top-level ID (30 total).

| Amendment | Existing owners | Required evidence |
|---|---|---|
| AM-01 Optional dated surveillance/band facts | ID-01, EQ-01, TIME-01; phases 02,05,07,16 | Source/coverage report, additive table, overlapping regimes, historical unknowns, price-only plans unchanged |
| AM-02 Shared validation and versioned anomaly decisions | API-01, QA-01, RES-01; phases 04,07,16,19,22 | Same outcomes through builder/ad-hoc paths; genuine crash retained; hard violation scoped; later resolution cannot leak |
| AM-03 Evidence-backed session grids | ID-01, TIME-01; phases 05,16,17 | Special/closed/unknown sessions distinguished; calendar corrections preserve prior snapshots |
| AM-04 Quarantine/replay and dependency isolation | BUILD-02, NET-02, STORE-01; phases 03,04,09,18 | Poisoned partition blocks dependants, independent work completes, replay is idempotent |
| AM-05 Safe local store and independent snapshot readers | STORE-01/02; phases 04,18,21,22 | Two reader processes remain pinned during writer refresh; partial snapshot invisible; path diagnostics and verified restore |
| AM-06 Recipe identity and recursive invalidation | RES-02/03, CORE-02; phases 16–19 | Cache isolation by policy/input/recipe; EMA/RSI/MACD correction matches complete recomputation |
| AM-07 Layout and resource budgets; compact observability | QA-01, STORE-02; phases 04,18,22 | Two query-shape benchmarks, bounded summaries/memory/spill, disk-full recovery |
| AM-08 Additive compatibility | CORE-01/02, STORE-01, API-01, DOC-01; phases 04,18,19,22 | Old configs/views/types/snapshots readable; absent metadata stays unknown; new policies produce new outputs |

Accepted readiness-review work and the current source/version decisions:

| Acceptance ID | Owner requirements / phases | Required closing evidence |
|---|---|---|
| R2 Commit and acknowledgement | STORE-01, BUILD-02, QA-01 / 04,09,22 | Pre-commit rollback, committed-but-ack-lost discovery, post-ack durability, duplicate-free retry |
| R3 Assertion lifecycle | STORE-01, TIME-01, RES-03 / 04,13,16,18 | Unchanged poll versus A → B → A, withdrawal/reinstatement, old snapshots intact |
| R4 Additive financial derivation | FUND-01, RES-02 / 04,13,17 | Instant/duration/additivity dictionary; valid revenue difference, rejected EPS/ratio/balance subtraction |
| R5 Cross-filing fact selection | FUND-01, TIME-01, RES-01 / 13,16 | Original/restated comparative and latest reporting period selected independently without duplicate panel rows |
| R6 Dated listing/series selection | ID-01, EQ-01, RES-01 / 05,07,16 | EQ → BE → EQ continuity/exclusion, BL collision, one instrument/decision row |
| R7 Full derivative terms history | ID-01, DER-01 / 05,10 | Dated strike/expiry/lot/settlement, evidenced or unresolved continuity, original EOD terms retained |
| R8 Research dependency bridge | BUILD-01, STORE-02, RES-01 / 04,09,16 | History-bundle versus resolved-result semantics; warmup/prior-filing gaps → explicit acquisition → new snapshot |
| R9 Partition completeness | CORE-02, STORE-01, BUILD-02 / 02,04,09 | Scope/field-aware coverage, failed/mutating pagination, poisoned row isolation, no false completeness |
| R10 Portable approved baseline | CORE-01, DOC-01 / 00 | Versioned multi-file specification hashes, intentional Git baseline, fresh-checkout resolution, historical alternatives marked |
| AM-09 Concrete capability targets | CORE-02, FUND-01, OWN-01, QA-01 / 02,13,14,22 | Named concepts/categories/bases/test intervals and software/data statuses; no silent requirement closure |
| AM-10 Durability/replay levels | STORE-01/02, RES-03, QA-01 / 04,18,22 | Platform publication protocol, process versus power-loss scope, artifact/logical/byte-rebuild distinctions |
| AM-11 Result lifecycle | API-01, UX-02 / 19,21 | Repeat materialize/iterate, disposed contexts, cancel/close query and worker cleanup |
| AM-12 Python/runtime and lean resume | CORE-01, QA-01, DOC-01 / 00,01,22 | Selective context and STATE resume; CPython 3.14 patch/build and core/extras platform matrix |
| AM-13 Yahoo EOD replacement | GLOB-01, NET-01, STORE-02, TIME-01 / 01,02,15,18,22 | Both symbol mappings, SDK isolation/options/captures, no unfinished bars, honest timing/coverage and offline replay |
| AM-14 Structured filings | NET-02, FUND-01, OWN-01, TIME-01 / 01–04,13,14,18,22 | Content-based dispatch, closed taxonomy packages, four statement families, contexts/units/lineage and progressive real-source coverage |
| AM-15 ETFs | ETF-01, ID-01 / 02,05,07,19,22 | Dated catalogue/metadata/EOD, fund-unit semantics, unknown classifications and no NAV/index substitution |
| AM-16 Discovery and EOD aggregation | ID-01, RES-02, API-01 / 02,05,17,19–22 | Ambiguous/stale local search, calendar-aware weekly/monthly bars, gaps/availability and correction recomputation |
| AM-17 Extraction and fact inspection | API-01, STORE-02, CORE-02, RES-03 / 01,04,09,18–22 | Same facts/diagnostics across sinks, no DuckDB store in direct mode, offline local parsing/trace, atomic bundles and honest replay limits |

R1 is intentionally absent from execution acceptance by owner direction. FRED-specific notice work is superseded with the removed provider. Preserve existing source attribution/use documentation. A structural documentation-checker pass does not close any mathematical, source-coverage or runtime gate above.

## Closing ownership

All 30 top-level requirements have release-closing owner Phase 22; contributor phases and their evidence are mapped in [the traceability table](verification.md#s19-1). R/AM contributor phases are listed above. Every phase closes its own outcomes and integration gate only. The register has no mutable status column; current phase states live in STATE. Phase 22 cannot mark a mandatory unsupported capability supported solely because software tests pass.
