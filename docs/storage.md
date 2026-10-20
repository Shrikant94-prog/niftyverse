# Durable local publication

Phase 04 provides bounded validated partitions, a single-owner catalog and
immutable bundles. It does not implement provider acquisition, economic filing
mapping, the full DataPlan builder or the Phase 16 research engine. Synthetic
examples prove storage behavior, not market-source support.

`niftyverse doctor [--store PATH]` prints resolved paths without opening a store.
`Store()` uses platformdirs' non-roaming local application-data directory.
The catalog, WAL, OS writer lock, content-addressed raw objects, staging,
spill, backups and temporary exports all reside beneath that root. Explicit
paths remain accepted; potential sync/network locations emit an unsupported
location warning. Detection is best-effort, not a corruption prediction.
No files move automatically. Live stores in OneDrive/network folders are outside
the supported deployment; immutable completed artifacts can be copied there.

`niftyverse.batches` defines a shared bounded partition/capture/batch contract.
Partition identity includes dataset, half-open dates, selected/whole-market
scope, universe, fields, basis, source generation and identity/quality policies.
Completeness needs source evidence; a projected subset cannot satisfy another
scope. Limits are 100,000 typed rows and 64 MiB per batch/capture. Larger work
must declare smaller independently complete partitions; these limits do not
authorize publishing partial pages as complete.

Price/ETF tables use decimal128(38,8), date32, stable listing/series keys and
explicit shares/fund-unit semantics. Values outside that decimal contract must
fail normalization, never round silently. Source financial assertions preserve
qualified concepts, lexical values, raw text, nil, precision, units, periods,
typed dimensions, context XML and locators independently of mapped economic
values. Analytical keys include entity, concept, exact period, basis, scope,
unit and dimensions. Additivity is explicit: instant/nonadditive facts cannot
be subtracted. Actual financial derivation remains a later-phase concern.

Captures distinguish original direct bytes from SDK-result bytes, retaining
SDK identity where declared; a cast never upgrades SDK evidence to wire bytes.
Content objects, capture envelopes, assertion occurrences and source checks
have separate identities. Withdrawal is evidenced state with a reason, not
inferred absence. Schema migrations run only on explicit store open, under
the writer lock, with a checkpointed pre-migration database backup and a
transaction per additive version. Version 3 adds optional market-state observations;
version 4 adds supplemental security EOD/delivery details while retaining the
existing price-table layout. Both preserve retained old backups and rollback
failed migrations. [Equity output semantics](equities.md#shared-output-boundary)
describe the added fields and shared validation. Version 2 adds nullable SDK metadata; old
unknowns remain null. Downgrades/newer unsupported versions fail. Fixture-v1
artifacts/API remain readable through their original reader.

Version 5 adds separate index price/volatility, TRI and valuation tables through
the same publication boundary. [Index semantics](indices.md) describe variant
scope, units and null reasons. Migration rollback and retained pre-v5 backups
remain supported; new physical backups report the actual catalog schema version.

Only the owning process/thread uses a writable connection. All mutation APIs
are synchronous and serialized by that owner; independent readers use immutable
snapshots or wait until it closes. Lock contention fails within a bounded wait
with a diagnostic. Importing the modules performs no I/O.

`publish(store, validated_batch)` first fsyncs a verified immutable raw object,
then a same-filesystem Arrow staging checkpoint. It commits typed facts,
occurrence/capture lineage, source check, coverage and committed job status in
one transaction. Progress callbacks run after commit. A stable check ID can be
retried after acknowledgement loss without inserting duplicate versions.
Changed input/config/schema under that ID fails and requires an explicit new
check. Unchanged polling adds only a check/coverage observation; A-B-A and
withdrawal/reinstatement retain separate occurrence IDs. Tied or backdated
conflicting occurrence evidence is rejected for explicit reconciliation.

`recover(store)` reports orphan/missing/corrupt raw objects, unfinished jobs and
staging directories. It never deletes or silently repairs them. Publication
stops on missing/corrupt committed references. Quarantined or partial partitions
retain raw/staged evidence and job diagnostics without publishing facts or
complete coverage. Corrected replay uses a new check/parser identity and the
same validator; independent partitions may proceed. DAG dependency blocking
belongs to the later full builder.

The tested protocol covers abrupt **process termination** and Python
cancellation/disk-full failures. Raw files are flushed/fsynced before references
commit; POSIX additionally fsyncs publication directories. Windows file fsync
and same-filesystem rename have process-crash tests; a complete Windows
directory-metadata/power-loss protocol is **not** certified. No platform has a
simulated hardware power-loss guarantee here. DuckDB supplies its transactional
WAL; filesystem/device caching may limit OS/power-loss durability. Disk loss
requires a verified off-device backup; a same-disk backup is insufficient.

`history_bundle(store, label, recipe=..., policy=...)` streams one consistent
committed view to typed Zstandard Parquet and retains all candidate occurrences,
coverage, checks and capture references, including quarantine diagnostics/raw.
It records unknown never-obtained revisions. It never substitutes latest values
for candidate history. Its snapshot identity includes selected occurrences,
artifacts/checksums, schema/normalizer identities, policy/recipe, code digest and
environment. Reusing a label fails; old snapshots are never overwritten.

`resolve_prices` is a tiny synthetic proof: explicit members, one session,
declared price basis and `retained-at-cutoff-v1`. It filters both known-at and
local collection before revision selection, retains a withdrawal reason and
left-joins missing members. It conservatively reports competing partitions as
conflicts. It supplies no historical membership/calendar inference or full
financial/availability engine. `resolved_result` verifies that exact selection
and freezes the output, chosen IDs, cutoff, members and source history identity.
Another decision/policy requires its history dependencies and a new output.

`backup(store, new_path)` makes a checkpointed closed-handle catalog copy under
the retained writer lock, then copies its referenced raw objects and verified
published snapshots. `restore(backup_path, new_store_path)` verifies checksums,
streams copies to a new directory, verifies the staged copies, checks schema
version and sample queries, then publishes. It never overwrites an existing
store. Unfinished jobs retain diagnostics/raw; resuming them requires the caller
to resupply/revalidate the bounded batch, not replay an expired source cursor.
No retention, vacuum or deletion of historical/user files is automatic.

`write_direct(validated_batch, new_path, encoding="csv"|"parquet")` uses the same
validation as persistent publication. It creates no store/catalog, snapshot ID
or persistent revision catalogue. It writes a new bounded partition bundle;
large work must use explicitly complete bounded partitions. The underlying
snapshot writer streams Arrow batches (65,536 rows per group) into one file per
table, rather than materializing a long history. Ingest partition identity is
separate from this small-table export layout; ordering/layout are pinned in the
manifest. Local benchmarks compare stable listing/date and date/listing orders;
they do not prescribe a provider's physical partition contract.

CSV is UTF-8 with deterministic schema column order: `N` is null and `V<JSON>`
encodes a value (exact decimal strings, ISO dates/UTC instants, original text,
nested typed dimensions). Empty strings, literal null text and leading-zero
IDs survive. Parquet preserves typed lists, structs, dates, instants and exact
decimals. `read_bundle` verifies metadata identity and streamed file checksums;
`Bundle.table(name)` explicitly materializes and decodes the exact verified
bytes. `scan_polars(bundle, name)` verifies pinned immutable Parquet files and
returns a real lazy scan with its own read context. Readers never attach the
active writable catalog; callers must not mutate immutable bundle files.

Raw captures are retained by default. `retain_raw=False` keeps hashes/origin/
locators and explicitly marks raw replay unavailable. Required failures prevent
publication; `allow_partial=True` retains typed failure/coverage diagnostics
with a **partial** status, never a complete label. Existing destinations always
fail; no overwrite policy is implemented. Cancellation/disk-full at staged,
manifest, rename and final-sync boundaries preserves prior output. A caught
final-sync failure removes the new ready manifest and leaves inspectable files
that readers reject. An abrupt crash after complete atomic rename can leave a
valid complete bundle; callers reconcile it before retrying. Failure of the
filesystem even to remove a marker is outside a software-only rollback claim.

Reproducibility levels are explicit: artifact SHA-256 validates stored bytes;
logical recomputation requires retained inputs and pinned selection/code/
environment; byte-identical regeneration across library/platform versions is
not certified. Raw SDK replay begins at its SDK capture, not unavailable wire
responses. Decimal/integer comparisons remain exact. Checksums detect accidental
corruption; they are not independent attestation or tamper-proof signatures.
