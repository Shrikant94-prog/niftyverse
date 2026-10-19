# niftyverse - execution state

**Only execution-status authority.** Updated 19 October 2026.

## Active work

- **Phase:** 04 - Durable store and publication protocol. All checkpoints, local commits, merge into local main and GitHub push authorized. Retain phase-04; do not start Phase 05.
- **Status:** NV-04-01 and NV-04-02 checkpoint checks verified; NV-04-03 active; phase incomplete.
- **Start:** inspected clean tracked main/origin main `1abbb1c`; only untracked owner `Sample_Files/`. No pre-existing phase-04. Created phase-04 from that local main, preserving all existing branches/files.
- **Prerequisites:** Phase 01 and 03 completion evidence inspected and their software is in main ancestry. Current frozen full-extra baseline: 169 passed on Windows CPython 3.14.7, uv 0.12.9. Synthetic storage batches establish no provider support.
- **Next action:** test immutable history/resolved bundles, temporal proof, consistent backup/restore, direct CSV/Parquet faults and no-store parity; measure local ingest/query baselines.

## Read first

1. [PLAN purpose](PLAN.md#purpose), [phase boundary](PLAN.md#phase-goals), [Phase 04 acceptance/gate](docs/phases/04.md), [workflow](docs/WORKFLOW.md#phase-loop).
2. Current checkpoint: [logical keys](docs/specs/data-model.md#s7-1), [partition state](docs/specs/builder.md#s10-2), [storage](docs/specs/storage.md#s11), assigned R2/3/4/8/9 and AM-02/04/05/07/08/10/14/17 in [requirements](docs/specs/requirements.md#s18-2).
3. Affected interfaces: `core.py`, `builder.py`, `storage/`, source assertion records in `filing_xml.py`. Prerequisites: [01 completion](docs/evidence/01-20261018-completion.md), [03 completion](docs/evidence/03-20261019-completion.md).

## Acceptance mapping

| Checkpoint | Independent expected cases / procedure | Result |
|---|---|---|
| NV-04-01 AC1/2/4/5 | Actual temporary DuckDB migration/rollback, old unknown metadata, distinct occurrences/checks; scope/field/basis, financial/ETF identities; cross-process lock; path diagnostics | [Schema evidence](docs/evidence/04-20261019-schema.md): 34 focused/compatibility tests pass; final shared-sink runtime parity follows in NV-04-03 |
| NV-04-02 AC1/2 | Separate-process crash/restart at all three boundaries; exact facts/lineage/coverage; lifecycle, staging/retry/cancel/disk-full | [Publication evidence](docs/evidence/04-20261019-publication.md): 44 focused/compatibility tests pass; lint and strict types pass |
| NV-04-03 AC1/2/4 | Hand-checked temporal fixture; pinned readers; history/resolved snapshots; backup restore/corruption; CSV/Parquet same-batch no-store faults; ingest/two query benchmarks | Pending |
| All AC3 and PH-04-GATE | Commands, observed results, source/environment identity, focused review, integrated gate and affected regressions | Pending |

## Verification and limitations

- Baseline `uv run --frozen --extra filings pytest -q`: 169 passed. Existing uv cache and Git metadata require sandbox escalation; approved prefixes are used.
- Preserve Phase 01 fixture-v1 API and readable artifacts. No economic mapper, full builder/research engine or provider breadth in Phase 04.
- Phase 03 remains verified: offline XII only; missing 2026 taxonomy and mismatched 2018 vendor specimen quarantine. No source readiness upgrade from synthetic storage checks.
- Process-crash publication and power-loss/off-device recovery claims must remain separate. Platform evidence pending.

## Phase ledger

| Phase | State | Evidence |
|---|---|---|
| 00 | verified | [Resume](docs/evidence/00-20261018-resume.md) |
| 01 | verified through PH-01-GATE | [Completion](docs/evidence/01-20261018-completion.md) |
| 02 | verified, integrated and pushed | [Completion](docs/evidence/02-20261018-completion.md) |
| 03 | verified, integrated and pushed | [Completion](docs/evidence/03-20261019-completion.md) |
| 04 | authorized; NV-04-01 active | Current record above |
| 05-09, 12-18, 10-11, 19-22 | not started | No next-phase authorization |
