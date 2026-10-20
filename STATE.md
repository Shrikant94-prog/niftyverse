# niftyverse - execution state

**Only execution-status authority.** Updated 21 October 2026.

## Active work

- **Phase:** 09 - Full DataPlan builder and incremental operation. Authorized through verified local merge and GitHub push; retain phase-09. Do not start Phase 12.
- **Start:** phase-09 created from inspected local/origin main `a6ac0d0`. No pre-existing phase branch; tracked tree clean; owner untracked `Sample_Files/` preserved. No reset or alternative revision. Remote fetched; main unchanged.
- **Prerequisites:** Phase 04/05/07/08 completion evidence inspected against current batch, catalog, publication, calendar and adapter interfaces and main ancestry. Phase 06 provides only its declared component interval; dependent broader membership must block honestly. Pre-edit full-extra regression **431 passed**, 45.33 s.
- **Checkpoint:** NV-09-01/02/03 focused verification complete; final scoped review and PH-09-GATE closure remain. Incremental/public/direct tests plus publication/bundles **100 passed**, strict mypy 99 files and lint pass. [Compiler](docs/evidence/09-20261021-compiler.md), [executor](docs/evidence/09-20261021-executor.md), [incremental evidence](docs/evidence/09-20261021-incremental.md).
- **Blockers:** None for explicit-universe software work. Historical membership and provider support remain restricted to existing verified evidence.

## Read first

1. [PLAN purpose](PLAN.md#purpose), [phase boundary](PLAN.md#phase-goals), [Phase 09 contract](docs/phases/09.md), [workflow](docs/WORKFLOW.md#phase-loop).
2. Current gate/review: [incremental evidence](docs/evidence/09-20261021-incremental.md), [builder usage](docs/builder.md); [refresh](docs/specs/builder.md#s10-3), [execution](docs/specs/builder.md#s10-2), [publication](docs/specs/storage.md#s11-2), [direct extraction](docs/specs/storage.md#s11-6). Inspect affected compiler/executor/storage/CLI and tests only.
3. Prerequisite completion evidence: [04](docs/evidence/04-20261020-completion.md), [05](docs/evidence/05-20261020-completion.md), [07](docs/evidence/07-20261021-completion.md), [08](docs/evidence/08-20261021-completion.md). Membership scope: [06](docs/evidence/06-20261020-completion.md). Acceptance rows R2/R8/R9/AM-04/AM-17 in [requirements](docs/specs/requirements.md#s18-2).

## Acceptance mapping

| Checkpoint | Independent expected outcome / current result |
|---|---|
| NV-09-01 AC1/2/3/4 | **16 compiler cases / 35 affected pass**, strict types/lint/format pass. Deterministic Python/TOML, scope/parser/policy/history isolation, local research gaps/output preflight and resource budgets. [Evidence](docs/evidence/09-20261021-compiler.md). |
| NV-09-02 AC1/2/3/4 | **14 executor cases / 133 affected pass**, strict types/lint/format pass. Bounded admission/retries, commit-boundary events, dependency/poison isolation, direct parity/partial output, v6 migration and quarantine backup/restore. [Evidence](docs/evidence/09-20261021-executor.md). |
| NV-09-03 AC1/2/3/4 | **16 incremental cases / 100 combined pass**; cancel/reopen/resume/rerun, compatibility, overlap/repair/reconcile, failed/mutating pagination and offline/direct limits. [Evidence](docs/evidence/09-20261021-incremental.md). |
| PH-09-GATE | **4 integrated cases pass**; multi-dataset cancel/resume/rerun, immutable history, scoped membership blocking, direct no-store and real CLI events. Final scoped review, full regression and installed-wheel gates pending. |

## Verification and limitations

- Phase 08 verified source `25837b9`, merged `51ae195`, integration record `a6ac0d0`; 431 full-extra / 387 core with 3 optional skips, strict types/lint/wheel and eight actual hosted jobs passed. [Completion](docs/evidence/08-20261021-completion.md).
- Source support and membership are scoped evidence, not ten-year readiness. New provider scope and future research computations are excluded.

## Phase ledger

| Phase | State | Evidence |
|---|---|---|
| 00 | verified | [Resume](docs/evidence/00-20261018-resume.md) |
| 01 | verified | [Completion](docs/evidence/01-20261018-completion.md) |
| 02 | verified, integrated and pushed | [Completion](docs/evidence/02-20261018-completion.md) |
| 03 | verified, integrated and pushed | [Completion](docs/evidence/03-20261019-completion.md) |
| 04 | verified, integrated and pushed | [Completion](docs/evidence/04-20261020-completion.md) |
| 05 | verified, integrated and pushed | [Completion](docs/evidence/05-20261020-completion.md) |
| 06 | verified, integrated and pushed | [Completion](docs/evidence/06-20261020-completion.md) |
| 07 | verified, integrated and pushed; phase-07 retained | [Completion](docs/evidence/07-20261021-completion.md) |
| 08 | verified, integrated and pushed; phase-08 retained | [Completion](docs/evidence/08-20261021-completion.md) |
| 09 | active final gate/review | Acceptance mapping above |
| 12-18, 10-11, 19-22 | not started | No next-phase authorization |
