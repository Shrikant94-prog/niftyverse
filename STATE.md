# niftyverse - execution state

**Only execution-status authority.** Updated 21 October 2026.

## Active work

- **Phase:** 07 - Historical equities and delivery. All four checkpoints and PH-07-GATE verified; local integration/push pending. Verified source `b8ccde7d1bcf2af905453f47f031b15d149e977e`; all eight hosted jobs passed. Do not start Phase 08.
- **Start:** `phase-07` created from inspected local main/origin main `0e030f98a8de55598a17eddf4c4a27ae46d841b3`. Tracked files clean; owner untracked `Sample_Files/` preserved. No reset, alternate revision or imported legacy implementation/environment. Local commits, merge and GitHub push authorized; retain branch.
- **Prerequisites:** Phase 02/03/04/05 evidence inspected against containing Git ancestry, actual source/report interfaces and Phase 06 completion. Current full-extra pre-edit regression **300 passed**, 39.77 s. Actual old/recent equity JSON now verified on five rows through the officially linked route/type, separate from initial failed candidates and SLBMH lending data. Historical identity and optional surveillance source limitations remain explicit.
- **Checkpoint assumptions:** normalize only evidenced raw traded prices/quantities; preserve close/settlement, source units/nulls and dated listing lineage. No current-list backfill, price filling, NAV/index substitution or optional-surveillance dependency in price-only work. Use shared publication validation and existing safe report decoder/transport; full DataPlan remains Phase 09.
- **Next:** Recheck main and tested-tree identity, commit completion evidence, merge phase-07 into main with a merge commit, push both heads and confirm remote ancestry. Retain phase-07. Phase 08 is next eligible, not started.


## Read first

1. [Completion audit](docs/evidence/07-20261021-completion.md), [gate/review evidence](docs/evidence/07-20261020-gate.md), then [PLAN purpose](PLAN.md#purpose), [phase boundary](PLAN.md#phase-goals), [Phase 07 acceptance/gate](docs/phases/07.md), [workflow](docs/WORKFLOW.md#phase-loop).
2. Current checkpoint: [ETF source scope](docs/specs/sources.md#s5-8), [ETF semantics](docs/specs/analytics.md#s12-5), [existing ETF evidence](docs/evidence/02-20261018-etf-discovery.md), [current equity API/source evidence](docs/capabilities/phase07-equity-observations.json). [Quality/output evidence](docs/evidence/07-20261020-quality.md) and [usage](docs/equities.md) for affected boundaries only.
3. [Capability report](docs/capabilities/README.md), [partition contracts](docs/capabilities/partitions.md), [report samples](docs/evidence/02-20261018-reports.md), [ETF samples](docs/evidence/02-20261018-etf-discovery.md). Inspect only affected `ingestion.py`, `batches.py`, `identity.py`, `calendars.py`, `market_state.py`, transport/publication schemas and their tests. Prerequisites: [02](docs/evidence/02-20261018-completion.md), [03](docs/evidence/03-20261019-completion.md), [04](docs/evidence/04-20261020-completion.md), [05](docs/evidence/05-20261020-completion.md).

## Acceptance mapping

| Checkpoint | Input and independent expected outcome / current result |
|---|---|
| NV-07-01 AC1/2/3 | **16 focused tests pass**: exact decimal/source units, failed/truncated/overlapping pages/windows, source mutations and schema changes; EQ/BE/EQ plus BL yields three rows/30 units/3037.5000 turnover, EQ-only distinct exclusion. Actual old/recent JSON five rows and independent report value references match. [Evidence](docs/evidence/07-20261020-json.md); source/tests pinned by containing checkpoint commit. |
| NV-07-02 AC1/2/3/4 | **10 report/delivery cases** pass; combined phase suite **26 passed**. Whole actual legacy/UDiFF sources decode 1690/3675 rows; actual old/current delivery 1636/3511 rows. Old count/delivered-total reconcile; exact RELIANCE derived fractions/published percentages agree. Unsupported/partial/poisoned partitions and incompatible/zero/unknown denominators explicit. [Evidence](docs/evidence/07-20261020-reports.md). |
| NV-07-03 AC1/2/3/4 | Comparable tolerance/unit/basis checks retain both paths and block material conflicts; extreme moves remain warning-tagged facts with own known-at; dead/missing/closed/unavailable/policy states distinct. Optional states preserve volume and unknown execution. Shared negative rejection, v3-v4 migration/rollback/backup, DB/direct details parity and exact monetary conversion pass. **46 phase tests**, **346 full-extra tests**; [evidence](docs/evidence/07-20261020-quality.md). |
| NV-07-04 AC1/2/3 | Verified ETF source samples plus dated rename/reuse/metadata absence/conflict fixtures; fund-unit/traded-price semantics and no historical current-classification projection. **14 ETF cases pass**, combined phase suite **60 passed**, strict mypy **80 files**. Four actual old/recent JSON/report pairs match independent values; whole current catalogue 355 rows validated. Current 20 October EOD is unverified (empty JSON/report 404), not complete no-data. [Evidence](docs/evidence/07-20261020-etfs.md). |
| PH-07-GATE | Integrated JSON/report reconciliation, explicit gap states, dated selection with no duplicate turnover, renamed/dead fixtures and ETF semantics. **2 integrated equity/ETF cases passed**: paired JSON/archive decoding, raw OHLC/units, dated rename/EQ-BE-EQ/BL totals, dead/missing gaps, EQ-only exclusion and scoped conflict quarantine. Review repairs have failing-before-fix evidence. **364 full-extra tests pass**; [gate evidence](docs/evidence/07-20261020-gate.md). |

## Verification and limitations

- Final source `b8ccde7`: **364 full-extra tests passed**, **320 core passed / 3 optional skips**, format/lint/strict mypy (**81 files**), fresh installed core wheel and all eight [hosted jobs](https://github.com/Shrikant94-prog/niftyverse/actions/runs/39459108549) passed. Additive schema v4 migration/rollback/backup and DB/direct parity verified. No dependency/lock/workflow changes. Source support is exact-window experimental; current 20 October ETF availability, historical mandates/identity and optional surveillance remain unverified. See [completion audit](docs/evidence/07-20261021-completion.md).
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
| 07 | verified; local integration/push pending | [JSON](docs/evidence/07-20261020-json.md), [reports](docs/evidence/07-20261020-reports.md), [quality/shared output](docs/evidence/07-20261020-quality.md); [ETF](docs/evidence/07-20261020-etfs.md); [gate](docs/evidence/07-20261020-gate.md); [completion](docs/evidence/07-20261021-completion.md); local integration/push pending |
| 08-09, 12-18, 10-11, 19-22 | not started | No next-phase authorization |
