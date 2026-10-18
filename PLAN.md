# niftyverse — delivery plan

**Revision:** 18 October 2026, lean fresh-start baseline. **Progress:** [STATE.md](STATE.md) only.

<a id="purpose"></a>
## Purpose and boundaries

Build a local-first Python research-data library for NSE equities, ETFs, indices, historical derivatives, reports, corporate events, financial statements, ownership, and two Yahoo global indices. A researcher declares a universe, dates, and datasets; the library acquires explicit source data, validates it, stores or exports it, and produces reproducible research inputs with visible gaps.

Preserve all 30 requirement IDs, decisions D-01–D-17, and R2–R10 / AM-01–AM-17. The complete [product contract](docs/specs/product.md#s1) and [requirement register](docs/specs/requirements.md#s2-1) define scope. CPython is 3.14.x; distribution/import/CLI is `niftyverse`. This baseline starts at Phase 00; previous implementation and test results do not count as completed work here.

Exclude live/intraday acquisition, RBI, trading/backtesting engines, IV/Greeks, continuous futures, PDF/OCR, and advanced action-return reconstruction. Split/bonus adjustment remains the supported initial basis. Direct extraction shares validated Arrow batches and exports without opening DuckDB. No compulsory GSD framework, GitHub issue hierarchy, duplicate status registers, or recursive planning skills.

The ten-year benchmark remains `[2016-09-01, 2026-09-01)`, with monthly decisions and explicit timing policies. A small independently verified interval comes first; full historical readiness depends on evidence. Missing source history cannot be repaired by inventing data or weakening criteria.

<a id="reading-route"></a>
## Reading route

At task entry: **AGENTS → STATE → listed PLAN/phase sections → only relevant topic sections → affected code/tests**. Read the active phase's short header/gate, then the current subtask. Links are lookup routes, not a request to read everything they reference. Original numbered section IDs are retained in topic documents to make exact references stable.

| Need | Selective reference |
|---|---|
| Scope or deferred feature | [Product](docs/specs/product.md#s1), [backlog](docs/specs/product.md#s22) |
| Requirement or amendment | [Requirements](docs/specs/requirements.md#s2-1), [amendments](docs/specs/requirements.md#s18-2) |
| Provider/filing evidence | [Sources](docs/specs/sources.md#s5) |
| Ownership or dependency | [Architecture](docs/specs/architecture.md#s6-2) |
| Identity, schema, time | [Data model](docs/specs/data-model.md#s7) |
| Historical universe | [Membership](docs/specs/membership.md#s8) |
| HTTP, archives, workers | [Transport](docs/specs/transport.md#s9) |
| DataPlan/resume/coverage | [Builder](docs/specs/builder.md#s10) |
| Writes, snapshots, export | [Storage](docs/specs/storage.md#s11) |
| Formula, action, resampling | [Analytics](docs/specs/analytics.md#s12) |
| Public interface | [API](docs/specs/api.md#s13) |
| Terminal or notebook | [Experience](docs/specs/experience.md#s14) |
| Tests/release evidence | [Verification](docs/specs/verification.md#s16) |
| A specific uncertainty | [Risks](docs/specs/risks.md#s21) |

<a id="phase-goals"></a>
## Phase goals

One authorized phase is one goal; its numbered outcomes are internal checkpoints. The agent executes them sequentially through tests, repairs, and the integration gate. It updates only STATE for progress and does not ask to continue after each checkpoint. Read [WORKFLOW](docs/WORKFLOW.md#phase-loop) at phase entry, not after every edit. Phase authorization does not authorize the next phase, package publication, or remote changes.

Before dependent code, resolve the current subtask's interface/schema and independent expected outcomes. Investigation is bounded and local to the uncertainty. Source blockers may leave dependent work blocked while independent work continues under the same authorized phase. A failed or unrun mandatory criterion never becomes complete.

<a id="roadmap"></a>
## Static roadmap

Default sequence is the table order; phase numbers are stable identifiers, not implied execution order. Each linked brief contains precise prerequisites. Research phases 12–18 run before derivatives 10–11, while integrated API Phase 19 waits for both. No phase is split across release waves. Phase 06 input/evidence blockers need not prevent explicit-universe work in 07–09; membership-dependent requests still require its verified intervals.

| Phase | Capability | Reviewable outcome |
|---|---|---|
| [00](docs/phases/00.md) | Fresh baseline and lean workflow | Portable baseline; proven selective-reading handoff |
| [01](docs/phases/01.md) | Package and offline vertical slice | Installed package; offline DB/direct-file slice; bounded previews |
| [02](docs/phases/02.md) | Source contracts and coverage reconnaissance | Bounded capability evidence and concrete unknowns |
| [03](docs/phases/03.md) | Transport and safe archive ingestion | Bounded transport, archives, and evidenced filing decoders |
| [04](docs/phases/04.md) | Durable store and publication protocol | Atomic publication, recovery, snapshots, and direct bundles |
| [05](docs/phases/05.md) | Identities, contracts foundation and calendars | Dated identities and evidenced calendars |
| [06](docs/phases/06.md) | NIFTY 500 verification and corrections | Membership audit, correction ledger, verified sub-window |
| [07](docs/phases/07.md) | Historical equities and delivery | Equity/delivery/ETF history with field coverage |
| [08](docs/phases/08.md) | Index prices, valuation and TRI | Separate index price, valuation, and TRI datasets |
| [09](docs/phases/09.md) | Full DataPlan builder and incremental operation | Useful incremental acquisition with resume and honest gaps |
| [12](docs/phases/12.md) | Corporate actions, announcements, events | Raw corporate events and evidenced split/bonus terms |
| [13](docs/phases/13.md) | Financial filing catalogs and facts | Financial statements with validated concepts and contexts |
| [14](docs/phases/14.md) | Shareholding catalogs and facts | Ownership facts with compatible categories/denominators |
| [15](docs/phases/15.md) | Yahoo/yfinance global EOD closes | Isolated Yahoo captures, completed bars, offline replay |
| [16](docs/phases/16.md) | Temporal research engine | Publication-aware research panels retaining missing members |
| [17](docs/phases/17.md) | Adjustments and standard features | Versioned adjustments, indicators, EOD aggregation |
| [18](docs/phases/18.md) | Reproducibility and correction propagation | Correction propagation, pinned replay, snapshot comparison |
| [10](docs/phases/10.md) | Historical derivatives | Dated derivative contracts and EOD history |
| [11](docs/phases/11.md) | Participant and market reports | Participant and market reports with units and limitations |
| [19](docs/phases/19.md) | Fluent API and SQL ergonomics | Integrated fluent/SQL, extraction, parsing, and tracing API |
| [20](docs/phases/20.md) | Rich terminal completion | Complete terminal workflow and clean machine output |
| [21](docs/phases/21.md) | Jupyter explorer completion | Bounded notebook exploration and cancellation |
| [22](docs/phases/22.md) | Hardening, documentation and release candidate | Measured release readiness, artifacts, and explicit data limits |

The first useful acquisition milestone is Phase 09. Phase 18 proves the full reference research path on a verified interval. Phase 22 integrates all promised datasets and assesses ten-year readiness. Estimates are deliberately omitted until actual source and implementation evidence supports them.

<a id="acceptance"></a>
## Acceptance and change control

Every phase brief retains stable outcome/acceptance IDs and expected verification. Passing helper tests is insufficient without its integration gate. Separate software status, provider capability, dataset coverage, and human visual acceptance. Phase 22 consolidates release evidence; no earlier phase claims the entire release complete.

Detailed topic contracts have one authoritative location. Phase briefs link them and state observable acceptance; STATE never copies the whole specification. A newly discovered defect changes code/tests; a genuinely changed product contract changes its owning topic and affected acceptance together. Record accepted rationale in the relevant specification and Git history, not in another mutable decision/status hierarchy.
