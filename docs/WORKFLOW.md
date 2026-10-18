# Phase execution and evidence

This is the only detailed workflow reference. Read it once at phase entry, or the relevant section when recovering. It is not an additional agent, framework, or progress log.

<a id="phase-loop"></a>
## Phase loop

1. **Enter:** Read AGENTS, STATE, and its selected PLAN/phase sections. Inspect the actual Git/workspace state. Match prerequisite evidence to the current code and environment; do not assume an inherited green summary proves current behavior.
2. **Bind the goal:** Use the phase brief's outcome, scope, gate, and acceptance IDs. Phase authorization covers all internal subtasks and ordinary repairs; no permission request is needed at every checkpoint. If only analysis was requested, do not start implementation. Explicitly requested Goal mode can sustain the work across turns; ordinary authorization alone does not create a goal automatically.
3. **Prepare the next checkpoint:** Select the next unfinished checkpoint whose prerequisites are satisfied. Inspect its relevant callers, interfaces, schemas, and tests. State intended behavior, scope, material assumptions and checks before editing; resolve uncertainty from evidence and ask only about consequential unresolved choices. Record a compact acceptance-to-evidence mapping in STATE for the active checkpoint: input, independent expected outcome, test/procedure, and current result. Investigate only unresolved contracts needed for this step. Do not create execution-plan files for every subtask.
4. **Implement and validate:** Apply [test-first verification](#test-first), then implement the smallest coherent change. Keep required validation and error handling; do not dismiss failures as impossible without contract evidence. Reassess a growing diff against the checkpoint's scope; no unrelated cleanup or speculative abstractions.
5. **Checkpoint and continue:** Run focused tests and applicable static checks. Preserve an intentional checkpoint commit when authorized; otherwise record the exact diff/revision. Update STATE with the next checkpoint and continue automatically inside the phase. Do not reread unchanged documents or repeat already-passing expensive checks without a relevant change.
6. **Integrate:** Run the phase's integration gate plus affected regressions. Review the selected diff, acceptance evidence, and impacted dependencies. For high-risk data/time/storage boundaries, use a fresh scoped review context if available/authorized; never claim independence from a second pass by the same context. Do not spawn agents unless the user authorized delegation. No whole-repository audit after each repair.
7. **Close:** Resolve demonstrated blocking defects, rerun affected checks, record evidence, and update only STATE's current status/ledger. A phase is verified only when all required outcomes and its gate pass. Report remaining source/dataset limits and the next eligible phase. Do not start that phase without authorization.

Checkpoints are recovery boundaries, not prompts the owner must repeatedly approve. Product choices, external access/input, destructive operations, or actions outside authorized scope can still require user input.

<a id="test-first"></a>
## Test-first verification

- Define expected results from the contract or independently checked examples before production edits; do not derive test expectations from the implementation under test.
- For bug fixes, write or select a reproducer and run it before the fix. Confirm failure for the reported defect, not an unrelated import/setup error; rerun it after the fix.
- For validation, parsing, storage and external-input boundaries, write relevant invalid-input, boundary and no-side-effect tests before implementation. Assert the specified error and unchanged protected state, not merely that an exception occurred. Run them before implementation where executable; preserve valid-input acceptance checks too.
- A negative test exercises rejected input; it need not fail on an already-correct implementation. Do not introduce a defect to obtain a red test. For other new behavior, test observable normal and applicable failure cases; documentation/format-only changes need no artificial negative tests.
- If test-first execution is impractical, record the concrete reason and alternative verification with the checkpoint evidence. An exception to ordering never waives verification or acceptance.
- Cover every coherent code checkpoint with executed relevant tests/build/lint checks. Behavior changes require an executable behavioral check; compilation or lint alone is insufficient. Refactors require relevant before/after behavior checks.
- After subsequent edits, rerun checks whose results may be invalidated. At phase closure run required integration gates and affected regressions. Do not rerun expensive unchanged checks without a relevant reason.
- Record commands, exit status, actual results and tested revision. Distinguish pre-existing failures using evidence. Never weaken assertions, skip required checks or alter expected results merely to obtain a pass.
- If a required check cannot run, report the blocker and remaining checks; retain unverified status. Never treat interrupted commands, test counts or stale green results as proof.

<a id="definition-of-done"></a>
## Definition of done and review boundaries

- Every AC has observed evidence against the current relevant code/input/environment; every phase gate has an integrated result. A planned filename or green subset of tests is not evidence for the remaining criteria.
- `NV-XX-YY-AC3` means: record the acceptance ID, independent expected result, exact command/procedure and observed result, source/working-tree identity, relevant environment/lock identity, and artifact or test reference. The evidence may cover several criteria together without duplicating logs.
- Distinguish source-checkout tests from fresh installed-wheel tests, frozen dependency reproduction from unconstrained consumer compatibility, Python-level network spies from subprocess/native isolation, and local checks from actual hosted CI.
- Each blocking review finding must identify a violated contract, demonstrated defect or missing required evidence. Substantive behavior violations, data corruption, source misrepresentation, and required gate failures block completion. Style preferences, speculative abstractions, and unrelated enhancements do not; record them as backlog only if useful.
- An unchanged accepted contract is not reopened because another reviewer prefers a different design. New concrete evidence of a defect may reopen it. Do not cap review rounds by ignoring valid defects; avoid repeated broad reviews by checking the specific repair and its consequences.
- Human visual acceptance is separate from automated checks. If required and unavailable, retain the pending criterion; finish independent work and request that concrete review instead of repeatedly redesigning the display.

<a id="verification-commands"></a>
## Verification commands

Before package creation, use `python tools/check_docs.py` for the documentation baseline. It checks structure, links, IDs, and dependency consistency; it cannot certify data or code.

After Phase 01 creates and locks the package, use the checked-in tool configuration:

```text
uv sync --frozen
uv run --frozen ruff format --check src tests
uv run --frozen ruff check src tests
uv run --frozen mypy src tests
uv run --frozen pytest <affected-tests> -q
```

At phase closure, run the relevant integration and existing offline regression suite. Add only required extras/groups explicitly and record them. Never run live provider probes as an implicit consequence of default tests. Packaging gates build a fresh wheel from the selected source and test it in isolation. A generated CI definition is not successful CI evidence. Run documentation checks only when the document set changes. Treat commands above as conditional on actual tool/config availability, not a reason to generate unrelated scaffolding.

<a id="state-and-evidence"></a>
## State and evidence

STATE is the single current execution record: active phase/checkpoint, Read first links, evidence pointers, blockers, next action, and compact phase ledger. Update it at meaningful checkpoints and handoffs. Phase briefs and requirement maps are static contracts; never add live checkboxes/status columns to them.

Store concise observed evidence under `docs/evidence/<phase>-<revision>.md` when a phase closes or a blocked handoff needs a durable record. An evidence record is immutable historical evidence, not a second current status. Prefer test/code/CI artifact references over pasted logs. Git supplies chronology. A dirty working tree needs a diff/content digest as well as a base commit; do not claim an old commit identifies uncommitted tested code. The template is [EVIDENCE_TEMPLATE](EVIDENCE_TEMPLATE.md).

Provider capability manifests record scientific coverage and support evidence, not phase progress. They must distinguish supported/experimental/blocked datasets and tested intervals. Performance logs and source captures belong in controlled local artifacts; keep raw data, credentials, and virtual environments out of Git. Exact logs may remain outside Git when the evidence record includes a reproducible procedure and hashes.

On compaction/resume, read AGENTS and STATE, inspect actual Git/diff state, then read only the active contracts and failing evidence. An interrupted command has unknown completion until checked. Do not recreate the whole plan, start Phase 00 again, or load all previous evidence records.

<a id="blockers"></a>
## Blockers, repeated failures, and research limits

After two unsuccessful attempts at the same failure, stop repeating that repair. Preserve the minimal reproducer and failed hypotheses, inspect the relevant contract/callers, and require a materially different evidence-backed hypothesis before another repair. If none is supported, report the concrete blocker and continue only independent authorized work. If blocked on a real input or decision, ask a concise question and continue only independent authorized work. Follow the runtime's actual goal/blocking controls; do not invent a pause, time budget, or automatic resume.

Source reconnaissance is finite: start with a named representative sample/window per capability family, apply the source request/attempt/deadline budgets, and record unavailable evidence. Repeated access failure does not authorize endless endpoint guessing, challenge bypass, or broad crawling. Phase 02 can complete its bounded investigation with explicit blockers; dependent implementation cannot claim supported capability without a valid source response and independent expected facts.

Blocked outcomes can be bypassed only for demonstrably independent checkpoints. Record the missing prerequisite and the exact limited scope in STATE. Do not mark the blocked phase verified or remove its requirement. Full historical reconstruction is not a prerequisite for a verified small interval or fixed-universe EOD work.

<a id="fresh-start"></a>
## Fresh project and baseline

Use a new owner-selected directory. Copy this document bundle and its documentation checker only. Do not copy old source/tests, environments, data stores, `.planning`, GSD skills, or hooks. Keep the old repository untouched as a historical reference; active instructions must not route to it.

Phase 00 inspects effective inherited rules and skill triggers in the chosen runtime. If unrelated global or parent instructions force broad loading, report that concrete configuration problem and resolve it within authorization. Do not edit global settings blindly. Use native runtime context/goal features; no framework installation is required. No new project skill is needed for routine Python development.

The delivered `docs/BASELINE.json` records specification hashes and source provenance. Establish an intentional Git baseline in Phase 00; an authorized start with this bundle adopts this revision without a repeated ceremonial approval. The manifest is a historical fingerprint, not an editable progress register. Later accepted specification changes are versioned in Git and may create a new baseline fingerprint; do not silently rewrite old evidence. R10 now means a portable, versioned multi-file baseline. AM-12 keeps CPython/runtime verification and replaces the removed GSD pin with selective-loading and resume evidence.
