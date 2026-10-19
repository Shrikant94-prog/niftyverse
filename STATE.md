# niftyverse - execution state

**Only execution-status authority.** Updated 20 October 2026.

## Active work

- **Phase:** 04 - Durable store and publication protocol. All checkpoints and PH-04-GATE verified. Local final merge and GitHub push authorized; retain phase-04. Do not start Phase 05.
- **Status:** Verified, ready for final local integration. All eight hosted jobs and overall workflow concluded success. Merge/publication remain the next action.
- **Start:** phase-04 created from inspected clean local main/origin main `1abbb1c5d7cdf3790ec198d84533c0de25fa2478`. Owner untracked `Sample_Files/` preserved. No reset, alternate start or discarded work.
- **Verified source:** `9b72748037476c310e22c614c138eb90dbb63997`. Final evidence/status commit is metadata only. Main reconciliation returned up to date; no conflict. Git records the final phase head and containing merge parents.
- **Next action:** commit final evidence; recheck main identity, merge with a merge commit, confirm verified source/test/config trees, push main and retained phase-04, verify remote identities. Next eligible phase: 05, not started.

## Read first

1. [PLAN purpose](PLAN.md#purpose), [phase boundary](PLAN.md#phase-goals), [Phase 04 acceptance/gate](docs/phases/04.md), [workflow](docs/WORKFLOW.md#phase-loop).
2. [Final completion and hosted evidence](docs/evidence/04-20261020-completion.md), [storage protocol/usage/limits](docs/storage.md).
3. Only for a concrete remaining dependency: [logical keys](docs/specs/data-model.md#s7-1), [partition contracts](docs/specs/builder.md#s10-2), [storage](docs/specs/storage.md#s11), `batches.py`, `storage/`, their tests. Do not reopen settled source research or rerun unchanged expensive checks.

## Acceptance mapping

| Checkpoint | Independent verification and observed result |
|---|---|
| NV-04-01 AC1-5 | [Schema evidence](docs/evidence/04-20261019-schema.md): real migrations/rollback and old nullable metadata, identity/partition separation, cross-process lock, OS-local defaults/risk warnings, typed financial/ETF schemas. Current regressions and common DB/file validation pass. |
| NV-04-02 AC1-3 | [Publication evidence](docs/evidence/04-20261019-publication.md): separate-process abrupt exit at all commit/ack boundaries; exact facts/lineage/check/coverage/job state; duplicate-free retry, unchanged polling, A-B-A, withdrawal/reinstatement, cancel/ack/disk-full/raw recovery. Current gate passes. |
| NV-04-03 AC1-4 | [Snapshots/direct/benchmark evidence](docs/evidence/04-20261019-snapshots.md): exact temporal oracle, two pinned readers, baseline snapshots, backup/restore/corruption, DB/CSV/Parquet parity with no-store spies, both formats' publication faults, replay limits, 100,000-row ingest/two query-shape benchmarks. |
| PH-04-GATE | [Completion](docs/evidence/04-20261020-completion.md): Windows full-extra 224 pass; matched Linux 3.14.7 core 180 pass/3 optional skips; fresh installed core wheels; all eight hosted jobs and workflow success on verified source. Ruff format/lint, strict mypy (45 source files), docs baseline/self-tests pass. |

## Verification and limitations

- Hosted [39303421939](https://github.com/Shrikant94-prog/niftyverse/actions/runs/39303421939): Windows/macOS 3.14.8, Linux 3.14.7. Each behavior platform 180 core pass/3 optional skips plus 51 filing cases. All five extras and macOS installation pass.
- Earlier two failed Linux runs remain historical evidence. [Matched 3.14.7 reproduction/repair](docs/evidence/04-20261020-parquet-exit.md) fixed native background Parquet read teardown; handshake-only repair did not. No relaxed deadline, skipped case or forced success.
- Lock/dependencies/config/workflow unchanged. Exact environment, wheel/lock hashes, commands and benchmark metrics are in completion evidence. Core optional-stack isolation and fixture-v1 compatibility pass.
- Process-crash publication is tested; hardware/OS power loss and Windows directory-metadata durability are not certified. Off-device backup is needed for disk loss. Artifact, logical and byte-regeneration levels remain distinct; raw omission limits replay. Synthetic contracts do not establish provider support or full financial/research semantics.
- Phase 03 source limits remain: XII offline only; missing 2026 taxonomy and mismatched 2018 vendor specimen quarantined. No source-readiness upgrade, hidden acquisition or next-phase work.

## Phase ledger

| Phase | State | Evidence |
|---|---|---|
| 00 | verified | [Resume](docs/evidence/00-20261018-resume.md) |
| 01 | verified | [Completion](docs/evidence/01-20261018-completion.md) |
| 02 | verified, integrated and pushed | [Completion](docs/evidence/02-20261018-completion.md) |
| 03 | verified, integrated and pushed | [Completion](docs/evidence/03-20261019-completion.md) |
| 04 | PH-04-GATE verified; final integration next | [Completion](docs/evidence/04-20261020-completion.md) |
| 05-09, 12-18, 10-11, 19-22 | not started | No next-phase authorization |
