"""Crash/ack fault matrix with real durable restarts, not mocked transactions."""

import asyncio
import os
import subprocess
import sys
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest
from test_store_schema import NOW, example

from niftyverse.core import ValidationError
from niftyverse.storage.catalog import Store
from niftyverse.storage.publication import publish, recover


@pytest.mark.parametrize(
    "boundary,committed",
    [
        ("before_commit", False),
        ("after_commit", True),
        ("after_ack", True),
    ],
)
def test_process_crash_commit_matrix(tmp_path: Path, boundary: str, committed: bool) -> None:
    root = tmp_path / "store"
    child = """
import os, sys
from pathlib import Path
from niftyverse.storage.catalog import Store
from niftyverse.storage.publication import publish
from test_store_schema import example
def fault(boundary):
    if boundary == sys.argv[2]: os._exit(73)
with Store(Path(sys.argv[1])) as store:
    publish(store, example(), fault=fault,
            acknowledge=lambda receipt: Path(sys.argv[3]).write_text(receipt.occurrence_id))
raise AssertionError('fault not reached')
"""
    ack = tmp_path / "ack"
    env = {
        **os.environ,
        "PYTHONPATH": str(Path(__file__).parent.resolve())
        + os.pathsep
        + str(Path("src").resolve()),
    }
    result = subprocess.run(
        [sys.executable, "-c", child, str(root), boundary, str(ack)],
        env=env,
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert result.returncode == 73, result.stderr
    assert ack.exists() == (boundary == "after_ack")
    # This is a fresh owning process context after the original abruptly exited.
    with Store(root) as store:
        for table in ("equity_daily", "occurrences", "source_checks", "coverage", "captures"):
            assert store.connection.execute(f"SELECT count(*) FROM {table}").fetchone() == (
                int(committed),
            )
        status = store.connection.execute("SELECT status FROM jobs").fetchone()
        assert status == ("committed" if committed else "staged",)
        report = recover(store)
        assert not report.missing_raw
        assert len(report.orphan_raw) == (0 if committed else 1)
        receipt = publish(store, example())
        assert receipt.reused == committed
        assert store.connection.execute("SELECT count(*) FROM equity_daily").fetchone() == (1,)
        assert store.connection.execute("SELECT status FROM coverage").fetchone() == ("complete",)
        assert store.connection.execute("SELECT count(*) FROM source_checks").fetchone() == (1,)


def test_poll_A_B_A_withdrawal_reinstatement_and_check_collision(tmp_path: Path) -> None:
    a = example()
    with Store(tmp_path / "store") as store:
        first = publish(store, a)
        poll = publish(store, replace(a, check_id="poll", checked_at=NOW + timedelta(seconds=1)))
        assert poll.occurrence_id == first.occurrence_id
        b = replace(
            example("2.5000", check="B"),
            known_at=NOW + timedelta(seconds=2),
            checked_at=NOW + timedelta(seconds=2),
        )
        second = publish(store, b)
        third = publish(
            store,
            replace(
                a,
                check_id="again-A",
                known_at=NOW + timedelta(seconds=3),
                checked_at=NOW + timedelta(seconds=3),
            ),
        )
        withdrawn = replace(
            a,
            check_id="withdraw",
            state="withdrawn",
            reason="source_retracted",
            tables=(),
            known_at=NOW + timedelta(seconds=4),
            checked_at=NOW + timedelta(seconds=4),
        )
        fourth = publish(store, withdrawn)
        fifth = publish(
            store,
            replace(
                a,
                check_id="reinstate",
                known_at=NOW + timedelta(seconds=5),
                checked_at=NOW + timedelta(seconds=5),
            ),
        )
        assert len({r.occurrence_id for r in (first, second, third, fourth, fifth)}) == 5
        assert store.connection.execute("SELECT count(*) FROM raw_objects").fetchone() == (2,)
        assert store.connection.execute("SELECT count(*) FROM source_checks").fetchone() == (6,)
        assert store.connection.execute("SELECT count(*) FROM equity_daily").fetchone() == (4,)
        assert store.connection.execute(
            "SELECT state, reason FROM occurrences WHERE occurrence_id=?", [fourth.occurrence_id]
        ).fetchone() == ("withdrawn", "source_retracted")
        with pytest.raises(ValidationError, match="check identity"):
            publish(store, replace(b, check_id=a.check_id))
        with pytest.raises(ValidationError, match="ordering"):
            publish(
                store,
                replace(
                    b,
                    check_id="ambiguous",
                    known_at=NOW + timedelta(seconds=5),
                    checked_at=NOW + timedelta(seconds=6),
                ),
            )


@pytest.mark.parametrize(
    "boundary,committed", [("before_commit", False), ("after_commit", True), ("after_ack", True)]
)
def test_cancellation_and_ack_failure_reconcile(
    tmp_path: Path, boundary: str, committed: bool
) -> None:
    def cancel(point: str) -> None:
        if point == boundary:
            raise asyncio.CancelledError

    with Store(tmp_path / "store") as store:
        with pytest.raises(asyncio.CancelledError):
            publish(store, example(), fault=cancel)
        assert store.connection.execute("SELECT count(*) FROM coverage").fetchone() == (
            int(committed),
        )
        publish(store, example())
        assert store.connection.execute("SELECT count(*) FROM coverage").fetchone() == (1,)


def test_quarantine_staging_replay_and_missing_raw(tmp_path: Path) -> None:
    batch = example()
    with Store(tmp_path / "store") as store:
        with pytest.raises(ValidationError, match="quarantined"):
            publish(store, replace(batch, coverage="quarantined", reason="poisoned-row"))
        assert store.connection.execute("SELECT count(*) FROM coverage").fetchone() == (0,)
        assert store.connection.execute("SELECT status FROM jobs").fetchone() == ("quarantined",)
        # An independent partition still commits; explicit corrected replay uses a new check.
        publish(store, replace(batch, check_id="replay", normalizer_version="fixed-v2"))
        assert store.connection.execute("SELECT count(*) FROM equity_daily").fetchone() == (1,)
        raw = store.root / "raw" / "sha256" / batch.capture.sha256[:2] / batch.capture.sha256
        raw.unlink()
        assert recover(store).missing_raw == (batch.capture.sha256,)
        with pytest.raises(ValidationError, match="missing.*raw"):
            publish(store, replace(batch, check_id="new-poll"))


def test_ack_callback_error_and_disk_full_preserve_committed_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import errno

    from niftyverse.storage import publication

    def lost_ack(_: object) -> None:
        raise RuntimeError("progress consumer failed")

    with Store(tmp_path / "store") as store:
        with pytest.raises(RuntimeError, match="progress"):
            publish(store, example(), acknowledge=lost_ack)
        assert publish(store, example()).reused

        def full(*_: object) -> None:
            raise OSError(errno.ENOSPC, "injected disk full")

        monkeypatch.setattr(publication, "write_bytes", full)
        new = replace(
            example("2.5000", check="new"),
            known_at=NOW + timedelta(seconds=1),
            checked_at=NOW + timedelta(seconds=1),
        )
        with pytest.raises(OSError) as error:
            publish(store, new)
        assert error.value.errno == errno.ENOSPC
        assert store.connection.execute("SELECT count(*) FROM equity_daily").fetchone() == (1,)
        assert store.connection.execute("SELECT count(*) FROM coverage").fetchone() == (1,)
        assert not recover(store).missing_raw


def test_changed_staged_input_and_corrupt_raw_do_not_publish(tmp_path: Path) -> None:
    def stop(point: str) -> None:
        if point == "before_commit":
            raise RuntimeError("stop")

    batch = example()
    with Store(tmp_path / "store") as store:
        with pytest.raises(RuntimeError, match="stop"):
            publish(store, batch, fault=stop)
        with pytest.raises(ValidationError, match="check identity"):
            publish(store, replace(batch, normalizer_version="changed"))
        assert store.connection.execute("SELECT count(*) FROM coverage").fetchone() == (0,)
        publish(store, batch)
        raw = store.location.paths["raw"] / batch.capture.sha256[:2] / batch.capture.sha256
        raw.write_bytes(b"corrupt")
        assert recover(store).corrupt_raw == (batch.capture.sha256,)
        with pytest.raises(ValidationError, match="corrupt"):
            publish(store, batch)
