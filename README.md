# niftyverse — lean fresh-start document bundle

This bundle prepares a fresh implementation. It contains specifications and documentation tooling, not a completed library. The old repository has not been changed.

## Start here

1. Select a new project directory and place the bundle contents at its root. Keep the old checkout, environments, and stores separate; do not overwrite them.
2. Open that directory as the coding project. Ask the agent to read `AGENTS.md`, then `STATE.md`, and only the listed sections. The startup order is intentional.
3. When ready to execute, authorize **Phase 00 only** as a goal, including its sequential subtasks, verification, and local checkpoint commits. No GSD bootstrap is needed.
4. At each phase boundary, inspect the result and authorize the next phase. Internal checkpoints do not require repeated owner prompts.

Example goal wording:

> Complete Phase 00 in this fresh project using AGENTS.md, STATE.md, and their selective references. Execute its subtasks sequentially, verify the acceptance criteria, and create local checkpoint commits. Update only STATE.md for progress. Preserve unrelated files; do not push, publish, or begin Phase 01. Report a concrete blocker rather than inventing evidence.

## What changed

- Three short root control files; detailed contracts live in topic specifications.
- One phase per authorized goal; static phase briefs retain acceptance IDs and expected verification.
- One current-state record; no GSD-generated plans/summaries, issue hierarchy, or duplicate progress tracking.
- Fresh implementation from Phase 00. No inherited code, test passes, or phase approvals are claimed.
- Original split/bonus and database-free direct extraction contracts retained; the rationale and other new-plan proposals are recorded in [design decisions](docs/DESIGN_DECISIONS.md).
- All 30 requirements, 17 D decisions, 26 R/AM IDs, 76 outcome IDs, 259 outcome acceptance IDs, and 23 phase gates are retained. Framework-specific baseline criteria are explicitly revised, not silently deleted.

Read [PLAN.md](PLAN.md) for routes and delivery sequence. [DOCUMENT_CHECKS](docs/DOCUMENT_CHECKS.md) reports documentation validation only. `python tools/check_docs.py` reruns structural/link/ID/dependency checks; it does not test application behavior.

The topic files retain original numbered section identifiers for stable lookup. Their length is intentional reference detail, not default context. No agent should read all specifications or all phases to start a routine task.
