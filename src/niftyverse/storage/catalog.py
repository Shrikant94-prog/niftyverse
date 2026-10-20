"""Single-owner typed catalog and transactional additive migrations."""

import os
import shutil
import threading
import warnings
from collections.abc import Callable
from math import isfinite
from pathlib import Path
from uuid import uuid4

import duckdb
import pyarrow as pa
from filelock import FileLock, Timeout

from niftyverse.storage.durable import sync_directory, sync_file
from niftyverse.storage.paths import diagnose_store
from niftyverse.storage.schemas import SCHEMAS

CATALOG_VERSION = 3


class WriterBusy(RuntimeError):
    """Another owner holds the live catalog; read an immutable snapshot instead."""


def migrate(
    connection: duckdb.DuckDBPyConnection,
    *,
    target: int = CATALOG_VERSION,
    fault: Callable[[], None] | None = None,
) -> None:
    connection.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY)"
    )
    row = connection.execute("SELECT coalesce(max(version), 0) FROM schema_migrations").fetchone()
    assert row is not None
    current = row[0]
    if not 0 <= current <= target <= CATALOG_VERSION:
        raise ValueError("unsupported migration version; downgrade is forbidden")
    for version in range(current + 1, target + 1):
        connection.execute("BEGIN TRANSACTION")
        try:
            if version == 1:
                connection.execute(
                    "CREATE TABLE captures (capture_id VARCHAR PRIMARY KEY, "
                    "kind VARCHAR NOT NULL, source_id VARCHAR NOT NULL, "
                    "origin VARCHAR NOT NULL, byte_length BIGINT NOT NULL)"
                )
                connection.execute(
                    "CREATE TABLE raw_objects "
                    "(sha256 VARCHAR PRIMARY KEY, byte_length BIGINT NOT NULL)"
                )
                connection.execute(
                    "CREATE TABLE capture_objects "
                    "(capture_id VARCHAR PRIMARY KEY, raw_sha256 VARCHAR NOT NULL)"
                )
                connection.execute(
                    "CREATE TABLE partitions "
                    "(partition_id VARCHAR PRIMARY KEY, contract_json VARCHAR NOT NULL)"
                )
                connection.execute(
                    "CREATE TABLE occurrences (occurrence_id VARCHAR PRIMARY KEY, "
                    "partition_id VARCHAR NOT NULL, content_identity VARCHAR NOT NULL, "
                    "capture_id VARCHAR NOT NULL, state VARCHAR NOT NULL, reason VARCHAR, "
                    "known_at TIMESTAMPTZ NOT NULL, checked_at TIMESTAMPTZ NOT NULL, "
                    "source_revision VARCHAR, schema_version VARCHAR NOT NULL, "
                    "normalizer_version VARCHAR NOT NULL)"
                )
                connection.execute(
                    "CREATE TABLE source_checks (check_id VARCHAR PRIMARY KEY, "
                    "request_identity VARCHAR NOT NULL, partition_id VARCHAR NOT NULL, "
                    "occurrence_id VARCHAR NOT NULL, checked_at TIMESTAMPTZ NOT NULL, "
                    "request_fingerprint VARCHAR)"
                )
                connection.execute(
                    "CREATE TABLE coverage (check_id VARCHAR PRIMARY KEY, "
                    "partition_id VARCHAR NOT NULL, occurrence_id VARCHAR NOT NULL, "
                    "status VARCHAR NOT NULL, evidence VARCHAR NOT NULL)"
                )
                connection.execute(
                    "CREATE TABLE jobs (check_id VARCHAR PRIMARY KEY, "
                    "request_identity VARCHAR NOT NULL, partition_id VARCHAR NOT NULL, "
                    "status VARCHAR NOT NULL, raw_sha256 VARCHAR NOT NULL, reason VARCHAR)"
                )
                for name, definition in SCHEMAS.items():
                    if name == "market_state_observations":
                        continue  # Introduced by migration 3, including on fresh databases.
                    empty = pa.Table.from_batches([], schema=definition)
                    connection.register("schema_input", empty)
                    connection.execute(
                        f"CREATE TABLE {name} AS SELECT CAST(NULL AS VARCHAR) AS occurrence_id, "
                        "* FROM schema_input WHERE false"
                    )
                    connection.unregister("schema_input")
            elif version == 2:
                connection.execute("ALTER TABLE captures ADD COLUMN sdk_version VARCHAR")
            elif version == 3:
                connection.register(
                    "schema_input",
                    pa.Table.from_batches([], schema=SCHEMAS["market_state_observations"]),
                )
                try:
                    connection.execute(
                        "CREATE TABLE market_state_observations AS "
                        "SELECT CAST(NULL AS VARCHAR) AS occurrence_id, "
                        "* FROM schema_input WHERE false"
                    )
                finally:
                    connection.unregister("schema_input")
            if fault:
                fault()
            connection.execute("INSERT INTO schema_migrations VALUES (?)", [version])
            connection.execute("COMMIT")
        except BaseException:
            connection.execute("ROLLBACK")
            raise


class Store:
    """Explicit writable context. The owning thread alone may use its connection.

    Other processes use immutable bundles, or wait for this context to close.
    No opening a store, migration or path creation happens at import time.
    """

    def __init__(self, root: Path | None = None, *, lock_timeout: float = 0.2) -> None:
        if not isfinite(lock_timeout) or not 0 <= lock_timeout <= 30:
            raise ValueError("writer lock timeout must be finite and within 0..30 seconds")
        self.location = diagnose_store(root)
        self.root = self.location.root
        self.lock_timeout = lock_timeout
        self._connection: duckdb.DuckDBPyConnection | None = None
        self._owner: tuple[int, int] | None = None
        self._lock: FileLock | None = None

    @property
    def connection(self) -> duckdb.DuckDBPyConnection:
        if self._connection is None or self._owner != (os.getpid(), threading.get_ident()):
            raise RuntimeError("store connection requires its open owning process/thread")
        return self._connection

    def __enter__(self) -> Store:
        if self._connection is not None:
            raise RuntimeError("store already open")
        for risk in self.location.risks:
            warnings.warn(risk, UserWarning, stacklevel=2)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = FileLock(self.location.paths["lock"], timeout=self.lock_timeout)
        try:
            self._lock.acquire()
        except Timeout as error:
            raise WriterBusy(
                f"writer busy at {self.root}; close its owner or read a snapshot"
            ) from error
        try:
            for key in ("raw", "staging", "spill", "snapshots", "exports", "backups"):
                self.location.paths[key].mkdir(parents=True, exist_ok=True)
            self._owner = (os.getpid(), threading.get_ident())
            db = self.location.paths["catalog"]
            self._connection = duckdb.connect(
                str(db),
                config={
                    "temp_directory": str(self.location.paths["spill"]),
                    "memory_limit": "256MB",
                    "threads": "2",
                },
            )
            self.connection.execute("SET enable_external_access = false")
            # Explicit open, checkpointed backup before any additive migration.
            if self.connection.execute(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_name='schema_migrations'"
            ).fetchone() == (1,):
                row = self.connection.execute(
                    "SELECT max(version) FROM schema_migrations"
                ).fetchone()
                if row and row[0] is not None and row[0] < CATALOG_VERSION:
                    self.connection.execute("CHECKPOINT")
                    # Windows DuckDB holds an exclusive file handle. Keep our
                    # OS writer lock, close the DB, then copy its checkpoint.
                    self._connection.close()
                    self._connection = None
                    backup_path = self.location.paths["backups"] / (
                        f"pre-migration-v{row[0]}-{uuid4().hex}.duckdb"
                    )
                    shutil.copyfile(db, backup_path)
                    sync_file(backup_path)
                    sync_directory(backup_path.parent)
                    self._connection = duckdb.connect(
                        str(db),
                        config={
                            "temp_directory": str(self.location.paths["spill"]),
                            "memory_limit": "256MB",
                            "threads": "2",
                        },
                    )
                    self.connection.execute("SET enable_external_access = false")
            migrate(self.connection)
        except BaseException:
            self.close()
            raise
        return self

    def read_table(self, name: str) -> pa.Table:
        if name not in SCHEMAS:
            raise ValueError("unknown fact table")
        table = self.connection.execute(f"SELECT * FROM {name}").to_arrow_table()
        # DuckDB preserves values/types but not Arrow NOT NULL metadata in CTAS.
        return table.cast(
            pa.schema([pa.field("occurrence_id", pa.string(), False), *SCHEMAS[name]])
        )

    def checkpoint_copy(self, destination: Path) -> None:
        """Consistent physical copy while retaining writer ownership (Windows too)."""
        self.connection.execute("CHECKPOINT")
        self.connection.close()
        self._connection = None
        try:
            if destination.exists():
                raise FileExistsError(destination)
            shutil.copyfile(self.location.paths["catalog"], destination)
        finally:
            self._connection = duckdb.connect(
                str(self.location.paths["catalog"]),
                config={
                    "temp_directory": str(self.location.paths["spill"]),
                    "memory_limit": "256MB",
                    "threads": "2",
                },
            )
            self.connection.execute("SET enable_external_access = false")

    def close(self) -> None:
        if self._connection is not None:
            self.connection.close()
            self._connection = None
        if self._lock is not None:
            self._lock.release()
            self._lock = None
        self._owner = None

    def __exit__(self, *_: object) -> None:
        self.close()
