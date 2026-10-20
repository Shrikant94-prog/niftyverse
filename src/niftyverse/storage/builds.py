"""Operational checkpoints; canonical facts/coverage remain publication-owned."""

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any
from uuid import uuid4

from niftyverse.batches import Partition, identity
from niftyverse.core import ValidationError
from niftyverse.planning import CacheEntry, WorkGraph
from niftyverse.storage.catalog import Store
from niftyverse.storage.durable import digest_file, publish_raw
from niftyverse.storage.publication import recover


def committed_cache(store: Store) -> tuple[CacheEntry, ...]:
    report = recover(store)
    if report.missing_raw or report.corrupt_raw:
        raise ValidationError("missing/corrupt committed raw; explicit repair required")
    records = store.connection.execute(
        "SELECT p.contract_json, c.source_id, o.schema_version, o.normalizer_version, "
        "o.state, v.status FROM source_checks s "
        "JOIN coverage v USING(check_id) JOIN occurrences o ON o.occurrence_id=s.occurrence_id "
        "JOIN partitions p ON p.partition_id=s.partition_id "
        "JOIN captures c ON c.capture_id=o.capture_id "
        "QUALIFY row_number() OVER (PARTITION BY s.partition_id "
        "ORDER BY s.checked_at DESC, o.known_at DESC, s.check_id DESC)=1"
    ).fetchall()
    from datetime import date

    result = []
    for contract, source, schema, parser, state, coverage in records:
        if state != "active" or coverage not in {"complete", "no_observations"}:
            continue
        values = json.loads(contract)
        for name in ("start", "end"):
            values[name] = date.fromisoformat(values[name])
        for name in ("universe", "fields"):
            values[name] = tuple(values[name])
        result.append(CacheEntry(Partition(**values), source, schema, parser, "history_bundle"))
    return tuple(result)


def checkpoint_identity(graph: WorkGraph) -> str:
    base = Path(__file__).parent.parent
    modules = (
        base / "planning.py",
        base / "execution.py",
        base / "batches.py",
        Path(__file__),
        Path(__file__).with_name("publication.py"),
        Path(__file__).with_name("schemas.py"),
    )
    return identity((graph.plan_hash, [(p.name, digest_file(p)) for p in modules]))


def start_run(store: Store, graph: WorkGraph, resume: str | None) -> str:
    fingerprint = checkpoint_identity(graph)
    if resume:
        old = store.connection.execute(
            "SELECT plan_hash, checkpoint_identity FROM build_runs WHERE run_id=?",
            [resume],
        ).fetchone()
        if not old:
            raise ValidationError("unknown persistent resume ID")
        if old != (graph.plan_hash, fingerprint):
            raise ValidationError(
                "incompatible checkpoint: plan/config/source/code/local inputs changed"
            )
        store.connection.execute("UPDATE build_runs SET status='running' WHERE run_id=?", [resume])
        return resume
    run = uuid4().hex
    manifest: dict[str, Any] = {
        "config_schema": graph.plan.version,
        "code_identity": fingerprint,
        "requested_start": graph.plan.start,
        "requested_end": graph.plan.end,
        "effective_intervals": [(j.partition.start, j.partition.end) for j in graph.jobs],
        "local_hashes": graph.local_hashes,
        "calendar_hash": graph.calendar_hash,
        "config": asdict(graph.plan),
        "source_contracts": [asdict(j.capability) for j in graph.jobs if j.capability],
        "jobs": [
            {
                "id": j.id,
                "partition": asdict(j.partition),
                "source_format": j.source_format,
                "dependencies": j.dependencies,
            }
            for j in graph.jobs
        ],
        "input_occurrences": {
            j.id: latest_occurrence(store, j.partition.identity) for j in graph.jobs
        },
    }
    store.connection.execute(
        "INSERT INTO build_runs VALUES (?, ?, ?, ?, 'running')",
        [
            run,
            graph.plan_hash,
            fingerprint,
            json.dumps(manifest, default=str, sort_keys=True),
        ],
    )
    return run


def latest_occurrence(store: Store, partition: str) -> str | None:
    row = store.connection.execute(
        "SELECT occurrence_id FROM occurrences WHERE partition_id=? "
        "ORDER BY known_at DESC LIMIT 1",
        [partition],
    ).fetchone()
    return row[0] if row else None


def changed_in_run(store: Store, graph: WorkGraph, run: str) -> set[str]:
    row = store.connection.execute(
        "SELECT manifest_json FROM build_runs WHERE run_id=?",
        [run],
    ).fetchone()
    assert row
    baseline = json.loads(row[0])["input_occurrences"]
    changed = set()
    for job in graph.jobs:
        check = store.connection.execute(
            "SELECT occurrence_id FROM source_checks WHERE check_id=?",
            [identity((run, job.id))],
        ).fetchone()
        if check and check[0] != baseline[job.id]:
            changed.add(job.id)
    return changed


def record_work(
    store: Store,
    run: str,
    job: str,
    status: str,
    *,
    reason: str | None = None,
    check: str | None = None,
    raw: str | None = None,
    attempts: int = 0,
) -> None:
    store.connection.execute(
        "INSERT INTO build_work VALUES (?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT (run_id, job_id) DO UPDATE SET status=excluded.status, "
        "reason=excluded.reason, check_id=excluded.check_id, raw_sha256=excluded.raw_sha256, "
        "attempts=excluded.attempts",
        [run, job, status, reason, check, raw, attempts],
    )


def quarantine_raw(store: Store, body: bytes, sha: str) -> None:
    publish_raw(store.location.paths["raw"], sha, body)
