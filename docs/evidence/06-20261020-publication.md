# Phase 06 replay and publication observations

Historical software verification and a component-scoped evidence example.
[STATE](../../STATE.md) holds the current completion/blocker decision. This
record does not establish a complete dated NIFTY 500 snapshot.

## Tested source and environment

Parser checkpoint `6822801`, replay checkpoint `d627e4c`; the containing commit
pins the publication code, focused review repairs, tests and wheel-smoke changes
observed here. Tests ran on the same staged source/test/tool tree; documentation
and completion metadata were subsequently updated. No dependency, lock, workflow
or provider capability changes. No legacy source/environment was imported.

Windows NT 10.0.26200, CPython 3.14.7 MSC v.1944 AMD64,
uv 0.12.9. Frozen Windows `uv.lock` SHA-256
`71224e6730b34a20a25b34de7d32148d2710eab1d43c7495193d1f14950287b0`.

## Acceptance observations

| Criteria | Independent expected results and observed evidence |
|---|---|
| NV-06-02 AC1/2/3 | `tests/test_membership.py`: independently authored A on Jan 1, B from Jan 2, accepted date correction moving the switch to Jan 3 at its review cutoff. Pending/rejected and earlier-known recipes retain Jan 2. Added/deleted events, exact-original guards, absent removals, overlaps and same-date ordering are checked. Contradicted endpoints, missing independent checks/inventory and raw-only event evidence remain blocked. Temporary components never acquire instrument IDs; unresolved identities block strict selection. |
| NV-06-02 AC1/2 | `tests/test_membership_identity.py` uses the Phase 05 dated catalogue: OLD resolves to a before 2022 and b thereafter; NEW resolves to a; M& M stays distinct from M&M. Temporary/security collisions remain ambiguous. Socket denial proves no Python network lookup. |
| NV-06-03 AC1/2/3 software | `tests/test_membership_publication.py`: both CSV/Parquet retain the exact old replay, create a new output and report only Jan 2 to Jan 3 membership invalidation. Partial outputs preserve gap/contradiction reasons and reject strict selection. Forged replay/parent metadata reject before destination creation; manifest/rename/final-sync injected failures leave no complete marker. Source hashes, recipes, code fingerprints and parent lineage survive publication. |
| Integrated owned scenario | `tests/test_phase06_gate.py`: literal negative input, corrected independently evidenced starting state, old partial output/new complete output and explained invalidation under socket denial; original unchanged. This fixture proves software behavior only. |
| Exact original | `tools/audit_membership.py <owner-file> --require-original` exited 0 on final relevant source. All inherited figures, seven notice conflicts, exact hash and unchanged bytes reconcile as in [original observations](06-20261020-audit.md). |

Test-first collection preceded each new module and failed because that module did
not yet exist. This establishes ordering, not behavioral bug reproduction.
Focused review subsequently produced real failing reproducers before repairs:
raw-only intermediate event certified from matching endpoints; accepted review
preceding replacement evidence; mutable parent metadata entering lineage. All
three regressions now pass. Review was by the implementation agent; no delegated
or independent agent review is claimed.

## Executed software checks

All final commands below exited 0 on the source pinned by this checkpoint:

- `uv run --frozen ruff format --check src tests`: **66 files** formatted.
- `uv run --frozen ruff check src tests`: pass.
- `uv run --frozen mypy src tests`: **64 files**, strict, pass.
- `uv run --frozen pytest tests/test_membership.py tests/test_membership_audit.py tests/test_membership_identity.py tests/test_membership_publication.py tests/test_phase06_gate.py -q`: **34 passed**.
- `uv run --frozen --all-extras pytest -q`: **298 passed**, 38.03 s.
- `uv sync --frozen` followed by `uv run --frozen pytest -q`: **254 passed,
  3 optional skips**, 10.44 s. Full-extra coverage above exercises those modules.
- `uv run --frozen python tools/check_wheel.py --lane core`: fresh isolated
  installed core wheel SHA-256
  `09c60fbe83ec08d076f1ed3ea7794e98b7c2465e8f50b89b4f3c09fdfd10bac8`;
  frozen hash-checked dependencies and `uv pip check` pass. Python 3.12/3.15
  rejection and installed membership audit/correction/publication/old replay
  checks pass under Python socket/process audit guards. This is not a native
  firewall or a replication of every source test in an installed interpreter.
- `uv run --frozen python .local/check_index.py`: byte-matched staged files
  checked via temporary index export; documentation baseline/self-tests pass,
  **90 Markdown files** before this record. Final metadata gets its own check.
- `git diff --cached --check`: pass.

An earlier full-extra run was invalidated by concurrently executing `uv sync`,
which removed its optional filing dependency mid-run (39 failures/259 passes).
The failure was environmental, not a source regression; that run is not claimed
as passing evidence. The clean full-extra rerun above completed before further
dependency changes. Earlier 296-test verification preceded two new regressions
and is not substituted for the final 298-test result.

## Actual evidence example and its exact scope

Manually read the primary [20 February 2026 notice](https://www.niftyindices.com/Press_Release/ind_prs20022026_1.pdf),
page 1. The affected-index table includes Nifty 500. It establishes the component's
last included close on February 23 and effective exclusion on February 24.
Its earlier dummy inclusion and later listing are separate facts; no price,
tradability or full-index membership was inferred.

The retained [reviewed note](06-kwil-reviewed-note.json) has SHA-256
`18273872cdd2765561706f782f27d8c17b93816893c311a5219496c5416e6435`
of its LF UTF-8 Git bytes. The reference identifies this note's hash, not a
fabricated raw-PDF hash. Raw PDF retention timed out on a bounded direct attempt;
the primary page was readable through web tooling. Initial bounded source
capture observed all five notices and the current CSV successfully; PDF capture
was a nonretaining inspection. No challenge bypass or endpoint search followed.
The current CSV has 501 rows and no effective date; it was not backdated.

Executed `uv run --frozen python .local/phase06/kwil_candidate.py`, exit 0,
on 2026-10-20 at 14:32:33 UTC. This local procedure uses the actual original hash,
the retained official-note hash, explicit date-only announcement, observed
knowledge/review times, a separate component identity, and scope
**Nifty500/component:kwality-walls-demerger**. The window is
**[2026-02-23, 2026-02-24)**. A working starting assertion is explicitly
unresolved; it does not invent a dated source snapshot from the CSV omission.
An accepted correction establishes that component using the notice; independent
boundary checks match the included/excluded states. The inventory assertion is
limited to that component and that one session.

Observed OS-local output directory:
`C:\Users\SHRIKA~1\AppData\Local\Temp\niftyverse-phase06-kwil-candidate-5nuak243`.
The local procedure/report remain under `.local/phase06/`; original data and
runtime bundles are not committed. Exact retained recipes permit offline replay.

| Identity | Observed |
|---|---|
| Old membership version | a2a9c6d8d829431005df4a43045013da479750c7dbe9300496e0527b9e04df7b |
| New membership version | be159aca393778f38157dd5f3375edd77148f57a2bd5afc669d57248367b33d0 |
| Old bundle | 2c717cb1db55ad70c300d1c3715f8b0b452914a5c95c4dd784988d6329b34a5c |
| New bundle | d41e49470e1c12c11844dbf55a698eb5905efd65bc95ed458dded026e5551061 |
| State | old partial, new complete within the explicit component scope |
| Invalidation | February 23 through exclusive February 24; membership_changed, verification_changed; correction establish-kwil-last-included-session |

Loading both bundles reproduces their exact recipes. The older assertion stays
blocked; the new strict selection returns the separate component and no security
instrument IDs. The original hash remains unchanged. A successful component
output never grants a full-index claim. The owner scope question remains in
STATE; this record does not silently resolve it or close PH-06-GATE.

No human visual criterion applies. Full historical curation and a complete dated
index baseline remain separate from this observed software/component example.
No next phase was started, and final integration is not claimed here.
