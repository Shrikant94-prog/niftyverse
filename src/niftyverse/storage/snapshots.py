"""Consistent history, minimal resolved proof and verified physical backup/restore.

The tiny price selector is deliberately not the Phase 16 research engine.
"""

import json
import os
import tempfile
from collections.abc import Callable, Iterator
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import duckdb
import pyarrow as pa

from niftyverse.batches import utc
from niftyverse.core import ValidationError
from niftyverse.storage.bundles import (
    Bundle,
    TableStream,
    member,
    publish_bundle,
    read_bundle,
)
from niftyverse.storage.durable import digest_file, sync_directory
from niftyverse.storage.publication import recover
from niftyverse.storage.schemas import MONEY, SCHEMAS

if TYPE_CHECKING:
    from niftyverse.storage.catalog import Store

CATALOG_TABLES = (
    "schema_migrations",
    "captures",
    "raw_objects",
    "capture_objects",
    "partitions",
    "occurrences",
    "source_checks",
    "coverage",
    "jobs",
    *SCHEMAS,
)
PRICE_RESULT = pa.schema(
    [
        pa.field("listing_id", pa.string(), False),
        pa.field("session_date", pa.date32(), False),
        pa.field("close", MONEY),
        pa.field("occurrence_id", pa.string()),
        pa.field("missing_reason", pa.string()),
    ]
)


def _label(label: str) -> None:
    if not label or not all(c.isalnum() or c in "-_" for c in label):
        raise ValidationError("snapshot label must be a simple name")


def history_bundle(
    store: Store,
    label: str,
    *,
    recipe: str,
    policy: str,
    fault: Callable[[str], None] | None = None,
) -> Bundle:
    _label(label)
    report = recover(store)
    if report.missing_raw or report.corrupt_raw:
        raise ValidationError("missing/corrupt raw prevents complete history bundle")
    destination = store.location.paths["snapshots"] / label
    conn = store.connection
    conn.execute("BEGIN TRANSACTION")
    try:
        occurrences = conn.execute(
            "SELECT occurrence_id FROM occurrences ORDER BY occurrence_id"
        ).fetchall()
        metadata = {
            "kind": "history_bundle",
            "status": "complete",
            "recipe": recipe,
            "policy": policy,
            "candidate_occurrences": [r[0] for r in occurrences],
            "raw_replay_available": True,
            "readiness": "only locally retained candidate assertions; "
            "never-obtained revisions unknown",
            "sql_semantics": "all retained assertions; no implicit latest selection",
        }
        raw = []
        for (sha,) in conn.execute(
            "SELECT sha256 FROM raw_objects UNION SELECT raw_sha256 FROM jobs ORDER BY 1"
        ).fetchall():
            if not (store.location.paths["raw"] / sha[:2] / sha).is_file():
                raise ValidationError("missing staged raw prevents complete history bundle")
            raw.append(("raw/" + sha, store.location.paths["raw"] / sha[:2] / sha))

        def streams() -> Iterator[TableStream]:
            for name in CATALOG_TABLES:
                reader = conn.execute(f"SELECT * FROM {name}").to_arrow_reader(batch_size=65_536)
                yield name, reader.schema, reader

        publish_bundle(destination, streams(), metadata, raw=raw, fault=fault)
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return read_bundle(destination)


def resolve_prices(
    history: Bundle,
    members: tuple[str, ...],
    session: date,
    cutoff: datetime,
    *,
    basis: str = "raw",
) -> pa.Table:
    """Retained-at-cutoff-v1: filter evidence before choosing partition revision.

    Only explicit membership, one session, raw/declared basis and exact locally
    retained timestamps. No inferred historical availability/calendar/identity.
    Competing partitions remain a conflict; missing members remain rows.
    """
    utc(cutoff)
    if (
        history.manifest["kind"] != "history_bundle"
        or history.manifest["policy"] != "retained-at-cutoff-v1"
    ):
        raise ValidationError("unsupported history selection policy")
    if not members or len(set(members)) != len(members):
        raise ValidationError("explicit unique membership required")
    partitions = {}
    for row in history.table("partitions").to_pylist():
        contract = json.loads(row["contract_json"])
        if (
            contract["dataset"] in {"equity_daily", "etf_daily"}
            and contract["basis"] == basis
            and "close" in contract["fields"]
            and contract["start"] <= session.isoformat() < contract["end"]
        ):
            partitions[row["partition_id"]] = contract
    selected: dict[str, dict[str, Any]] = {}
    for row in history.table("occurrences").to_pylist():
        if (
            row["partition_id"] not in partitions
            or row["known_at"] > cutoff
            or row["checked_at"] > cutoff
        ):
            continue
        previous = selected.get(row["partition_id"])
        if previous is None or previous["known_at"] < row["known_at"]:
            selected[row["partition_id"]] = row
    prices = []
    for table in ("equity_daily", "etf_daily"):
        prices.extend(history.table(table).to_pylist())
    output = []
    for listing in members:
        candidates = []
        for partition_id, occurrence in selected.items():
            contract = partitions[partition_id]
            if contract["scope"] == "selected" and listing not in contract["universe"]:
                continue
            if occurrence["state"] == "withdrawn":
                candidates.append((None, occurrence["occurrence_id"], occurrence["reason"]))
            else:
                candidates.extend(
                    (r["close"], occurrence["occurrence_id"], r["missing_reason"])
                    for r in prices
                    if r["occurrence_id"] == occurrence["occurrence_id"]
                    and r["listing_id"] == listing
                    and r["session_date"] == session
                )
        value, occurrence_id, reason = (
            candidates[0]
            if len(candidates) == 1
            else (None, None, "conflict" if candidates else "missing_price")
        )
        output.append(
            {
                "listing_id": listing,
                "session_date": session,
                "close": value,
                "occurrence_id": occurrence_id,
                "missing_reason": reason,
            }
        )
    return pa.Table.from_pylist(output, schema=PRICE_RESULT)


def resolved_result(
    history: Bundle,
    prices: pa.Table,
    destination: Path,
    *,
    recipe: str,
    cutoff: datetime,
    members: tuple[str, ...],
    basis: str = "raw",
) -> Bundle:
    utc(cutoff)
    if not prices.schema.equals(PRICE_RESULT):
        raise ValidationError("resolved schema mismatch")
    sessions = set(prices["session_date"].to_pylist())
    if len(sessions) != 1 or not prices.equals(
        resolve_prices(history, members, next(iter(sessions)), cutoff, basis=basis)
    ):
        raise ValidationError("resolved values/membership do not match pinned selection")
    selected = sorted({v for v in prices["occurrence_id"].to_pylist() if v is not None})
    if not set(selected).issubset(history.manifest["candidate_occurrences"]):
        raise ValidationError("selected occurrence not in pinned history")
    metadata = {
        "kind": "resolved_result",
        "status": "complete",
        "recipe": recipe,
        "source_history_id": history.manifest["snapshot_id"],
        "policy": history.manifest["policy"],
        "cutoff": cutoff.isoformat(),
        "members": members,
        "basis": basis,
        "selected_occurrences": selected,
        "raw_replay_available": False,
        "readiness": "frozen outputs only; "
        "other selections require dependency preflight on history",
        "sql_semantics": "named resolved selection only",
    }
    publish_bundle(destination, [("prices", prices.schema, prices.to_batches())], metadata)
    return read_bundle(destination)


def backup(
    store: Store, destination: Path, *, fault: Callable[[str], None] | None = None
) -> Bundle:
    report = recover(store)
    if report.missing_raw or report.corrupt_raw:
        raise ValidationError("missing/corrupt raw prevents backup")
    with tempfile.TemporaryDirectory(
        prefix=".backup-", dir=store.location.paths["staging"]
    ) as folder:
        catalog = Path(folder) / "catalog.duckdb"
        store.checkpoint_copy(catalog)
        raw = [("catalog.duckdb", catalog)]
        for (sha,) in store.connection.execute(
            "SELECT sha256 FROM raw_objects UNION SELECT raw_sha256 FROM jobs ORDER BY 1"
        ).fetchall():
            if not (store.location.paths["raw"] / sha[:2] / sha).is_file():
                raise ValidationError("missing staged raw prevents backup")
            raw.append(
                (f"raw/sha256/{sha[:2]}/{sha}", store.location.paths["raw"] / sha[:2] / sha)
            )
        for snapshot in store.location.paths["snapshots"].iterdir():
            if snapshot.is_dir() and (snapshot / "manifest.json").is_file():
                read_bundle(snapshot)
                raw.extend(
                    (f"snapshots/{snapshot.name}/{p.relative_to(snapshot).as_posix()}", p)
                    for p in snapshot.rglob("*")
                    if p.is_file()
                )
        metadata = {
            "kind": "backup",
            "status": "complete",
            "raw_replay_available": True,
            "catalog_version": 3,
            "unfinished_jobs": report.unfinished_jobs,
            "staging_replay": "caller must resupply/revalidate unfinished batch; "
            "committed state retained",
        }
        publish_bundle(destination, [], metadata, raw=raw, fault=fault)
    return read_bundle(destination)


def restore(source: Path, destination: Path) -> None:
    """Verify/copy into an unpublished sibling, sample-query it, then publish."""
    if destination.exists():
        raise FileExistsError(destination)
    bundle = read_bundle(source)
    if bundle.manifest["kind"] != "backup":
        raise ValidationError("restore requires a complete backup")
    with tempfile.TemporaryDirectory(prefix=".restore-", dir=destination.parent) as folder:
        stage = Path(folder) / "store"
        stage.mkdir()
        for name, entry in bundle.manifest["artifacts"].items():
            path = member(stage, name)
            path.parent.mkdir(parents=True, exist_ok=True)
            # Copy in bounded chunks, then verify exactly the staged bytes.
            with member(source, name).open("rb") as inp, path.open("xb") as out:
                while chunk := inp.read(1024 * 1024):
                    out.write(chunk)
                out.flush()
                os.fsync(out.fileno())
            if path.stat().st_size != entry["bytes"] or digest_file(path) != entry["sha256"]:
                raise ValidationError("restore artifact checksum mismatch")
        with duckdb.connect(
            str(stage / "catalog.duckdb"), read_only=True, config={"enable_external_access": False}
        ) as conn:
            # Retained v2 backups remain readable; Store explicitly migrates on open.
            if conn.execute("SELECT max(version) FROM schema_migrations").fetchone() not in {
                (2,),
                (3,),
                (4,),
            }:
                raise ValidationError("unsupported restored catalog schema")
            conn.execute("SELECT count(*) FROM occurrences").fetchone()
            conn.execute("SELECT count(*) FROM coverage").fetchone()
        for directory in sorted(
            (p for p in stage.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True
        ):
            sync_directory(directory)
        sync_directory(stage)
        os.rename(stage, destination)
        sync_directory(destination.parent)
