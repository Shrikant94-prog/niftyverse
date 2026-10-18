"""Source-backed rendered assertions and adversarial bounded dispatch."""

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest

from niftyverse.filings import FilingFailure, FilingLimits, decode_filing

pytest.importorskip("lxml.etree", reason="requires explicit filings extra")

_loop: asyncio.AbstractEventLoop


@pytest.fixture(scope="module", autouse=True)
def filing_loop() -> Iterator[None]:
    global _loop
    _loop = asyncio.new_event_loop()
    yield
    _loop.close()


@pytest.fixture
def rendered() -> bytes:
    return (Path(__file__).parent / "fixtures/filings/rendered-2026.html").read_bytes()


def test_real_rendered_contexts_and_original_values(rendered: bytes) -> None:
    result = _loop.run_until_complete(decode_filing(rendered, source="owned-snapshot"))
    assert result.family == "integrated_rendered_financial_html"
    assert result.source == "owned-snapshot" and not result.complete
    assert ("NSE Symbol", "RELIANCE") in result.metadata
    assert ("Description of presentation currency", "INR") in result.metadata
    assert ("Level of rounding used in financial results", "Lakhs") in result.metadata
    table = result.tables[1]
    row = next(c.row for c in table.cells if c.text == "Revenue from operations")
    assert [c.text for c in table.cells if c.row == row][-2:] == ["3,11,85,000.00"] * 2
    assert any(c.text == "01-04-2026" for c in table.cells)
    assert any(c.text == "30-06-2026" for c in table.cells)
    assert any(c.text == "15.48" for c in table.cells)
    assert table.cells[0].colspan == 2
    assert all(c.locator.startswith("table[") for c in table.cells)
    assert any("Lakhs" in h for h in table.headings)


def test_real_annual_four_statement_references() -> None:
    body = (Path(__file__).parent / "fixtures/filings/rendered-2025.html").read_bytes()
    result = _loop.run_until_complete(decode_filing(body))
    values = {c.text for t in result.tables for c in t.cells}
    assert {
        "2645730000000",
        "9801360000000",
        "19501210000000",
        "1787030000000",
        "-1375350000000",
        "-318910000000",
        "64400000000",
        "252110000000",
        "14.34",
        "51.47",
    } <= values
    assert len(result.tables) == 12


@pytest.mark.parametrize(
    "body,code",
    [
        (b"<html><title>Access Denied</title></html>", "source_blocked"),
        (b"<html><table><tr><td>123</td></tr></table></html>", "unsupported_family"),
        (
            b'<?xml version="1.0"?><xbrl xmlns="http://www.xbrl.org/2003/instance"/>',
            "taxonomy_unavailable",
        ),
        (
            b'<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"><ix:nonFraction/></html>',
            "unsupported_inline",
        ),
        (b'<!DOCTYPE x [<!ENTITY a SYSTEM "file:///secret">]><x>&a;</x>', "external_reference"),
        (
            b'<x xmlns:xi="http://www.w3.org/2001/XInclude"><xi:include href="file:///secret"/></x>',
            "external_reference",
        ),
        (b"<not-closed", "invalid_document"),
        (b"\xff\xfe<\x00h\x00t\x00m\x00l\x00", "unsupported_encoding"),
    ],
)
def test_dispatch_failures(body: bytes, code: str) -> None:
    with pytest.raises(FilingFailure) as caught:
        _loop.run_until_complete(decode_filing(body))
    assert caught.value.code == code


def test_size_depth_cells_time_and_cancellation(rendered: bytes) -> None:
    for limits, code in [
        (FilingLimits(max_bytes=10), "document_limit"),
        (FilingLimits(max_depth=3), "depth_limit"),
        (FilingLimits(max_cells=3), "cell_limit"),
        (FilingLimits(max_nodes=3), "node_limit"),
        (FilingLimits(max_text=10), "text_limit"),
    ]:
        with pytest.raises(FilingFailure, match=code):
            _loop.run_until_complete(decode_filing(rendered, limits=limits))
    now = 0.0

    def clock() -> float:
        nonlocal now
        now += 1
        return now

    with pytest.raises(FilingFailure, match="deadline"):
        _loop.run_until_complete(
            decode_filing(rendered, limits=FilingLimits(deadline=2), clock=clock)
        )

    async def check() -> None:
        job = asyncio.create_task(decode_filing(rendered))
        await asyncio.sleep(0)
        job.cancel()
        with pytest.raises(asyncio.CancelledError):
            await job
        assert not [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]

    _loop.run_until_complete(check())


def test_unregistered_damage_cannot_reuse_known_recovery(rendered: bytes) -> None:
    for body in [rendered.replace(b"RELIANCE", b"ALTERED"), rendered.replace(b"</table>", b"", 1)]:
        with pytest.raises(FilingFailure, match="invalid_document"):
            _loop.run_until_complete(decode_filing(body))


def test_valid_spans_and_inert_page_resources(rendered: bytes, tmp_path: Path) -> None:
    from lxml import etree

    # Normalize only this owned adversarial fixture, never the source snapshots.
    root = etree.HTML(rendered, parser=etree.HTMLParser(no_network=True))
    cell = root.findall(".//td")[0]
    cell.set("rowspan", "2")
    marker = etree.SubElement(cell, "img", src="file:///should-not-be-read")
    marker.tail = ""
    body = etree.tostring(root, method="html")
    result = _loop.run_until_complete(decode_filing(body))
    assert result.tables[0].cells[1].rowspan == 2
    cell.set("rowspan", "99999")
    with pytest.raises(FilingFailure, match="invalid_span"):
        _loop.run_until_complete(decode_filing(etree.tostring(root, method="html")))
    assert not list(tmp_path.iterdir())


def test_parser_python_allocation_bound(rendered: bytes) -> None:
    import tracemalloc

    tracemalloc.start()
    try:
        result = _loop.run_until_complete(decode_filing(rendered))
        _, peak = tracemalloc.get_traced_memory()
        assert result.tables and peak < 16 * 1024 * 1024
    finally:
        tracemalloc.stop()


def test_real_legacy_financial_html() -> None:
    body = (Path(__file__).parent / "fixtures/filings/legacy-reliance.html").read_bytes()
    result = _loop.run_until_complete(decode_filing(body, source="official-legacy"))
    assert result.family == "legacy_financial_html" and result.complete is False
    assert ("Period Ended", "31-Dec-2009") in result.metadata
    assert ("Consolidated / Non-Consolidated", "Non-Consolidated") in result.metadata
    assert len(result.tables) == 3  # layout wrappers do not duplicate their nested facts
    cells = [c for t in result.tables for c in t.cells]
    assert sum(c.text == "5685600.00" for c in cells) == 1
    assert any(c.text == "Amount(Rs. in lakhs)" for c in cells)
    assert any(c.text == "12.30" for c in cells)
    assert any(c.text == "-" for c in cells)
    assert any(c.locator.startswith("table[5]") for c in cells)
