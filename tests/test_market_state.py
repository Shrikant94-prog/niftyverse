"""AM-01 independent overlapping-state and publication boundary checks."""

from dataclasses import asdict, replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import duckdb
import pyarrow as pa
import pytest
from test_store_schema import NOW, example

from niftyverse.core import ValidationError
from niftyverse.market_state import MarketStateObservation, state_on
from niftyverse.storage.bundles import read_bundle, write_direct
from niftyverse.storage.catalog import Store, migrate
from niftyverse.storage.publication import publish
from niftyverse.storage.schemas import SCHEMAS


def observation(kind: str = "ASM") -> MarketStateObservation:
    return MarketStateObservation(
        "obs-" + kind,
        "0001",
        "CM",
        kind,
        "present",
        "stage-1",
        date(2026, 1, 1),
        None,
        None,
        NOW,
        None,
        "unknown",
        "Asia/Kolkata",
        None,
        None,
        "source-rule-2026",
        "owned",
        "row:1",
    )


def test_overlap_snapshot_unknown_absence_and_explicit_removal() -> None:
    asm, gsm = observation(), observation("GSM")
    band = replace(
        observation("price_band"),
        lower=Decimal("9.125"),
        upper=None,
        basis="dynamic-operating-range",
    )
    rows = (asm, gsm, band)
    assert state_on(rows, "0001", "CM", "ASM", date(2026, 1, 1), NOW) == (asm,)
    assert state_on(rows, "0001", "CM", "GSM", date(2026, 1, 1), NOW) == (gsm,)
    assert state_on(rows, "0001", "CM", "price_band", date(2026, 1, 1), NOW)[0].upper is None
    # A snapshot and incomplete-list absence establish no historical interval.
    assert state_on(rows, "0001", "CM", "ASM", date(2026, 1, 2), NOW) == ()
    assert state_on(rows, "0002", "CM", "ASM", date(2026, 1, 1), NOW) == ()
    removed = replace(
        asm, observation_id="removed", state="removed", value=None, observed_on=date(2026, 1, 2)
    )
    unknown = replace(removed, observation_id="unknown", state="unknown")
    na = replace(removed, observation_id="na", state="not_applicable")
    assert {r.state for r in (removed, unknown, na)} == {"removed", "unknown", "not_applicable"}
    assert state_on((removed,), "0001", "CM", "ASM", date(2026, 1, 2), NOW) == (removed,)


@pytest.mark.parametrize(
    "changes",
    [
        {"state": "unrestricted"},
        {"lower": 1.25},
        {"lower": Decimal("20"), "upper": Decimal("10")},
        {"effective_to": date(2026, 1, 2)},
        {"publication_precision": "instant"},
        {"state": "removed", "lower": Decimal("1")},
        {"basis": ""},
    ],
)
def test_invalid_state_rejected(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        replace(observation(), **changes)  # type: ignore[arg-type]


def test_effective_interval_known_at_and_date_only_publication() -> None:
    from datetime import timedelta

    row = replace(
        observation(),
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 1, 3),
        publication_precision="date",
        publication_date=date(2026, 1, 1),
    )
    assert row.publication_time is None
    assert state_on((row,), "0001", "CM", "ASM", date(2026, 1, 2), NOW) == (row,)
    assert state_on((row,), "0001", "CM", "ASM", date(2026, 1, 3), NOW) == ()
    assert (
        state_on((row,), "0001", "CM", "ASM", date(2026, 1, 1), NOW - timedelta(seconds=1)) == ()
    )


def test_market_schema_migration_is_additive_and_rolls_back(tmp_path: Path) -> None:
    with duckdb.connect(str(tmp_path / "old.duckdb")) as conn:
        migrate(conn, target=2)
        assert conn.execute(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_name='market_state_observations'"
        ).fetchone() == (0,)
        conn.execute("INSERT INTO captures VALUES ('id', 'direct_raw', 'owned', 'local', 1, NULL)")
        with pytest.raises(RuntimeError, match="injected"):
            migrate(conn, fault=lambda: (_ for _ in ()).throw(RuntimeError("injected")))
        assert conn.execute("SELECT max(version) FROM schema_migrations").fetchone() == (2,)
        assert conn.execute(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_name='market_state_observations'"
        ).fetchone() == (0,)
        migrate(conn)
        assert conn.execute("SELECT source_id FROM captures").fetchone() == ("owned",)
        assert conn.execute("SELECT count(*) FROM market_state_observations").fetchone() == (0,)


def test_retained_v2_backup_restores_then_migrates_on_explicit_open(tmp_path: Path) -> None:
    from niftyverse.storage.bundles import publish_bundle
    from niftyverse.storage.snapshots import restore

    catalog = tmp_path / "v2.duckdb"
    with duckdb.connect(str(catalog)) as conn:
        migrate(conn, target=2)
        conn.execute(
            "INSERT INTO captures VALUES ('old', 'direct_raw', 'retained', 'local', 1, NULL)"
        )
    publish_bundle(
        tmp_path / "backup",
        [],
        {"kind": "backup", "status": "complete", "catalog_version": 2},
        raw=[("catalog.duckdb", catalog)],
    )
    restored = tmp_path / "restored"
    restore(tmp_path / "backup", restored)
    with Store(restored) as store:
        assert store.connection.execute("SELECT source_id FROM captures").fetchone() == (
            "retained",
        )
        assert store.connection.execute(
            "SELECT max(version) FROM schema_migrations"
        ).fetchone() == (3,)
        assert store.read_table("market_state_observations").num_rows == 0
        backups = list(store.location.paths["backups"].glob("pre-migration-v2-*.duckdb"))
        assert len(backups) == 1
    with duckdb.connect(str(backups[0]), read_only=True) as conn:
        assert conn.execute("SELECT max(version) FROM schema_migrations").fetchone() == (2,)


@pytest.mark.parametrize("encoding", ["csv", "parquet"])
def test_shared_validation_db_direct_parity_and_no_side_effects(
    tmp_path: Path, encoding: str
) -> None:
    rows = [asdict(observation()), asdict(observation("GSM"))]
    base = example()
    table = pa.Table.from_pylist(rows, schema=SCHEMAS["market_state_observations"])
    batch = replace(
        base,
        partition=replace(base.partition, dataset="market_state_observations", fields=("state",)),
        tables=(("market_state_observations", table),),
    )
    with Store(tmp_path / "store") as store:
        publish(store, batch)
        expected = store.read_table("market_state_observations").drop(["occurrence_id"])
    write_direct(batch, tmp_path / "direct", encoding=encoding)
    assert read_bundle(tmp_path / "direct").table("market_state_observations").equals(expected)
    rows[0]["state"] = "invalid"
    with pytest.raises(ValidationError, match="state"):
        invalid = replace(
            batch,
            tables=(
                ("market_state_observations", pa.Table.from_pylist(rows, schema=table.schema)),
            ),
        )
        write_direct(invalid, tmp_path / "bad", encoding=encoding)
    assert not (tmp_path / "bad").exists()
    with Store(tmp_path / "store") as store:
        assert store.read_table("market_state_observations").num_rows == 2
