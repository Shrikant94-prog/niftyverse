# niftyverse â€” execution state

**Only execution-status authority.** Updated 19 October 2026 in the selected fresh workspace.

## Active work

- **Phase:** 03 ? Transport and safe archive ingestion. Owner authorizes sequential implementation, local commits, merge into local main, GitHub push; retain `phase-03`. Do not start Phase 04.
- **Status:** incomplete. NV-03-01?03 verified; rendered filing boundary verified only for its two evidenced specimens. Required XML/inline/legacy and taxonomy gate remain unfinished. Branch starts at clean main `a481636`; main/origin unchanged after fetch.
- **Current checkpoint:** NV-03-04 ? evidenced filing dispatch/decoding and source blockers.
- **Prerequisite:** Phase 02 merged at `5bc94ba`; completion evidence and relevant report/filing observations inspected. Current frozen CPython 3.14.7 suite: 68 pass. Missing XML/inline/legacy/taxonomy evidence remains a dependent filing limitation, not a pass.
- **Next action:** preserve partial checkpoint and run hosted checks; resolve exact source/taxonomy inputs, then implement dependent structured decoding. Owner question pending for official URLs/local paths. No final merge while PH-03-GATE is incomplete.

## Read first

1. [PLAN purpose](PLAN.md#purpose) and [phase boundary](PLAN.md#phase-goals).
2. [Phase 03 acceptance](docs/phases/03.md), [gate](docs/phases/03.md#gate), and [workflow](docs/WORKFLOW.md#phase-loop) (read at entry).
3. Current checkpoint: [transport budgets/lifecycle/policy](docs/specs/transport.md#s9). Assigned AM-04/AM-14 in [requirements](docs/specs/requirements.md#s18-2).
4. For archive dispatch: [report observations](docs/evidence/02-20261018-reports.md). For filing decoder: [real samples and missing families](docs/evidence/02-20261018-filings-yahoo.md), [manifest](docs/capabilities/manifest-v1.json), [safety contract](docs/specs/transport.md#s9-6). Read only when that checkpoint is active.

## Acceptance mapping and evidence

| Checkpoint | Independent expectation / procedure | Observed result |
|---|---|---|
| NV-03-01 AC1?3 | Fake transport/clock; shared concurrency, admission/request/byte/deadline bounds, cleanup and HTTP protocol fallback | [8 transport cases pass; 76 total tests; types/lint pass](docs/evidence/03-20261018-transport.md). |
| NV-03-02 AC1?3 | Deterministic 429/403/5xx/timeout, refresh serialization, retry/cancel/redaction | [23 transport cases; 91 total tests; types/lint pass](docs/evidence/03-20261018-retries.md). |
| NV-03-03 AC1?3 | Real verified report headers plus owned hostile ZIP/CSV, atomic rejection and provenance | [24 ingestion cases; all four official report replays; 115 total tests](docs/evidence/03-20261018-ingestion.md). |
| NV-03-04 AC1?3 | Independently checked real-family facts, bounded decoder and taxonomy isolation | [Partial filing evidence](docs/evidence/03-20261019-filings.md): 14 filing tests / 130 full-extra tests; fresh wheels pass. Rendered assertions only. Structured requirements unfinished. |
| PH-03-GATE | Integrated fault/safety suite and affected regressions, no unsupported source claims | **Incomplete:** common fault/archive checks pass; required structured source assertions, closed taxonomies and inline/legacy evidence absent. |

## Source limits and prerequisites

- NSE www landing 403: no bypass/retry; dependent API probes are unsent `circuit_open`, not empty successes. Archives work independently. NIFTY POST candidates redirect; variant identities unverified.
- New Phase 03 older/integrated XML and official 2020/2025 taxonomy downloads are recorded in [observations](docs/capabilities/phase03-filing-observations.json). Closed dependencies absent; integrated XML needs 2026 rather than 2025 taxonomy. Legacy/bank/genuine-inline samples still missing. Dependent structured decoder/mapper claims remain blocked. Current lots cannot certify past terms. No ten-year or strict historical-version timing claim. Bounded failures do not yet justify a source/scope change.
- Yahoo capture is SDK-result, not wire bytes; internal HTTP count/bytes unknown. Production worker/normalizer, final-bar/correction tests and continuous coverage remain later phases.
- Raw captures/caches stay local in `.local/phase02`; plans/metadata hashes committed. Surveillance adds no price-only dependency. No R1 gate or old scaffold/data/code adopted.
- Phase 01 prerequisite rechecked: 43 offline tests pass before changes; hosted run 39145886497 success at `a563c9c5f03ba4601b1fe2a24b6b21e0aff30481`. [Completion](docs/evidence/01-20261018-completion.md) retains wheel/platform and owner appearance acceptance. Phase 00 [evidence](docs/evidence/00-20261018-resume.md) retained.

## Phase ledger

| Phase | State | Evidence |
|---|---|---|
| 00 | verified | [Resume](docs/evidence/00-20261018-resume.md) |
| 01 | verified through PH-01-GATE | [Completion](docs/evidence/01-20261018-completion.md) |
| 02 | verified, locally integrated and pushed | [Completion](docs/evidence/02-20261018-completion.md) |
| 03â€“09, 12â€“18, 10â€“11, 19â€“22 | not started | â€” |

## Checkpoint handoff

Phase 03 partial work on `phase-03`: common HTTP checkpoints `2a081ba`/`9af7f46`, ingestion `a4cb3b2`, then containing rendered/diagnostic checkpoint. Core 116 pass/one optional module skipped; full filings extra 130 pass; types/lint/fresh wheels pass. Missing families/taxonomy closure and implementation keep PH-03-GATE incomplete. Main remains `a481636`; no merge, no Phase 04. Retain the phase branch. GitHub push for branch CI is authorized. See partial filing evidence for exact current constraints, source hashes, source vs software verification, and next action.
