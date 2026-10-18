"""Bounded dispatch and source assertions for evidenced financial filing families.

This module performs no economic mapping, taxonomy downloads or publication.
XML decoding requires an explicit closed local taxonomy. Unsupported versions
and genuine inline inputs fail explicitly; no summary replaces missing facts.
"""

import asyncio
import hashlib
import importlib.metadata
import math
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, overload

# Exact real specimens contain known malformed attributes/optional closures.
# Do not generalize their recovery profile to newly acquired broken documents.
_RECOVERED_SPECIMENS = frozenset(
    {
        "2fdffa2d19d0b275b0d3dae9b95ecf515a90c29ad0e84f7fe3134213579e6747",
        "0a22cb0aad493e026a0775fb889341ccbd5f61be355ef3ad194d46592889c629",
        "baa0c6c7a6c59ded283c4f0bd118d8a8f9d487048e4c285d2baaaae6834d2556",
    }
)

if TYPE_CHECKING:
    from lxml import etree

    from niftyverse.filing_xml import TaxonomyPackage, XmlAssertions


class FilingFailure(ValueError):
    """Safe typed diagnostic, independent of untrusted parser error text."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(message or code)


class FilingProcessorUnavailable(FilingFailure):
    """The optional pinned processor is unavailable."""

    def __init__(self) -> None:
        super().__init__("missing_dependency", "Install niftyverse[filings] (lxml==6.1.3)")


def require_filing_processor() -> None:
    """Check the explicitly requested processor without importing it in core."""
    try:
        if importlib.metadata.version("lxml") != "6.1.3":
            raise FilingProcessorUnavailable()
    except importlib.metadata.PackageNotFoundError:
        raise FilingProcessorUnavailable() from None


@dataclass(frozen=True)
class FilingLimits:
    max_bytes: int = 8 * 1024 * 1024
    max_depth: int = 64
    max_nodes: int = 100000
    max_cells: int = 100000
    max_tables: int = 128
    max_text: int = 1024 * 1024
    max_total_text: int = 16 * 1024 * 1024
    max_span: int = 256
    max_facts: int = 100000
    max_contexts: int = 10000
    max_resources: int = 32
    max_taxonomy_bytes: int = 32 * 1024 * 1024
    max_attributes: int = 64
    max_namespaces: int = 64
    max_name_chars: int = 2048
    deadline: float = 30

    def __post_init__(self) -> None:
        if min(
            self.max_bytes,
            self.max_depth,
            self.max_nodes,
            self.max_cells,
            self.max_tables,
            self.max_text,
            self.max_total_text,
            self.max_span,
            self.max_facts,
            self.max_contexts,
            self.max_resources,
            self.max_taxonomy_bytes,
            self.max_attributes,
            self.max_namespaces,
            self.max_name_chars,
        ) <= 0 or (not math.isfinite(self.deadline) or self.deadline <= 0):
            raise ValueError("invalid filing limits")


@dataclass(frozen=True)
class HtmlCell:
    row: int
    column: int
    rowspan: int
    colspan: int
    raw_text: str
    text: str
    locator: str
    is_header: bool


@dataclass(frozen=True)
class HtmlTable:
    headings: tuple[str, ...]
    cells: tuple[HtmlCell, ...]


@dataclass(frozen=True)
class HtmlAssertions:
    family: Literal["integrated_rendered_financial_html", "legacy_financial_html"]
    source: str
    sha256: str
    metadata: tuple[tuple[str, str], ...]
    tables: tuple[HtmlTable, ...]
    diagnostics: tuple[str, ...]
    complete: Literal[False] = False


def _text(element: etree._Element) -> str:
    return "".join(element.itertext())


def _span(value: str | None, limits: FilingLimits) -> int:
    if value is None:
        return 1
    if not re.fullmatch(r"[0-9]{1,3}", value) or not 1 <= int(value) <= limits.max_span:
        raise FilingFailure("invalid_span")
    return int(value)


@overload
async def decode_filing(
    body: bytes,
    *,
    source: str = "",
    limits: FilingLimits | None = None,
    clock: Callable[[], float] = time.monotonic,
    taxonomy: None = None,
) -> HtmlAssertions: ...


@overload
async def decode_filing(
    body: bytes,
    *,
    taxonomy: TaxonomyPackage,
    source: str = "",
    limits: FilingLimits | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> HtmlAssertions | XmlAssertions: ...


async def decode_filing(
    body: bytes,
    *,
    source: str = "",
    limits: FilingLimits | None = None,
    clock: Callable[[], float] = time.monotonic,
    taxonomy: TaxonomyPackage | None = None,
) -> HtmlAssertions | XmlAssertions:
    """Decode exact table/column contexts, captions, original values and locators.

    Native parser receives 4096-byte chunks with a cancellation/time checkpoint
    between them. Finite input/node/depth/text/cell/span bounds constrain owned
    memory; no child process, task, external resource or database is created.
    This is syntax-level source evidence, not XBRL validation or mapped facts.
    """
    require_filing_processor()
    from lxml import etree

    limits = limits or FilingLimits()
    expires = clock() + limits.deadline

    async def checkpoint() -> None:
        await asyncio.sleep(0)
        if clock() >= expires:
            raise FilingFailure("deadline")

    if len(body) > limits.max_bytes:
        raise FilingFailure("document_limit")
    try:
        body.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise FilingFailure("unsupported_encoding") from None
    digest = hashlib.sha256(body).hexdigest()
    known_recovery = digest in _RECOVERED_SPECIMENS
    lower = body.lower()
    if b"\x00" in body:
        raise FilingFailure("unsupported_encoding")
    if any(marker in lower for marker in (b"<!entity", b"<![", b"xinclude")):
        raise FilingFailure("external_reference")
    if any(
        marker in lower[:8192]
        for marker in (b"access denied", b"captcha", b"verify you are human", b"request rejected")
    ):
        raise FilingFailure("source_blocked")
    if any(
        uri in lower
        for uri in (b"http://www.xbrl.org/2013/inlinexbrl", b"http://www.xbrl.org/2008/inlinexbrl")
    ):
        raise FilingFailure("unsupported_inline")

    class DenyResolver(etree.Resolver):
        def resolve(self, url: str | None, pubid: str | None, context: object) -> None:
            raise FilingFailure("external_reference")

    # Root detection uses actual parsed XML, not URL, year or context names.
    is_html = bool(re.search(rb"<(?:[a-z0-9_-]+:)?html(?:\s|>)", lower[:4096]))
    if not is_html and taxonomy is not None:
        from niftyverse.filing_xml import decode_xml_filing

        return await decode_xml_filing(
            body, taxonomy, source=source, limits=limits, clock=clock, _expires=expires
        )
    parser: etree.HTMLPullParser | etree.XMLPullParser
    if is_html:
        for tag in (b"table", b"tr", b"td", b"th"):
            starts = len(re.findall(b"<" + tag + rb"(?:\s|>)", lower))
            ends = len(re.findall(b"</" + tag + rb"\s*>", lower))
            if starts != ends and not known_recovery:
                raise FilingFailure("invalid_document")
        parser = etree.HTMLPullParser(
            events=("start", "end"),
            no_network=True,
            huge_tree=False,
            recover=True,
            encoding="utf-8",
        )
    else:
        if b"<!doctype" in lower:
            raise FilingFailure("external_reference")
        parser = etree.XMLPullParser(
            events=("start", "end"),
            no_network=True,
            resolve_entities=False,
            load_dtd=False,
            dtd_validation=False,
            huge_tree=False,
            recover=False,
        )
    parser.resolvers.add(DenyResolver())
    depth = nodes = cells = total_text = 0
    try:
        for offset in range(0, len(body), 4096):
            await checkpoint()
            parser.feed(body[offset : offset + 4096])
            for event, element in parser.read_events():
                if event == "start":
                    depth += 1
                    nodes += 1
                    if depth > limits.max_depth:
                        raise FilingFailure("depth_limit")
                    if nodes > limits.max_nodes:
                        raise FilingFailure("node_limit")
                    if element.tag in {"td", "th"}:
                        cells += 1
                        if cells > limits.max_cells:
                            raise FilingFailure("cell_limit")
                else:
                    depth -= 1
                    for text in (element.text, element.tail):
                        if text:
                            if len(text) > limits.max_text:
                                raise FilingFailure("text_limit")
                            total_text += len(text)
                            if total_text > limits.max_total_text:
                                raise FilingFailure("text_limit")
        root = parser.close()
        await checkpoint()
    except etree.LxmlError:
        raise FilingFailure("invalid_document") from None
    diagnostics: tuple[str, ...] = ()
    if is_html and parser.feed_error_log:
        allowed = {"ERR_TAG_NAME_MISMATCH", "ERR_GT_REQUIRED", "ERR_NAME_REQUIRED"}
        if not known_recovery or any(
            entry.type_name not in allowed for entry in parser.feed_error_log
        ):
            raise FilingFailure("invalid_document")
        diagnostics = ("html_recovered",)
    if root is None:
        raise FilingFailure("invalid_document")
    if root.tag == "{http://www.xbrl.org/2003/instance}xbrl":
        raise FilingFailure("taxonomy_unavailable")
    if not is_html or root.tag != "html":
        raise FilingFailure("unsupported_family")
    titles = root.findall(".//title")
    legacy = (
        b"net sales/income from operation" in lower and b"consolidated / non-consolidated" in lower
    )
    if not legacy and (len(titles) != 1 or _text(titles[0]).strip() != "IndAS Details"):
        raise FilingFailure("unsupported_family")
    tables: list[HtmlTable] = []
    headings: list[str] = []
    table_index = -1
    for element in root.iter():
        await checkpoint()
        if element.tag in {"h1", "h2", "h3", "caption"}:
            headings.append(" ".join(_text(element).split()))
        if element.tag != "table":
            continue
        table_index += 1
        if table_index >= limits.max_tables:
            raise FilingFailure("table_limit")
        if element.findall(".//table") and not legacy:
            raise FilingFailure("unsupported_nested_table")
        table_cells: list[HtmlCell] = []
        occupied: dict[tuple[int, int], bool] = {}
        rows = element.xpath("./tr | ./thead/tr | ./tbody/tr | ./tfoot/tr")
        for row_no, row in enumerate(rows):
            await checkpoint()
            if legacy and row.findall(".//table"):
                continue
            column = 0
            for cell in row:
                if cell.tag not in {"td", "th"}:
                    continue
                while (row_no, column) in occupied:
                    column += 1
                rowspan, colspan = (
                    _span(cell.get("rowspan"), limits),
                    _span(cell.get("colspan"), limits),
                )
                # Keep span occupancy finite separately from physical cell count.
                if len(occupied) + rowspan * colspan > limits.max_cells:
                    raise FilingFailure("span_limit")
                for y in range(row_no, row_no + rowspan):
                    for x in range(column, column + colspan):
                        if (y, x) in occupied:
                            raise FilingFailure("overlapping_span")
                        occupied[y, x] = True
                raw = _text(cell)
                if len(raw) > limits.max_text:
                    raise FilingFailure("text_limit")
                table_cells.append(
                    HtmlCell(
                        row_no,
                        column,
                        rowspan,
                        colspan,
                        raw,
                        " ".join(raw.split()),
                        f"table[{table_index}]/row[{row_no}]/column[{column}]",
                        cell.tag == "th",
                    )
                )
                column += colspan
        if table_cells or not legacy:
            tables.append(HtmlTable(tuple(headings), tuple(table_cells)))
        headings.clear()
    if not tables:
        raise FilingFailure("unsupported_family")
    if legacy:
        legacy_rows: dict[int, list[str]] = {}
        for cell in tables[0].cells:
            legacy_rows.setdefault(cell.row, []).append(cell.text)
        legacy_metadata = tuple(
            (values[index], values[index + 1])
            for values in legacy_rows.values()
            if len(values) == 4
            for index in (0, 2)
        )
        expected = {
            "Symbol",
            "Company",
            "Audited / Un-Audited",
            "Period",
            "Consolidated / Non-Consolidated",
            "Period Ended",
        }
        cell_texts = {c.text for t in tables[1:] for c in t.cells}
        if (
            not expected <= {k for k, v in legacy_metadata if v}
            or not {"Amount(Rs. in lakhs)", "Net Sales/Income from Operation"} <= cell_texts
        ):
            raise FilingFailure("unsupported_family")
        return HtmlAssertions(
            "legacy_financial_html", source, digest, legacy_metadata, tuple(tables), diagnostics
        )
    metadata_rows: dict[int, list[str]] = {}
    for cell in tables[0].cells:
        metadata_rows.setdefault(cell.row, []).append(cell.text)
    metadata = tuple(
        (values[0], values[1]) for values in metadata_rows.values() if len(values) == 2
    )
    required = {
        "NSE Symbol",
        "ISIN",
        "Name of company",
        "Description of presentation currency",
        "Nature of report standalone or consolidated",
    }
    if not required <= {key for key, value in metadata if value}:
        raise FilingFailure("unsupported_family")
    details = dict(metadata)
    if details["Description of presentation currency"] != "INR (in Actuals)" and not (
        details["Description of presentation currency"] == "INR"
        and details.get("Level of rounding used in financial results") == "Lakhs"
    ):
        raise FilingFailure("unsupported_units")
    financial = any(
        {
            "Revenue from operations",
            "Date of start of reporting period",
            "Date of end of reporting period",
        }
        <= {c.text for c in table.cells}
        for table in tables[1:]
    )
    if not financial:
        raise FilingFailure("unsupported_family")
    return HtmlAssertions(
        "integrated_rendered_financial_html",
        source,
        digest,
        metadata,
        tuple(tables),
        diagnostics,
    )
