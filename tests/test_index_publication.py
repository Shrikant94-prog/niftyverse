"""Typed persistent/direct index publication, invalid-input atomicity and migration."""

from dataclasses import replace
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa
import pytest
from test_index_datasets import tri_wire, tris, valuation_wire, values
from test_index_price_adapter import decode, wire
from test_indices import D1, D2, GROSS, KNOWN, NET, PRICE, calendar

from niftyverse.batches import Capture, Partition, ValidatedBatch
from niftyverse.core import ValidationError
from niftyverse.indices import index_history
from niftyverse.storage.bundles import read_bundle, write_direct
from niftyverse.storage.catalog import Store, migrate
from niftyverse.storage.indices import make_index_batch
from niftyverse.storage.publication import publish
from niftyverse.storage.snapshots import backup, restore


def batch(dataset: str = "index_daily", kind: str = "price") -> ValidatedBatch:
    variant = GROSS if kind == "gross_tri" else NET if kind == "net_tri" else PRICE
    body = (
        wire()
        if dataset == "index_daily"
        else valuation_wire()
        if dataset == "index_valuations"
        else tri_wire("14 Oct 2026")
    )
    rows: Any = (
        decode(body)
        if dataset == "index_daily"
        else values(body)
        if dataset == "index_valuations"
        else tris(body, variant)
    )
    history = index_history(
        rows,
        variant=variant,
        start=D1,
        end=D2,
        calendar=calendar(),
        known_at=KNOWN,
        source_complete=True,
    )
    fields = (
        ("close",)
        if dataset == "index_daily"
        else ("pe", "pb", "dividend_yield")
        if dataset == "index_valuations"
        else ("value",)
    )
    part = Partition(
        dataset,
        D1,
        D2,
        (variant.variant_id,),
        fields,
        "valuation_ratios_percent" if dataset == "index_valuations" else variant.kind,
        "owned-v1",
        "explicit-index",
        "no-fill",
        "owned expected grid/count",
    )
    return make_index_batch(
        history,
        partition=part,
        capture=Capture(body, "direct_raw", "owned", "owned:wire"),
        check_id=dataset + kind,
        checked_at=KNOWN,
        known_at=KNOWN,
    )


@pytest.mark.parametrize(
    "dataset,kind",
    [
        ("index_daily", "price"),
        ("index_tri", "gross_tri"),
        ("index_tri", "net_tri"),
        ("index_valuations", "price"),
    ],
)
@pytest.mark.parametrize("encoding", ["csv", "parquet"])
def test_db_and_direct_typed_index_values_match(
    tmp_path: Path, dataset: str, kind: str, encoding: str
) -> None:
    source = batch(dataset, kind)
    with Store(tmp_path / "store") as store:
        publish(store, source)
        expected = store.read_table(dataset).drop(["occurrence_id"])
    write_direct(source, tmp_path / "direct", encoding=encoding)
    actual = read_bundle(tmp_path / "direct").table(dataset)
    assert expected.equals(actual) and actual.num_rows == 1
    assert actual.to_pylist()[0]["variant_kind"] == kind
    assert actual.to_pylist()[0]["raw_sha256"] == source.capture.sha256


@pytest.mark.parametrize(
    "dataset,change,reason",
    [
        ("index_daily", {"variant_kind": "gross_tri"}, "variant"),
        ("index_daily", {"unit": "INR"}, "unit"),
        ("index_daily", {"low": 24000}, "OHLC"),
        ("index_daily", {"variant_id": "other"}, "scope"),
        ("index_daily", {"raw_sha256": "a" * 64}, "capture"),
        ("index_tri", {"variant_kind": "price"}, "variant"),
        ("index_valuations", {"variant_kind": "net_tri"}, "variant"),
        ("index_valuations", {"yield_unit": "fraction"}, "unit"),
        ("index_valuations", {"pe": None, "pe_reason": None}, "reason"),
        ("index_valuations", {"pb": None, "pb_reason": "source_null"}, "complete"),
    ],
)
def test_shared_validation_rejects_poison_without_opening_destination(
    tmp_path: Path,
    dataset: str,
    change: dict[str, Any],
    reason: str,
) -> None:
    source = batch(dataset, "gross_tri" if dataset == "index_tri" else "price")
    name, table = source.tables[0]
    rows = table.to_pylist()
    rows[0].update(change)
    with pytest.raises(ValidationError, match=reason):
        bad = replace(source, tables=((name, pa.Table.from_pylist(rows, schema=table.schema)),))
        write_direct(bad, tmp_path / "bad")
    assert not (tmp_path / "bad").exists()


def test_partition_basis_and_source_mismatch_reject() -> None:
    source = batch()
    with pytest.raises(ValidationError, match="basis"):
        replace(source, partition=replace(source.partition, basis="gross_tri"))
    with pytest.raises(ValidationError, match="capture"):
        replace(source, capture=Capture(b"wrong", "direct_raw", "owned", "owned:p"))


def test_nullable_valuations_publish_explicit_partial_with_zero_retained(tmp_path: Path) -> None:
    body = valuation_wire(pe=None, pb="0", divYield="0")
    history = index_history(
        values(body),
        variant=PRICE,
        start=D1,
        end=D2,
        calendar=calendar(),
        known_at=KNOWN,
        source_complete=True,
    )
    template = batch("index_valuations")
    source = make_index_batch(
        history,
        partition=template.partition,
        capture=Capture(body, "direct_raw", "owned", "owned:v"),
        check_id="null-valuation",
        checked_at=KNOWN,
        known_at=KNOWN,
    )
    assert source.coverage == "partial"
    with pytest.raises(ValidationError, match="partial"):
        write_direct(source, tmp_path / "denied")
    assert not (tmp_path / "denied").exists()
    with Store(tmp_path / "store") as store:
        with pytest.raises(ValidationError, match="partial"):
            publish(store, source)
        assert store.read_table("index_valuations").num_rows == 0
        expected = source.tables[0][1]
    write_direct(source, tmp_path / "partial", allow_partial=True)
    actual = read_bundle(tmp_path / "partial").table("index_valuations")
    assert actual.equals(expected)
    row = actual.to_pylist()[0]
    assert row["pe"] is None and row["pe_reason"] == "source_null"
    assert row["pb"] == 0 and row["dividend_yield"] == 0 and row["pb_reason"] is None


def test_v4_upgrade_is_additive_transactional_and_keeps_backup(tmp_path: Path) -> None:
    root = tmp_path / "store"
    root.mkdir()
    with duckdb.connect(str(root / "catalog.duckdb")) as conn:
        migrate(conn, target=4)
        conn.execute("CREATE TABLE owner_marker AS SELECT 23 AS value")
        assert conn.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_name='index_tri'"
        ).fetchone() == (0,)

        def fail() -> None:
            raise OSError("injected v5 failure")

        with pytest.raises(OSError, match="injected"):
            migrate(conn, fault=fail)
        assert conn.execute("SELECT max(version) FROM schema_migrations").fetchone() == (4,)
        assert conn.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_name='index_daily'"
        ).fetchone() == (0,)
    with Store(root) as store:
        assert store.connection.execute(
            "SELECT max(version) FROM schema_migrations"
        ).fetchone() == (5,)
        assert store.connection.execute("SELECT value FROM owner_marker").fetchone() == (23,)
        publish(store, batch("index_tri", "net_tri"))
        assert store.read_table("index_tri").num_rows == 1
        backups = list(store.location.paths["backups"].glob("pre-migration-v4-*.duckdb"))
        assert len(backups) == 1
    with duckdb.connect(str(backups[0]), read_only=True) as conn:
        assert conn.execute("SELECT max(version) FROM schema_migrations").fetchone() == (4,)
        assert conn.execute("SELECT value FROM owner_marker").fetchone() == (23,)


def test_index_backup_has_actual_schema_and_restores_exact_rows(tmp_path: Path) -> None:
    with Store(tmp_path / "store") as store:
        publish(store, batch("index_valuations"))
        expected = store.read_table("index_valuations")
        saved = backup(store, tmp_path / "backup")
        assert saved.manifest["catalog_version"] == 5
    restore(saved.path, tmp_path / "restored")
    with Store(tmp_path / "restored") as store:
        assert store.read_table("index_valuations").equals(expected)
