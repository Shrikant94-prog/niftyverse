# niftyverse - execution state

**Only execution-status authority.** Updated 21 October 2026.

## Active work

- **Phase:** 08 - Index prices, valuation and TRI; authorized through verified local merge and GitHub push. Do not start Phase 09.
- **Start:** `phase-08` created from inspected local/origin main `f9aac6bbe4a042ba97406ef8b21374a18890cf93`. Tracked tree clean; no pre-existing phase branch. Owner untracked `Sample_Files/` preserved. No reset or alternate revision.
- **Prerequisites:** Phase 02/03/04/05 and 07 completion evidence inspected against source interfaces and Git ancestry. Phase 02 index redirects and blocked VIX remain limitations pending bounded new evidence. Full-extra pre-edit regression **364 passed**, 37.26 s.
- **Checkpoint:** NV-08-01 verified; next NV-08-02. Explicit price/gross/net variant identities and source aliases; exact historical daily values/lineage, true half-open coverage and explicit gaps. No ETF/current substitute or Phase 09 DataPlan.
- **Next:** NV-08-01 tests/source verification and implementation, then NV-08-02, NV-08-03, integrated gate, reconciliation, verified local merge and authorized push. Retain phase-08.

## Read first

1. [PLAN purpose](PLAN.md#purpose), [phase boundary](PLAN.md#phase-goals), [Phase 08 contract](docs/phases/08.md), [workflow](docs/WORKFLOW.md#phase-loop).
2. Current checkpoint: [identity and representation](docs/specs/data-model.md#s7), [index semantics](docs/specs/analytics.md#s12-1), [AM-03](docs/specs/requirements.md#s18-2). Inspect affected index adapters/models, publication schemas/validation and tests only.
3. [Capability report](docs/capabilities/README.md), [partition contracts](docs/capabilities/partitions.md); relevant retained Phase 02 index/VIX samples. Prerequisites: [02](docs/evidence/02-20261018-completion.md), [03](docs/evidence/03-20261019-completion.md), [04](docs/evidence/04-20261020-completion.md), [05](docs/evidence/05-20261020-completion.md), [07](docs/evidence/07-20261021-completion.md).

## Acceptance mapping

| Checkpoint | Independent expected outcome / current result |
|---|---|
| NV-08-01 AC1/2/3 | Typed variants/aliases; collisions unresolved; exact source dates/values/lineage; empty and missing coverage explicit; ETF/current rejection. **18 focused identity/decoder cases pass**; with shared transport **44 pass**, strict mypy/lint/format pass. Five actual old/recent price rows match manually retained exact closes. [Evidence](docs/evidence/08-20261021-price.md). |
| NV-08-02 AC1/2/3 | Separate valuation/TRI schemas and coverage; null differs from zero; joins preserve identities and unsupported dates. Pending predecessor. |
| NV-08-03 AC1/2/3 | Historical VIX only for verified source/interval; current-only capability limitation; mistaken variant/invalid valuation rejected. Pending predecessor. |
| PH-08-GATE | Integrated price/PE/PB/yield/TRI never conflated, true dates/gaps, no ETF/current-VIX substitution. Pending checkpoints. |

## Verification and limitations

- Phase 07 verified at `b8ccde7`, merged/pushed as `f9aac6b`; 364 full-extra, 320 core/3 optional skips, installed wheel and eight hosted jobs pass. [Completion](docs/evidence/07-20261021-completion.md).
- Source evidence certifies exact sampled windows only, never ten-year history or historical publication vintages. No new provider or legacy import. Owner files preserved.

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
| 07 | verified, integrated and pushed; phase-07 retained | [JSON](docs/evidence/07-20261020-json.md), [reports](docs/evidence/07-20261020-reports.md), [quality/shared output](docs/evidence/07-20261020-quality.md); [ETF](docs/evidence/07-20261020-etfs.md); [gate](docs/evidence/07-20261020-gate.md); [completion](docs/evidence/07-20261021-completion.md) |
| 08 | active, NV-08-01 | Acceptance mapping above |
| 09, 12-18, 10-11, 19-22 | not started | No next-phase authorization |
