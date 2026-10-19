"""Real issuer inline evidence plus owned transformations and hostile boundaries."""

import asyncio
import hashlib
import json
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest

from niftyverse.filing_xml import TaxonomyPackage
from niftyverse.filings import FilingFailure, FilingLimits, decode_filing
from niftyverse.taxonomy_zip import TaxonomyMember, load_taxonomy_zip

etree = pytest.importorskip("lxml.etree", reason="requires explicit filings extra")
FIXTURES = Path(__file__).parent / "fixtures/filings"
IX = "{http://www.xbrl.org/2013/inlineXBRL}"
LIMITS = FilingLimits(
    max_bytes=16 * 1024 * 1024,
    max_resources=64,
    max_taxonomy_bytes=40 * 1024 * 1024,
    max_nodes=160000,
    max_total_text=64 * 1024 * 1024,
)
_loop: asyncio.AbstractEventLoop


@pytest.fixture(scope="module", autouse=True)
def inline_loop() -> Iterator[None]:
    global _loop
    _loop = asyncio.new_event_loop()
    yield
    _loop.close()


@pytest.fixture(scope="module")
def package() -> TaxonomyPackage:
    folder = FIXTURES / "taxonomy-xii"
    data = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    assert (
        hashlib.sha256((folder / "resources.zip").read_bytes()).hexdigest()
        == data["archive_sha256"]
    )
    return _loop.run_until_complete(
        load_taxonomy_zip(
            (folder / "resources.zip").read_bytes(),
            version=data["version"],
            entrypoint=data["entrypoint"],
            entry_refs=tuple(data["entry_refs"]),
            members=tuple(
                TaxonomyMember(uri, record["member"], record["sha256"])
                for uri, record in data["resources"].items()
            ),
            limits=LIMITS,
        )
    )


def test_real_inline_exact_values_context_units_and_continuations(
    package: TaxonomyPackage,
) -> None:
    body = (FIXTURES / "xii-2023.html").read_bytes()
    result = _loop.run_until_complete(decode_filing(body, taxonomy=package, limits=LIMITS))
    assert result.family == "inline_xbrl" and result.complete is False
    assert len(result.facts) == 323
    cash = next(f for f in result.facts if f.locator == "#f8")
    assert cash.concept == "{http://fasb.org/us-gaap/2022}CashAndCashEquivalentsAtCarryingValue"
    assert (cash.raw_value, cash.value, cash.context_id, cash.unit_id) == (
        "942,024",
        "942024",
        "c2",
        "u1",
    )
    assert next(c for c in result.contexts if c.identifier == "c2").instant == "2023-06-30"
    signature = next(c for c in result.contexts if c.identifier == "signature")
    assert signature.forever and signature.other_xml and "Signature" in signature.other_xml[0]
    assert next(u for u in result.units if u.identifier == "u1").numerator == (
        "{http://www.xbrl.org/2003/iso4217}USD",
    )
    period = next(f for f in result.facts if f.locator == "#f2")
    assert period.value == "2023-06-30" and period.raw_value == "June 30, 2023"
    auditor = next(f for f in result.facts if f.locator == "#f3")
    assert auditor.continuation_locators == ("#f4",)
    assert "Auditor's Responsibilities" in (auditor.value or "")
    assert result.taxonomy_version == package.version and result.taxonomy_sha256


def test_prefixes_opaque_contexts_exact_scale_sign_and_exclusion(package: TaxonomyPackage) -> None:
    body = (FIXTURES / "xii-2023.html").read_bytes()
    root = etree.fromstring(body)
    cash = root.find(f".//{IX}nonFraction[@id='f8']")
    assert cash is not None
    cash.text = "123456789012345678901234567890.1234"
    cash.attrib.pop("format")
    cash.set("sign", "-")
    cash.set("scale", "3")
    changed = etree.tostring(root).replace(b"c2", b"OpaquePeriod").replace(b"ix:", b"inline:")
    changed = changed.replace(b"xmlns:ix=", b"xmlns:inline=")
    result = _loop.run_until_complete(decode_filing(changed, taxonomy=package, limits=LIMITS))
    assert result.family == "inline_xbrl"
    fact = next(f for f in result.facts if f.locator == "#f8")
    assert fact.value == "-123456789012345678901234567890123.4"
    assert fact.context_id == "OpaquePeriod" and fact.scale == 3 and fact.sign == "-"
    # Owned variation tests exclusion without changing real-source support claims.
    root = etree.fromstring(body)
    cash = root.find(f".//{IX}nonFraction[@id='f8']")
    assert cash is not None
    excluded = etree.SubElement(cash, IX + "exclude")
    excluded.text = "footnote"
    result = _loop.run_until_complete(
        decode_filing(etree.tostring(root), taxonomy=package, limits=LIMITS)
    )
    assert result.family == "inline_xbrl"
    fact = next(f for f in result.facts if f.locator == "#f8")
    assert fact.value == "942024" and "footnote" in fact.raw_value


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("format", "ixt:unknown", "unsupported_transformation"),
        ("sign", "+", "invalid_inline_number"),
        ("scale", "999999999", "inline_scale_limit"),
        ("contextRef", "absent", "unresolved_context_unit"),
        ("target", "other", "unsupported_inline"),
    ],
)
def test_invalid_inline_attributes_reject_atomically(
    package: TaxonomyPackage, field: str, value: str, code: str
) -> None:
    root = etree.fromstring((FIXTURES / "xii-2023.html").read_bytes())
    cash = root.find(f".//{IX}nonFraction[@id='f8']")
    assert cash is not None
    cash.set(field, value)
    with pytest.raises(FilingFailure) as error:
        _loop.run_until_complete(
            decode_filing(etree.tostring(root), taxonomy=package, limits=LIMITS)
        )
    assert error.value.code == code


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ("cycle", "continuation_cycle"),
        ("missing", "unresolved_continuation"),
        ("duplicate", "duplicate_id"),
    ],
)
def test_continuation_graph_failures(package: TaxonomyPackage, change: str, code: str) -> None:
    root = etree.fromstring((FIXTURES / "xii-2023.html").read_bytes())
    continuation = root.find(f".//{IX}continuation[@id='f4']")
    assert continuation is not None
    if change == "duplicate":
        continuation.set("id", "f3")
    else:
        continuation.set("continuedAt", "f4" if change == "cycle" else "absent")
    with pytest.raises(FilingFailure) as error:
        _loop.run_until_complete(
            decode_filing(etree.tostring(root), taxonomy=package, limits=LIMITS)
        )
    assert error.value.code == code


@pytest.mark.parametrize("value", [".5", "\u2212"])
def test_registry_2011_rejects_wrong_numeric_lexical_forms(
    package: TaxonomyPackage, value: str
) -> None:
    root = etree.fromstring((FIXTURES / "xii-2023.html").read_bytes())
    cash = root.find(f".//{IX}nonFraction[@id='f8']")
    assert cash is not None
    cash.text = value
    cash.set("format", "ixt:numdotdecimal" if value == ".5" else "ixt:zerodash")
    with pytest.raises(FilingFailure, match="invalid_transformation"):
        _loop.run_until_complete(
            decode_filing(etree.tostring(root), taxonomy=package, limits=LIMITS)
        )


def test_nested_facts_are_explicitly_unsupported(package: TaxonomyPackage) -> None:
    root = etree.fromstring((FIXTURES / "xii-2023.html").read_bytes())
    cash = root.find(f".//{IX}nonFraction[@id='f8']")
    assert cash is not None
    child = etree.SubElement(cash, IX + "nonNumeric")
    child.set("name", "dei:EntityRegistrantName")
    child.set("contextRef", "c1")
    child.text = "nested"
    with pytest.raises(FilingFailure, match="unsupported_inline"):
        _loop.run_until_complete(
            decode_filing(etree.tostring(root), taxonomy=package, limits=LIMITS)
        )


def test_mixed_inline_versions_cannot_silently_drop_facts(package: TaxonomyPackage) -> None:
    root = etree.fromstring((FIXTURES / "xii-2023.html").read_bytes())
    etree.SubElement(root, "{http://www.xbrl.org/2008/inlineXBRL}nonFraction").text = "1"
    with pytest.raises(FilingFailure, match="unsupported_inline"):
        _loop.run_until_complete(
            decode_filing(etree.tostring(root), taxonomy=package, limits=LIMITS)
        )


def test_closed_taxonomy_external_resources_deadline_and_cancel(package: TaxonomyPackage) -> None:
    body = (FIXTURES / "xii-2023.html").read_bytes()
    incomplete = replace(package, resources=package.resources[:-1])
    with pytest.raises(FilingFailure, match="taxonomy_unavailable"):
        _loop.run_until_complete(decode_filing(body, taxonomy=incomplete, limits=LIMITS))
    with pytest.raises(FilingFailure, match="external_reference"):
        _loop.run_until_complete(
            decode_filing(
                b'<!DOCTYPE html [<!ENTITY x SYSTEM "file:///secret">]>' + body,
                taxonomy=package,
                limits=LIMITS,
            )
        )
    for limits, code in [
        (replace(LIMITS, max_facts=1), "fact_limit"),
        (replace(LIMITS, max_resources=1), "taxonomy_limit"),
        (replace(LIMITS, max_nodes=1), "node_limit"),
    ]:
        with pytest.raises(FilingFailure, match=code):
            _loop.run_until_complete(decode_filing(body, taxonomy=package, limits=limits))
    elapsed = iter(range(1000000))
    with pytest.raises(FilingFailure, match="deadline"):
        _loop.run_until_complete(
            decode_filing(
                body,
                taxonomy=package,
                limits=replace(LIMITS, deadline=2),
                clock=lambda: float(next(elapsed)),
            )
        )

    async def cancel() -> None:
        task = asyncio.create_task(decode_filing(body, taxonomy=package, limits=LIMITS))
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]

    _loop.run_until_complete(cancel())

    async def cancel_during_work() -> None:
        calls = 0

        def cancelling_clock() -> float:
            nonlocal calls
            calls += 1
            if calls == 2000:
                current = asyncio.current_task()
                assert current is not None
                current.cancel()
            return 0.0

        task = asyncio.create_task(
            decode_filing(body, taxonomy=package, limits=LIMITS, clock=cancelling_clock)
        )
        with pytest.raises(asyncio.CancelledError):
            await task
        assert calls >= 2000
        assert not [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]

    _loop.run_until_complete(cancel_during_work())
