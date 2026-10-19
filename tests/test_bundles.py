"""Independent direct-bundle and snapshot/restore acceptance examples."""

import asyncio
import errno
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import duckdb
import pyarrow as pa
import pytest
from test_store_schema import NOW, example, financial_example

from niftyverse.core import ValidationError
from niftyverse.storage.bundles import read_bundle, write_direct
from niftyverse.storage.catalog import Store
from niftyverse.storage.publication import publish
from niftyverse.storage.snapshots import (
    backup,
    history_bundle,
    resolve_prices,
    resolved_result,
    restore,
)


@pytest.mark.parametrize("encoding", ["csv", "parquet"])
@pytest.mark.parametrize("batch", [example(), financial_example()])
def test_direct_roundtrip_matches_db_without_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    encoding: str,
    batch: object,
) -> None:
    from niftyverse.batches import ValidatedBatch

    assert isinstance(batch, ValidatedBatch)
    with Store(tmp_path / "store") as store:
        publish(store, batch)
        expected = {n: store.read_table(n).drop(["occurrence_id"]) for n, _ in batch.tables}

    def no_store(*_: object, **__: object) -> None:
        raise AssertionError("direct output opened a store")

    monkeypatch.setattr(duckdb, "connect", no_store)
    monkeypatch.setattr(Store, "__enter__", no_store)
    destination = tmp_path / "direct"
    write_direct(batch, destination, encoding=encoding)
    result = read_bundle(destination)
    for name, table in expected.items():
        assert result.table(name).equals(table)
    manifest = result.manifest
    assert manifest["kind"] == "direct_extract"
    assert manifest["raw_replay_available"] is True
    assert manifest["batch"]["capture"]["sha256"] == batch.capture.sha256
    assert manifest["batch"]["coverage"] == batch.coverage
    assert manifest["batch"]["partition"]["basis"] == batch.partition.basis
    assert manifest["snapshot_id"] is None
    assert (destination / "raw" / batch.capture.sha256).read_bytes() == batch.capture.body


@pytest.mark.parametrize("encoding", ["csv", "parquet"])
def test_raw_omission_and_partial_are_explicit(tmp_path: Path, encoding: str) -> None:
    batch = example()
    destination = tmp_path / "out"
    write_direct(batch, destination, encoding=encoding, retain_raw=False)
    result = read_bundle(destination)
    assert result.manifest["raw_replay_available"] is False
    assert not (destination / "raw").exists()
    partial = replace(batch, coverage="partial", reason="failed_page")
    with pytest.raises(ValidationError, match="partial"):
        write_direct(partial, tmp_path / "bad")
    assert not (tmp_path / "bad").exists()
    write_direct(partial, tmp_path / "partial", allow_partial=True)
    assert read_bundle(tmp_path / "partial").manifest["status"] == "partial"
    assert read_bundle(tmp_path / "partial").manifest["batch"]["reason"] == "failed_page"


@pytest.mark.parametrize(
    "boundary", ["after_data", "before_manifest", "before_publish", "after_publish"]
)
@pytest.mark.parametrize("failure", ["cancel", "full"])
@pytest.mark.parametrize("encoding", ["csv", "parquet"])
def test_direct_faults_preserve_prior_bundle(
    tmp_path: Path,
    boundary: str,
    failure: str,
    encoding: str,
) -> None:
    prior = tmp_path / "prior"
    write_direct(example(), prior)
    before = {str(p.relative_to(prior)): p.read_bytes() for p in prior.rglob("*") if p.is_file()}

    def fault(point: str) -> None:
        if point == boundary:
            if failure == "cancel":
                raise asyncio.CancelledError
            raise OSError(errno.ENOSPC, "disk full")

    with pytest.raises((asyncio.CancelledError, OSError)):
        write_direct(example(), tmp_path / "new", encoding=encoding, fault=fault)
    assert not (tmp_path / "new" / "manifest.json").exists()
    assert {
        str(p.relative_to(prior)): p.read_bytes() for p in prior.rglob("*") if p.is_file()
    } == before
    with pytest.raises(FileExistsError):
        write_direct(example("2.0000"), prior, fault=fault)
    assert read_bundle(prior).table("equity_daily")["close"][0].as_py() == Decimal("1.25")


def test_history_resolved_temporal_proof_and_backup_restore(tmp_path: Path) -> None:
    a = example("100.0000")
    with Store(tmp_path / "store") as store:
        original = publish(store, a)
        history_bundle(store, "baseline", recipe="synthetic-v1", policy="retained-at-cutoff-v1")
        later = replace(
            example("90.0000", check="later"),
            checked_at=NOW + timedelta(days=1),
            known_at=NOW + timedelta(days=1),
        )
        revised = publish(store, later)
        withdrawn = replace(
            a,
            check_id="withdraw",
            state="withdrawn",
            reason="source_retracted",
            tables=(),
            checked_at=NOW + timedelta(days=2),
            known_at=NOW + timedelta(days=2),
        )
        retracted = publish(store, withdrawn)
        history = history_bundle(
            store, "all", recipe="synthetic-v1", policy="retained-at-cutoff-v1"
        )
        members = ("0001", "missing-price")
        first = resolve_prices(history, members, date(2026, 1, 1), NOW)
        second = resolve_prices(history, members, date(2026, 1, 1), NOW + timedelta(days=1))
        third = resolve_prices(history, members, date(2026, 1, 1), NOW + timedelta(days=2))
        assert first.to_pylist() == [
            {
                "listing_id": "0001",
                "session_date": date(2026, 1, 1),
                "close": Decimal("100"),
                "occurrence_id": original.occurrence_id,
                "missing_reason": None,
            },
            {
                "listing_id": "missing-price",
                "session_date": date(2026, 1, 1),
                "close": None,
                "occurrence_id": None,
                "missing_reason": "missing_price",
            },
        ]
        assert second["close"].to_pylist() == [Decimal("90"), None]
        assert second["occurrence_id"][0].as_py() == revised.occurrence_id
        assert third["close"].to_pylist() == [None, None]
        assert third["occurrence_id"][0].as_py() == retracted.occurrence_id
        assert third["missing_reason"][0].as_py() == "source_retracted"
        resolved = resolved_result(
            history,
            first,
            tmp_path / "resolved",
            recipe="tiny-price-v1",
            cutoff=NOW,
            members=members,
        )
        assert resolved.manifest["kind"] == "resolved_result"
        assert resolved.manifest["selected_occurrences"] == [original.occurrence_id]
        assert resolved.table("prices").equals(first)
        assert history.table("occurrences").num_rows == 3
        assert (
            read_bundle(store.root / "snapshots" / "baseline").table("occurrences").num_rows == 1
        )
        backup(store, tmp_path / "backup")
    restore(tmp_path / "backup", tmp_path / "restored")
    with Store(tmp_path / "restored") as restored:
        assert restored.read_table("equity_daily")["close"].to_pylist() == [
            Decimal("100"),
            Decimal("90"),
        ]
        assert restored.connection.execute("SELECT count(*) FROM coverage").fetchone() == (3,)
        assert (
            read_bundle(restored.root / "snapshots" / "baseline").table("occurrences").num_rows
            == 1
        )
    artifact = next((tmp_path / "backup").rglob("*.parquet"))
    artifact.write_bytes(artifact.read_bytes()[:20])
    with pytest.raises(ValidationError, match="checksum"):
        restore(tmp_path / "backup", tmp_path / "bad-restore")
    assert not (tmp_path / "bad-restore").exists()


def test_corruption_incomplete_manifest_and_snapshot_fault(tmp_path: Path) -> None:
    out = tmp_path / "out"
    write_direct(example(), out)
    (out / "equity_daily.parquet").write_bytes(b"truncated")
    with pytest.raises(ValidationError, match="checksum"):
        read_bundle(out)
    incomplete = tmp_path / "incomplete"
    incomplete.mkdir()
    with pytest.raises(ValidationError, match="manifest"):
        read_bundle(incomplete)
    with Store(tmp_path / "store") as store:
        publish(store, example())

        def fail(point: str) -> None:
            if point == "before_manifest":
                raise OSError(errno.ENOSPC, "full")

        with pytest.raises(OSError):
            history_bundle(store, "bad", recipe="v1", policy="retained-at-cutoff-v1", fault=fail)
        assert not (store.root / "snapshots" / "bad").exists()


def test_csv_nested_null_empty_literal_and_leading_zero_values(tmp_path: Path) -> None:
    batch = financial_example()
    name, table = batch.tables[1]
    row = table.to_pylist()[0]
    row.update(raw_value='null,\r\n"quoted" é', decimals="", precision="0001")
    batch = replace(
        batch,
        tables=(
            batch.tables[0],
            (name, pa.Table.from_pylist([row], schema=table.schema)),
            batch.tables[2],
        ),
    )
    write_direct(batch, tmp_path / "csv", encoding="csv")
    result = read_bundle(tmp_path / "csv")
    assert result.table(name).equals(batch.tables[1][1])
    assert result.table(name)["decimals"][0].as_py() == ""
    assert result.table(name)["precision"][0].as_py() == "0001"


def test_two_reader_processes_remain_pinned_during_refresh(tmp_path: Path) -> None:
    import subprocess
    import sys
    from concurrent.futures import ThreadPoolExecutor

    child = """
import sys
from pathlib import Path
from niftyverse.storage.bundles import read_bundle
bundle = read_bundle(Path(sys.argv[1]))
print(bundle.table('equity_daily')['close'][0].as_py(), flush=True)
sys.stdin.readline()
print(bundle.table('equity_daily')['close'][0].as_py(), flush=True)
"""
    with Store(tmp_path / "store") as store:
        publish(store, example())
        pinned = history_bundle(store, "old", recipe="v1", policy="retained-at-cutoff-v1")
        readers = [
            subprocess.Popen(
                [sys.executable, "-c", child, str(pinned.path)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            for _ in range(2)
        ]
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                ready = [pool.submit(p.stdout.readline) for p in readers if p.stdout]
                assert [f.result(timeout=15).strip() for f in ready] == ["1.25000000"] * 2
            revised = replace(
                example("2.5000", check="new"),
                checked_at=NOW + timedelta(days=1),
                known_at=NOW + timedelta(days=1),
            )
            publish(store, revised)
            fresh = history_bundle(store, "new", recipe="v1", policy="retained-at-cutoff-v1")
            assert fresh.manifest["snapshot_id"] != pinned.manifest["snapshot_id"]
            for process in readers:
                output, errors = process.communicate("continue\n", timeout=15)
                assert process.returncode == 0, errors
                assert output.strip() == "1.25000000"
        finally:
            for process in readers:
                if process.poll() is None:
                    process.kill()
                    process.communicate()


def test_collected_later_cannot_backdate_and_resolved_cannot_relabel(tmp_path: Path) -> None:
    with Store(tmp_path / "store") as store:
        publish(store, replace(example(), checked_at=NOW + timedelta(days=2)))
        history = history_bundle(store, "history", recipe="v1", policy="retained-at-cutoff-v1")
    members = ("0001",)
    before = resolve_prices(history, members, date(2026, 1, 1), NOW)
    assert before["close"].to_pylist() == [None]
    after = resolve_prices(history, members, date(2026, 1, 1), NOW + timedelta(days=2))
    assert after["close"].to_pylist() == [Decimal("1.25")]
    with pytest.raises(ValidationError, match="pinned selection"):
        resolved_result(
            history, after, tmp_path / "false", recipe="v1", cutoff=NOW, members=members
        )
    assert not (tmp_path / "false").exists()


def test_reader_parses_exact_checksum_verified_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "out"
    write_direct(example(), destination)
    bundle = read_bundle(destination)
    original = Path.read_bytes

    def replace_after_read(path: Path) -> bytes:
        payload = original(path)
        if path.name == "equity_daily.parquet":
            path.write_bytes(b"corrupt-after-capture")
        return payload

    monkeypatch.setattr(Path, "read_bytes", replace_after_read)
    assert bundle.table("equity_daily")["close"].to_pylist() == [Decimal("1.25")]


def test_real_artifact_write_failure_never_publishes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from niftyverse.storage import bundles

    def full(*_: object, **__: object) -> None:
        raise OSError(errno.ENOSPC, "full during file write")

    monkeypatch.setattr(bundles, "sync_file", full)
    with pytest.raises(OSError):
        write_direct(example(), tmp_path / "new")
    assert not (tmp_path / "new").exists()
    assert not list(tmp_path.iterdir())


def test_final_directory_sync_failure_removes_ready_marker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from niftyverse.storage import bundles

    destination = tmp_path / "new"
    from niftyverse.storage.durable import sync_directory as sync

    def fail(path: Path) -> None:
        if path == destination.parent and destination.exists():
            raise OSError(errno.ENOSPC, "final directory sync")
        sync(path)

    monkeypatch.setattr(bundles, "sync_directory", fail)
    with pytest.raises(OSError, match="final directory"):
        write_direct(example(), destination)
    assert not (destination / "manifest.json").exists()


def test_etf_sdk_capture_and_lazy_parquet_inspection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from niftyverse.storage.bundles import Bundle, scan_polars

    batch = example()
    row = batch.tables[0][1].to_pylist()[0]
    row["quantity_unit"] = "fund_units"
    batch = replace(
        batch,
        partition=replace(batch.partition, dataset="etf_daily"),
        capture=replace(batch.capture, kind="sdk_result", sdk_version="owned-sdk-1"),
        tables=(("etf_daily", pa.Table.from_pylist([row], schema=batch.tables[0][1].schema)),),
    )
    with Store(tmp_path / "store") as store:
        publish(store, batch)
        expected = store.read_table("etf_daily").drop(["occurrence_id"])
    write_direct(batch, tmp_path / "out")
    bundle = read_bundle(tmp_path / "out")
    assert bundle.manifest["batch"]["capture"]["kind"] == "sdk_result"
    assert bundle.manifest["batch"]["capture"]["sdk_version"] == "owned-sdk-1"
    assert bundle.table("etf_daily").equals(expected)

    def no_materialized_table(*_: object) -> None:
        raise AssertionError("lazy scan materialized an Arrow table")

    monkeypatch.setattr(Bundle, "table", no_materialized_table)
    lazy = scan_polars(bundle, "etf_daily")
    assert "Parquet SCAN" in lazy.explain()
    assert lazy.select("close").collect()["close"].to_list() == [Decimal("1.25")]


def test_history_and_backup_retain_quarantine_capture_references(tmp_path: Path) -> None:
    batch = replace(example(), coverage="quarantined", reason="failed-page")
    with Store(tmp_path / "store") as store:
        with pytest.raises(ValidationError, match="quarantined"):
            publish(store, batch)
        history = history_bundle(store, "quarantine", recipe="v1", policy="retained-at-cutoff-v1")
        assert history.table("equity_daily").num_rows == 0
        assert history.table("jobs")["status"].to_pylist() == ["quarantined"]
        assert (history.path / "raw" / batch.capture.sha256).read_bytes() == batch.capture.body
        backup(store, tmp_path / "backup")
    restore(tmp_path / "backup", tmp_path / "restored")
    raw = tmp_path / "restored/raw/sha256" / batch.capture.sha256[:2] / batch.capture.sha256
    assert raw.read_bytes() == batch.capture.body
    with Store(tmp_path / "restored") as store:
        assert store.connection.execute("SELECT status FROM jobs").fetchone() == ("quarantined",)
