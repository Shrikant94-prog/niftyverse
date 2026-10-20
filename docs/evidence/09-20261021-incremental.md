# Phase 09 incremental operation and public integration observations

Observed 21 October 2026 on phase-09 after `0cecfbe`. The containing checkpoint
pins source/tests. Tested Git blobs: planning `899a95a8f357341eba241b491fe7bb8eccbd7b20`,
execution `ef5e66b178de15b9eaed272c9496e3a063c50375`, builder
`41dbef5c20f58af4e4443f1d53e721577b4aeb5b`, local inputs
`a8f8c8e2cd0b0528a1506f6a04dd348aa3157a41`, CLI
`aadb971f9e0a937631d94ef686c91f36f5ce97d4`. Test blobs: incremental
`1fff7cb23f93f251d67116475e1dee807dd72d46`, gate
`0cb1f256e15ab8ecfb438d79941138e37dc6b5da`, input boundaries
`23611d4ff96d2fc91e59d347e48ff3377df7ce39`.
Current status is only [STATE](../../STATE.md).

## Observed acceptance

- NV-09-03-AC1: cancel after first committed unit, close/reopen the real store,
  resume only the missing unit, then unchanged rerun: exact fact, occurrence,
  check and coverage counts remain unchanged; no provider call on the unchanged
  run. Incompatible universe/config checkpoint rejects before acquisition;
  changed local bytes after compilation also reject. Injected before-commit,
  after-commit and after-ack cancellation reconciles real durable coverage and
  reaches two facts/occurrences/checks without duplicate business assertions.
- NV-09-03-AC2: two-session initial history plus one-session refresh acquires
  only the newer session and preserves the old value. Repeated unchanged polling
  adds one check but no fact revision. Exact-identity repair rechecks only its
  selected partition; reconcile rechecks the wider explicit interval. Failed
  page, changed source generation between pages, duplicate content, nonadvancing
  cursor, inconsistent count and unstabilized exhaustion each leave zero
  complete coverage for the affected day; unrelated day commits. Offline missing
  inputs defer without calling a network provider. Persistent raw recovery is
  checked before reuse; cache hints alone never cause direct extraction skips.
- NV-09-03-AC4 / AM-17: direct run IDs and history snapshot IDs remain null;
  bounded retry/re-extraction limits are explicit. Validated partial batches
  retain available facts only under explicit partial policy, with partial
  status and zero complete-partition progress. Memory/file parity and absent
  store are tested. Corrupt bundles, omitted raw and ambiguous local revisions
  reject. CSV and Parquet replay preserve exact source/capture/scope/schema.
- Initial PH-09-GATE observations: multi-dataset dependent graph cancels after
  one publication, resumes three, then reuses all four without acquisition.
  Two equity/two ETF facts, four source checks and four coverage rows match
  independent expectations. Successful build publishes an immutable history
  bundle and ID; direct output has no DB/snapshot ID. Unverified membership
  blocks only its two jobs; fixed-universe jobs still publish. CLI explain is
  local, CLI commit counts reflect real events, rerun reports cached work, and
  missing offline input exits 1 without false completeness.

## Checks and ordering

Incremental tests preceded implementation: first run **3 failed / 11 passed**,
specifically missing resume reuse, missing post-compile local-input guard and
missing operation fields. Gate tests preceded public build/extract/CLI code;
first run stopped at absent exports. Explicit partial-batch tests failed for
quarantining all available data before the partial sink repair. Local replay
negative checks were added after its first implementation (ordering exception:
the valid CLI integrated tests were already driving that new boundary); all
malformed/size/corruption/no-store cases were then executed. They do not waive
the input boundary's acceptance.

Final commands exited 0:

```text
uv run --frozen pytest tests/test_planning.py tests/test_execution.py tests/test_incremental.py tests/test_phase09_gate.py tests/test_acquisition_inputs.py tests/test_publication.py tests/test_bundles.py -q
100 passed, 11.32 s
uv run --frozen mypy src tests
99 files, strict pass
uv run --frozen ruff check src tests
pass
```

The Phase 09 subset is **58 cases**, 5.56 s in its preceding run. Full phase
closure and installed-wheel verification follow the final scoped review.
Environment and unchanged lock identity remain as in
[compiler evidence](09-20261021-compiler.md). CLI tests substitute only its
asyncio runner with the pre-created offline test loop, retaining actual
compiler/provider/executor/store/events and unchanged socket denial. This is
separate from an installed command-line subprocess test. Local bundle replay
is not a new provider proof or a claim that original bytes were re-parsed.

Page-token continuation is deliberately partition restart, not persistent
cursor reuse. Historical membership and provider support are not expanded;
future filing/Yahoo session grids and feature invalidation computations remain
their assigned phases. No automatic schedule or hidden discovery is present.
