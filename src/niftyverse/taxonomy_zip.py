"""Explicit, bounded in-memory taxonomy ZIP loading; never extract or fetch."""

import asyncio
import io
import time
import zipfile
import zlib
from collections.abc import Callable
from dataclasses import dataclass

from niftyverse.filing_xml import TaxonomyPackage, TaxonomyResource
from niftyverse.filings import FilingFailure, FilingLimits
from niftyverse.ingestion import IngestionFailure, IngestionLimits, _check_directory, _safe_member


@dataclass(frozen=True)
class TaxonomyMember:
    uri: str
    member: str
    sha256: str


async def load_taxonomy_zip(
    body: bytes,
    *,
    version: str,
    entrypoint: str,
    entry_refs: tuple[str, ...],
    members: tuple[TaxonomyMember, ...],
    aliases: tuple[tuple[str, str], ...] = (),
    limits: FilingLimits | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> TaxonomyPackage:
    """All members must match the explicit closed manifest and source hashes.

    Shared report archive checks reject traversal, symlinks, encryption, ZIP64,
    metadata/member excess and unsupported compression. Expansion/ratio checks
    precede reads; chunk checkpoints bound elapsed work and permit cancellation.
    """
    limits = limits or FilingLimits()
    expires = clock() + limits.deadline
    if len(body) > limits.max_taxonomy_bytes or len(members) > limits.max_resources:
        raise FilingFailure("taxonomy_limit")
    if not members or len({m.member for m in members}) != len(members):
        raise FilingFailure("invalid_taxonomy")
    if any(
        "\\" in m.member
        or ":" in m.member
        or "\x00" in m.member
        or any(part in {"", ".", ".."} for part in m.member.split("/"))
        for m in members
    ):
        raise FilingFailure("unsafe_taxonomy_archive")
    directory_limits = IngestionLimits(max_members=limits.max_resources)
    try:
        _check_directory(body, directory_limits)
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            infos = archive.infolist()
            if {i.filename for i in infos} != {m.member for m in members}:
                raise FilingFailure("taxonomy_manifest_mismatch")
            names: set[str] = set()
            expanded = 0
            for info in infos:
                _safe_member(info, (".xml", ".xsd"))
                if info.filename.casefold() in names:
                    raise IngestionFailure("duplicate_member")
                names.add(info.filename.casefold())
                expanded += info.file_size
                if expanded > limits.max_taxonomy_bytes or info.file_size > limits.max_bytes:
                    raise FilingFailure("taxonomy_limit")
                if info.file_size > max(1, info.compress_size) * directory_limits.max_ratio:
                    raise IngestionFailure("ratio_limit")
            resources = []
            for member in members:
                content = bytearray()
                with archive.open(member.member) as stream:
                    while True:
                        await asyncio.sleep(0)
                        if clock() >= expires:
                            raise FilingFailure("deadline")
                        chunk = stream.read(65536)
                        if not chunk:
                            break
                        if len(content) + len(chunk) > limits.max_bytes:
                            raise FilingFailure("taxonomy_limit")
                        content.extend(chunk)
                resources.append(TaxonomyResource(member.uri, bytes(content), member.sha256))
    except IngestionFailure, zipfile.BadZipFile, EOFError, zlib.error, RuntimeError:
        raise FilingFailure("unsafe_taxonomy_archive") from None
    return TaxonomyPackage(version, entrypoint, entry_refs, tuple(resources), aliases)
