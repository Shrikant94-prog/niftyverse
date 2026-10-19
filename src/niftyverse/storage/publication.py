"""Atomic facts/lineage/coverage with durable raw-first staging and ack recovery."""

import json
import os
import tempfile
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import uuid4

import pyarrow as pa

from niftyverse.batches import ValidatedBatch, identity
from niftyverse.core import ValidationError
from niftyverse.storage.catalog import Store
from niftyverse.storage.durable import digest_file, publish_raw, sync_directory, write_bytes


@dataclass(frozen=True)
class Receipt:
    check_id: str
    occurrence_id: str
    reused: bool


@dataclass(frozen=True)
class RecoveryReport:
    missing_raw: tuple[str, ...]
    corrupt_raw: tuple[str, ...]
    orphan_raw: tuple[str, ...]
    unfinished_jobs: tuple[str, ...]
    staged_directories: tuple[str, ...]


def recover(store: Store) -> RecoveryReport:
    objects = store.connection.execute("SELECT sha256 FROM raw_objects ORDER BY sha256").fetchall()
    missing, corrupt = [], []
    for (sha,) in objects:
        path = store.location.paths["raw"] / sha[:2] / sha
        if not path.is_file():
            missing.append(sha)
        elif digest_file(path) != sha:
            corrupt.append(sha)
    tracked = {r[0] for r in objects}
    orphans = sorted(
        p.name
        for p in store.location.paths["raw"].glob("*/*")
        if p.is_file() and p.name not in tracked
    )
    jobs = store.connection.execute(
        "SELECT check_id FROM jobs WHERE status != 'committed' ORDER BY check_id"
    ).fetchall()
    stages = tuple(sorted(p.name for p in store.location.paths["staging"].iterdir()))
    return RecoveryReport(
        tuple(missing), tuple(corrupt), tuple(orphans), tuple(r[0] for r in jobs), stages
    )


def _stage(store: Store, batch: ValidatedBatch) -> None:
    root = store.location.paths["staging"]
    destination = root / identity(batch.check_id)
    if destination.exists():
        metadata = json.loads((destination / "checkpoint.json").read_text(encoding="utf-8"))
        if metadata["request_identity"] != batch.request_identity:
            raise ValidationError("staged check identity changed; use a new check")
        for name, sha in metadata["files"].items():
            if digest_file(destination / name) != sha:
                raise ValidationError("staged batch checksum mismatch; explicit replay required")
        return
    with tempfile.TemporaryDirectory(prefix=".stage-", dir=root) as folder:
        stage = Path(folder) / "checkpoint"
        stage.mkdir()
        files = {}
        for name, table in batch.tables:
            sink = pa.BufferOutputStream()
            with pa.ipc.new_file(sink, table.schema) as writer:
                writer.write_table(table)
            path = stage / f"{name}.arrow"
            write_bytes(path, sink.getvalue().to_pybytes())
            files[path.name] = digest_file(path)
        metadata = {
            "request_identity": batch.request_identity,
            "partition": asdict(batch.partition),
            "raw_sha256": batch.capture.sha256,
            "check_id": batch.check_id,
            "schema_version": batch.schema_version,
            "normalizer_version": batch.normalizer_version,
            "files": files,
        }
        write_bytes(
            stage / "checkpoint.json", json.dumps(metadata, default=str, sort_keys=True).encode()
        )
        sync_directory(stage)
        os.rename(stage, destination)
        sync_directory(root)


def publish(
    store: Store,
    batch: ValidatedBatch,
    *,
    fault: Callable[[str], None] | None = None,
    acknowledge: Callable[[Receipt], None] | None = None,
) -> Receipt:
    """Commit a full partition; progress acknowledgement never owns completeness.

    On failure, a caller reconciles/retries the same stable check ID. Changed
    inputs require a new check. Quarantined/partial work remains staged only.
    """
    batch.__post_init__()
    conn = store.connection
    old = conn.execute(
        "SELECT request_identity, occurrence_id FROM source_checks WHERE check_id=?",
        [batch.check_id],
    ).fetchone()
    if old:
        if old[0] != batch.request_identity:
            raise ValidationError("committed check identity changed")
        report = recover(store)
        if report.missing_raw or report.corrupt_raw:
            raise ValidationError("missing/corrupt committed raw; repair before publication")
        receipt = Receipt(batch.check_id, old[1], True)
        if acknowledge:
            acknowledge(receipt)
        return receipt
    report = recover(store)
    if report.missing_raw or report.corrupt_raw:
        raise ValidationError("missing/corrupt committed raw; repair before publication")
    previous_job = conn.execute(
        "SELECT request_identity FROM jobs WHERE check_id=?", [batch.check_id]
    ).fetchone()
    if previous_job and previous_job[0] != batch.request_identity:
        raise ValidationError("staged check identity changed; use a new check")
    publish_raw(store.location.paths["raw"], batch.capture.sha256, batch.capture.body)
    _stage(store, batch)
    status = "staged" if batch.coverage in {"complete", "no_observations"} else batch.coverage
    conn.execute(
        "INSERT INTO jobs VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT DO NOTHING",
        [
            batch.check_id,
            batch.request_identity,
            batch.partition.identity,
            status,
            batch.capture.sha256,
            batch.reason,
        ],
    )
    if status != "staged":
        raise ValidationError(
            f"{status} partition retained for explicit replay; no facts/complete coverage"
        )
    candidates = (
        conn.execute(
            "SELECT occurrence_id, content_identity, known_at, source_revision "
            "FROM occurrences WHERE partition_id=? ORDER BY known_at DESC LIMIT 1",
            [batch.partition.identity],
        )
        .to_arrow_table()
        .to_pylist()
    )
    latest = tuple(candidates[0].values()) if candidates else None
    unchanged = bool(
        latest and latest[1] == batch.content_identity and latest[3] == batch.source_revision
    )
    if latest and (batch.known_at < latest[2] or (batch.known_at == latest[2] and not unchanged)):
        raise ValidationError(
            "ambiguous/backdated assertion ordering; explicit reconciliation required"
        )
    occurrence = latest[0] if unchanged and latest else uuid4().hex
    receipt = Receipt(batch.check_id, occurrence, False)
    conn.execute("BEGIN TRANSACTION")
    committed = False
    try:
        if not unchanged:
            conn.execute(
                "INSERT INTO raw_objects VALUES (?, ?) ON CONFLICT DO NOTHING",
                [batch.capture.sha256, len(batch.capture.body)],
            )
            conn.execute(
                "INSERT INTO captures VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT DO NOTHING",
                [
                    batch.capture.identity,
                    batch.capture.kind,
                    batch.capture.source_id,
                    batch.capture.origin,
                    len(batch.capture.body),
                    batch.capture.sdk_version,
                ],
            )
            conn.execute(
                "INSERT INTO capture_objects VALUES (?, ?) ON CONFLICT DO NOTHING",
                [batch.capture.identity, batch.capture.sha256],
            )
            conn.execute(
                "INSERT INTO partitions VALUES (?, ?) ON CONFLICT DO NOTHING",
                [
                    batch.partition.identity,
                    json.dumps(asdict(batch.partition), default=str, sort_keys=True),
                ],
            )
            conn.execute(
                "INSERT INTO occurrences VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    occurrence,
                    batch.partition.identity,
                    batch.content_identity,
                    batch.capture.identity,
                    batch.state,
                    batch.reason,
                    batch.known_at,
                    batch.checked_at,
                    batch.source_revision,
                    batch.schema_version,
                    batch.normalizer_version,
                ],
            )
            for name, table in batch.tables:
                conn.register("validated_input", table)
                try:
                    conn.execute(
                        f"INSERT INTO {name} SELECT ? AS occurrence_id, * FROM validated_input",
                        [occurrence],
                    )
                finally:
                    conn.unregister("validated_input")
        conn.execute(
            "INSERT INTO source_checks VALUES (?, ?, ?, ?, ?, ?)",
            [
                batch.check_id,
                batch.request_identity,
                batch.partition.identity,
                occurrence,
                batch.checked_at,
                batch.capture.request_fingerprint,
            ],
        )
        conn.execute(
            "INSERT INTO coverage VALUES (?, ?, ?, ?, ?)",
            [
                batch.check_id,
                batch.partition.identity,
                occurrence,
                batch.coverage,
                batch.partition.completeness_evidence,
            ],
        )
        conn.execute("UPDATE jobs SET status='committed' WHERE check_id=?", [batch.check_id])
        if fault:
            fault("before_commit")
        conn.execute("COMMIT")
        committed = True
        if fault:
            fault("after_commit")
        if acknowledge:
            acknowledge(receipt)
        if fault:
            fault("after_ack")
    except BaseException:
        if not committed:
            conn.execute("ROLLBACK")
        raise
    return receipt
