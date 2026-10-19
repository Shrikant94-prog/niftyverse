"""Immutable typed file bundles. Direct output has no catalog dependency."""

import base64
import csv
import hashlib
import io
import json
import os
import sys
import tempfile
from collections.abc import Callable, Iterable, Iterator
from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal
from importlib.metadata import version
from pathlib import Path, PurePosixPath
from typing import Any

import polars as pl
import pyarrow as pa
import pyarrow.parquet as pq

from niftyverse.batches import ValidatedBatch, identity
from niftyverse.core import ValidationError
from niftyverse.storage.durable import digest_file, sync_directory, sync_file, write_bytes


def environment() -> dict[str, str]:
    return {
        "python": sys.version,
        "pyarrow": version("pyarrow"),
        "duckdb": version("duckdb"),
        "niftyverse": version("niftyverse"),
        "publication_code": identity(
            [
                (p.name, digest_file(p))
                for p in (
                    Path(__file__),
                    Path(__file__).with_name("schemas.py"),
                    Path(__file__).with_name("snapshots.py"),
                    Path(__file__).with_name("publication.py"),
                    Path(__file__).with_name("catalog.py"),
                    Path(__file__).with_name("durable.py"),
                    Path(__file__).parent.parent / "batches.py",
                )
            ]
        ),
    }


def member(root: Path, name: str) -> Path:
    relative = PurePosixPath(name)
    if (
        not name
        or "\\" in name
        or ":" in name
        or relative.is_absolute()
        or any(p in {"..", "."} for p in relative.parts)
    ):
        raise ValidationError("unsafe artifact member")
    result = root.joinpath(*relative.parts)
    if not result.resolve().is_relative_to(root.resolve()):
        raise ValidationError("artifact escapes bundle")
    return result


def _decode(value: Any, dtype: pa.DataType) -> Any:
    if value is None:
        return None
    if pa.types.is_decimal(dtype):
        return Decimal(value)
    if pa.types.is_date(dtype):
        return date.fromisoformat(value)
    if pa.types.is_timestamp(dtype):
        return datetime.fromisoformat(value)
    if pa.types.is_list(dtype):
        return [_decode(item, dtype.value_type) for item in value]
    if pa.types.is_struct(dtype):
        return {field.name: _decode(value[field.name], field.type) for field in dtype}
    return value


def _write_table(
    path: Path, schema: pa.Schema, batches: Iterable[pa.RecordBatch], encoding: str
) -> int:
    count = 0
    if encoding == "parquet":
        with pq.ParquetWriter(path, schema, compression="zstd") as writer:
            for batch in batches:
                writer.write_batch(batch, row_group_size=65_536)
                count += batch.num_rows
    elif encoding == "csv":
        with path.open("x", encoding="utf-8", newline="") as handle:
            writer_csv = csv.writer(handle, lineterminator="\n")
            writer_csv.writerow(schema.names)
            for batch in batches:
                for row in batch.to_pylist():
                    writer_csv.writerow(
                        [
                            "N"
                            if row[name] is None
                            else "V"
                            + json.dumps(
                                row[name],
                                default=str,
                                ensure_ascii=False,
                                separators=(",", ":"),
                            )
                            for name in schema.names
                        ]
                    )
                count += batch.num_rows
            handle.flush()
            os.fsync(handle.fileno())
    else:
        raise ValidationError("encoding must be csv or parquet")
    sync_file(path)
    return count


TableStream = tuple[str, pa.Schema, Iterable[pa.RecordBatch]]


def publish_bundle(
    destination: Path,
    tables: Iterable[TableStream],
    metadata: dict[str, Any],
    *,
    encoding: str = "parquet",
    raw: Iterable[tuple[str, bytes | Path]] = (),
    fault: Callable[[str], None] | None = None,
) -> None:
    """Spool bounded Arrow batches to a new sibling directory; manifest last.

    Existing destinations always fail. No overwrite or cross-run resume policy
    is implied. Unpublished temporary siblings are never discoverable bundles.
    """
    if destination.exists():
        raise FileExistsError(destination)
    if encoding not in {"csv", "parquet"}:
        raise ValidationError("encoding must be csv or parquet")
    with tempfile.TemporaryDirectory(prefix=".niftyverse-", dir=destination.parent) as folder:
        stage = Path(folder) / "bundle"
        stage.mkdir()
        artifacts = {}
        table_names = set()
        for name, schema, batches in tables:
            if not name.isidentifier() or name in table_names:
                raise ValidationError("invalid/duplicate bundle table name")
            table_names.add(name)
            path = stage / f"{name}.{encoding}"
            count = _write_table(path, schema, batches, encoding)
            artifacts[path.name] = {
                "sha256": digest_file(path),
                "bytes": path.stat().st_size,
                "table": name,
                "rows": count,
                "encoding": encoding,
                "schema": base64.b64encode(schema.serialize().to_pybytes()).decode("ascii"),
            }
        for name, source in raw:
            path = member(stage, name)
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(source, bytes):
                write_bytes(path, source)
            else:
                # Streaming copy; active DB files must already be checkpointed/closed.
                with source.open("rb") as inp, path.open("xb") as out:
                    while chunk := inp.read(1024 * 1024):
                        out.write(chunk)
                    out.flush()
                    os.fsync(out.fileno())
            sha = digest_file(path)
            if name.startswith("raw/") and sha != path.name:
                raise ValidationError("raw capture checksum mismatch")
            artifacts[name] = {"sha256": sha, "bytes": path.stat().st_size}
        if fault:
            fault("after_data")
        manifest = {
            **metadata,
            "bundle_version": 1,
            "artifacts": artifacts,
            "environment": environment(),
            "reproducibility": {
                "artifact_bytes": "sha256 verified",
                "logical_replay": "requires retained inputs, pinned recipe/code/environment",
                "byte_regeneration": "not certified across runs/platforms/library versions",
            },
            "layout": {
                "bucket": "bounded-partition or whole-small-table",
                "compression": "zstd" if encoding == "parquet" else None,
                "row_group_rows_max": 65_536,
                "ordering": "declared input/committed order; no implicit latest selection",
                "csv_encoding": "UTF-8; N=null; V<JSON>=typed value; "
                "ISO dates/UTC instants; exact decimal strings",
            },
        }
        manifest["bundle_id"] = identity(manifest)
        manifest["snapshot_id"] = (
            manifest["bundle_id"]
            if manifest["kind"] in {"history_bundle", "resolved_result"}
            else None
        )
        # Verify every file before publishing completion, including raw copies.
        for name, entry in artifacts.items():
            if digest_file(member(stage, name)) != entry["sha256"]:
                raise ValidationError("artifact checksum changed before publication")
        if fault:
            fault("before_manifest")
        write_bytes(
            stage / "manifest.json",
            json.dumps(manifest, default=str, sort_keys=True, indent=2).encode(),
        )
        for directory in sorted(
            (p for p in stage.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True
        ):
            sync_directory(directory)
        sync_directory(stage)
        if fault:
            fault("before_publish")
        if destination.exists():
            raise FileExistsError(destination)
        os.rename(stage, destination)
        try:
            if fault:
                fault("after_publish")
            sync_directory(destination.parent)
        except BaseException:
            # Destination was new and is wholly ours. Keep inspectable files,
            # but no ready marker if final publication did not acknowledge.
            (destination / "manifest.json").unlink(missing_ok=True)
            sync_directory(destination)
            raise


def load_manifest(destination: Path) -> dict[str, Any]:
    try:
        manifest: dict[str, Any] = json.loads((destination / "manifest.json").read_bytes())
        original = dict(manifest)
        bundle_id = original.pop("bundle_id")
        original.pop("snapshot_id")
        if (
            manifest["bundle_version"] != 1
            or manifest["status"] not in {"complete", "partial"}
            or identity(original) != bundle_id
            or manifest["snapshot_id"]
            != (bundle_id if manifest["kind"] in {"history_bundle", "resolved_result"} else None)
        ):
            raise ValidationError("incomplete/changed bundle manifest")
        return manifest
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ValidationError(f"invalid/missing bundle manifest: {error}") from error


def verified_bytes(destination: Path, name: str, entry: dict[str, Any]) -> bytes:
    try:
        payload = member(destination, name).read_bytes()
    except OSError as error:
        raise ValidationError("artifact checksum/missing file") from error
    if len(payload) != entry["bytes"] or hashlib.sha256(payload).hexdigest() != entry["sha256"]:
        raise ValidationError("artifact checksum mismatch")
    return payload


@dataclass(frozen=True)
class Bundle:
    path: Path
    manifest: dict[str, Any]

    def table(self, name: str) -> pa.Table:
        for filename, entry in self.manifest["artifacts"].items():
            if entry.get("table") != name:
                continue
            payload = verified_bytes(self.path, filename, entry)
            schema = pa.ipc.read_schema(pa.BufferReader(base64.b64decode(entry["schema"])))
            if entry["encoding"] == "parquet":
                table = pq.read_table(pa.BufferReader(payload))
                if not table.schema.equals(schema, check_metadata=False):
                    raise ValidationError("Parquet schema mismatch")
            else:
                reader = csv.reader(io.StringIO(payload.decode("utf-8"), newline=""))
                if next(reader, None) != schema.names:
                    raise ValidationError("CSV schema/header mismatch")
                rows = []
                for cells in reader:
                    if len(cells) != len(schema):
                        raise ValidationError("CSV row width mismatch")
                    row: dict[str, Any] = {}
                    for cell, field in zip(cells, schema, strict=True):
                        if cell == "N":
                            row[field.name] = None
                        elif cell.startswith("V"):
                            row[field.name] = _decode(json.loads(cell[1:]), field.type)
                        else:
                            raise ValidationError("CSV null/value encoding mismatch")
                    rows.append(row)
                table = pa.Table.from_pylist(rows, schema=schema)
            if table.num_rows != entry["rows"]:
                raise ValidationError("artifact row count mismatch")
            return table
        raise KeyError(name)


def read_bundle(destination: Path) -> Bundle:
    manifest = load_manifest(destination)
    for name, entry in manifest["artifacts"].items():
        # Stream validation avoids materializing large backup/snapshot artifacts.
        path = member(destination, name)
        if (
            not path.is_file()
            or path.stat().st_size != entry["bytes"]
            or digest_file(path) != entry["sha256"]
        ):
            raise ValidationError("artifact checksum/missing file")
    return Bundle(destination, manifest)


def scan_polars(bundle: Bundle, name: str) -> pl.LazyFrame:
    """Verify a pinned immutable Parquet artifact, then return a real lazy scan.

    The caller owns its read context. This never opens/attaches the live store.
    Replacing files inside a published immutable bundle violates its contract.
    """
    verified = read_bundle(bundle.path)
    if verified.manifest["bundle_id"] != bundle.manifest["bundle_id"]:
        raise ValidationError("pinned bundle identity changed")
    for filename, entry in verified.manifest["artifacts"].items():
        if entry.get("table") == name:
            if entry["encoding"] != "parquet":
                raise ValidationError("lazy scan requires Parquet")
            return pl.scan_parquet(member(bundle.path, filename))
    raise KeyError(name)


def write_direct(
    batch: ValidatedBatch,
    destination: Path,
    *,
    encoding: str = "parquet",
    retain_raw: bool = True,
    allow_partial: bool = False,
    fault: Callable[[str], None] | None = None,
) -> None:
    batch.__post_init__()
    partial = batch.coverage not in {"complete", "no_observations"}
    if partial and not allow_partial:
        raise ValidationError("partial/quarantined output requires explicit allow_partial")
    metadata = {
        "kind": "direct_extract",
        "status": "partial" if partial else "complete",
        "raw_replay_available": retain_raw,
        "batch": {
            "partition": asdict(batch.partition),
            "check_id": batch.check_id,
            "checked_at": batch.checked_at.isoformat(),
            "known_at": batch.known_at.isoformat(),
            "source_revision": batch.source_revision,
            "state": batch.state,
            "reason": batch.reason,
            "capture": {
                "sha256": batch.capture.sha256,
                "capture_id": batch.capture.identity,
                "kind": batch.capture.kind,
                "source_id": batch.capture.source_id,
                "origin": batch.capture.origin,
                "sdk_version": batch.capture.sdk_version,
                "request_fingerprint": batch.capture.request_fingerprint,
            },
            "schema_version": batch.schema_version,
            "normalizer_version": batch.normalizer_version,
            "coverage": batch.coverage,
        },
    }
    raw = [("raw/" + batch.capture.sha256, batch.capture.body)] if retain_raw else []

    def streams() -> Iterator[TableStream]:
        for name, table in batch.tables:
            yield name, table.schema, table.to_batches(max_chunksize=65_536)

    publish_bundle(destination, streams(), metadata, encoding=encoding, raw=raw, fault=fault)
