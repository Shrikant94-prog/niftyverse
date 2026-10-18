# Verification and release scenarios

**Execution rule:** Apply [test-first verification](../WORKFLOW.md#test-first) to the relevant checks below. This document owns test coverage; WORKFLOW owns ordering, exceptions and evidence.

**Read when:** Selecting relevant tests or preparing the final integration/release gate. Do not run the complete release matrix after every change.

**Authority:** detailed product contract, revision 18 October 2026. Implementation and dataset support are not claimed. Progress belongs only in root STATE.

## Section lookup

- [16.1 Verification pyramid](#s16-1)
- [16.2 High-value invariants](#s16-2)
- [16.3 CI and release checks](#s16-3)
- [16.4 Observability](#s16-4)
- [16.4.1 Validation and anomaly decision rules](#s16-4-1)
- [16.5 Security and data-use boundaries](#s16-5)
- [16.6 Performance measurement](#s16-6)
- [16.7 Structured-filing and output-mode verification](#s16-7)
- [19.1 Requirement-to-phase map](#s19-1)
- [19.2 Cross-cutting release scenarios](#s19-2)
- [19.3 Additional integrity scenarios from the review](#s19-3)
- [19.4 Accepted readiness-review and Yahoo scenarios](#s19-4)
- [20.1 What carries forward](#s20-1)
- [20.2 Required documentation set](#s20-2)

Read the selected section and its necessary dependencies; this lookup is not a full-file reading checklist. Original section numbers are retained as stable references.

<a id="s16"></a>
## 16. Quality, observability, security, and performance

<a id="s16-1"></a>
### 16.1 Verification pyramid

| Layer | Required cases | Execution policy |
|---|---|---|
| Pure unit tests | Config, time precision, decimals, IDs, formulas, error mapping | Fast, no network |
| Property tests | Idempotent publication, interval operations, adjustment invariants, pagination monotonicity | Deterministic seeds retained for failures |
| Adapter contracts | Independently captured/synthetic JSON/CSV generations and malformed responses | Offline by default; originals only when storage/redistribution is permitted |
| Storage integration | Atomic facts+coverage, staged visibility, schema migration, export round-trip | Temporary stores with real DuckDB |
| Recovery tests | Kill before/after raw publish, transaction failure, disk full, cancellation, lock contention | Assert exact recoverable state, not merely no exception |
| Research integration | Revised filing, future action, timezone/date-only timing, missing dead-company price | Assert no look-ahead and no silent universe shrinkage |
| UX | Clean JSON, narrow terminal, escaped notebook HTML, widget cancellation, payload bounds | Offline fixtures and selected frontend smoke tests |
| End-to-end | Small DataPlan → build → research → snapshot → SQL/export → replay | Runs without internet from owned fixtures |
| Live contracts | Small permitted probes for current capability evidence | Opt-in, paced, timestamped, secrets redacted |

Behavioral gates outweigh a coverage percentage. Proposed baseline: at least 85% branch coverage for core implementation, with every critical temporal, retry, commit/recovery and identity decision branch represented by a meaningful test. Exclude generated migrations/third-party code only with documented justification. Do not game coverage with assertions that restate implementation.

<a id="s16-2"></a>
### 16.2 High-value invariants

1. Rebuilding unchanged inputs changes no canonical business facts.
2. A failed partition never claims complete coverage.
3. Every published fact has resolvable provenance; every pinned snapshot retains its dependencies.
4. A revised fact known later cannot enter an earlier strict decision.
5. Symbol reuse cannot merge different securities.
6. Missing prices cannot remove eligible universe rows.
7. Raw values remain unchanged by adjustment/feature computation.
8. Split factors preserve compatible price × share-volume products within representation tolerance.
9. CSV/Parquet exports reconstruct documented types/nulls and selected versions.
10. Displaying a result performs no I/O and cannot execute source-provided HTML.
11. Source throttling never produces an unbounded retry/task queue.
12. Offline replay produces the same canonical/derived values under pinned versions, or explicitly reports an unavailable dependency.
13. A genuine extreme move is retained; a later explanation cannot silently change an earlier historical eligibility decision.
14. Unknown surveillance or calendar coverage never becomes an assumed unrestricted state or a dropped universe member.
15. Recursive indicator corrections propagate through the declared state dependency; nominal lookback is not an invalidation cutoff.

<a id="s16-3"></a>
### 16.3 CI and release checks

- On changes: Ruff format/check, strict type checking, unit/property/integration tests, package build and clean-wheel imports.
- Python 3.14 Windows/Linux behavior lanes and macOS smoke lane. Notebook, pandas-conversion and Yahoo extras are tested separately from minimal core, with the exact interpreter patch/build and dependency lock recorded.
- Offline CI by default. Network smoke tests are manually enabled or separately scheduled with bounded budgets; a provider outage must not be disguised as a package regression.
- Dependency lock update workflow reruns compatibility, exports, decimals, SQL schemas, notebook renders and golden data tests.
- Minimal-install tests assert there is no accidental import of pandas, Jupyter, Plotly, yfinance or legacy wrappers. The separate Yahoo lane verifies the SDK's transitive dependencies and adapter boundary; offline replay of a Yahoo capture works without importing the SDK.
- Check documentation commands, TOML examples, public symbols, type information and CLI help against the installed wheel.
- Schema/API changes require migration or explicit versioned behavior; no silent persisted-contract break.

<a id="s16-4"></a>
### 16.4 Observability

Use standard logging with a `NullHandler` at library level; applications control handlers. Structured events carry build/job/partition IDs, source, dataset, attempt, elapsed time, rows/bytes, cache state, schema version and quality codes. Redact secrets before both logs and durable metadata.

Persist compact build events and final reports. Offer in-process counters/histograms for request latency, status, backoff, cache hit, queue occupancy, parse/validation/commit duration, data freshness and coverage. An optional future metrics exporter must not become a core server requirement. UI derives from these events rather than scraping logs.

Distinguish **source freshness**, **last successful collection**, and **research admissibility**. Configure dataset-specific stale thresholds; do not label all daily series stale on holidays. Diagnostics should answer: what is missing, why, when it was last checked, and what can be done next.

Persist bounded per-partition summaries for row/duplicate counts, null fractions, value ranges, units and selected robust distribution statistics. Compare like segment/series/basis/calendar populations and distinguish membership changes from provider-semantic drift. Alert through existing quality events/reports; no monitoring server or model-drift platform is required. Missing baseline or too few admissible observations means insufficient evidence, not a passed drift test. Distribution change is a prompt to investigate, not proof of corruption or authority to rescale values.

<a id="s16-4-1"></a>
### 16.4.1 Validation and anomaly decision rules

| Rule class | Default action | Evidence and boundary |
|---|---|---|
| Deterministic contract failure | Quarantine affected atomic partition; stop its dependants | Missing critical fields, impossible source-defined OHLC/units, invalid keys, nonfinite required values; preserve raw and exact rule/version |
| Material reconciliation conflict | Retain competing evidence; quarantine or block the affected requested field/partition under an explicit rule | Confirm comparable source basis first; no provider-majority vote or silent preference |
| Statistical anomaly | Preserve plausible source facts with a warning and review status | Extreme returns/volume, unusual gaps or distribution shifts alone do not prove error |
| Evidence-backed correction/override | Append a reviewed resolution/correction, then revalidate and create new versions | Record evidence, reviewer, known-at time, original values and affected dependencies; never overwrite raw or old snapshots |

No universal 3-sigma, 90% or 95% price-change cutoff defines validity. Rule thresholds/baselines are dataset-specific, versioned and computed from admissible prior observations where used historically; corporate actions, series/unit changes and calendar gaps are explanatory evidence, not inferred repairs. Bound statistical work to selected fields and trailing summaries. A researcher may opt into a stricter anomaly exclusion policy, but exclusions produce reason-coded nulls on retained eligible rows and report sample impact. No default clipping, winsorization, forward-fill, split inference or deletion of crash/delisting observations. This policy separates canonical conformance, statistical suspicion and workflow readiness.

<a id="s16-5"></a>
### 16.5 Security and data-use boundaries

Validate remote hosts/redirects, archive bounds, local path handling, secret redaction and notebook escaping. Sanitize fixture captures. Disable unnecessary DuckDB external query capabilities in the ad-hoc reader. Explicit plugin imports are trusted local code, not sandboxed extensions.

Retain source attribution and usage/redistribution notes in capability metadata. Public accessibility does not itself establish redistribution rights. Do not publish raw provider captures, bundled datasets, packages, or websites as part of implementation without a separate release decision. The audit trail supports reproducibility; do not call it certified regulatory compliance or independent tamper proofing.

<a id="s16-6"></a>
### 16.6 Performance measurement

Separate network-bound and local-compute measurements. Record machine, OS, interpreter, dependency versions, storage medium, fixture size, cache state and concurrency settings.

Benchmarks: decode and normalize 1 million synthetic EOD rows; Arrow→DuckDB ingest; warm/cold filtered SQL; Parquet scan/export; million-row indicator computation; incremental no-change build; prepared notebook preview; memory during bounded backpressure. Include realistic nulls, revisions, strings and decimals.

Budget total process memory, temporary/spill disk, raw retention, snapshots and restore headroom in addition to the existing DuckDB limit. Explain estimates and check available disk before large writes; estimates do not replace bounded streaming or disk-full recovery. A fixed 500-security × 252-session × 10-year panel is roughly 1.26 million rows before revisions/features, a sizing illustration rather than actual historical coverage. Derivative contracts can dominate scale and retain separate request/partition limits. No 128 GiB machine, lakehouse or distributed execution is justified by that equity-panel estimate alone.

Establish measured baselines in phase 1/4 and update after justified architectural changes. Proposed regression gate on a stable benchmark runner: investigate >30% median latency or peak-memory regression across repeated samples. Do not fail noisy shared CI from one measurement. Proposed UX target: prepared static preview under 100ms on the recorded development machine; verify, report actuals, and tune payloads.

No speed multiplier against legacy wrappers is claimed. There is no provider SLA or guaranteed complete historical coverage. Local reliability goals are concrete instead: atomic publication, bounded retries/memory, accurate status, reproducible snapshots, and tested recovery.

<a id="s16-7"></a>
### 16.7 Structured-filing and output-mode verification

Maintain a hashed local corpus index by source/family/taxonomy/sector/basis/statement with independently checked expected facts and a held-out set; raw provider captures are not committed or redistributed automatically. Include prefix changes, dimensional and comparative contexts, typed dimensions, decimals/precision versus scale, nil/zero/missing, unit conversions, duplicate conflicts, revisions, inline transformations/continuations and HTML spans/template drift. Unknown/unavailable cases must remain visible. Real-source cases certify only their tested families; synthetic cases prove failure/edge handling.

Test minimum core without filing/Yahoo imports, then separate exact Python 3.14 optional-extra lanes. Decode offline with a closed taxonomy package and assert no DNS/HTTP/file escape. Test cancellation and resource ceilings. Compare canonical values, schema, provenance and failure status across DB/memory/CSV/Parquet; test direct export without a store, completion-marker failures and raw-retention limits. Broaden coverage during phases 13/14 and consolidate it in 22; no invented 15-year success criterion.

<a id="s19"></a>
## 19. Traceability and integration gates

<a id="s19-1"></a>
### 19.1 Requirement-to-phase map

| Requirement group | Primary phases | Final evidence |
|---|---|---|
| CORE-01 / CORE-02 | 00,01,02,09,19 | Installed wheel, capability protocol, type/config tests |
| NET-01 / NET-02 | 02,03,07,10,11 | Fault budgets, archive safety, independent source contracts |
| STORE-01 / STORE-02 | 04,18,22 | Atomic publication, snapshots, restore/replay, export round-trip |
| ID-01 / UNI-01 / UNI-02 | 05,06,10,16 | Alias/contract cases, supplied-file audit, verified intervals |
| EQ-01 / ETF-01 / IDX-01 | 02,05,07,08 | Historical price/report contracts, dated ETF metadata and coverage |
| DER-01 / REP-01 / REP-02 | 10,11 | Contract/report unit and generation tests |
| CORP-01 / FUND-01 / OWN-01 | 12,13,14 | Typed action/filing/ownership facts and limits |
| GLOB-01 | 01,02,15,18 | Both Yahoo index mappings, SDK isolation/options, completed sessions, actual history/timing and captured-result replay |
| BUILD-01 / BUILD-02 | 09,18 | Incremental/resume/refresh/repair and failure status |
| TIME-01 / RES-01 / RES-02 / RES-03 | 16,17,18 | Temporal panel, formula fixtures, correction propagation |
| API-01 / UX-01 / UX-02 | 01,09,19,20,21 | Real end-to-end APIs and reviewed terminal/notebook outputs |
| QA-01 / DOC-01 | Every phase; consolidation 22 | Verification logs, executable docs, readiness report |

<a id="s19-2"></a>
### 19.2 Cross-cutting release scenarios

1. **New researcher:** install core, initialize a tiny plan, explain it, build a supported interval, see quality warnings, query/export it without learning internal schema names first.
2. **Existing store:** rerun unchanged plan, refresh recent corrections, cancel mid-download and resume without duplicate facts or missing committed data.
3. **Bad universe:** load the supplied NIFTY 500 file, receive exact structural/evidence problems, review a correction, publish only verified intervals, and preserve the original.
4. **Dead security:** include a locally identified delisted security; retrieve available history without a current quote; keep missing history in the panel with reasons.
5. **Revised filing:** an old decision sees the original admissible filing, a later decision sees its revision, latest-vintage mode sees current values, and all three are reproducible.
6. **Archive transition:** load equivalent records from supported pre/post-format generations; preserve their units/keys and surface disagreement.
7. **Derivatives:** select a bounded expiry universe, inspect stored EOD contracts/chain and participant reports, and see missing multiplier/strike coverage explicitly.
8. **Notebook scale:** display a large result instantly from a bounded preview, filter the full snapshot on demand, cancel a slow query, and export selected results.
9. **Offline reproduction:** disconnect the network and reproduce a pinned research snapshot; a missing raw/parser dependency produces a clear replay limitation.
10. **Recovery:** simulate a crash/disk failure and restore a verified backup; canonical facts, lineage, coverage and snapshot hashes agree afterward.

Additional release scenarios: a saved filing parses offline and traces a number to its unit/context/period; the same bounded request yields equivalent validated DB/CSV/Parquet facts without creating a store for direct output; an unsupported document family remains explicit; ETF search ambiguity is preserved; weekly/monthly EOD bars disclose gaps and become available only after their inputs. These scenarios exercise AM-14–AM-17 without adding live, PDF or universal-history claims.

<a id="s19-3"></a>
### 19.3 Additional integrity scenarios from the review

1. **Extreme but valid move:** preserve a source-consistent crash and a verified split as distinct cases; quarantine a deterministic invalid price row at its declared partition boundary. An optional anomaly exclusion keeps the eligible row with a reason, and a later explanation does not backdate knowledge.
2. **Regulatory uncertainty:** overlapping ASM/GSM/other state facts and dated bands select by admissible evidence; a current list cannot populate old dates. A band-touch row with nonzero volume remains unchanged; missing state is unknown. Price-only requests still work, while an explicitly state-required workflow reports blocked coverage.
3. **Calendar and schema changes:** holiday/special-session/unknown-session fixtures give distinct outcomes. An altered required JSON key quarantines a partition and leaves its coverage incomplete; an extra noncritical key does not. A new parser replays retained raw bytes without duplicate facts.
4. **Concurrent readers and publication:** two independent notebook-like readers remain on immutable snapshot A during a writer update and snapshot B export. Crash before B's completion manifest leaves A readable and B unpublished. No external reader opens the live catalog.
5. **Feature reproducibility:** changing raw input, action/calendar/quality policy or recipe invalidates only the declared dependencies. Identical filing fact versions at different decision instants produce the appropriate distinct ages/staleness outcomes without an incorrect cache hit. A recursive indicator correction beyond its nominal window matches full recomputation; old snapshots reproduce or identify a missing pinned implementation.
6. **Compatibility and API equivalence:** previous config/API examples, canonical keys/columns and SQL views retain meaning after an additive migration. Builder/ad-hoc/cache paths report equivalent validation; external dataframe/SQL transformations cannot manufacture verified provenance. Requested output schemas do not expand silently.

<a id="s19-4"></a>
### 19.4 Accepted readiness-review and Yahoo scenarios

1. **R2/R3 publication lifecycle:** pre-commit failure publishes nothing; lost acknowledgement and post-ack failure retain committed facts/coverage. Repeated polling differs from A → B → A; withdrawal/reinstatement affects only admissible selections and leaves earlier snapshots reproducible.
2. **R4/R5 financial correctness:** compatible additive revenue derives a quarter; EPS/ratio/instant balances reject generic subtraction. A later restated Q1 comparative changes Q1 only when admissible, with Q2 still the newest reporting period and one analytical fact per key.
3. **R6/R7 dated identities:** EQ → BE → EQ plus BL observations follow the configured series policy; derivative strike/lot/expiry changes preserve both sessions' actual terms and evidenced continuity. No cross-series duplicate output or historical term overwrite.
4. **R8/R9 dependencies/completeness:** missing pre-window prices, prior filings or candidate revisions are visible in local research preflight. Explicit acquisition yields a new history bundle; the old snapshot remains unchanged. Partial scopes, failed pages and moving catalogs cannot satisfy unproven complete coverage.
5. **R10/AM-12 reproducible project setup:** a fresh project checkout resolves its versioned multi-file specification baseline/hashes, all registered requirements and amendment acceptance IDs; the interpreter minor is 3.14 and the runtime resumes from the single STATE record with selective document loading. Persisted state resumes without relying on unsupported runtime warnings.
6. **AM-13 Yahoo source boundary:** both canonical series resolve correctly; fixture assertions verify disabled adjustment/repair and Close selection, all-null/error classification, holiday/DST/early-close behavior and unfinished-bar exclusion. Deadlines/cancellation leave no active worker or complete coverage from partial work. Capture replay without yfinance yields the same canonical values while clearly retaining SDK provenance and unknown historical availability.
7. **AM-10/11 artifact and UI lifecycle:** stored-byte verification and logical recomputation have distinct outcomes; floating tolerances and output ordering are explicit. Materialize then iterate the same query without exhaustion; close/cancel the explorer during a query and prove connections/workers are released and stale callbacks discarded.

<a id="s20"></a>
## 20. Clean-room migration and documentation

<a id="s20-1"></a>
### 20.1 What carries forward

**No legacy NSE code, function names, implementation formulas, wrapper dependencies or copied test suites.** The earlier repository audit supplies endpoint leads only. The owner's selected yfinance dependency is the sole scoped overseas-acquisition exception; do not copy its implementation or expose its public API as this package's API. Core orchestration/storage/research and all NSE adapters remain independently implemented.

| Existing user need | New implementation | Migration material |
|---|---|---|
| Download historical stock data | DataPlan or immutable equity request | New API example, date-boundary and series explanation |
| Obtain index prices/valuations/TRI | Typed index datasets | Variant selection and comparable-return tutorial |
| Fetch historical F&O | Contracts plus EOD dataset | Expiry/strike/unit examples and bounded request planning |
| Download reports | Official report registry and adapters | Schema-generation/coverage guide |
| Inspect results/shareholding | Filing catalogues plus verified JSON/XBRL/inline-XBRL facts and scoped legacy financial HTML | Four statement families, context/unit mapping and measured coverage |
| Process a saved filing or save without a database | Shared local parsing and direct Arrow/Polars/CSV/Parquet extraction | Output manifests, partial/error status and replay limits |
| Discover ETFs and inspect EOD periods | Dated local catalogue search, ETF EOD and weekly/monthly recipes | Ambiguity, fund units, calendars and availability |
| Adjust prices/calculate indicators | Versioned split/bonus and feature modules | Formula/warmup/action-limitation guide |
| Work with pandas | Optional conversion from canonical result | Nullable/decimal/timezone conversion notes |
| Cache data for research | Durable store/snapshot workflow | Incremental builds, corrections and replay |

Write task-to-task migration examples rather than aliases or line-by-line ports. The new package must install and function when all legacy clones are absent. Dependency/import checks enforce this boundary.

<a id="s20-2"></a>
### 20.2 Required documentation set

- Ten-minute offline tutorial and small online quickstart with source limitations.
- DataPlan/TOML cookbook, CLI help and notebook workbench.
- Financial/ownership coverage guide and data dictionary.
- NIFTY 500 verification/correction tutorial and delisted-security manifest format.
- Historical derivatives and reports tutorial; no advanced-model promises.
- Point-in-time versus locally observed versus latest-vintage guide with one worked revision example.
- Split/bonus adjustment and indicator conventions, missingness and staleness.
- SQL/Arrow/Polars/pandas/export guide with result lifecycle and memory boundaries.
- Recovery, backup, schema upgrade, source blocking, diagnostics and offline replay runbooks.
- Source contract/coverage report, contribution standards, performance methodology, dependency/platform matrix and release notes.
- Financial concept additivity/cross-filing selection, assertion lifecycle, listing policy and full derivative-term history with executable edge cases.
- Research preflight/acquisition/history-bundle workflow; distinguish stored-artifact verification, logical recomputation and byte-identical regeneration.
- Yahoo optional-extra setup, canonical-symbol mapping, completed-session rule, source attribution/use notes, SDK capture/replay boundary and timing/coverage limits; no FRED-key instructions.

Required additions to the documentation set: filing-format/taxonomy support matrix, statement and ownership dictionaries, independently checked corpus procedure, local parsing and fact-trace tutorial, direct extraction/file-manifest guide, ETF identity/units, instrument search and weekly/monthly EOD semantics. State measured coverage by family/period/field and explain why no universal 15-year guarantee follows from a working parser.
