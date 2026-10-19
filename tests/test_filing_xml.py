"""Real 2020 XML/closed resources, independent numerical source expectations."""

import asyncio
import hashlib
import json
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from niftyverse.filing_xml import TaxonomyPackage, TaxonomyResource, decode_xml_filing
from niftyverse.filings import FilingFailure, FilingLimits

pytest.importorskip("lxml.etree", reason="requires explicit filings extra")
_loop: asyncio.AbstractEventLoop
FIXTURES = Path(__file__).parent / "fixtures/filings"
NS = "http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin"


@pytest.fixture(scope="module", autouse=True)
def xml_loop() -> Iterator[None]:
    global _loop
    _loop = asyncio.new_event_loop()
    yield
    _loop.close()


@pytest.fixture
def package() -> TaxonomyPackage:
    folder = FIXTURES / "taxonomy2020"
    data = json.loads((folder / "manifest.json").read_text())
    resources = []
    for key, record in data["resources"].items():
        with zipfile.ZipFile(folder / record["archive"]) as archive:
            body = archive.read(record["member"])
        resources.append(TaxonomyResource(key, body, record["sha256"]))
    return TaxonomyPackage(
        data["version"],
        data["entrypoint"],
        tuple(data["entry_refs"]),
        tuple(resources),
        tuple(data["aliases"].items()),
    )


def test_real_xml_source_assertions(package: TaxonomyPackage) -> None:
    body = (FIXTURES / "older-indas.xml").read_bytes()
    result = _loop.run_until_complete(decode_xml_filing(body, package, source="official-snapshot"))
    assert result.source == "official-snapshot" and result.complete is False
    facts = [f for f in result.facts if f.concept == f"{{{NS}}}RevenueFromOperations"]
    assert [(f.context_id, f.value, f.decimals) for f in facts] == [
        ("OneD", "1282600000000.00", "-7"),
        ("FourD", "3966450000000.00", "-7"),
    ]
    contexts = {c.identifier: c for c in result.contexts}
    for fact in facts:
        assert contexts[fact.context_id].entity == "RELIANCE"
        assert contexts[fact.context_id].start == "2024-10-01"
        assert contexts[fact.context_id].end == "2024-12-31"
        assert fact.unit_id == "INR" and fact.locator.startswith("/xbrl/child[")
    unit = next(u for u in result.units if u.identifier == "INRPerShare")
    assert unit.numerator == ("{http://www.xbrl.org/2003/iso4217}INR",)
    assert unit.denominator == ("{http://www.xbrl.org/2003/instance}shares",)
    assert any(c.dimensions for c in result.contexts)
    assert result.taxonomy_sha256 and result.taxonomy_version == package.version


def test_prefix_and_context_permutations_preserve_facts(package: TaxonomyPackage) -> None:
    body = (FIXTURES / "older-indas.xml").read_bytes()
    permuted = body.replace(b"in-bse-fin:", b"changed:").replace(
        b"xmlns:in-bse-fin=", b"xmlns:changed="
    )
    permuted = permuted.replace(b"OneD", b"OpaqueContextName")
    a = _loop.run_until_complete(decode_xml_filing(body, package))
    b = _loop.run_until_complete(decode_xml_filing(permuted, package))
    assert [(f.concept, f.value, f.unit_id) for f in a.facts] == [
        (f.concept, f.value, f.unit_id) for f in b.facts
    ]
    assert any(c.identifier == "OpaqueContextName" for c in b.contexts)


def test_closed_package_hash_and_unknown_references(package: TaxonomyPackage) -> None:
    body = (FIXTURES / "older-indas.xml").read_bytes()
    for reference in [
        b"file:///secret.xsd",
        b"../../escape.xsd",
        b"https://evil.test/taxonomy.xsd",
    ]:
        bad = body.replace(b"Ind-AS_entry_point_2020-03-31.xsd", reference)
        with pytest.raises(FilingFailure, match="taxonomy_unavailable"):
            _loop.run_until_complete(decode_xml_filing(bad, package))
    resources = package.resources[:-1]
    incomplete = TaxonomyPackage(
        package.version, package.entrypoint, package.entry_refs, resources, package.aliases
    )
    with pytest.raises(FilingFailure, match="taxonomy_unavailable"):
        _loop.run_until_complete(decode_xml_filing(body, incomplete))
    first = package.resources[0]
    with pytest.raises(FilingFailure, match="taxonomy_hash"):
        TaxonomyResource(first.uri, first.body + b" ", first.sha256)
    assert (
        hashlib.sha256(body).hexdigest()
        == "7a4376e20bcff469a6674116f0e45a76233d6358517d082a0a714ba78e6c2e96"
    )


def test_duplicate_context_and_limits_reject_atomically(package: TaxonomyPackage) -> None:
    body = (FIXTURES / "older-indas.xml").read_bytes()
    with pytest.raises(FilingFailure, match="duplicate_context"):
        _loop.run_until_complete(
            decode_xml_filing(body.replace(b'id="FourD"', b'id="OneD"'), package)
        )
    for limits, code in [
        (FilingLimits(max_facts=1), "fact_limit"),
        (FilingLimits(max_contexts=1), "context_limit"),
        (FilingLimits(max_depth=2), "depth_limit"),
    ]:
        with pytest.raises(FilingFailure, match=code):
            _loop.run_until_complete(decode_xml_filing(body, package, limits=limits))
    with pytest.raises(FilingFailure, match="external_reference"):
        _loop.run_until_complete(
            decode_xml_filing(
                b'<!DOCTYPE x [<!ENTITY a SYSTEM "file:///secret">]><x>&a;</x>', package
            )
        )


def test_duplicate_period_and_unapproved_document_reference(package: TaxonomyPackage) -> None:
    from lxml import etree

    original = (FIXTURES / "older-indas.xml").read_bytes()
    root = etree.fromstring(original)
    period = root.find(".//{http://www.xbrl.org/2003/instance}period")
    assert period is not None
    etree.SubElement(period, "{http://www.xbrl.org/2003/instance}startDate").text = "2000-01-01"
    with pytest.raises(FilingFailure, match="invalid_period"):
        _loop.run_until_complete(decode_xml_filing(etree.tostring(root), package))


def test_comments_are_inert_within_periods(package: TaxonomyPackage) -> None:
    body = (
        (FIXTURES / "older-indas.xml")
        .read_bytes()
        .replace(b"<xbrli:period>", b"<xbrli:period><!-- inert -->", 1)
    )
    result = _loop.run_until_complete(decode_xml_filing(body, package))
    assert result.facts


def test_forever_period_is_preserved_without_invented_dates(package: TaxonomyPackage) -> None:
    from lxml import etree

    root = etree.fromstring((FIXTURES / "older-indas.xml").read_bytes())
    period = root.find(".//{http://www.xbrl.org/2003/instance}period")
    assert period is not None
    for child in list(period):
        period.remove(child)
    etree.SubElement(period, "{http://www.xbrl.org/2003/instance}forever")
    result = _loop.run_until_complete(decode_xml_filing(etree.tostring(root), package))
    assert result.contexts[0].forever is True
    assert result.contexts[0].start is result.contexts[0].end is result.contexts[0].instant is None
    etree.SubElement(period, "{http://www.xbrl.org/2003/instance}instant").text = "2023-01-01"
    with pytest.raises(FilingFailure, match="invalid_period"):
        _loop.run_until_complete(decode_xml_filing(etree.tostring(root), package))


def test_unapproved_document_reference(package: TaxonomyPackage) -> None:
    from lxml import etree

    root = etree.fromstring((FIXTURES / "older-indas.xml").read_bytes())
    link = etree.SubElement(root, "{http://www.xbrl.org/2003/linkbase}linkbaseRef")
    link.set("{http://www.w3.org/1999/xlink}href", "file:///should-not-be-read")
    with pytest.raises(FilingFailure, match="taxonomy_unavailable"):
        _loop.run_until_complete(decode_xml_filing(etree.tostring(root), package))


def test_nil_duplicate_fact_and_cancel_cleanup(package: TaxonomyPackage) -> None:
    import copy

    from lxml import etree

    root = etree.fromstring((FIXTURES / "older-indas.xml").read_bytes())
    fact = root.find(f"{{{NS}}}RevenueFromOperations")
    assert fact is not None
    duplicate = copy.deepcopy(fact)
    root.append(duplicate)
    fact.set("{http://www.w3.org/2001/XMLSchema-instance}nil", "true")
    fact.text = None
    result = _loop.run_until_complete(decode_xml_filing(etree.tostring(root), package))
    facts = [f for f in result.facts if f.concept == f"{{{NS}}}RevenueFromOperations"]
    assert len(facts) == 3 and facts[0].nil and facts[0].value is None
    assert facts[-1].value == "1282600000000.00"

    async def check() -> None:
        job = asyncio.create_task(decode_xml_filing(etree.tostring(root), package))
        await asyncio.sleep(0)
        job.cancel()
        with pytest.raises(asyncio.CancelledError):
            await job
        assert not [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]

    _loop.run_until_complete(check())


def test_shared_content_dispatch_with_explicit_taxonomy(package: TaxonomyPackage) -> None:
    from niftyverse.filings import decode_filing

    result = _loop.run_until_complete(
        decode_filing((FIXTURES / "older-indas.xml").read_bytes(), taxonomy=package)
    )
    assert result.family == "older_financial_xbrl" and result.facts


@pytest.mark.parametrize(
    ("name", "code"),
    [
        ("missing-taxonomy-2026.xml", "taxonomy_unavailable"),
        ("mismatched-2018.xml", "schema_namespace_mismatch"),
    ],
)
def test_real_unavailable_and_vendor_mismatched_sources_are_quarantined(
    package: TaxonomyPackage, name: str, code: str
) -> None:
    from niftyverse.filings import decode_filing

    with pytest.raises(FilingFailure) as failure:
        _loop.run_until_complete(decode_filing((FIXTURES / name).read_bytes(), taxonomy=package))
    assert failure.value.code == code


def test_quarantine_status_without_an_explicit_package() -> None:
    from niftyverse.filings import decode_filing

    for name, code in [
        ("mismatched-2018.xml", "schema_namespace_mismatch"),
        ("missing-taxonomy-2026.xml", "taxonomy_unavailable"),
    ]:
        with pytest.raises(FilingFailure) as failure:
            _loop.run_until_complete(decode_filing((FIXTURES / name).read_bytes()))
        assert failure.value.code == code


def test_large_inherited_namespace_is_rejected_before_output_expansion(
    package: TaxonomyPackage,
) -> None:
    body = (FIXTURES / "older-indas.xml").read_bytes()
    body = body.replace(
        b"<xbrli:xbrl ",
        b'<xbrli:xbrl xmlns:unused="https://example.test/' + b"x" * 5000 + b'" ',
        1,
    )
    with pytest.raises(FilingFailure, match="namespace_limit"):
        _loop.run_until_complete(decode_xml_filing(body, package))
