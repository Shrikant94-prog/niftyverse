"""Offline delisted manifests, independent renamed/dead and missing-date cases."""

import csv
import io
import socket
from datetime import date
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from test_identity import CUTOFF

from niftyverse.core import ValidationError
from niftyverse.delisted import import_delisted, member_request


def records() -> list[dict[str, str | None]]:
    common = {
        "instrument_id": "dead-a",
        "listing_id": "dead-eq",
        "name": "Dead Alpha",
        "asset_type": "equity",
        "issuer_id": None,
        "issuer_name": None,
        "exchange": "NSE",
        "series": "EQ",
        "namespace": "symbol",
        "isin": None,
        "listing_date": "2010-01-01",
        "delisting_date": "2024-01-01",
        "source_id": "owned-manifest",
        "evidence_ref": "notice:1",
        "known_at": "2025-01-01T00:00:00+00:00",
        "confidence": "verified",
        "status": "delisted",
        "price_history": "source_unavailable",
    }
    return [
        {**common, "identifier": "OLDDEAD", "valid_from": "2010-01-01", "valid_to": "2020-01-01"},
        {**common, "identifier": "NEWDEAD", "valid_from": "2020-01-01", "valid_to": "2024-01-01"},
        {
            **common,
            "instrument_id": "unknown-a",
            "listing_id": "unknown-eq",
            "name": "Unknown Dates",
            "identifier": "UNKNOWN",
            "listing_date": None,
            "delisting_date": None,
            "valid_from": None,
            "valid_to": None,
            "price_history": "unknown",
        },
    ]


def write_manifest(path: Path, rows: list[dict[str, str | None]]) -> None:
    if path.suffix == ".parquet":
        pq.write_table(
            pa.Table.from_pylist(rows, schema=pa.schema([(k, pa.string()) for k in rows[0]])), path
        )
    else:
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
        path.write_text(stream.getvalue(), encoding="utf-8")


@pytest.mark.parametrize("suffix", [".csv", ".parquet"])
def test_dead_rename_missing_dates_and_membership_are_local(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, suffix: str
) -> None:
    path = tmp_path / ("delisted" + suffix)
    write_manifest(path, records())

    def denied(*args: object, **kwargs: object) -> None:
        raise AssertionError("dead-company request used network/current quote")

    monkeypatch.setattr(socket, "socket", denied)
    manifest = import_delisted(path, version_id="manifest-1", collected_at=CUTOFF)
    assert (
        manifest.catalogue.resolve("OLDDEAD", "symbol", date(2019, 12, 31), CUTOFF)
        .matches[0]
        .instrument.instrument_id
        == "dead-a"
    )
    assert (
        manifest.catalogue.resolve("NEWDEAD", "symbol", date(2020, 1, 1), CUTOFF)
        .matches[0]
        .instrument.instrument_id
        == "dead-a"
    )
    assert (
        manifest.catalogue.resolve("OLDDEAD", "symbol", date(2020, 1, 1), CUTOFF).status
        == "identity_unresolved"
    )
    request = manifest.request("NEWDEAD", "symbol", date(2023, 1, 1), CUTOFF)
    assert request.identity_status == "resolved" and request.price_status == "source_unavailable"
    unknown = manifest.request("UNKNOWN", "symbol", date(2023, 1, 1), CUTOFF)
    assert unknown.identity_status == "identity_unresolved" and unknown.listing_state == "unknown"
    assert manifest.records[-1].listing_date is None
    member = member_request(
        manifest, "unknown-a", date(2023, 1, 1), CUTOFF, membership_established=True
    )
    assert (
        member.eligible
        and member.instrument_id == "unknown-a"
        and member.listing_state == "unknown"
    )
    dead = member_request(
        manifest, "dead-a", date(2025, 1, 1), CUTOFF, membership_established=True
    )
    assert (
        dead.eligible
        and dead.listing_state == "not_listed"
        and dead.price_status == "source_unavailable"
    )


@pytest.mark.parametrize(
    "change",
    [
        {"valid_from": "yesterday"},
        {"listing_date": "2025-01-01", "delisting_date": "2024-01-01"},
        {"known_at": "2025-01-01"},
        {"evidence_ref": ""},
        {"confidence": "guess"},
        {"instrument_id": ""},
        {"price_history": "0"},
    ],
)
def test_malformed_manifest_rejects_whole_input_without_state(
    tmp_path: Path, change: dict[str, str]
) -> None:
    path = tmp_path / "bad.csv"
    rows = records()
    rows[-1].update(change)
    write_manifest(path, rows)
    before = path.read_bytes()
    with pytest.raises(ValidationError):
        import_delisted(path, version_id="bad", collected_at=CUTOFF)
    assert path.read_bytes() == before
    assert set(tmp_path.iterdir()) == {path}


def test_ambiguous_manifest_and_conflicting_stable_ids_reject_atomically(tmp_path: Path) -> None:
    rows = records()
    rows.append(
        {**rows[1], "instrument_id": "different", "listing_id": "different-eq", "name": "Other"}
    )
    path = tmp_path / "ambiguous.csv"
    write_manifest(path, rows)
    with pytest.raises(ValidationError, match="ambiguous"):
        import_delisted(path, version_id="bad", collected_at=CUTOFF)
    rows = records()
    rows[1]["name"] = "Conflicting identity"
    write_manifest(path, rows)
    with pytest.raises(ValidationError, match="conflict"):
        import_delisted(path, version_id="bad", collected_at=CUTOFF)
    assert set(tmp_path.iterdir()) == {path}
