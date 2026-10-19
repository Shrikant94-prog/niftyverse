"""The same archive boundary applies before local taxonomy bytes are trusted."""

import asyncio
import hashlib
import io
import zipfile
from collections.abc import Iterator
from dataclasses import replace

import pytest

from niftyverse.filings import FilingFailure, FilingLimits
from niftyverse.taxonomy_zip import TaxonomyMember, load_taxonomy_zip

_loop: asyncio.AbstractEventLoop
URI = "https://taxonomy.example.test/entry.xsd"
BODY = b'<schema xmlns="http://www.w3.org/2001/XMLSchema"/>'


@pytest.fixture(scope="module", autouse=True)
def archive_loop() -> Iterator[None]:
    global _loop
    _loop = asyncio.new_event_loop()
    yield
    _loop.close()


def archive(name: str, body: bytes = BODY) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as target:
        target.writestr(name, body)
    return stream.getvalue()


def test_valid_bytes_are_hashed_without_extracting() -> None:
    result = _loop.run_until_complete(
        load_taxonomy_zip(
            archive("entry.xsd"),
            version="owned-test",
            entrypoint=URI,
            entry_refs=(URI,),
            members=(TaxonomyMember(URI, "entry.xsd", hashlib.sha256(BODY).hexdigest()),),
        )
    )
    assert result.resources[0].body == BODY


@pytest.mark.parametrize(
    "name", ["../entry.xsd", "/entry.xsd", "C:/entry.xsd", "x\\entry.xsd", "nested.zip"]
)
def test_unsafe_names_fail_before_reading(name: str) -> None:
    with pytest.raises(FilingFailure, match="unsafe_taxonomy_archive"):
        _loop.run_until_complete(
            load_taxonomy_zip(
                archive(name),
                version="owned-test",
                entrypoint=URI,
                entry_refs=(URI,),
                members=(TaxonomyMember(URI, name, hashlib.sha256(BODY).hexdigest()),),
            )
        )


def test_expansion_hash_truncation_and_cancellation() -> None:
    member = TaxonomyMember(URI, "entry.xsd", hashlib.sha256(BODY).hexdigest())
    for body, records, limits, code in [
        (
            archive("entry.xsd", b"x" * 100000),
            (member,),
            FilingLimits(),
            "unsafe_taxonomy_archive",
        ),
        (
            archive("entry.xsd"),
            (replace(member, sha256="0" * 64),),
            FilingLimits(),
            "taxonomy_hash",
        ),
        (archive("entry.xsd")[:-5], (member,), FilingLimits(), "unsafe_taxonomy_archive"),
        (archive("entry.xsd"), (member,), FilingLimits(max_taxonomy_bytes=10), "taxonomy_limit"),
    ]:
        with pytest.raises(FilingFailure, match=code):
            _loop.run_until_complete(
                load_taxonomy_zip(
                    body,
                    version="owned-test",
                    entrypoint=URI,
                    entry_refs=(URI,),
                    members=records,
                    limits=limits,
                )
            )

    async def cancel() -> None:
        task = asyncio.create_task(
            load_taxonomy_zip(
                archive("entry.xsd"),
                version="owned-test",
                entrypoint=URI,
                entry_refs=(URI,),
                members=(member,),
            )
        )
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]

    _loop.run_until_complete(cancel())
