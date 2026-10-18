# Product scope and research workloads

**Read when:** Scope changes, research workload selection, or deferred-feature questions. Ordinary implementation uses the active phase brief instead.

**Authority:** detailed product contract, revision 18 October 2026. Implementation and dataset support are not claimed. Progress belongs only in root STATE.

## Section lookup

- [1.1 First-release outcome](#s1-1)
- [1.2 Confirmed decision ledger](#s1-2)
- [1.3 Explicit architectural recommendations](#s1-3)
- [1.4 Evidence labels](#s1-4)
- [1.5 Review decisions and compatibility boundary](#s1-5)
- [4.1 Primary workload](#s4-1)
- [4.2 Research modes](#s4-2)
- [22.1 RBI macro backlog](#s22-1)
- [22.2 Live and advanced analytics backlog](#s22-2)
- [22.3 Reviewed advanced analytics and infrastructure backlog](#s22-3)

Read the selected section and its necessary dependencies; this lookup is not a full-file reading checklist. Original section numbers are retained as stable references.

<a id="s1"></a>
## 1. Product contract and settled decisions

<a id="s1-1"></a>
### 1.1 First-release outcome

A researcher declares a universe, dates, and datasets once. The library explains the work, obtains permitted source data, validates and stores it incrementally, and produces reproducible SQL/Polars research outputs. It also provides an approachable ad-hoc API, informative terminal output, and useful Jupyter displays.

The distinguishing feature is **trustworthy research with a pleasant daily workflow**: historical membership, dated identities, publication-aware joins, visible gaps, replayable builds, and traceable corrections are built into the same system as progress bars and charts.

This is a data and research-input library. Portfolio optimization, order execution, brokerage connectivity, trading signals, backtest engines, and investment-performance claims are outside this release.

<a id="s1-2"></a>
### 1.2 Confirmed decision ledger

| ID | Decision | Basis |
|---|---|---|
| D-01 | Build production code and public API names from scratch; do not copy/import/wrap the legacy NSE libraries. The explicitly selected `yfinance` dependency is a narrow exception for overseas index EOD acquisition only. | 20 September source choice; NSE clean-room boundary remains. Previously recorded endpoint leads are candidates only; no clone is needed in this workspace. |
| D-02 | Include historical equity, ETF, index, derivatives, financial, ownership, corporate-event, report, and global-index functionality below. | Latest request and scope answers. Source availability still requires verification. |
| D-03 | Defer all RBI macro ingestion and all live market data. | Latest request; supersedes the earlier weekly/fortnightly/monthly release scope. |
| D-04 | Include historical derivatives and standard indicators; defer continuous futures, option IV/Greeks, and dividend/rights/merger-aware returns. | Latest explicit answer. Preserve raw action/contract facts now. |
| D-05 | Allow public NSE/NSE Indices JSON/CSV/ZIP; official financial/ownership XBRL XML and genuine inline XBRL; verified legacy NSE financial-result HTML tables; the narrow Yahoo daily-history SDK path in [§5.6](sources.md#s5-6). | 26 September filing-format amendment. No general HTML scraping, PDF/OCR, browser/challenge bypass or live-data expansion. |
| D-06 | Geography: NSE plus Yahoo Finance S&P 500 (`^GSPC`) and Nasdaq Composite (`^IXIC`) EOD closes through `yfinance`. Other exchanges/regions remain pluggable. | Owner's 20 September replacement of FRED; no active FRED implementation or automatic fallback, no BSE implementation. |
| D-07 | Interactive notebook tables/charts on demand; lightweight automatic previews. Rich terminal experience is required. | Latest explicit answer. |
| D-08 | New consistent API, migration examples, optional pandas conversion. No legacy compatibility layer. | Latest explicit answer. |
| D-09 | uv, async HTTPX, msgspec, Polars/PyArrow, DuckDB; standard-library asyncio. Isolate yfinance's synchronous transport and pandas output inside an optional Yahoo adapter. | Core stack retained; SDK boundary is the explicit D-06 exception. |
| D-10 | DuckDB is canonical storage for persistent builds/research; direct extraction can return Arrow/Polars or publish CSV/Parquet without creating a DuckDB store. | 26 September output-mode amendment; both paths share schemas, validation and provenance. |
| D-11 | Pin this release to CPython **3.14.x**: `.python-version` = `3.14`, package `requires-python = ">=3.14,<3.15"`; record the exact tested patch/build in reproducibility manifests. | Owner's 20 September pin. No 3.12 baseline or automatic 3.15 promotion; changing the minor version requires a separate decision. |
| D-12 | Python and TOML configuration; no YAML user-config dependency. | Configuration contract; no YAML user-config dependency. |
| D-13 | Treat the supplied NIFTY 500 file as research input requiring correction and verification. | User corrected the earlier NIFTY 50 input and requested this workflow. |
| D-14 | Ten-year NIFTY 500 reference workload, local-first operation, no stated hardware/deadline constraint. | Prior discussion; fixed acceptance window below. |
| D-15 | Add NSE ETF catalogue, evidenced metadata and EOD history as ETF-01; commodity spot remains deferred. | Owner-selected scope after sibling-library review; no ETF substitution for index datasets. |
| D-16 | Add local instrument search and calendar-aware weekly/monthly aggregation from acquired EOD. | Reuse dated identity and pure analytics contracts; intraday/live remain deferred. |
| D-17 | Expose offline filing parsing and fact tracing through the same decoder/mapper/lineage used by acquisition. | Library usability and auditability; processing local input does not establish provider authenticity or historical availability. |

The scope decisions above are settled; the fresh-start workflow amendment is recorded in [design decisions](../DESIGN_DECISIONS.md). Parser selection, measured source coverage and runtime compatibility remain implementation evidence tasks; investigate them rather than invent answers.


<a id="s1-3"></a>
### 1.3 Explicit architectural recommendations

These are design recommendations, not claims that the user specified every implementation detail:

- **Click + Rich** for CLI; shared build events feed terminal and notebook renderers.
- **ipywidgets + Plotly** in an optional `notebook` extra. Use bounded, server-paged tables built from standard widgets and escaped HTML; no mandatory pandas-based grid.
- **mypy strict + Ruff**, pytest, Hypothesis, HTTPX mock transport, and a small opt-in network contract suite.
- **One owning process per writable DuckDB store**, concurrent downloads, bounded queues, serialized commits.
- **Immutable raw objects, versioned canonical facts, immutable research snapshots**; CSV exports include schema/provenance sidecars.
- **Readiness gates** distinguish download success from suitability for a requested research workflow.
- **One authorized phase goal at a time**, with sequential verified checkpoints and a single STATE record.

Numerical limits later in this document are configurable initial engineering budgets, not measured NSE limits or hardware promises.

<a id="s1-4"></a>
### 1.4 Evidence labels

| Label | Meaning |
|---|---|
| Verified—local | Directly inspected local input or code, with a file/function reference. |
| Verified—published | Supported by a linked primary-source document. |
| Design | A chosen contract for the new library, not an existing feature. |
| Candidate | An endpoint or capability needing current response verification. |
| Inference | A reasoned conclusion with insufficient evidence for verification. |

An endpoint in a clone does not prove it still works, supplies complete history, permits a particular request rate, or contains all required numerical fields.

<a id="s1-5"></a>
### 1.5 Review decisions and compatibility boundary

The review labels **[Adopt in Phase 1 - Core Integrity]**, **[Defer to Phase 2 - Advanced/ML Layer]**, and **[Reject - Anti-pattern/Over-engineering]** mean current-release work, later-release backlog, and declined proposals respectively. They do **not** renumber implementation phases 00–22. Adopt also includes retaining an already agreed requirement; it does not make every suggestion new scope.

Preserve the original 29 requirement IDs and bounded indicator catalog; add ETF-01 and the owner's dated amendments above. D-01/D-05/D-06/D-09/D-11, the global-provider examples and the derivative/financial selection contracts are intentionally clarified before implementation. Earlier FRED examples are superseded, not silently mapped to Yahoo identifiers. Historical derivatives and standard indicators remain in the first release. DuckDB stays canonical for persistent builds; direct extraction is the explicit D-10 exception. No new orchestration service, cloud filesystem, ML dependency or technical-indicator suite enters core. The later migration rules govern implemented/persisted contracts; they do not freeze erroneous pre-implementation pseudocode.

Additive schema changes use ordered migrations and nullable/defaulted metadata or companion tables. Existing configurations and selected output schemas keep their behavior; new optional datasets are absent unless selected. Never reinterpret a missing historical field as a verified negative. Version quality policies, recipes, manifests and layout metadata; old records lacking these additions remain readable with `unknown`/legacy provenance. Retain old policy execution for reproducibility or explicitly report an unavailable replay dependency. Changes to accepted values, exclusions or formulas require a new policy/recipe identity and new snapshot, never in-place rewriting. Incompatible future changes require a versioned interface plus explicit migration and compatibility views; no destructive rename/drop or silent config upgrade.

Current-release additions concentrate on surveillance-state provenance, scoped validation/anomaly decisions, dependency-correct recomputation, and operational acceptance. Later-release analytics must first satisfy [§22.3](product.md#s22-3). Neither this architecture nor a chosen coding framework guarantees flawless data, ML validity, alpha, or regulatory certification.

<a id="s3"></a>
## 3. All ten blueprint improvements

The earlier blueprint informed the ten improvements below. This table preserves the actionable decisions; the historical blueprint is not a required implementation input.

| # | Suggestion | Implementation | Acceptance |
|---|---|---|---|
| 1 | msgspec models | Typed wire structs and separate canonical records | Invalid fields fail with context; raw retained |
| 2 | First-class Polars | Arrow batches, `to_polars()`, snapshot lazy scans | No pandas in core; copies measured |
| 3 | HTTPX async pooling | Scoped pooled clients, budgets, HTTP/2 negotiation | Limits hold; HTTP/1.1 fallback works |
| 4 | Rich CLI | Dataset progress, waits, hits, commit status, resume | Helpful display; clean machine output |
| 5 | Jupyter display | Summary cards, bounded previews, sparklines, explorer | Display triggers no network/SQL/full materialization |
| 6 | Fluent chaining | Immutable dates/dataset/adjustment/feature requests | No I/O until explicit `fetch()` |
| 7 | Typing | Public annotations/protocols, `py.typed` | Installed-wheel type checks pass |
| 8 | uv | Lockfile/groups/reproducible build | Frozen clean install passes |
| 9 | Ruff | Format/lint/import/correctness rules | Same local and CI checks |
| 10 | DataSource | Dataset-aware capabilities and fetch/normalize contracts | NSE/Yahoo/fixture providers share orchestration with declared acquisition boundaries |

**Design safeguards:** JSON-to-Arrow parsing allocates; zero-copy applies only at compatible boundaries. HTTP/2 is negotiated. Array-like structs do not decode arbitrary object-shaped NSE JSON. Benchmark speed claims. Join fundamentals by availability, not period end. A 20-observation rolling SQL window includes 19 preceding rows plus the current row. Do not copy blueprint snippets as production contracts.

<a id="s4"></a>
## 4. Reference research workflows

| Workflow | Value | Limitation | Decision |
|---|---|---|---|
| Ad-hoc workbench | History, fluent API, SQL, notebook exploration | Weak universe-correctness test | First tutorial/internal preview |
| Monthly NIFTY 500 panel | Identity, membership, availability, filings, reproducibility | Requires historical evidence | **Primary integration workload** |
| Daily research refresh | EOD, filings, corrections, gaps | Not a live feed | Operational acceptance; user/external scheduler invokes |
| Historical derivatives | Contract discovery, EOD, participant reports | No IV/Greeks/continuous series | Separate release workflow |
| India/US context | Yahoo EOD index closes and cross-market timing | A bar date or exchange close is not evidence of when this exact value was disseminated | Include with timing/coverage labels |

<a id="s4-1"></a>
### 4.1 Primary workload

**Design:** Freeze the benchmark to `[2016-09-01, 2026-09-01)`. All date ranges are start-inclusive/end-exclusive. Earlier membership and feature-warmup inputs remain usable.

- Universe: NIFTY 500 membership effective at each decision time, including eligible delisted/renamed securities.
- Decision: first verified NSE session each month at **10:00 Asia/Kolkata**.
- Prices: completed prior sessions only. Features: 21/63/252-session returns, 21/63-session volatility, 20-session traded-value average, comparable index-relative returns.
- Financial/ownership: latest admissible comparable facts, publication age, ownership changes, explicit missingness.
- Global: S&P 500/Nasdaq closes and returns under the selected timing policy.
- Output: eligible instrument/decision rows, values, quality flags, version references, snapshot and recipe IDs.
- Keep eligible instruments without prices; distinguish non-membership from lack of priceability.
- Compile indicator warmup as visible extra dependencies; never fabricate a 252-session feature from a shorter history.

First prove a small independently verified interval. Attempt the full ten-year workload and publish its readiness map; certify only intervals with sufficient evidence. Measure Yahoo's actual coverage for the fixed window and earlier feature warmup; requesting `max` or a distant start date is not proof of complete history. The former FRED rolling-history constraint no longer defines this provider, but source gaps and missing historical revision/publication evidence still can block readiness.

<a id="s4-2"></a>
### 4.2 Research modes

- **Strict historical evidence:** admit only versions with evidence of public availability by decision time.
- **Locally observed:** admit only versions captured by this installation before the decision time.
- **Latest vintage:** retrospective use of latest stored versions, clearly labeled.
- Optional user-declared lag scenarios are **assumption-based research**, not verified point-in-time evidence.

Strict mode can be sparse. Explain why; never silently switch modes for completeness.

<a id="s22"></a>
## 22. Deferred modules: preserve context without building them

<a id="s22-1"></a>
### 22.1 RBI macro backlog

The entire RBI importer is deferred. No Excel dependency, macro DataPlan entry, macro phase, or macro acceptance requirement belongs in this release.

Retain the supplied `50 Macroeconomic Indicators.xlsx` (historical owner-held input, excluded from this project) and prior findings for future work:

- Local-file-first ingestion, because no current download URL was supplied.
- Weekly/Fortnightly/Monthly selected in the prior scope; Quarterly explicitly excluded.
- Prior recorded selected-sheet inventory (not reverified for this fresh project): 49 labeled series, 11,867 numeric observations and 479 missing markers; fixture-specific, not universal RBI format guarantees.
- Incorrect declared dimensions can omit the last populated column; verify real cell extents with a future importer.
- Separate CPI base-year variants and merger-basis ratio variants; do not infer original publication vintages from one workbook.

The source is preserved; no workbook modification is part of this plan. Quarterly **company financials and shareholding** remain in the current release; only RBI macro work is deferred.

<a id="s22-2"></a>
### 22.2 Live and advanced analytics backlog

Reuse future provider interfaces, canonical IDs, budgets and event streams when designing live acquisition, but add no live-specific service now. Historical EOD option-chain exploration is already included and must not grow into polling.

Continuous futures will need dated roll rules and explicit roll-return versus adjusted-price semantics. IV/Greeks will need model choice, rate/forward inputs, expiry clocks, solver domains and numerical tests. Advanced action returns will need a holdings/cashflow ledger and rights/merger assumptions. Deferring these avoids falsely presenting raw EOD data as a validated valuation/backtest engine.

<a id="s22-3"></a>
### 22.3 Reviewed advanced analytics and infrastructure backlog

These are **[Defer to Phase 2 - Advanced/ML Layer]**, not release promises. Add one only for a concrete research requirement with verified inputs, a versioned mathematical contract, independent fixtures and measured maintenance/compute cost. The existing standard catalog, rolling beta and drawdown remain first-release obligations.

| Later capability | Admission conditions and statistical boundary |
|---|---|
| Dividend/economic total returns | Separate cashflow/entitlement/reinvestment/basis contract, including ex/payment dates and unsupported actions; never relabel split/bonus price returns or mix them with TRI unnoticed |
| Broader TA indicators, including ATR; optional TA-Lib backend | Exact seeding/warmup/null conventions, numerical tolerance/parity fixtures, optional dependency/platform checks; no blanket clone or change to current formulas |
| Corwin–Schultz spread and Amihud illiquidity | Label estimates/proxies; specify action/overnight-jump/price-limit/sparse-trading treatment, true currency-turnover units, zero-denominator policy and minimum usable observations; no execution or institutional-flow claims |
| Global beta/correlation and cointegration expansion | Explicit information-time/return-interval alignment across markets, holidays/DST/lag evidence; no repeated foreign return treated as independent observations. Cointegration additionally needs trailing estimation, sample/structural-break diagnostics and multiple-testing controls |
| Cross-sectional z-scores and sector neutralization | Point-in-time universe and historical sector taxonomy, comparable bases, declared weights/sample minimum/zero dispersion, retained missing rows; fitted residualization is not proof of alpha |
| Idiosyncratic volatility, rolling maximum drawdown, recovery and expected shortfall | Trailing model/benchmark and degrees-of-freedom contracts; distinguish drawdown from maximum peak-to-trough drawdown. Future recovery times are censored labels, not as-of features; tail estimates disclose small samples and quantile conventions |
| Hurst estimates | Pin estimator, scale/window choice, minimum data and uncertainty checks; no deterministic trending/mean-reversion interpretation or automatic signal |
| HMM/regime probabilities | Version fitted model, training cutoff, refit schedule, seed and state mapping. Historical decisions use filtered probabilities with admissible inputs, never smoothing over future observations |
| PCA, scaling, imputation and fitted feature selection | Fit within each permitted training window/fold; persist fit artifacts and transform future data without refitting on it. No automatic PCA before dataset split; orthogonal components do not guarantee prediction or out-of-sample independence. [ML leakage guidance](https://scikit-learn.org/stable/common_pitfalls.html) |
| Forward-return/volatility-adjusted labels and tensor exports | Separate target namespace/type and label information interval from feature DAG; define horizon, entry basis, denominator timing, missing terminal prices and action treatment. Never feed targets into features. Temporal evaluation excludes overlapping training-label outcomes from validation where applicable; no current training/backtest engine |
| NLP/text documents | Reuse current announcement/filing metadata and availability evidence first. New content ingestion needs explicit format/data-use scope decisions; PDF/OCR and general narrative scraping remain deferred; scoped numerical filing extraction is now included under D-05 |
| Advanced drift/model monitoring, external orchestration, remote storage/lakehouse or serving feature store | Require measured need or explicit multiwriter/cloud/service scope; optional integrations invoke existing contracts. Prove storage atomicity/consistency/restore and reader compatibility before migration. No new service merely to satisfy an enterprise label |

Reject the proposed replacements and overbuilt extrapolations **now**: mandatory Iceberg/Delta, Dagster/Prefect, universal fsspec I/O, Z-ordering, broker DLQ/schema-registry servers, duplicated full lineage on each row, and a never-halt publication rule. Local validated partitions, referenced lineage and immutable snapshots address the present workload. Future integrations are separate decisions, not dormant core implementations.
