"""Independent Phase 04 storage contracts, using real stores and processes."""

import os
import subprocess
import sys
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import duckdb
import pyarrow as pa
import pytest

from niftyverse.batches import Capture, Partition, ValidatedBatch
from niftyverse.core import ValidationError
from niftyverse.storage.catalog import Store, migrate
from niftyverse.storage.paths import diagnose_store
from niftyverse.storage.schemas import SCHEMAS

NOW = datetime(2026, 1, 2, tzinfo=UTC)


def example(value: str = "1.2500", *, check: str = "check-1") -> ValidatedBatch:
    partition = Partition(
        "equity_daily",
        date(2026, 1, 1),
        date(2026, 1, 2),
        ("0001",),
        ("close",),
        "raw",
        "synthetic-v1",
        "identity-v1",
        "quality-v1",
        "single-session selected listing; source row count verified",
    )
    capture = Capture(b"owned-source-" + value.encode(), "direct_raw", "owned", "local:owned")
    rows = [
        {
            "listing_id": "0001",
            "series": "EQ",
            "session_date": date(2026, 1, 1),
            "open": None,
            "high": None,
            "low": None,
            "close": Decimal(value),
            "quantity": None,
            "quantity_unit": "shares",
            "turnover": None,
            "currency": "INR",
            "locator": "row:1",
            "missing_reason": None,
        }
    ]
    return ValidatedBatch(
        partition,
        capture,
        check,
        NOW,
        NOW,
        None,
        "active",
        None,
        (("equity_daily", pa.Table.from_pylist(rows, schema=SCHEMAS["equity_daily"])),),
        "complete",
        "schema-v1",
        "normalizer-v1",
    )


def test_batch_rejects_poison_duplicates_scope_and_unknown_types() -> None:
    batch = example()
    table = batch.tables[0][1]
    with pytest.raises(ValidationError, match="duplicate"):
        replace(batch, tables=(("equity_daily", pa.concat_tables([table, table])),))
    with pytest.raises(ValidationError, match="scope"):
        replace(batch, partition=replace(batch.partition, universe=("other",)))
    with pytest.raises(ValidationError, match="schema"):
        replace(
            batch,
            tables=(
                (
                    "equity_daily",
                    table.cast(
                        pa.schema(
                            [
                                pa.field(
                                    f.name,
                                    pa.float64() if f.name == "close" else f.type,
                                    f.nullable,
                                )
                                for f in table.schema
                            ]
                        )
                    ),
                ),
            ),
        )
    with pytest.raises(ValidationError, match="UTC"):
        replace(batch, checked_at=NOW.replace(tzinfo=None))
    with pytest.raises(ValidationError, match="withdrawal"):
        replace(batch, state="withdrawn")
    with pytest.raises(ValidationError, match="SDK"):
        replace(batch.capture, kind="sdk_result")


def test_partition_identity_preserves_scope_fields_and_basis() -> None:
    part = example().partition
    assert (
        len(
            {
                part.identity,
                replace(part, universe=("0002",)).identity,
                replace(part, fields=("open",)).identity,
                replace(part, basis="adjusted").identity,
            }
        )
        == 4
    )
    assert (
        replace(part, universe=("0002", "0001")).identity
        == replace(part, universe=("0001", "0002")).identity
    )


def test_catalog_typed_schema_and_old_metadata_migration(tmp_path: Path) -> None:
    root = tmp_path / "store"
    with Store(root) as store:
        assert store.connection.execute(
            "SELECT max(version) FROM schema_migrations"
        ).fetchone() == (5,)
        for name, schema in SCHEMAS.items():
            table = store.read_table(name)
            assert table.schema.remove(0).equals(schema, check_metadata=False)
    legacy = tmp_path / "legacy.duckdb"
    with duckdb.connect(str(legacy)) as conn:
        migrate(conn, target=1)
        conn.execute("INSERT INTO captures VALUES ('hash', 'direct_raw', 'source', 'local:x', 1)")
        migrate(conn)
        assert conn.execute("SELECT sdk_version FROM captures").fetchone() == (None,)
        assert conn.execute("SELECT source_id FROM captures").fetchone() == ("source",)
    with duckdb.connect(str(tmp_path / "rollback.duckdb")) as conn:
        migrate(conn, target=1)
        with pytest.raises(RuntimeError, match="injected"):
            migrate(conn, fault=lambda: (_ for _ in ()).throw(RuntimeError("injected")))
        assert conn.execute("SELECT max(version) FROM schema_migrations").fetchone() == (1,)
        assert "sdk_version" not in [
            r[1] for r in conn.execute("PRAGMA table_info('captures')").fetchall()
        ]


def test_cross_process_writer_contention_is_bounded(tmp_path: Path) -> None:
    root = tmp_path / "store"
    child = """
import sys
from pathlib import Path
from niftyverse.storage.catalog import Store, WriterBusy
try:
    with Store(Path(sys.argv[1]), lock_timeout=0.1): pass
except WriterBusy:
    print('writer rejected')
else:
    raise AssertionError('second writer admitted')
"""
    with Store(root):
        result = subprocess.run(
            [sys.executable, "-c", child, str(root)], text=True, capture_output=True, timeout=15
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "writer rejected"
    with Store(root):
        pass


def test_path_diagnostics_are_nonmutating_and_explicit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "local-data"))
    default = diagnose_store()
    assert not default.risks
    assert all(path.is_relative_to(default.root) for path in default.paths.values())
    assert not default.root.exists()
    risk = diagnose_store(tmp_path / "OneDrive" / "active")
    assert "unsupported" in " ".join(risk.risks)
    assert not risk.root.exists()
    network = diagnose_store(
        Path("//server/share/store") if os.name == "nt" else Path("/net/share")
    )
    assert network.risks
    with pytest.warns(UserWarning, match="unsupported"):
        with Store(risk.root):
            pass


def test_etf_units_and_filing_dimensions_have_typed_identity() -> None:
    batch = example()
    price = batch.tables[0][1].to_pylist()[0]
    etf = replace(batch.partition, dataset="etf_daily")
    with pytest.raises(ValidationError, match="quantity unit"):
        replace(
            batch,
            partition=etf,
            tables=(("etf_daily", pa.Table.from_pylist([price], schema=SCHEMAS["etf_daily"])),),
        )
    price["quantity_unit"] = "fund_units"
    valid = replace(
        batch,
        partition=etf,
        tables=(("etf_daily", pa.Table.from_pylist([price], schema=SCHEMAS["etf_daily"])),),
    )
    assert valid.tables[0][1]["close"][0].as_py() == Decimal("1.25000000")
    with pytest.raises(ValidationError, match="dataset"):
        replace(batch, partition=etf)


def financial_example() -> ValidatedBatch:
    batch = example()
    dimension = {
        "axis": "{urn:test}Region",
        "member": "{urn:test}India",
        "typed_xml": None,
        "container": "segment",
    }
    doc = {
        "document_id": "doc",
        "filing_id": "filing",
        "raw_sha256": batch.capture.sha256,
        "format": "xml",
        "parser_version": "parser-v1",
        "taxonomy_version": "tax-v1",
        "taxonomy_sha256": "a" * 64,
        "publication_time": None,
        "publication_precision": "unknown",
    }
    source = {
        "assertion_id": "fact",
        "document_id": "doc",
        "concept": "{urn:test}Revenue",
        "context_id": "c1",
        "entity": "issuer",
        "entity_scheme": "urn:entity",
        "period_start": date(2025, 10, 1),
        "period_end": date(2025, 12, 31),
        "instant": None,
        "dimensions": [dimension],
        "context_xml": "<context/>",
        "unit_numerator": ["{urn:iso}INR"],
        "unit_denominator": [],
        "value": "100.000",
        "raw_value": "100.000",
        "nil": False,
        "decimals": "3",
        "precision": None,
        "locator": "fact:1",
        "mapping_status": "reported",
    }
    fact = {
        "assertion_id": "fact",
        "entity_id": "issuer",
        "concept": "{urn:test}Revenue",
        "period_start": date(2025, 10, 1),
        "period_end": date(2025, 12, 31),
        "period_kind": "duration",
        "basis": "standalone",
        "scope": "company",
        "unit": "INR",
        "dimensions": [dimension],
        "value": Decimal("100"),
        "additivity": "additive_duration",
        "derivation": "reported",
    }
    tables = tuple(
        (name, pa.Table.from_pylist(rows, schema=SCHEMAS[name]))
        for name, rows in (
            ("filing_documents", [doc]),
            ("filing_source_assertions", [source]),
            ("financial_facts", [fact]),
        )
    )
    return replace(
        batch, partition=replace(batch.partition, dataset="financial_facts"), tables=tables
    )


def test_financial_analytical_keys_and_additivity(tmp_path: Path) -> None:
    batch = financial_example()
    name, table = batch.tables[-1]
    row = table.to_pylist()[0]
    incompatible = {**row, "basis": "consolidated"}
    valid = replace(
        batch,
        tables=(
            *batch.tables[:-1],
            (name, pa.Table.from_pylist([row, incompatible], schema=SCHEMAS[name])),
        ),
    )
    with Store(tmp_path / "store") as store:
        assert (
            store.read_table(name).schema.field("dimensions").type
            == SCHEMAS[name].field("dimensions").type
        )
    assert valid.tables[-1][1].num_rows == 2
    with pytest.raises(ValidationError, match="nonadditive"):
        replace(
            batch,
            tables=(
                *batch.tables[:-1],
                (
                    name,
                    pa.Table.from_pylist(
                        [{**row, "additivity": "nonadditive", "derivation": "difference"}],
                        schema=SCHEMAS[name],
                    ),
                ),
            ),
        )
    with pytest.raises(ValidationError, match="capture"):
        replace(batch, capture=replace(batch.capture, body=b"unrelated"))


def test_doctor_reports_paths_without_opening_store(tmp_path: Path) -> None:
    from click.testing import CliRunner

    from niftyverse.cli import main

    root = tmp_path / "OneDrive" / "store"
    result = CliRunner().invoke(main, ["doctor", "--store", str(root)])
    assert result.exit_code == 0
    assert "unsupported" in result.output
    assert "catalog.duckdb" in result.output and "spill" in result.output
    assert not root.exists()


def test_explicit_open_backs_up_old_catalog_and_keeps_occurrences_distinct(tmp_path: Path) -> None:
    root = tmp_path / "store"
    root.mkdir()
    with duckdb.connect(str(root / "catalog.duckdb")) as conn:
        migrate(conn, target=1)
        conn.execute("INSERT INTO captures VALUES ('shared', 'direct_raw', 'owned', 'local:x', 1)")
        for occurrence in ("first-A", "later-A"):
            conn.execute(
                "INSERT INTO occurrences VALUES (?, 'partition', 'same-content', 'shared', "
                "'active', NULL, ?, ?, NULL, 'v1', 'v1')",
                [occurrence, NOW, NOW],
            )
        conn.execute(
            "INSERT INTO source_checks VALUES "
            "('check', 'request', 'partition', 'later-A', ?, NULL)",
            [NOW],
        )
    with Store(root) as store:
        assert store.connection.execute("SELECT count(*) FROM occurrences").fetchone() == (2,)
        assert store.connection.execute("SELECT count(*) FROM captures").fetchone() == (1,)
        assert store.connection.execute("SELECT count(*) FROM source_checks").fetchone() == (1,)
    (backup_path,) = (root / "backups").glob("pre-migration-v1-*.duckdb")
    with duckdb.connect(str(backup_path), read_only=True) as conn:
        assert conn.execute("SELECT max(version) FROM schema_migrations").fetchone() == (1,)
        assert conn.execute("SELECT origin FROM captures").fetchone() == ("local:x",)


def test_dimension_order_does_not_create_a_new_analytical_fact() -> None:
    batch = financial_example()
    name, table = batch.tables[-1]
    row = table.to_pylist()[0]
    dimension = {
        "axis": "{urn:test}Product",
        "member": "{urn:test}Steel",
        "typed_xml": None,
        "container": "segment",
    }
    row["dimensions"].append(dimension)
    duplicate = {**row, "dimensions": list(reversed(row["dimensions"])), "assertion_id": "another"}
    source_name, source_table = batch.tables[1]
    source = source_table.to_pylist()[0]
    source2 = {**source, "assertion_id": "another"}
    with pytest.raises(ValidationError, match="analytical key"):
        replace(
            batch,
            tables=(
                batch.tables[0],
                (source_name, pa.Table.from_pylist([source, source2], schema=source_table.schema)),
                (name, pa.Table.from_pylist([row, duplicate], schema=table.schema)),
            ),
        )


@pytest.mark.parametrize("timeout", [-1.0, float("inf"), float("nan")])
def test_unbounded_lock_timeout_rejects_without_files(tmp_path: Path, timeout: float) -> None:
    with pytest.raises(ValueError, match="timeout"):
        Store(tmp_path / "never-created", lock_timeout=timeout)
    assert not list(tmp_path.iterdir())
