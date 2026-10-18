"""Explicit typed CSV bundle encoding; no DuckDB import or store."""

import csv
import hashlib
import io
import json
import os
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

from niftyverse.core import FixtureBatch, FixtureRow, ValidationError

_FIELDS = ["instrument_id", "session_date", "close", "label"]
_TYPES = ["string", "date32", "decimal128(18,4)", "string"]


def write_fixture_bundle(batch: FixtureBatch, destination: Path) -> None:
    """Write a new local bundle after validation; existing outputs are refused."""
    if destination.exists():
        raise FileExistsError(destination)
    with tempfile.TemporaryDirectory(prefix=".niftyverse-", dir=destination.parent) as folder:
        stage = Path(folder) / "bundle"
        stage.mkdir()
        with (stage / "data.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(_FIELDS)
            for row in batch.rows:
                writer.writerow(
                    [
                        "V" + row.instrument_id,
                        "V" + row.session_date.isoformat(),
                        "N" if row.close is None else "V" + format(row.close, ".4f"),
                        "N" if row.label is None else "V" + row.label,
                    ]
                )
        manifest = {
            "schema_version": "fixture-v1",
            "fields": dict(zip(_FIELDS, _TYPES, strict=True)),
            "encoding": "N=null; V<text>=value; UTF-8; ISO dates; decimal scale 4",
            "capture_kind": "owned-fixture-json",
            "source_id": "owned-offline-fixture",
            "raw_sha256": batch.raw_sha256,
            "raw_replay_available": False,
            "data_sha256": hashlib.sha256((stage / "data.csv").read_bytes()).hexdigest(),
            "rows": len(batch.rows),
            "normalizer_version": "fixture-v1",
            "publication_time": None,
        }
        (stage / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
        )
        os.rename(stage, destination)


def read_fixture_bundle(destination: Path) -> FixtureBatch:
    """Explicitly read a fixture-v1 bundle, validating bytes, schema and values."""
    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    payload = (destination / "data.csv").read_bytes()
    if (
        manifest.get("schema_version") != "fixture-v1"
        or manifest.get("fields") != dict(zip(_FIELDS, _TYPES, strict=True))
        or manifest.get("data_sha256") != hashlib.sha256(payload).hexdigest()
    ):
        raise ValidationError("fixture bundle schema/hash mismatch")

    def value(cell: str) -> str | None:
        if cell == "N":
            return None
        if cell.startswith("V"):
            return cell[1:]
        raise ValidationError("fixture CSV cell lacks N/V encoding")

    rows = []
    with io.StringIO(payload.decode("utf-8"), newline="") as handle:
        reader = csv.reader(handle)
        if next(reader, None) != _FIELDS:
            raise ValidationError("fixture CSV header mismatch")
        for cells in reader:
            if len(cells) != 4:
                raise ValidationError("fixture CSV row width mismatch")
            instrument, session, close, label = map(value, cells)
            if instrument is None or session is None:
                raise ValidationError("fixture CSV required value is null")
            rows.append(
                FixtureRow(
                    instrument,
                    date.fromisoformat(session),
                    None if close is None else Decimal(close),
                    label,
                )
            )
    if len(rows) != manifest.get("rows"):
        raise ValidationError("fixture CSV row count mismatch")
    return FixtureBatch(tuple(rows), manifest["raw_sha256"])
