"""Bounded local planning context and replay of explicitly supplied typed bundles.

Replay retains source/capture identities, but does not reparse source bytes or
upgrade experimental provider coverage. Live adapters implement Provider directly.
"""

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from niftyverse.batches import MAX_BYTES, MAX_ROWS, Capture, Partition, ValidatedBatch
from niftyverse.calendars import Calendar, Session
from niftyverse.core import ValidationError
from niftyverse.execution import Acquired, AcquisitionFailure
from niftyverse.planning import Capability, Job
from niftyverse.storage.bundles import load_manifest, read_bundle, verified_bytes


def _partition(value: dict[str, Any]) -> Partition:
    values = dict(value)
    for name in ("start", "end"):
        values[name] = date.fromisoformat(values[name])
    for name in ("universe", "fields"):
        values[name] = tuple(values[name])
    return Partition(**values)


@dataclass(frozen=True)
class PlanningContext:
    capabilities: tuple[Capability, ...]
    calendar: Calendar | None

    @classmethod
    def from_json(cls, payload: bytes) -> PlanningContext:
        if len(payload) > 8 * 1024 * 1024:
            raise ValidationError("planning context byte limit")
        try:
            values = json.loads(payload)
            if not isinstance(values, dict) or values.keys() - {"capabilities", "calendar"}:
                raise ValidationError("unknown planning context keys")
            caps = []
            for item in values["capabilities"]:
                item = dict(item)
                for name in ("start", "end"):
                    item[name] = date.fromisoformat(item[name])
                caps.append(Capability(**item))
            calendar = None
            if values.get("calendar") is not None:
                item = dict(values["calendar"])
                item["known_at"] = datetime.fromisoformat(item["known_at"])
                sessions = []
                for row in item["sessions"]:
                    row = dict(row)
                    row["session_date"] = date.fromisoformat(row["session_date"])
                    for name in ("opens_at", "closes_at"):
                        row[name] = datetime.fromisoformat(row[name]) if row[name] else None
                    sessions.append(Session(**row))
                item["sessions"] = tuple(sessions)
                calendar = Calendar(**item)
            return cls(tuple(caps), calendar)
        except (ValueError, TypeError, KeyError, AttributeError) as error:
            raise ValidationError("invalid planning context") from error


def load_batch(path: Path) -> ValidatedBatch:
    """Read a bounded partition bundle with retained raw and shared validation."""
    if (path / "manifest.json").stat().st_size > 1024 * 1024:
        raise ValidationError("bundle manifest byte limit")
    manifest = load_manifest(path)
    if manifest["kind"] != "direct_extract" or not manifest.get("raw_replay_available"):
        raise AcquisitionFailure("raw_replay_unavailable")
    artifacts = manifest["artifacts"]
    if (
        sum(e["bytes"] for e in artifacts.values()) > 2 * MAX_BYTES
        or sum(e.get("rows", 0) for e in artifacts.values()) > MAX_ROWS
    ):
        raise ValidationError("replay bundle budget exceeded")
    for name, entry in artifacts.items():
        if entry.get("encoding") == "parquet":
            with pa.BufferReader(verified_bytes(path, name, entry)) as source:
                with pq.ParquetFile(source, pre_buffer=False) as parquet:
                    if (
                        parquet.metadata.num_rows > MAX_ROWS
                        or sum(
                            parquet.metadata.row_group(i).total_byte_size
                            for i in range(parquet.metadata.num_row_groups)
                        )
                        > MAX_BYTES
                    ):
                        raise ValidationError("decoded replay budget exceeded")
    bundle = read_bundle(path)
    meta = manifest["batch"]
    capture = meta["capture"]
    raw_name = "raw/" + capture["sha256"]
    raw = verified_bytes(path, raw_name, artifacts[raw_name])
    captured = Capture(
        raw,
        capture["kind"],
        capture["source_id"],
        capture["origin"],
        capture["sdk_version"],
        capture["request_fingerprint"],
    )
    if captured.identity != capture["capture_id"]:
        raise ValidationError("replay capture identity mismatch")
    return ValidatedBatch(
        _partition(meta["partition"]),
        captured,
        meta["check_id"],
        datetime.fromisoformat(meta["checked_at"]),
        datetime.fromisoformat(meta["known_at"]),
        meta["source_revision"],
        meta["state"],
        meta["reason"],
        tuple((e["table"], bundle.table(e["table"])) for e in artifacts.values() if "table" in e),
        meta["coverage"],
        meta["schema_version"],
        meta["normalizer_version"],
    )


class BundleProvider:
    """Explicit offline replay; absent input is a typed deferred gap."""

    offline_capable = True

    def __init__(self, paths: tuple[Path, ...]) -> None:
        self.paths: dict[str, Path] = {}
        for path in paths:
            if (path / "manifest.json").stat().st_size > 1024 * 1024:
                raise ValidationError("bundle manifest byte limit")
            meta = load_manifest(path)
            if meta["kind"] != "direct_extract":
                raise ValidationError("input-bundle requires a typed partition extraction")
            key = _partition(meta["batch"]["partition"]).identity
            if key in self.paths:
                raise ValidationError("ambiguous replay partition; choose one explicit revision")
            self.paths[key] = path

    async def acquire(self, job: Job, *, attempt: int, offline: bool) -> Acquired:
        path = self.paths.get(job.partition.identity)
        if path is None:
            raise AcquisitionFailure("offline_missing_input", deferred=True)
        try:
            return Acquired(load_batch(path))
        except (KeyError, TypeError, OSError) as error:
            raise ValidationError("invalid replay bundle") from error
