# Phase 04 commit/ack and lifecycle observations

Observed 19 October 2026 on phase-04 after `0beb748`. The containing checkpoint
commit identifies this tested code. Current status belongs in [STATE](../../STATE.md).
Environment/unchanged dependencies match [schema evidence](04-20261019-schema.md).

Independent oracles are in `tests/test_publication.py`, written before the new
module existed (initial collection reports missing API, not a defect reproducer).
The three-boundary matrix starts a separate Python writer, terminates it with
`os._exit(73)` at the actual boundary, then opens the surviving database from
the parent process. There is no graceful writer cleanup or mocked transaction.

| Acceptance | Expected durable state | Observed result |
|---|---|---|
| NV-04-02-AC1 precommit | Zero fact/occurrence/check/capture/coverage rows; staged job/raw may survive; no ack | Exact counts all zero. One orphan raw reported, staged job retained, no ack file. Retry commits exactly one unit. |
| NV-04-02-AC1 committed ack lost | One fact, occurrence, check, capture and complete coverage; committed job; no ack | Exact counts all one after restart; retry reuses durable occurrence, no duplicate. |
| NV-04-02-AC1 postack | Same complete committed state and persisted ack | Exact counts one, ack file exists, retry remains one. |
| NV-04-02-AC2 | Unchanged poll creates only a check; A-B-A, withdrawal and reinstatement preserve five occurrences | Six checks, five occurrences, four price rows, two raw content objects; withdrawn state keeps reason. Check collisions/tied conflicting ordering reject. |
| NV-04-02-AC1/2 negative/recovery | Cancel each boundary; fail ack callback; disk-full stage; quarantine; changed retry; corrupt/missing raw | All pass. Cancellation before commit rolls back coverage; later cancellation/ack errors preserve it. Disk-full adds no facts/coverage and preserves prior state. Quarantine retains job/raw but no facts/coverage; explicit corrected replay commits. Missing/corrupt committed raw blocks publication. Changed staged input cannot reuse check ID. |
| NV-04-02-AC3 | Commands/current source/environment and observed durable states | This record plus executable fault matrix and containing commit. |

Executed exit 0:

```text
uv run --frozen pytest tests/test_publication.py tests/test_store_schema.py tests/test_slice.py -q
uv run --frozen ruff check src tests
uv run --frozen mypy src tests
```

**44 passed**; lint passes; strict types pass (**42 source files**). A real
minimal-core run exposed DuckDB's optional pytz requirement for direct Python
TIMESTAMPTZ fetch. Reading the typed timestamp through Arrow fixes it without
adding optional dependencies. The lifecycle test now passes in the same core
environment. Formatting was applied to affected files.

Raw/file content uses flush/fsync before catalog references commit; POSIX also
fsyncs containing publication directories. Windows process-crash behavior above
is observed. This is not power-cut/OS-crash certification, a distributed
transaction, exactly-once network delivery or disk-loss protection. A crash can
leave raw/staging orphans; recovery reports them without deletion. Broader
platform execution and immutable snapshot/backup verification remain part of
the final gate. Full builder DAG orchestration remains Phase 09.
