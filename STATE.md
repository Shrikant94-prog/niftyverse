# niftyverse - execution state

**Only execution-status authority.** Updated 19 October 2026 in the selected fresh workspace.

## Active work

- **Phase:** 03 - Transport and safe archive ingestion. Owner authorizes sequential implementation, local commits, final merge commit into local main, GitHub push; retain phase-03. Do not start Phase 04.
- **Status:** incomplete; execution blocked on the pending non-NSE decoder-fixture scope decision after three consecutive goal turns. NV-03-01 through 03 verified. Source assertions verified for older 2020 XML with a closed package, owner-linked legacy HTML and two integrated HTML specimens. Genuine-inline/newer-taxonomy acceptance remains unfinished.
- **Current checkpoint:** NV-03-04; extensive research found a genuine XBRL International issuer report. Owner scope clarification is pending before using non-NSE report/taxonomy bytes solely for shared-decoder verification.
- **Prerequisite:** Phase 02 integrated at 5bc94ba; current starting baseline a481636, clean initial tree. All 68 frozen baseline tests passed before changes. Earlier Phase 02 [completion](docs/evidence/02-20261018-completion.md) and relevant report/filing evidence inspected.
- **Git:** branch from local main a481636; runtime checkpoint f8bb373 and research checkpoints a944a1c/f85c447 pushed to origin/phase-03. All pass eight hosted jobs. Main/origin unchanged at last fetch; no merge yet.
- **Next action:** await the pending non-NSE fixture scope answer. If owner accepts codec-only use of the real XII report, acquire a bounded closed taxonomy package and implement/test evidenced inline constructs. NSE inline acquisition stays unsupported. No final integration while PH-03-GATE is incomplete.

## Read first

1. [PLAN purpose](PLAN.md#purpose) and [phase boundary](PLAN.md#phase-goals).
2. [Phase 03 acceptance](docs/phases/03.md), [gate](docs/phases/03.md#gate), [workflow](docs/WORKFLOW.md#phase-loop) (read at entry).
3. Active evidence: [inline research and hosted verification](docs/evidence/03-20261019-inline-research.md), [research observations](docs/capabilities/phase03-inline-observations.json), [XML/legacy checkpoint](docs/evidence/03-20261019-xml-legacy.md). [Filing safety](docs/specs/transport.md#s9-6); assigned AM-04/AM-14 in [requirements](docs/specs/requirements.md#s18-2).
4. For a concrete dependency only: [transport budgets/policy](docs/specs/transport.md#s9), [report observations](docs/evidence/02-20261018-reports.md), [initial filing facts](docs/evidence/02-20261018-filings-yahoo.md), [minimum manifest](docs/capabilities/manifest-v1.json).

## Acceptance mapping and evidence

| Checkpoint | Independent expected procedure | Observed result |
|---|---|---|
| NV-03-01 AC1-3 | Concurrent fake streams/clock, shared process/family/global limits, admission/request/byte/deadline caps, cleanup/fallback | [Transport evidence](docs/evidence/03-20261018-transport.md); related-host budget-split repair reproduced and verified in [filing checkpoint](docs/evidence/03-20261019-filings.md). |
| NV-03-02 AC1-3 | Deterministic 429/403/5xx/timeout, exact waits/counts, concurrent refresh, cancel/redaction | [Retry evidence](docs/evidence/03-20261018-retries.md); 24 current transport tests pass. |
| NV-03-03 AC1-3 | Real four report schemas plus hostile ZIP/CSV, atomic rejection/provenance | [Ingestion evidence](docs/evidence/03-20261018-ingestion.md); expiry/control-text reproducers repaired, 26 cases pass and four full official replays retain exact counts. |
| NV-03-04 AC1-3 | Real facts, QName/context/unit/dimensions/locators, offline closure and bounded malformed/cancellation cases | [XML/legacy evidence](docs/evidence/03-20261019-xml-legacy.md): 24 filing cases, 142 full-extra tests; fresh wheels pass. 2020 XML/legacy/integrated rendered assertions verified; genuine inline/newer versions unfinished. |
| PH-03-GATE | Integrated fault/safety suite and affected regressions; real-family evidence | **Incomplete:** common/2020 XML/legacy checks pass. Genuine-inline sample/decoder/transformation evidence and unresolved newer taxonomy requirements remain pending. |

## Verification and limitations

- Current code: CPython 3.14.7, uv 0.12.9. Frozen default suite: **118 pass, 2 optional modules skipped** (lxml absent). Explicit filings extra: **142 pass**. Ruff format/lint and strict mypy pass (30 source files).
- Fresh core and filings wheel hash 5650cb178a9b761683bf5e1d9da850884f233a26256e9a65a1e071b7ec0f3d75; installed core imports new boundaries without optional parser, installed extra decodes real HTML/XML with closed local package. Python audit denial is not an OS firewall or RSS sandbox.
- Lock 4b4b8542e9473f2ed5a77ef8c549efe62db7bbbdf9a65f368ebbd9a0228ec58f. lxml 6.1.3 optional; types-lxml development signatures. No Arelle runtime installed/imported: only explicit research-wheel resource bytes form the pinned 19-resource local taxonomy package.
- Runtime f8bb373 and research-only a944a1c/f85c447 pass all eight hosted jobs; [latest observed research run](https://github.com/Shrikant94-prog/niftyverse/actions/runs/39158106346) includes Windows/Ubuntu core, explicit filings subset and fresh installed filings wheel. Details in the research/hosted evidence.
- Owner supplied legacy URL and two Sample_Files XML inputs; originals remain untouched/untracked. Legacy content is 31-Dec-2009. 2018 XML has a 2018 namespace but a 2017-named schemaRef; 2025 input matches already acquired older-taxonomy facts. Neither is genuine inline.
- Owner-requested extensive research: eight additional named public NSE HTML specimens returned 200, all with zero inline namespace/fact/context elements; two announcement specimens are ordinary XML. NSE circular identifies an entity-facing NEAPS report route. No qualifying public NSE inline specimen was verified; no claim that none exists. SEC Infosys download returned 403, respected. XII's actual 2023 report returned 200 and contains 316 numeric facts, 7 text facts and 4 continuations. Exact twelve direct-request observations and primary sources are recorded. No new provider host was added to production/recon registries.
- Older 2020 package now closes offline. Integrated 2026 XML needs a matching package; published/archive collection inspected contains 2025, with no silent substitution. Source assertions are separate from full XBRL calculation/formula/dimensional validity and financial/ownership economic mapping.
- Further bounded inspection of already captured older NSE archives confirms a 2018 namespace/entrypoint package but no 2017-named entrypoint in that collection. The owner's 2018 XML names the latter; no alias can be established from file metadata alone. This independent check did not resolve that mismatch.
- NSE www 403 circuit remains respected; no bypass/retry there. Raw captures stay .local/phase02 and .local/phase03; only suitable bounded test inputs, metadata and hashes committed. No historical completeness/publication-vintage certification.
- Phase 01 human appearance/platform evidence remains in [completion](docs/evidence/01-20261018-completion.md); Phase 00 [evidence](docs/evidence/00-20261018-resume.md) retained. No old scaffold/environments/code/data adopted.

## Phase ledger

| Phase | State | Evidence |
|---|---|---|
| 00 | verified | [Resume](docs/evidence/00-20261018-resume.md) |
| 01 | verified through PH-01-GATE | [Completion](docs/evidence/01-20261018-completion.md) |
| 02 | verified, integrated and pushed | [Completion](docs/evidence/02-20261018-completion.md) |
| 03 | incomplete; execution blocked pending fixture-scope answer | Current acceptance mapping above |
| 04-09, 12-18, 10-11, 19-22 | not started | No next-phase authorization |

## Checkpoint handoff

Resume Phase 03 on retained phase-03 when the pending scope answer arrives. The XML/legacy checkpoint and research are pushed and hosted-green. Research located a real inline report from XII; the asynchronous question asks whether it may be used with its closed taxonomy only as decoder verification input under the phase's no-new-provider boundary. This same decision remains pending across three goal turns; independent common work, public-source research, archived-2018 inspection and latest CI observation have completed. Do not repeat those checks or implement the dependent scope before the answer. No upload question remains pending. Preserve untracked Sample_Files. Do not begin Phase 04, merge an incomplete gate, or report Phase 03 complete.
