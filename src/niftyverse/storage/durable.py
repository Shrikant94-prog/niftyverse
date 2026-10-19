"""Same-filesystem publication primitives with explicit platform scope.

File fsync + directory fsync on POSIX. Windows fsyncs file contents; Python
does not supply a tested directory-metadata/power-loss protocol here. Both
platforms are tested for abrupt process termination, not simulated power loss.
"""

import hashlib
import os
import tempfile
from pathlib import Path


def sync_directory(path: Path) -> None:
    if os.name != "nt":
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def sync_file(path: Path) -> None:
    with path.open("rb") as stream:
        os.fsync(stream.fileno())


def write_bytes(path: Path, payload: bytes) -> None:
    """Write an owned new staged file; caller controls final publication."""
    with path.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def digest_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def publish_raw(root: Path, sha256: str, payload: bytes) -> Path:
    directory = root / sha256[:2]
    directory.mkdir(exist_ok=True)
    sync_directory(root)
    destination = directory / sha256
    if destination.exists():
        if digest_file(destination) != sha256:
            raise ValueError("corrupt immutable raw object")
        return destination
    descriptor, name = tempfile.mkstemp(prefix=".raw-", dir=directory)
    stage = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if digest_file(stage) != sha256:
            raise ValueError("raw hash mismatch")
        os.rename(stage, destination)
        sync_directory(directory)
        return destination
    finally:
        stage.unlink(missing_ok=True)
