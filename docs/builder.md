# Explicit DataPlan acquisition

`DataPlan`, `DatasetRequest`, `Capability`, `compile_plan`, `build` and `extract`
are public Python entry points. Compilation is local; executing a graph is an
explicit acquisition action. No provider discovery, automatic latest selection
or historical membership assumption occurs during explain.

```python
from niftyverse import DataPlan, compile_plan, build

plan = DataPlan.from_toml("""
version = 1
start = 2026-10-14
end = 2026-10-17
universe = ["a-reviewed-listing-id"]
store = 'C:/local-data/niftyverse'
source_formats = ["json"]
workers = 2
queue_limit = 2
[[datasets]]
dataset = "equity_daily"
fields = ["close", "quantity"]
""")
# Capabilities, calendar and providers below are explicitly supplied local
# evidence/adapters, not objects discovered or created by this example.
graph = compile_plan(plan, capabilities, calendar=calendar)
print(graph.explain())
result = await build(graph, providers, on_event=print)
```

Equivalent mappings use `DataPlan.from_mapping`. Dates accept Python `date`
objects or ISO strings. Unknown keys, unsupported fields/formats, invalid paths,
missing persistent store and resource overruns reject before acquisition.
Intervals have exclusive ends. Session partitions use an explicitly evidenced
Calendar; unknown dates block, while evidenced closed dates generate no work.
The early expansion guard conservatively budgets calendar days, including
unknown days. Explain separates base requests, retry upper bound and unresolved
capabilities. No HTTP calls or store creation occur in compilation.

The provider mapping is source ID to an object implementing the
`niftyverse.execution.Provider` protocol. `acquire(job, attempt=..., offline=...)`
returns `Acquired(ValidatedBatch(...))`; the existing adapters and normalizers
produce these batches. Provider implementations must enforce the capability's
per-job request limit, source-format policy, capture/batch size and shared
transport budgets. Retryable/deferred/source-wide errors use sanitized
`AcquisitionFailure` codes. A declared offline-capable provider may read local
inputs only; other providers are never invoked offline. This is a protocol
boundary, not an OS network sandbox.

Paginated complete batches require bounded, advancing, distinct page evidence,
source counts and a stable snapshot or explicit verified boundary/count
reconciliation. Exhaustion alone does not prove completeness. Partitions with
failed/mutating pages remain incomplete; poisoned partitions are isolated.
Whole-market validation must happen in the source adapter before projection.
Neither the builder nor a synthetic test establishes new provider support.

`DatasetRequest.required=False` retains visible optional warnings; required
failures block dependent work and yield non-success. Delivery details expand
compatible equity dependencies. Membership-dependent requests need explicit
verified scope/date evidence in `compile_plan(..., membership_coverage=...)`;
unrelated fixed-universe requests continue. Evidence tuples are supplied by the
caller after membership verification, never inferred from a scope name.

Persistent cancellation returns a run ID when cooperative cancellation is used.
Resume with `await build(graph, providers, resume=result.run_id)` using compatible
config, source contracts, code and local inputs. Abrupt interruption can be
discovered in `build_runs`; canonical committed coverage is reconciled before
rerunning missing units, regardless of the last progress event. Each incomplete
atomic partition restarts safely; no durable page-token continuation is promised.
Unchanged builds reuse only exact committed partitions with matching policies,
parser/schema and history semantics. Direct extraction does not consume a
persistent cache without explicitly supplied replay inputs.

Use `dataclasses.replace(plan, operation="refresh", overlap_sessions=7)` to
recheck the last seven evidenced sessions within the requested range. Filing
publication-day or Yahoo completed-session policies require their later verified
dataset adapters and explicit appropriate grids; they are not silently treated
as NSE sessions. `operation="repair"` requires exact `repair_partitions` identities
from the graph. `operation="reconcile"` rechecks the full requested interval.
No operation expands dates silently. Corrected versions retain old assertions;
unchanged checks advance source-check time without inventing fact versions.
Future research materializations consume the existing immutable history and
correction lineage; this phase does not implement their feature recomputation.

For direct output set `mode="memory"` or `mode="files"`, omit `store`, and use
`extract`. Files require a new `destination`, CSV or Parquet `encoding`, and
optionally `retain_raw=False`. File jobs spool as bounded partition bundles;
the run completion manifest is published before committed events. Required
failures leave no destination by default. Explicit `allow_partial=True` retains
available validated data with partial status and failure reasons; partial units
never increment complete-partition progress. Memory retention and admitted batch
reservations are bounded. Direct results have no durable resume/snapshot ID;
retry means bounded re-extraction, not continuing a persistent revision catalog.

The frozen research bridge accepts explicit `ResearchDependency` grids for
warmup, prior filings, history, actions or membership. `research_preflight`
returns missing scopes and a proposed DataPlan. The researcher explicitly builds
it and repins the returned history snapshot. A resolved result cannot replace
the missing history. Future research phases compute actual decision grids,
admissible prior filings and warmup endpoints; this interface never invents them.

## Thin command line

```text
niftyverse explain --plan plan.toml --context context.json
niftyverse build --plan plan.toml --context context.json --input-bundle partition-1 --input-bundle partition-2 --json
niftyverse build --plan plan.toml --context context.json --input-bundle partition-1 --input-bundle partition-2 --resume RUN_ID --json
niftyverse extract --plan extraction.toml --context context.json --input-bundle partition-1 --json
```

The context JSON contains `capabilities` (a list of Capability field objects) and
optional `calendar` (a Calendar field object, including Session objects). ISO
dates/timestamps encode the corresponding Python records; no scripts execute.
The CLI currently provides explicit offline replay of individual typed partition
bundles produced by `write_direct`; it does not guess live source parameters.
Python callers supply live adapters explicitly through the provider protocol.
Replay requires retained raw captures and compatible typed/source/parser scope;
it validates the existing decoded facts rather than claiming source re-parsing.
Duplicate partition revisions require an explicit selection. Corruption, missing
raw and unavailable inputs stay visible. Plan/context/input manifests are hashed
as local inputs for checkpoint compatibility.

Progress on stderr is generated solely from executor events. `--json` puts only
the bounded status summary on stdout; incomplete required work exits nonzero.
Explain does not open the live catalog or inspect input bundles. For explicit
local-cache explain in Python, read `committed_cache(store)` in an owning Store
context and pass those entries to the compiler. The executor independently
rechecks actual committed state and never trusts caller cache hints as facts.

Source windows and historical membership retain the prerequisite phases'
declared limits. Process-crash publication guarantees and power-loss limits
remain those of [storage](specs/storage.md#s11-2); direct bundle completion never
certifies ten-year history or historical public vintages.
