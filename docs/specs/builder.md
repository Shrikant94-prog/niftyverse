# Acquisition planning and incremental execution

**Read when:** DataPlan compilation, partition completeness, refresh, cancellation, resume, or research preflight.

**Authority:** detailed product contract, revision 18 October 2026. Implementation and dataset support are not claimed. Progress belongs only in root STATE.

## Section lookup

- [10.1 Compilation](#s10-1)
- [10.2 Execution and partition state](#s10-2)
- [10.3 Refresh and repair policies](#s10-3)
- [10.4 Quality/readiness report](#s10-4)

Read the selected section and its necessary dependencies; this lookup is not a full-file reading checklist. Original section numbers are retained as stable references.

<a id="s10"></a>
## 10. DataPlan compiler and incremental execution

<a id="s10-1"></a>
### 10.1 Compilation

1. Validate config version, keys, types, paths, date intervals, timezone and dataset filters.
2. Resolve local-file hashes, dated universe/identity/calendar inputs, provider capabilities and any mandatory blockers.
3. Expand dataset dependencies: delivery needs compatible equity keys; adjustments need actions; research indicators need warmup; derivatives need contracts.
4. Choose source representations and output mode explicitly. Prefer suitable whole-market reports; select filing formats through the capability registry. A JSON-only default remains JSON-only unless the request enables filing formats. Validate direct-output destinations without opening a DuckDB store; persistent build/research requires a store.
5. Partition work by provider-supported window, trading session/report generation and instrument/contract filters.
6. Compare expected partitions with committed coverage and requested refresh/reconciliation policy.
7. Produce a deterministic dependency graph, job fingerprints, bounded request estimates, unresolved estimates, and a dry-run report.

Compilation is local by default. An explicit discovery step may contact sources when capabilities/contracts are missing. `explain()` must show that discovery is needed rather than silently performing network I/O.

**Research dependency bridge (R8):** `client.research.explain(research)` locally validates the pinned input snapshot and emits missing dependencies plus a proposed acquisition DataPlan. Expand the actual decision/session grid, feature warmup, preceding admissible filings, membership baseline/events, action factors and candidate revisions required by the chosen mode. Pre-entry security prices may supply warmup without making that security an index member before entry. A 252-session return needs its two intended endpoints and the declared intervening-session policy; do not equate 252 returns with 252 prices. The user explicitly executes the proposed acquisition, receives a new immutable `history_bundle` snapshot, and uses `research.with_input_snapshot(new_snapshot.id)`. A requested mandatory dependency blocks the research build; optional missing features retain rows with reasons. No hidden acquisition, snapshot mutation or automatic latest-only fallback.

Do not expand all NIFTY 500 options over ten years by default. Derivative requests require explicit underlying/type/date scope; expiry/strike discovery can expand only under declared limits. Present the estimated job count and a configured budget error before a runaway build.

<a id="s10-2"></a>
### 10.2 Execution and partition state

States: `planned → ready → fetching → staged → validating → committed`; alternatives `skipped_cached`, `retry_wait`, `deferred`, `blocked`, `quarantined`, `failed`, `cancelled`. Coverage is not a synonym for job state.

- Jobs publish only after all required pages/batches for their atomic partition are present and validated.
- Staging checkpoints can retain partial pages, but readers never see them as complete canonical data.
- A restart revalidates source/config/schema identity before resuming page tokens; expired/unstable tokens restart the partition safely.
- A repeated page/content hash or non-advancing cursor is a pagination error, not an infinite loop.
- Missing data and verified no-observation partitions use explicit coverage records with evidence.
- Idempotency distinguishes unchanged source checks from new evidenced assertion occurrences ([§7.1](data-model.md#s7-1)). Content can be reused across A → B → A without discarding the final revision or inventing revisions on unchanged polling.
- Persist plan hash, config schema version, source contract versions, code version, local-input hashes, and requested versus effective date ranges.

Quarantine is the local dead-letter mechanism: retain raw hash/locator, sanitized request, parser/rule versions, affected partition, issue and replay attempts in the existing jobs/quality tables. Do not add a message broker or schema-registry service. Continue independent DAG branches; block affected dependants and return non-success when a required partition fails. Do not publish the other 99% of an atomic partition as complete. A source-wide contract break stops that capability; disk/transaction failures stop publication. Replay a quarantined partition through the same validation and idempotent commit path after a versioned parser/rule fix; arbitrary casts or raw-row skipping are not repair.

**Partition contract (R9; Phase 02 evidence → Phase 04 definition → Phase 09 integration):** every dataset declares partition keys, requested universe/fields/basis, source generation and identity/quality policy; expected completeness evidence; validation scope; and overlap/supersession rules. Whole-market report ingestion normally validates a source report/session before a selected-universe projection; if a dataset supports smaller independently complete units, declare and test them. A selected subset cannot satisfy whole-market coverage. JSON supplements and report coverage reconcile at matching keys/fields/bases without double-counting.

For paginated catalogs, require a stable source snapshot/cursor or verified ordering/count/boundary reconciliation. Pagination exhaustion alone is not proof of a consistent complete set if the source changes mid-fetch. Record `completeness_unverified` when the provider cannot establish it; do not publish false complete coverage. Yahoo completeness likewise combines requested completed sessions, observed/null/missing rows and source limitations, not merely a nonempty SDK return. Acceptance includes a failed page, source mutation between pages, poisoned row, partial-universe cache reuse and an unrelated partition that still completes.

<a id="s10-3"></a>
### 10.3 Refresh and repair policies

Initial configurable design: recheck the last seven local sessions for NSE EOD datasets, last 14 publication days for filing catalogs where date filters are verified, and last 30 completed US sessions for Yahoo index EOD. These overlap windows reduce ordinary misses but do not guarantee discovery of older revisions or reconstruct historical public vintages.

Expose explicit `refresh`, `repair`, and wider `reconcile` operations. A build may also recheck older partitions according to a declared rotation policy. Never create an autonomous scheduler merely because the library supports refresh. Store last checked time separately from last fact change.

When a source corrects old data, preserve the old version, publish the corrected version, compute affected feature/adjustment/universe intervals, and mark dependent materializations stale. Recompute only affected dependencies. A historical split correction may affect all earlier adjusted prices for that security; a rolling feature also needs its forward influence window.

Dependency influence is not always a finite lookback: EMA, Wilder RSI, MACD and running peaks can propagate a correction through all later observations until an explicit reset/anchor. Recipes declare bounded-window, recursive-state or anchored dependencies; recursive checkpoints pin their input prefix and are invalidated after a relevant correction. Never truncate recomputation at the nominal window just because a recursive feature has a period parameter.

<a id="s10-4"></a>
### 10.4 Quality/readiness report

Report at least: requested/available dates, expected/observed sessions, identity coverage, missing values, unavailable fields, unverified universe intervals, timing evidence, stale observations, provisional reports, unresolved corporate actions, parser/schema versions, quarantined partitions, and source access problems.

Required versus optional datasets are explicit in the plan. A required failure produces non-success status; optional partial coverage produces a visible warning and reason, never silently a successful complete result. Readiness is computed for the requested workflow, not as one opaque universal score.
