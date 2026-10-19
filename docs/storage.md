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
transaction per additive version. Version 2 adds nullable SDK metadata; old
unknowns remain null. Downgrades/newer unsupported versions fail. Fixture-v1
artifacts/API remain readable through their original reader.

Only the owning process/thread uses a writable connection. All mutation APIs
are synchronous and serialized by that owner; independent readers use immutable
snapshots or wait until it closes. Lock contention fails within a bounded wait
with a diagnostic. Importing the modules performs no I/O.
