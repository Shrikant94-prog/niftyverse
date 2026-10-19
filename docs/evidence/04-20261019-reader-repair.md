# Phase 04 hosted reader-test failure and repair

Observed 19 October 2026; current status belongs in [STATE](../../STATE.md).
Runtime source stays `65a4354`; this record's containing commit changes the
reader-process verification harness and status/evidence only.

[Run 39301943361](https://github.com/Shrikant94-prog/niftyverse/actions/runs/39301943361)
at `65a4354dd0cacdeb8084fbdb88fbdd928adde9c0` failed its Linux core pytest step:
**179 passed, 1 failed, 3 skipped**. The two-reader test obtained correct
initial pinned values; the timed-out `communicate` diagnostic contained the
correct refreshed pinned value and stdout/stderr EOF fragments. It timed out
inside subprocess selector communication at 15 seconds. This does not establish
a data-selection failure or conclusively diagnose a Python/native runtime bug.
Windows was cancelled by matrix fail-fast, not counted as passed. The six other
lanes (all five extras plus macOS install) concluded success.

Raw log stays ignored under `.local/phase04/linux-65a4354.log`; ANSI-stripped
UTF-8 `.txt` SHA-256:
`5ca2172f1d1a2ca90808f9d490da31ed94c02937e95eff30ebc0ac9cd36ae465`.
The failed run is retained; no rerun of unchanged tests is substituted for it.

The test used buffered `readline` followed by `communicate`'s platform-specific
raw communication machinery. The repair uses one buffered protocol, explicitly
releases both readers before waiting, checks both refreshed values, and still
requires clean exit code zero with the same 15-second deadlines. Cleanup kills
outstanding children before waiting for reader threads; an initial-read timeout
can no longer deadlock the executor context cleanup. No value assertion, reader
count, process-exit requirement, timeout or production behavior was relaxed.
Mixed buffered/raw communication is the repair hypothesis, not a certified root
cause. Actual hosted validation of the changed test remains required.

Executed exit 0 after repair:

- Windows `uv run --frozen pytest tests/test_bundles.py -k two_reader -q`:
  **1 passed, 31 deselected**; Ruff format/check and strict mypy pass.
- `wsl -d Ubuntu -- python3 '/mnt/c/Users/Shrikant Maurya/OneDrive/Documents/Git_Projects/niftyverse/tools/check_linux.py'`:
  fresh temporary core/dev environment, uv 0.12.9, CPython **3.14.4 GCC 15.2.0**,
  WSL2 Linux 6.18.33.2/glibc 2.43. **180 passed, 3 skipped**; formatting/lint,
  strict types and fresh isolated installed core wheel all pass. Runtime/files
  use only this fresh project and newly created temporary environments.
- Fresh Linux/WSL wheel hash
  `c4c7f9eea92694caddb92c4c8dfe12c30c3994a826c3a5055f8345a2d666eb31`;
  unchanged checked-out CRLF lock hash
  `71224e6730b34a20a25b34de7d32148d2710eab1d43c7495193d1f14950287b0`.

The same WSL procedure also passed before repair, so local WSL is explicitly
not claimed to reproduce the hosted 3.14.7 failure. Its POSIX directory-sync,
process-crash, migration and snapshot tests are useful additional platform
evidence, not a replacement for the outstanding hosted gate.
