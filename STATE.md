# niftyverse - execution state

**Only execution-status authority.** Updated 20 October 2026.

## Active work

- **Phase:** 07 - Historical equities and delivery. NV-07-01/02/03 verified; NV-07-04 next: dated ETF catalogue/metadata/EOD with independent unit/source evidence. Do not start Phase 08.
- **Start:** `phase-07` created from inspected local main/origin main `0e030f98a8de55598a17eddf4c4a27ae46d841b3`. Tracked files clean; owner untracked `Sample_Files/` preserved. No reset, alternate revision or imported legacy implementation/environment. Local commits, merge and GitHub push authorized; retain branch.
- **Prerequisites:** Phase 02/03/04/05 evidence inspected against containing Git ancestry, actual source/report interfaces and Phase 06 completion. Current full-extra pre-edit regression **300 passed**, 39.77 s. Actual old/recent equity JSON now verified on five rows through the officially linked route/type, separate from initial failed candidates and SLBMH lending data. Historical identity and optional surveillance source limitations remain explicit.
- **Checkpoint assumptions:** normalize only evidenced raw traded prices/quantities; preserve close/settlement, source units/nulls and dated listing lineage. No current-list backfill, price filling, NAV/index substitution or optional-surveillance dependency in price-only work. Use shared publication validation and existing safe report decoder/transport; full DataPlan remains Phase 09.
- **Next:** NV-07-04 source/catalogue contract inspection and tests before ETF mapping. Current metadata must remain observation-dated; never infer classification from names or link changed ISINs by symbol. Verify real ETF JSON/report samples independently, then integrated gate, scoped review, full verification, reconciliation, local merge and push.

## Read first

1. [PLAN purpose](PLAN.md#purpose), [phase boundary](PLAN.md#phase-goals), [Phase 07 acceptance/gate](docs/phases/07.md), [workflow](docs/WORKFLOW.md#phase-loop).
2. Current checkpoint: [ETF source scope](docs/specs/sources.md#s5-8), [ETF semantics](docs/specs/analytics.md#s12-5), [existing ETF evidence](docs/evidence/02-20261018-etf-discovery.md), [current equity API/source evidence](docs/capabilities/phase07-equity-observations.json). [Quality/output evidence](docs/evidence/07-20261020-quality.md) and [usage](docs/equities.md) for affected boundaries only.
3. [Capability report](docs/capabilities/README.md), [partition contracts](docs/capabilities/partitions.md), [report samples](docs/evidence/02-20261018-reports.md), [ETF samples](docs/evidence/02-20261018-etf-discovery.md). Inspect only affected `ingestion.py`, `batches.py`, `identity.py`, `calendars.py`, `market_state.py`, transport/publication schemas and their tests. Prerequisites: [02](docs/evidence/02-20261018-completion.md), [03](docs/evidence/03-20261019-completion.md), [04](docs/evidence/04-20261020-completion.md), [05](docs/evidence/05-20261020-completion.md).

## Acceptance mapping

| Checkpoint | Input and independent expected outcome / current result |
|---|---|
| NV-07-01 AC1/2/3 | **16 focused tests pass**: exact decimal/source units, failed/truncated/overlapping pages/windows, source mutations and schema changes; EQ/BE/EQ plus BL yields three rows/30 units/3037.5000 turnover, EQ-only distinct exclusion. Actual old/recent JSON five rows and independent report value references match. [Evidence](docs/evidence/07-20261020-json.md); source/tests pinned by containing checkpoint commit. |
| NV-07-02 AC1/2/3/4 | **10 report/delivery cases** pass; combined phase suite **26 passed**. Whole actual legacy/UDiFF sources decode 1690/3675 rows; actual old/current delivery 1636/3511 rows. Old count/delivered-total reconcile; exact RELIANCE derived fractions/published percentages agree. Unsupported/partial/poisoned partitions and incompatible/zero/unknown denominators explicit. [Evidence](docs/evidence/07-20261020-reports.md). |
| NV-07-03 AC1/2/3/4 | Comparable tolerance/unit/basis checks retain both paths and block material conflicts; extreme moves remain warning-tagged facts with own known-at; dead/missing/closed/unavailable/policy states distinct. Optional states preserve volume and unknown execution. Shared negative rejection, v3-v4 migration/rollback/backup, DB/direct details parity and exact monetary conversion pass. **46 phase tests**, **346 full-extra tests**; [evidence](docs/evidence/07-20261020-quality.md). |
| NV-07-04 AC1/2/3 | Verified ETF source samples plus dated rename/reuse/metadata absence/conflict fixtures; fund-unit/traded-price semantics and no historical current-classification projection. Pending checkpoint 03. |
| PH-07-GATE | Integrated JSON/report reconciliation, explicit gap states, dated selection with no duplicate turnover, renamed/dead fixtures and ETF semantics. Not yet run. |

## Verification and limitations

- NV-07-01/02/03 formatter/lint/strict mypy (**76 files**) and **46 focused tests** pass; final current full-extra suite **346 passed**, 40.37 s. Shared supplemental schema migration is additive v4, with rollback/retained backup and old restore compatibility verified. No dependencies/lock/workflow changes. JSON source investigation made 12 direct requests plus one bounded old-delivery fetch; source support remains exact-window experimental. No full-history/cursor/surveillance support claim.
- Phase 06 completed at verified source `60203d5`, merged/pushed as `0e030f9`; 300 full-extra tests, 256 core/3 optional skips and all eight hosted jobs passed. Actual membership verification covers only the declared KWIL component window. Full-index history remains unverified; explicit-universe equity work proceeds independently.
- Original owner membership CSV and `Sample_Files/` remain preserved. No next-phase work, dependency upgrades or unrelated refactors authorized.

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
| 07 | active, NV-07-01/02/03 verified | [JSON](docs/evidence/07-20261020-json.md), [reports](docs/evidence/07-20261020-reports.md), [quality/shared output](docs/evidence/07-20261020-quality.md); ETF/final gate pending |
| 08-09, 12-18, 10-11, 19-22 | not started | No next-phase authorization |
