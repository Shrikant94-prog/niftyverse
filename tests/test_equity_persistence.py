"""Actual additive migrations and identical typed equity details across sinks."""

from dataclasses import replace
from pathlib import Path

import duckdb
import pytest
from test_equity_json import D1, D2, wire
from test_equity_selection import KNOWN, calendar, catalogue

from niftyverse.adapters.equity_json import decode_equity_json
from niftyverse.batches import Capture, Partition, ValidatedBatch
from niftyverse.identity import ListingSelectionPolicy
from niftyverse.market_prices import MarketDataFailure, normalize_equities
from niftyverse.storage.bundles import read_bundle, write_direct
from niftyverse.storage.catalog import Store, migrate
from niftyverse.storage.equity import make_price_batch


def batch() -> ValidatedBatch:
    body = wire()
    rows = decode_equity_json(body, source_id="owned", locator="p")
    result = normalize_equities(
        rows,
        catalogue=catalogue(),
        calendar=calendar(),
        instrument_ids=("a",),
        start=D1,
        end=D2,
        known_at=KNOWN,
        policy=ListingSelectionPolicy("ordinary"),
        source_complete=True,
    )
    partition = Partition(
        "equity_daily",
        D1,
        D2,
        ("a-eq",),
        ("close", "quantity", "delivery_fraction"),
        "raw_traded",
        "nse_equity_json_v1",
        "dated",
        "quality-v1",
        "owned row count and grid",
    )
    return make_price_batch(
        result,
        partition=partition,
        capture=Capture(body, "direct_raw", "owned", "owned:p"),
        check_id="new-equity",
        checked_at=KNOWN,
        known_at=KNOWN,
    )


@pytest.mark.parametrize("encoding", ["csv", "parquet"])
def test_prices_details_and_delivery_have_db_direct_parity(tmp_path: Path, encoding: str) -> None:
    from niftyverse.storage.publication import publish

    source = batch()
    with Store(tmp_path / "store") as store:
        publish(store, source)
        expected = {
            name: store.read_table(name).drop(["occurrence_id"]) for name, _ in source.tables
        }
    write_direct(source, tmp_path / "direct", encoding=encoding)
    bundle = read_bundle(tmp_path / "direct")
    assert all(bundle.table(name).equals(table) for name, table in expected.items())
    detail = bundle.table("security_daily_details").to_pylist()[0]
    assert str(detail["delivery_fraction"]) == "0.400000000000" and detail["trades"] == 3
    assert str(detail["published_delivery_percent"]) == "40.00000000"
    assert detail["settlement_price"] is None and detail["quantity_unit"] == "shares"


def test_capture_mismatch_and_forged_fraction_reject_without_effect(tmp_path: Path) -> None:
    source = batch()
    with pytest.raises(MarketDataFailure, match="capture"):
        replace(source, capture=Capture(b"different", "direct_raw", "owned", "owned:p"))
    name, table = source.tables[1]
    rows = table.to_pylist()
    rows[0]["delivery_fraction"] = None
    import pyarrow as pa

    with pytest.raises(MarketDataFailure, match="delivery"):
        bad = replace(
            source,
            tables=(source.tables[0], (name, pa.Table.from_pylist(rows, schema=table.schema))),
        )
        write_direct(bad, tmp_path / "bad")
    assert not (tmp_path / "bad").exists()


def test_details_cannot_disagree_with_selected_price_quantity(tmp_path: Path) -> None:
    import pyarrow as pa

    source = batch()
    name, table = source.tables[1]
    rows = table.to_pylist()
    rows[0].update(
        comparable_quantity=20, published_delivery_percent=20, delivery_fraction="0.200000000000"
    )
    from decimal import Decimal

    rows[0]["delivery_fraction"] = Decimal("0.200000000000")
    rows[0]["published_delivery_percent"] = Decimal(20)
    with pytest.raises(MarketDataFailure, match="price_details"):
        bad = replace(
            source,
            tables=(source.tables[0], (name, pa.Table.from_pylist(rows, schema=table.schema))),
        )
        write_direct(bad, tmp_path / "bad-quantity")
    assert not (tmp_path / "bad-quantity").exists()


def test_v3_to_v4_rollback_backup_and_new_details(tmp_path: Path) -> None:
    path = tmp_path / "store"
    with Store(path) as store:
        assert store.connection.execute(
            "SELECT max(version) FROM schema_migrations"
        ).fetchone() == (6,)
    # Independently construct the actual pre-upgrade schema, not a renamed v4 DB.
    old = tmp_path / "old.duckdb"
    with duckdb.connect(str(old)) as conn:
        migrate(conn, target=3)
        conn.execute("CREATE TABLE owner_marker AS SELECT 7 AS value")

        def fail() -> None:
            raise OSError("injected migration failure")

        with pytest.raises(OSError, match="injected"):
            migrate(conn, fault=fail)
        assert conn.execute("SELECT max(version) FROM schema_migrations").fetchone() == (3,)
        assert conn.execute(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_name='security_daily_details'"
        ).fetchone() == (0,)
        assert conn.execute("SELECT value FROM owner_marker").fetchone() == (7,)
        migrate(conn)
        assert conn.execute("SELECT count(*) FROM security_daily_details").fetchone() == (0,)


def test_real_store_upgrade_keeps_v3_backup_and_marker(tmp_path: Path) -> None:
    root = tmp_path / "v3-store"
    root.mkdir()
    with duckdb.connect(str(root / "catalog.duckdb")) as conn:
        migrate(conn, target=3)
        conn.execute("CREATE TABLE owner_marker AS SELECT 19 AS value")
    with Store(root) as store:
        assert store.connection.execute("SELECT value FROM owner_marker").fetchone() == (19,)
        assert store.read_table("security_daily_details").num_rows == 0
        backups = list(store.location.paths["backups"].glob("pre-migration-v3-*.duckdb"))
        assert len(backups) == 1
    with duckdb.connect(str(backups[0]), read_only=True) as conn:
        assert conn.execute("SELECT max(version) FROM schema_migrations").fetchone() == (3,)
        assert conn.execute("SELECT value FROM owner_marker").fetchone() == (19,)


def test_delivery_only_output_retains_units_without_inventing_prices(tmp_path: Path) -> None:
    from datetime import date

    from test_equity_reports import DELIVERY_HEADER, DELIVERY_ROW

    from niftyverse.adapters.equity_reports import decode_delivery
    from niftyverse.delivery import normalize_deliveries

    body = DELIVERY_HEADER + DELIVERY_ROW
    on = date(2026, 10, 16)
    report = decode_delivery(body, session=on, source_id="owned", expected_rows=1)
    # Catalogue alias in this independently supplied fixture identifies ABC.
    cat = catalogue()
    cat = replace(cat, aliases=tuple(replace(a, identifier="ABC") for a in cat.aliases))
    result = normalize_deliveries(
        report.rows,
        catalogue=cat,
        calendar=calendar(),
        instrument_ids=("a",),
        start=on,
        end=date(2026, 10, 17),
        known_at=KNOWN,
        policy=ListingSelectionPolicy("ordinary"),
        source_complete=report.complete,
    )
    part = Partition(
        "security_daily_details",
        on,
        date(2026, 10, 17),
        ("a-eq",),
        ("delivery_fraction",),
        "traded_security_units",
        "delivery_csv_v1",
        "dated",
        "quality-v1",
        "owned count",
    )
    published = make_price_batch(
        result,
        partition=part,
        capture=Capture(body, "direct_raw", "owned", "owned:d"),
        check_id="delivery-only",
        checked_at=KNOWN,
        known_at=KNOWN,
    )
    assert [name for name, _ in published.tables] == ["security_daily_details"]
    write_direct(published, tmp_path / "delivery")
    table = read_bundle(tmp_path / "delivery").table("security_daily_details").to_pylist()
    assert str(table[0]["source_turnover"]) == "0.00015000"
    assert (
        table[0]["source_turnover_unit"] == "INR_lakh"
        and str(table[0]["delivery_fraction"]) == "0.400000000000"
    )


def test_complete_factory_requires_explicit_source_evidence() -> None:
    body = wire()
    result = normalize_equities(
        decode_equity_json(body, source_id="owned", locator="p"),
        catalogue=catalogue(),
        calendar=calendar(),
        instrument_ids=("a",),
        start=D1,
        end=D2,
        known_at=KNOWN,
        policy=ListingSelectionPolicy("ordinary"),
        source_complete=True,
    )
    with pytest.raises(MarketDataFailure, match="completeness"):
        make_price_batch(
            result,
            partition=replace(batch().partition, completeness_evidence=""),
            capture=Capture(body, "direct_raw", "owned", "owned:p"),
            check_id="empty-proof",
            checked_at=KNOWN,
            known_at=KNOWN,
        )


def test_requested_unknown_quantity_and_fraction_cannot_appear_complete() -> None:
    body = wire(CH_TOT_TRADED_QTY=None)
    result = normalize_equities(
        decode_equity_json(body, source_id="owned", locator="p"),
        catalogue=catalogue(),
        calendar=calendar(),
        instrument_ids=("a",),
        start=D1,
        end=D2,
        known_at=KNOWN,
        policy=ListingSelectionPolicy("ordinary"),
        source_complete=True,
    )
    candidate = make_price_batch(
        result,
        partition=batch().partition,
        capture=Capture(body, "direct_raw", "owned", "owned:p"),
        check_id="null-quantity",
        checked_at=KNOWN,
        known_at=KNOWN,
    )
    assert candidate.coverage == "partial"
    assert "field_gaps" in candidate.partition.completeness_evidence
