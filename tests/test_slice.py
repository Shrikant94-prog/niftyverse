"""Hand-authored exact-value oracles and validation-before-sink boundaries."""

import dataclasses
import hashlib
import json
from datetime import date
from decimal import Decimal, localcontext
from pathlib import Path

import duckdb
import polars as pl
import pytest
from hypothesis import given
from hypothesis import strategies as st

from niftyverse import build_fixture, extract_fixture
from niftyverse.adapters.fixture import decode_fixture
from niftyverse.core import FixtureBatch, FixtureRow, ValidationError
from niftyverse.storage.csv import read_fixture_bundle

PAYLOAD = Path(__file__).with_name("fixtures").joinpath("observations.json").read_bytes()
EXPECTED = [
    {
        "instrument_id": "0001",
        "session_date": date(2026, 9, 1),
        "close": Decimal("123.4500"),
        "label": "",
    },
    {"instrument_id": "0002", "session_date": date(2026, 9, 2), "close": None, "label": None},
    {
        "instrument_id": "0003",
        "session_date": date(2026, 9, 3),
        "close": Decimal("0.0000"),
        "label": "__NULL__",
    },
    {
        "instrument_id": "0004",
        "session_date": date(2026, 9, 4),
        "close": Decimal("99999999999999.9999"),
        "label": "<script>alert('x')</script>",
    },
]
EXPECTED_SCHEMA = {
    "instrument_id": pl.String,
    "session_date": pl.Date,
    "close": pl.Decimal(precision=18, scale=4),
    "label": pl.String,
}


def test_database_and_direct_values(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "slice.duckdb"
    stored = build_fixture(PAYLOAD, db)
    assert stored.to_polars().to_dicts() == EXPECTED
    assert stored.to_polars().schema == EXPECTED_SCHEMA
    assert stored.committed_rows == 4
    with duckdb.connect(str(db), read_only=True) as connection:
        assert connection.execute("select count(*) from observations").fetchone() == (4,)
        assert connection.execute("describe observations").fetchall()[2][1] == "DECIMAL(18,4)"

    def no_database(*args: object, **kwargs: object) -> None:
        raise AssertionError("direct output opened DuckDB")

    monkeypatch.setattr(duckdb, "connect", no_database)
    direct = extract_fixture(PAYLOAD, tmp_path / "bundle")
    assert direct.to_polars().to_dicts() == EXPECTED
    assert direct.to_polars().schema == EXPECTED_SCHEMA
    replay = read_fixture_bundle(tmp_path / "bundle")
    assert [dataclasses.asdict(row) for row in replay.rows] == EXPECTED
    assert replay.raw_sha256 == hashlib.sha256(PAYLOAD).hexdigest()
    manifest = json.loads((tmp_path / "bundle/manifest.json").read_text())
    assert manifest["capture_kind"] == "owned-fixture-json"
    assert manifest["raw_replay_available"] is False
    assert not list((tmp_path / "bundle").glob("*.duckdb"))


@pytest.mark.parametrize(
    "bad",
    [
        {},
        {"instrument_id": "0001"},
        {"instrument_id": 1, "session_date": "2026-09-01", "close": "1", "label": ""},
        {"instrument_id": "", "session_date": "2026-09-01", "close": "1", "label": ""},
        {"instrument_id": "x", "session_date": "2026-02-30", "close": "1", "label": ""},
        *[
            {"instrument_id": "x", "session_date": "2026-09-01", "close": value, "label": ""}
            for value in [
                "NaN",
                "Infinity",
                "-Infinity",
                "100000000000000",
                "-100000000000000",
                "0.00001",
                0.1,
                True,
            ]
        ],
    ],
)
def test_bad_batch_never_opens_sink(
    bad: dict[str, object],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = tmp_path / "existing.duckdb"
    with duckdb.connect(str(db)) as connection:
        connection.execute(
            "create table sentinel (id varchar); insert into sentinel values ('001')"
        )
    bundle = tmp_path / "existing"
    bundle.mkdir()
    (bundle / "data.csv").write_bytes(b"untouched\r\n")
    (bundle / "manifest.json").write_bytes(b'{"old":true}')
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    calls: list[str] = []

    def denied(*args: object, **kwargs: object) -> None:
        calls.append("open")
        raise AssertionError("invalid batch opened sink")

    monkeypatch.setattr(duckdb, "connect", denied)
    for payload in (json.dumps([bad]).encode(), json.dumps([EXPECTED_WIRE, bad]).encode()):
        for destination in (db, tmp_path / "new.duckdb"):
            with pytest.raises(ValidationError, match="fixture"):
                build_fixture(payload, destination)
        for destination in (bundle, tmp_path / "new-bundle"):
            with pytest.raises(ValidationError, match="fixture"):
                extract_fixture(payload, destination)
    assert not calls
    assert before == {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert not (tmp_path / "new-bundle").exists()
    assert not (tmp_path / "new.duckdb").exists()


EXPECTED_WIRE = {
    "instrument_id": "0001",
    "session_date": "2026-09-01",
    "close": "1.0000",
    "label": "",
}


def test_immutability_and_constructor_validation() -> None:
    batch = decode_fixture(PAYLOAD)
    with pytest.raises(dataclasses.FrozenInstanceError):
        batch.rows[0].close = Decimal("NaN")  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        batch.rows = ()  # type: ignore[misc]
    with pytest.raises(ValidationError):
        FixtureRow("001", date(2026, 9, 1), Decimal("NaN"), "")
    with pytest.raises(ValidationError):
        FixtureBatch([], "0" * 64)  # type: ignore[arg-type]


@pytest.mark.parametrize("payload", [b"not-json", b"{}", b"[null]", b"[]"])
def test_invalid_envelopes(payload: bytes, tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        extract_fixture(payload, tmp_path / "out")
    assert not list(tmp_path.iterdir())


def test_destinations_fail_without_overwrite(tmp_path: Path) -> None:
    db = tmp_path / "slice.duckdb"
    build_fixture(PAYLOAD, db)
    before = db.read_bytes()
    with pytest.raises(FileExistsError):
        build_fixture(PAYLOAD, db)
    assert db.read_bytes() == before
    out = tmp_path / "out"
    extract_fixture(PAYLOAD, out)
    snapshot = {p.name: p.read_bytes() for p in out.iterdir()}
    with pytest.raises(FileExistsError):
        extract_fixture(PAYLOAD, out)
    assert {p.name: p.read_bytes() for p in out.iterdir()} == snapshot


@given(st.integers(min_value=-(10**18 - 1), max_value=10**18 - 1))
def test_exact_decimal_validation_ignores_context(units: int) -> None:
    value = Decimal((int(units < 0), tuple(map(int, str(abs(units)))), -4))
    with localcontext() as context:
        context.prec = 6
        row = FixtureRow("0001", date(2026, 9, 1), value, "")
    assert row.close == value


def test_unsorted_fixture_has_equivalent_order(tmp_path: Path) -> None:
    payload = json.dumps(list(reversed(json.loads(PAYLOAD)))).encode()
    stored = build_fixture(payload, tmp_path / "db.duckdb")
    direct = extract_fixture(payload, tmp_path / "out")
    assert stored.to_polars().to_dicts() == direct.to_polars().to_dicts()


def test_duplicate_identity_rejected_before_sink(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="duplicates"):
        build_fixture(json.dumps([EXPECTED_WIRE, EXPECTED_WIRE]).encode(), tmp_path / "db")
    assert not list(tmp_path.iterdir())


def test_bundle_reader_parses_the_bytes_it_verified(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = tmp_path / "out"
    label = 'a,\r\n"quoted" é'
    payload = json.dumps([{**EXPECTED_WIRE, "label": label}]).encode()
    extract_fixture(payload, bundle)
    data_path = bundle / "data.csv"
    original_read = Path.read_bytes

    def replace_after_read(path: Path) -> bytes:
        captured = original_read(path)
        if path == data_path:
            path.write_bytes(captured.replace(b"V1.0000", b"V9.0000"))
        return captured

    monkeypatch.setattr(Path, "read_bytes", replace_after_read)
    replay = read_fixture_bundle(bundle)
    assert replay.rows[0].close == Decimal("1.0000")
    assert replay.rows[0].label == label


def test_bundle_reader_rejects_changed_bytes(tmp_path: Path) -> None:
    bundle = tmp_path / "out"
    extract_fixture(PAYLOAD, bundle)
    data_path = bundle / "data.csv"
    data_path.write_bytes(data_path.read_bytes().replace(b"V123.4500", b"V999.9999"))
    with pytest.raises(ValidationError, match="schema/hash mismatch"):
        read_fixture_bundle(bundle)
