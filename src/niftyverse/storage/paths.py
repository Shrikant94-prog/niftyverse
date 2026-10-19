"""Resolve all active storage beneath one OS-local root, without creating it."""

import os
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_data_path


@dataclass(frozen=True)
class StoreLocation:
    root: Path
    paths: dict[str, Path]
    risks: tuple[str, ...]


def diagnose_store(root: Path | None = None) -> StoreLocation:
    resolved = (
        (
            root
            if root is not None
            else user_data_path("niftyverse", appauthor=False, roaming=False) / "store"
        )
        .expanduser()
        .resolve()
    )
    text = str(resolved).lower().replace("\\", "/")
    risks = []
    synced = ("onedrive", "dropbox", "google drive", "googledrive", "icloud")
    if any(part in text for part in synced) or any(
        resolved.is_relative_to(Path(value).resolve())
        for key in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial")
        if (value := os.environ.get(key))
    ):
        risks.append("unsupported active store location: potentially synchronized folder")
    if text.startswith(("//", "/net/", "/mnt/")):
        risks.append("unsupported active store location: potentially network-mounted path")
    names = {
        "catalog": "catalog.duckdb",
        "wal": "catalog.duckdb.wal",
        "lock": "writer.lock",
        "raw": "raw/sha256",
        "staging": "staging",
        "spill": "spill",
        "snapshots": "snapshots",
        "exports": "exports",
        "backups": "backups",
    }
    return StoreLocation(resolved, {k: resolved / v for k, v in names.items()}, tuple(risks))
