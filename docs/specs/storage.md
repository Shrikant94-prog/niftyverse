# Storage, publication, snapshots, and extraction

**Read when:** Publication, migrations, export encoding, snapshot consistency, recovery, or direct extraction.

**Authority:** detailed product contract, revision 18 October 2026. Implementation and dataset support are not claimed. Progress belongs only in root STATE.

## Section lookup

- [11.1 Store layout](#s11-1)
- [11.2 Writer and publication protocol](#s11-2)
- [11.3 Raw cache versus canonical data](#s11-3)
- [11.4 Snapshots and exports](#s11-4)
- [11.5 Maintenance](#s11-5)
- [11.6 Direct extraction and file publication](#s11-6)

Read the selected section and its necessary dependencies; this lookup is not a full-file reading checklist. Original section numbers are retained as stable references.

<a id="s11"></a>
## 11. Storage, snapshots, and recovery

<a id="s11-1"></a>
### 11.1 Store layout

```text
<store-root>/
├── catalog.duckdb
├── writer.lock
├── raw/sha256/ab/<full-hash>
├── staging/<build-id>/<job-id>/
├── snapshots/<snapshot-id>/manifest.json + parquet/
├── exports/<export-id>/
├── logs/                         # Rotatable, redacted run diagnostics
└── backups/<backup-id>/
```

Default runtime storage uses an OS-local application-data directory or an explicit user path. **Design recommendation:** keep active DuckDB files outside OneDrive/network-synchronized folders; source code and completed immutable exports can remain in the current workspace. Detect/warn about potentially synchronized store locations and document the limitation. Do not move the user's files automatically.

This applies to the whole active store: WAL, locks, staging, raw publication, spill files and temporary exports, not just `catalog.duckdb`. `doctor` reports the resolved paths and known sync/network risks before acquisition; explicit existing paths remain accepted with a visible unsupported-location warning, not silent relocation. Local default paths remain the supported deployment. Copy completed verified backups/immutable exports for off-device recovery under the source's usage terms; syncing a live database or making a same-disk backup is not protection against disk loss. Path detection is best-effort and does not establish that corruption is inevitable.

<a id="s11-2"></a>
### 11.2 Writer and publication protocol

One process owns a writable store under a cross-platform lock. Within it, a dedicated writer owns its connection and receives validated batches. External processes cannot open arbitrary simultaneous live read/write connections; use published immutable snapshots for independent readers, or close the writer before opening the database read-only.

This is the chosen embedded-database deployment model, consistent with DuckDB's in-process concurrency documentation. Client/server or external-catalog deployment models are outside the current design. [DuckDB concurrency](https://duckdb.org/docs/current/connect/concurrency)

Publication sequence:

1. Write direct-source bytes or a declared SDK-result capture to a controlled temporary object, hash and verify length/schema as applicable, then durably publish the immutable object.
2. Stage decoded batches with job/checkpoint metadata.
3. Validate the full atomic partition and construct canonical fact versions/provenance.
4. Commit facts, lineage references, coverage and partition status in one DuckDB transaction.
5. Publish build progress only after commit acknowledgement.

A filesystem write and a database commit are not a distributed transaction. Order them so a crash can leave an unreferenced raw object, but never intentionally a committed fact pointing to a missing raw object. Recovery scans detect orphans, missing references and unfinished staging. No “exactly once network delivery” claim; promise idempotent publication for stable business keys.

**Commit failure matrix (R2):** a pre-commit failure rolls back that unit's facts, lineage and coverage together. If commit succeeds but acknowledgement/progress is lost, those records remain committed; restart discovers the unit and avoids duplicate assertion versions. A failure after acknowledgement also retains committed completeness. The transaction publishes coverage; acknowledgement controls progress notification only. Fault-inject all three boundaries, including cancellation near commit, and reconcile durable state before classifying a resumed job.

Define process-crash durability separately from OS/power-loss durability. Use same-filesystem controlled staging/publication and explicit buffered flush/file synchronization before committing references; define and test supported platform metadata/publication behavior rather than assuming rename alone is power-loss safe. Snapshot completion manifests follow verified artifact durability. Power-loss guarantees remain limited to the tested filesystem/OS protocol; disk-loss recovery uses a verified off-device backup. Include disk-full and missing-artifact recovery without claiming a Python file-sync primitive is a complete cross-platform protocol.

Independent notebooks open private read contexts over immutable snapshot files; they do not attach the active writable catalog. Capture each snapshot's selection from one consistent committed database view, verify all files/checksums, then publish its completion manifest; incomplete exports are not discoverable as ready snapshots. A reader stays on its pinned snapshot while a new one publishes. Lock contention is a bounded actionable failure, not a hang or a reason to introduce a second mutable canonical database.

<a id="s11-3"></a>
### 11.3 Raw cache versus canonical data

Raw content-addressed objects support replay and audit. A request index maps sanitized request fingerprint and source-check time to raw hashes. Cache policy respects source freshness and HTTP validators if supported. Cache hits must not conflate a previously successful request with complete requested date coverage.

Canonical DuckDB tables hold typed facts, versions, provenance, and coverage. Latest views are conveniences; historical selection must use explicit evidence policies. Retain old fact versions and correction records. Default raw retention is sufficient to reproduce pinned snapshots; garbage collection cannot delete objects referenced by retained snapshots or in-progress builds.

<a id="s11-4"></a>
### 11.4 Snapshots and exports

Snapshot identity includes the exact selected input versions/partitions, research recipe, availability policy, schema and normalizer versions, and artifact checksums. A plan hash alone is insufficient: the same plan on two dates may use different source revisions.

Acquisition publishes a `history_bundle`: a consistent, immutable set of retained candidate assertions/states, identity/calendar/membership evidence, coverage and capture references for its effective dependency window, without preselecting today's latest values. Research publishes a `resolved_result` with exact decision-specific selections. A history bundle cannot contain revisions never obtained; its readiness reports that limitation. A resolved result alone cannot satisfy a different historical selection without a dependency preflight. Snapshot SQL convenience views must declare whether they expose all assertions or a named resolved selection; no silent latest-vintage coercion.

Reproducibility has three explicit levels: (1) reopen/check the stored artifact bytes; (2) recompute the same logical values under pinned selection/code/environment, with declared ordering and numeric tolerances; (3) byte-identical regeneration only where a deterministic serialization/environment contract is tested. Artifact checksums validate level 1 and are not a blanket promise of level 3 across library/platform versions. Exact integer/decimal semantics remain exact; floating feature tolerance is recipe-specific. Yahoo replay begins at the SDK-result capture, not at unavailable original Yahoo responses.

- **Parquet:** typed, Zstandard-compressed by default, partitioned by appropriate dataset/date buckets, with manifest and row counts. Avoid thousands of tiny symbol/day files. Write to a temporary destination and publish completion marker/manifest last.
- **CSV:** UTF-8, deterministic column order, documented null/date/decimal encoding, timezone representation, and schema/provenance sidecar. Distinguish empty text from null using an explicit encoding contract. Preserve leading-zero identifiers.
- Default analytical CSV preserves original text. Offer an explicitly labeled spreadsheet-safe mode that escapes formula-like text; document that this modifies presentation and is not the canonical round-trip format.
- `scan_polars(snapshot)` exposes lazy Parquet scans. Do not call a wrapper around an already materialized table an out-of-core lazy scan.
- Snapshot comparison reports changed facts, membership, features and reasons; ignore irrelevant collection timestamps when determining business-data changes.

Keep ingest partitions separate from export layout. Benchmark coarse dataset/year (or size-appropriate date buckets) and sorting by stable instrument/contract ID plus session date against both long single-security history and cross-sectional date queries. Small datasets need not be partitioned. Record row-group/file counts, bytes scanned, memory and cold/warm latency; pin layout metadata in the manifest. Avoid current-symbol clustering and per-symbol/day file explosions. Z-ordering, mandatory fixed file sizes and claimed 99.9% pruning are not release requirements. Physical repacking creates new artifacts/manifests while preserving logical selection and old snapshot references. [Arrow partitioning guidance](https://arrow.apache.org/docs/python/dataset.html), [DuckDB Parquet guidance](https://duckdb.org/docs/current/data/parquet/tips)

<a id="s11-5"></a>
### 11.5 Maintenance

Version schema migrations with preconditions, backup and post-migration checks. No automatic destructive migration during import. Implement backup/restore as a consistent database plus manifest/raw references/snapshot artifacts; verify checksums and sample queries after restore. Document crash recovery and lock ownership diagnostics.

Retention and vacuum/cleanup are explicit commands with dry-run output and pinned-snapshot protection. No silent deletion of user inputs or old research snapshots. A hash chain can detect accidental corruption but is not independently attested or legally tamper-proof; use accurate audit-trail language.

<a id="s11-6"></a>
### 11.6 Direct extraction and file publication

`build` persists canonical history in DuckDB for durable checkpoints, incremental refresh, history bundles and research snapshots. `extract` uses the same acquisition, decoder, mapper, quality and coverage contracts but returns bounded Arrow/Polars or writes a new CSV/Parquet bundle directly, without creating/opening a DuckDB store. DuckDB may remain installed as a core dependency; this mode removes the store requirement, not that dependency. `parse_filing` reads an explicitly supplied local path/bytes and returns the same result/diagnostics without network or automatic output writes.

File output includes schema/version, deterministic decimal/null/date encoding, origin/capture kind, document hashes/locators, parser/taxonomy/mapping identities, fact lineage, requested/observed coverage and typed failures in a manifest/sidecars. Preserve periods and dimensions in typed tables/companion files; do not flatten away segment context or turn catalog-only output into complete statements. Same supported facts and validation outcomes must agree with the database path.

Stage in an owned temporary sibling location, validate/checksum all members, then publish a new bundle with its completion manifest last under the tested platform protocol. Existing destinations fail by default; overwrite needs an explicit policy. Readers ignore incomplete bundles. Fault/cancel/disk-full tests prove no misleading completion marker and no damage to previous output. Default required failures prevent successful complete publication; an explicit partial-output option retains failure/coverage status, never a complete label. Use bounded batches/spooling; do not materialize long histories merely to export them.

Export bundles retain raw filing captures by default for replay. An explicit `retain_raw=False` can omit bytes while retaining hashes/origin/locators and marking raw replay unavailable. Memory/local-parse results retain provenance but promise no durable raw retention until explicitly saved. Local origin or unknown filing/publication metadata remains unknown, even if numbers parse successfully. Raw documents and taxonomies follow existing data-use/redistribution rules.

Direct extraction has no persistent multi-run revision catalogue, database snapshot ID or cross-run resume guarantee. Retrying can re-extract a bounded request; resumable builds and temporal research use the persistent path. File manifests may support read-only inspection/tracing without upgrading an extraction bundle into a research history bundle.
