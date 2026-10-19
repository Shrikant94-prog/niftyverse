# Phase 04 reproduced Parquet reader exit hang

Observed 20 October 2026 local time (19 October UTC). Current status belongs in
[STATE](../../STATE.md). The containing commit identifies the repaired source.

## Failed hypothesis and reproducible defect

The handshake-only change in `2fdce68425204cd457503a31d37a2fa9b9adf417` did **not**
repair the hosted failure. [Run 39302618826](https://github.com/Shrikant94-prog/niftyverse/actions/runs/39302618826)
again reports **179 passed, 1 failed, 3 skipped**. This time both explicit
refreshed-value assertions pass and the timeout occurs in `process.wait(15)`.
This rules out the buffered/raw communication hypothesis as the cause. Six
other lanes pass; matrix fail-fast cancels Windows. Neither failed run closes
the gate. Previous [repair observations](04-20261019-reader-repair.md) remain
historical, not a claim of successful hosted repair.

The failure is reproducible locally using a **fresh managed CPython 3.14.7 Linux
Clang 22.1.3** environment matching the hosted build and frozen **PyArrow 26.0.0**.
The existing `test_two_reader_processes_remain_pinned_during_refresh` fails
before the production change: both price reads are correct, but the reader
cannot exit within 15 seconds. Distro Python 3.14.4 had passed, demonstrating
why its earlier success was insufficient for the hosted problem.

Primary-source investigation found a similar [Apache Arrow shutdown report](https://github.com/apache/arrow/issues/50482),
which describes completion followed by native threaded Parquet read teardown
deadlock and a nonthreaded workaround. That report covers earlier Arrow releases
and Python-file objects; it informs the hypothesis but is not substituted for
our actual 26.0.0 BufferReader before/after observations. Installed PyArrow 26.0.0
source/signatures confirm `ParquetFile(..., pre_buffer=False)`, its context
manager and `read(use_threads=False)`.

## Focused production repair and results

`Bundle.table` reads exactly one already checksum-verified captured Parquet
artifact. It now uses an explicitly closed BufferReader/ParquetFile, disables
background prebuffering and threaded column reads, and no longer creates a
Dataset scanner for that single file. It still parses the captured verified
bytes; reopening a potentially changed path is not used as a workaround. No
global Arrow thread setting, dependency upgrade, forced process exit, test
skip, timeout increase or weakened value/clean-exit assertion was introduced.
The separate actual lazy Polars scan remains lazy.

The **identical** Linux 3.14.7 test passes after this production change:
**1 passed, 31 deselected**, clean reader exits within the unchanged deadline.
Fresh Linux 3.14.7 full core regression: **180 passed, 3 optional modules skipped**.
Fresh installed core wheel, with optional stacks absent and Python network/
process guards, also passes publication/idempotency, snapshots/temporal proof,
backup/restore and both direct encodings. Linux/WSL wheel SHA-256:
`6ad5e46fa2664426512634d42a30cc68ee3da3b866569f71efaf7520c11419b5`.

Windows 3.14.7 focused storage regression: **55 passed**; Ruff formatting/lint
and strict mypy (**45 source files**) pass. Full-extra and final hosted execution
are recorded separately at completion. Ingest/export and SQL benchmark query
paths are unchanged; this repair changes explicit materialized file decoding.

## Reproduction evidence

Ignored `.local/phase04/reproduce_linux.py` creates a new `/tmp` environment,
uses official uv 0.12.9 with verified wheel SHA, requests Python 3.14.7, syncs
the frozen project and invokes the unchanged reader test. `--full` additionally
runs core pytest and the fresh installed-wheel check. It imports no old project
environment/data. Script SHA-256:
`89313efe9ddbfcbcd7f407a652ccd53c360a4b27c233b31d81d731409152c5b80`.

```text
wsl -d Ubuntu -- python3 '/mnt/c/Users/Shrikant Maurya/OneDrive/Documents/Git_Projects/niftyverse/.local/phase04/reproduce_linux.py'
wsl -d Ubuntu -- python3 '/mnt/c/Users/Shrikant Maurya/OneDrive/Documents/Git_Projects/niftyverse/.local/phase04/reproduce_linux.py' --full
```

First command: exit 1 before repair (16.47 s, process-exit TimeoutExpired), exit
0 after repair (1.23 s). Second: exit 0, reader 1.25 s, full core 7.05 s, fresh
wheel passes. Failed hosted log retained under ignored
`.local/phase04/linux-2fdce68.log`, Windows UTF-16 SHA-256
`5e07134710e9ef5a8231aa2394c0d8619ffe8c9f217d65ea7998f59f59b21a90`.
These actual observations support the local workaround, not certification of
every Arrow/native teardown path or every possible runtime/filesystem.
