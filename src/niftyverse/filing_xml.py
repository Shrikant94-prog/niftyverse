"""Pure source assertions with an explicitly supplied closed local taxonomy.

No implicit schema fetch, filesystem resolution, economic mapping or publication.
The supported real family is NSE Ind-AS 2020; unknown constructs fail explicitly.
"""

import asyncio
import hashlib
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Literal
from urllib.parse import unquote, urldefrag, urljoin, urlsplit

from niftyverse.filings import (
    FilingFailure,
    FilingLimits,
    _check_quarantine,
    require_filing_processor,
)

if TYPE_CHECKING:
    from lxml import etree

_XBRLI = "{http://www.xbrl.org/2003/instance}"
_XSD = "{http://www.w3.org/2001/XMLSchema}"
_LINK = "{http://www.xbrl.org/2003/linkbase}"
_XLINK = "{http://www.w3.org/1999/xlink}"
_XBRLDI = "{http://xbrl.org/2006/xbrldi}"
_NSE_2020 = "http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin"


def _uri(value: str) -> None:
    if len(value) > 2048:
        raise FilingFailure("taxonomy_unavailable")
    try:
        parts = urlsplit(value)
    except ValueError:
        raise FilingFailure("taxonomy_unavailable") from None
    path = unquote(parts.path)
    if (
        parts.scheme not in {"http", "https"}
        or not parts.hostname
        or parts.username
        or parts.password
        or parts.query
        or parts.fragment
        or "\\" in path
        or "\x00" in path
        or ".." in path.split("/")
    ):
        raise FilingFailure("taxonomy_unavailable")


@dataclass(frozen=True)
class TaxonomyResource:
    uri: str
    body: bytes
    sha256: str

    def __post_init__(self) -> None:
        _uri(self.uri)
        if (
            not isinstance(self.body, bytes)
            or hashlib.sha256(self.body).hexdigest() != self.sha256
        ):
            raise FilingFailure("taxonomy_hash")


@dataclass(frozen=True)
class TaxonomyPackage:
    version: str
    entrypoint: str
    entry_refs: tuple[str, ...]
    resources: tuple[TaxonomyResource, ...]
    aliases: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        _uri(self.entrypoint)
        object.__setattr__(self, "resources", tuple(self.resources))
        object.__setattr__(self, "entry_refs", tuple(self.entry_refs))
        object.__setattr__(self, "aliases", tuple(tuple(pair) for pair in self.aliases))
        if (
            not self.version
            or not self.entry_refs
            or not self.resources
            or len({r.uri for r in self.resources}) != len(self.resources)
            or len(dict(self.aliases)) != len(self.aliases)
        ):
            raise FilingFailure("invalid_taxonomy")
        for key, target in self.aliases:
            _uri(key)
            _uri(target)


@dataclass(frozen=True)
class Dimension:
    axis: str
    member: str | None
    typed_xml: str | None
    container: Literal["segment", "scenario"]


@dataclass(frozen=True)
class XmlContext:
    identifier: str
    entity: str
    entity_scheme: str
    instant: str | None
    start: str | None
    end: str | None
    dimensions: tuple[Dimension, ...]
    source_xml: str
    forever: bool = False
    other_xml: tuple[str, ...] = ()


@dataclass(frozen=True)
class XmlUnit:
    identifier: str
    numerator: tuple[str, ...]
    denominator: tuple[str, ...]


@dataclass(frozen=True)
class XmlFact:
    concept: str
    context_id: str
    unit_id: str | None
    value: str | None
    raw_value: str
    decimals: str | None
    precision: str | None
    nil: bool
    locator: str


@dataclass(frozen=True)
class XmlAssertions:
    family: Literal["older_financial_xbrl"]
    source: str
    sha256: str
    taxonomy_version: str
    taxonomy_sha256: str
    contexts: tuple[XmlContext, ...]
    units: tuple[XmlUnit, ...]
    facts: tuple[XmlFact, ...]
    complete: Literal[False] = False


class _Work:
    def __init__(
        self, limits: FilingLimits, clock: Callable[[], float], expires: float | None
    ) -> None:
        self.limits = limits
        self.clock = clock
        self.expires = clock() + limits.deadline if expires is None else expires
        self.nodes = self.text = 0
        self.output = 0

    def account(self, text: str) -> str:
        self.output += len(text)
        if len(text) > self.limits.max_text or self.output > self.limits.max_total_text:
            raise FilingFailure("output_limit")
        if self.clock() >= self.expires:
            raise FilingFailure("deadline")
        return text

    async def checkpoint(self) -> None:
        await asyncio.sleep(0)
        if self.clock() >= self.expires:
            raise FilingFailure("deadline")

    async def parse(self, body: bytes) -> etree._Element:
        from lxml import etree

        if len(body) > self.limits.max_bytes:
            raise FilingFailure("document_limit")
        try:
            body.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise FilingFailure("unsupported_encoding") from None
        lower = body.lower()
        if b"\x00" in body:
            raise FilingFailure("unsupported_encoding")
        if any(token in lower for token in (b"<!doctype", b"<!entity", b"xinclude")):
            raise FilingFailure("external_reference")

        class DenyResolver(etree.Resolver):
            def resolve(self, url: str | None, pubid: str | None, context: object) -> None:
                raise FilingFailure("external_reference")

        parser = etree.XMLPullParser(
            events=("start", "end"),
            no_network=True,
            load_dtd=False,
            resolve_entities=False,
            dtd_validation=False,
            recover=False,
            huge_tree=False,
        )
        parser.resolvers.add(DenyResolver())
        depth = 0
        try:
            for offset in range(0, len(body), 4096):
                await self.checkpoint()
                parser.feed(body[offset : offset + 4096])
                for event, element in parser.read_events():
                    if event == "start":
                        depth += 1
                        self.nodes += 1
                        namespaces = element.nsmap
                        if len(namespaces) > self.limits.max_namespaces or any(
                            len(uri) > self.limits.max_name_chars for uri in namespaces.values()
                        ):
                            raise FilingFailure("namespace_limit")
                        if (
                            len(element.attrib) > self.limits.max_attributes
                            or not isinstance(element.tag, str)
                            or len(element.tag) > self.limits.max_name_chars
                        ):
                            raise FilingFailure("attribute_limit")
                        if depth > self.limits.max_depth:
                            raise FilingFailure("depth_limit")
                        if self.nodes > self.limits.max_nodes:
                            raise FilingFailure("node_limit")
                    else:
                        depth -= 1
                        for text in (element.text, element.tail):
                            if text:
                                self.text += len(text)
                                if (
                                    len(text) > self.limits.max_text
                                    or self.text > self.limits.max_total_text
                                ):
                                    raise FilingFailure("text_limit")
            root = parser.close()
        except etree.LxmlError:
            raise FilingFailure("invalid_document") from None
        if root is None:
            raise FilingFailure("invalid_document")
        return root


async def _taxonomy(package: TaxonomyPackage, work: _Work) -> tuple[set[str], str]:
    resources = {r.uri: r for r in package.resources}
    if (
        max(len(resources), len(package.aliases), len(package.entry_refs))
        > work.limits.max_resources
        or sum(len(r.body) for r in resources.values()) > work.limits.max_taxonomy_bytes
    ):
        raise FilingFailure("taxonomy_limit")
    aliases = dict(package.aliases)
    pending = [package.entrypoint]
    visited: set[str] = set()
    concepts: set[str] = set()
    while pending:
        await work.checkpoint()
        uri = pending.pop()
        alias_seen: set[str] = set()
        while uri in aliases:
            if uri in alias_seen:
                raise FilingFailure("taxonomy_unavailable")
            alias_seen.add(uri)
            uri = aliases[uri]
        _uri(uri)
        if uri in visited:
            continue
        if uri not in resources:
            raise FilingFailure("taxonomy_unavailable")
        visited.add(uri)
        root = await work.parse(resources[uri].body)
        namespace = root.get("targetNamespace")
        if root.tag == _XSD + "schema" and namespace:
            for element in root.findall(_XSD + "element"):
                name = element.get("name")
                if name:
                    concepts.add(work.account(f"{{{namespace}}}{name}"))
        elif root.tag != _LINK + "linkbase":
            raise FilingFailure("invalid_taxonomy")
        for element in root.iter():
            if not isinstance(element.tag, str):
                continue
            href = None
            if element.tag in {_XSD + "import", _XSD + "include", _XSD + "redefine"}:
                href = element.get("schemaLocation")
            if element.tag.startswith(_LINK):
                href = element.get(_XLINK + "href") or href
            if href:
                target = urldefrag(urljoin(uri, href))[0]
                _uri(target)
                pending.append(target)
    identity = "\n".join(f"{uri} {resources[uri].sha256}" for uri in sorted(visited))
    identity += "\n" + package.version + "\n" + repr(package.entry_refs) + repr(package.aliases)
    return concepts, hashlib.sha256(identity.encode()).hexdigest()


def _qname(value: str, element: etree._Element) -> str:
    parts = value.split(":")
    if len(parts) > 2 or any(not re.fullmatch(r"[A-Za-z_][\w.-]*", p) for p in parts):
        raise FilingFailure("invalid_qname")
    prefix, local = parts if len(parts) == 2 else (None, parts[0])
    namespace = element.nsmap.get(prefix)
    if not namespace:
        raise FilingFailure("invalid_qname")
    return f"{{{namespace}}}{local}"


def _date_text(element: etree._Element, tag: str) -> str | None:
    value = element.findtext(_XBRLI + tag)
    if value is not None:
        try:
            if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
                raise ValueError
            date.fromisoformat(value)
        except ValueError:
            raise FilingFailure("invalid_period") from None
    return value


async def decode_xml_filing(
    body: bytes,
    package: TaxonomyPackage,
    *,
    source: str = "",
    limits: FilingLimits | None = None,
    clock: Callable[[], float] = time.monotonic,
    _expires: float | None = None,
) -> XmlAssertions:
    """Preserve source contexts/units/facts; reject unsupported contracts atomically.

    Closure is syntax/reference verification, not XBRL calculation, formula,
    dimensional-validity or economic-statement validation. Every required
    resource is explicitly supplied; no file/network resolver is invoked.
    """
    require_filing_processor()

    limits = limits or FilingLimits()
    if len(body) > limits.max_bytes:
        raise FilingFailure("document_limit")
    _check_quarantine(hashlib.sha256(body).hexdigest())
    work = _Work(limits, clock, _expires)
    root = await work.parse(body)
    if root.tag != _XBRLI + "xbrl":
        raise FilingFailure("unsupported_family")
    references = [e.get(_XLINK + "href") for e in root.findall(_LINK + "schemaRef")]
    if not references or any(ref not in package.entry_refs for ref in references):
        raise FilingFailure("taxonomy_unavailable")
    concepts, digest = await _taxonomy(package, work)
    if not any(c.startswith("{" + _NSE_2020 + "}") for c in concepts):
        raise FilingFailure("unsupported_taxonomy")
    contexts, units, facts = await _read_instance(root, concepts, work, _NSE_2020)
    return XmlAssertions(
        "older_financial_xbrl",
        source,
        hashlib.sha256(body).hexdigest(),
        package.version,
        digest,
        contexts,
        units,
        facts,
    )


async def _read_instance(
    root: etree._Element, concepts: set[str], work: _Work, namespace: str | None
) -> tuple[tuple[XmlContext, ...], tuple[XmlUnit, ...], tuple[XmlFact, ...]]:
    """Shared context/unit validation for XML and the bounded inline projection."""
    from lxml import etree

    limits = work.limits
    contexts: dict[str, XmlContext] = {}
    units: dict[str, XmlUnit] = {}
    for element in root:
        await work.checkpoint()
        if (
            isinstance(element.tag, str)
            and element.tag.startswith(_LINK)
            and element.tag != _LINK + "schemaRef"
        ):
            raise FilingFailure("taxonomy_unavailable")
        if element.tag == _XBRLI + "context":
            identifier = element.get("id", "")
            if not identifier or identifier in contexts:
                raise FilingFailure("duplicate_context")
            if len(contexts) >= limits.max_contexts:
                raise FilingFailure("context_limit")
            entity = element.find(_XBRLI + "entity/" + _XBRLI + "identifier")
            period = element.find(_XBRLI + "period")
            if entity is None or not entity.text or not entity.get("scheme") or period is None:
                raise FilingFailure("invalid_context")
            if (
                len(element.findall(_XBRLI + "period")) != 1
                or len(element.findall(_XBRLI + "entity/" + _XBRLI + "identifier")) != 1
            ):
                raise FilingFailure("invalid_context")
            period_tags = [child.tag for child in period if isinstance(child.tag, str)]
            if sorted(period_tags) not in [
                sorted([_XBRLI + "startDate", _XBRLI + "endDate"]),
                [_XBRLI + "instant"],
                [_XBRLI + "forever"],
            ]:
                raise FilingFailure("invalid_period")
            instant, start, end = (
                _date_text(period, t) for t in ("instant", "startDate", "endDate")
            )
            forever = period_tags == [_XBRLI + "forever"]
            if (not forever and instant is None and (start is None or end is None)) or (
                instant is not None and (start is not None or end is not None)
            ):
                raise FilingFailure("invalid_period")
            if start is not None and end is not None and start > end:
                raise FilingFailure("invalid_period")
            context_xml = work.account(etree.tostring(element, encoding="unicode"))
            dimensions: list[Dimension] = []
            other_xml: list[str] = []
            names: tuple[Literal["segment", "scenario"], ...] = ("segment", "scenario")
            for container_name in names:
                for container in element.findall(".//" + _XBRLI + container_name):
                    for member in container:
                        if not isinstance(member.tag, str):
                            continue
                        if member.tag == _XBRLDI + "explicitMember":
                            dimensions.append(
                                Dimension(
                                    _qname(member.get("dimension", ""), member),
                                    _qname(member.text or "", member),
                                    None,
                                    container_name,
                                )
                            )
                        elif member.tag == _XBRLDI + "typedMember":
                            if len(member) != 1:
                                raise FilingFailure("invalid_dimension")
                            dimensions.append(
                                Dimension(
                                    _qname(member.get("dimension", ""), member),
                                    None,
                                    etree.tostring(member[0], encoding="unicode"),
                                    container_name,
                                )
                            )
                        elif not member.tag.startswith((_XBRLI, _XBRLDI)):
                            other_xml.append(
                                work.account(etree.tostring(member, encoding="unicode"))
                            )
                            continue
                        else:
                            raise FilingFailure("unsupported_context")
                        dimension = dimensions[-1]
                        work.account(dimension.axis)
                        work.account(dimension.member or dimension.typed_xml or "")
            contexts[identifier] = XmlContext(
                identifier,
                entity.text,
                entity.get("scheme", ""),
                instant,
                start,
                end,
                tuple(dimensions),
                context_xml,
                forever,
                tuple(other_xml),
            )
        elif element.tag == _XBRLI + "unit":
            identifier = element.get("id", "")
            if not identifier or identifier in units:
                raise FilingFailure("duplicate_unit")
            if len(units) >= limits.max_contexts:
                raise FilingFailure("unit_limit")
            simple = element.findall(_XBRLI + "measure")
            divided = element.find(_XBRLI + "divide")
            if simple and divided is None:
                numerator = tuple(_qname(m.text or "", m) for m in simple)
                denominator: tuple[str, ...] = ()
            elif not simple and divided is not None:
                numerator = tuple(
                    _qname(m.text or "", m)
                    for m in divided.findall(_XBRLI + "unitNumerator/" + _XBRLI + "measure")
                )
                denominator = tuple(
                    _qname(m.text or "", m)
                    for m in divided.findall(_XBRLI + "unitDenominator/" + _XBRLI + "measure")
                )
                if not denominator:
                    raise FilingFailure("invalid_unit")
            else:
                raise FilingFailure("invalid_unit")
            if not numerator:
                raise FilingFailure("invalid_unit")
            for measure in numerator + denominator:
                work.account(measure)
            units[identifier] = XmlUnit(identifier, numerator, denominator)
    facts: list[XmlFact] = []
    for index, element in enumerate(root):
        await work.checkpoint()
        if (
            not isinstance(element.tag, str)
            or element.tag in {_XBRLI + "context", _XBRLI + "unit"}
            or element.tag.startswith(_LINK)
        ):
            continue
        if len(facts) >= limits.max_facts:
            raise FilingFailure("fact_limit")
        if element.tag not in concepts or (
            namespace is not None and not element.tag.startswith("{" + namespace + "}")
        ):
            raise FilingFailure("unknown_concept")
        if len(element):
            raise FilingFailure("unsupported_fact")
        context_id = element.get("contextRef", "")
        unit_id = element.get("unitRef")
        if context_id not in contexts or (unit_id is not None and unit_id not in units):
            raise FilingFailure("unresolved_context_unit")
        nil_value = element.get("{http://www.w3.org/2001/XMLSchema-instance}nil", "false")
        if nil_value not in {"true", "false", "0", "1"}:
            raise FilingFailure("invalid_nil")
        nil = nil_value in {"true", "1"}
        raw = element.text or ""
        if nil and raw.strip():
            raise FilingFailure("nil_conflict")
        decimals, precision = element.get("decimals"), element.get("precision")
        if decimals is not None and precision is not None:
            raise FilingFailure("precision_conflict")
        for value in (decimals, precision):
            if value is not None and value != "INF" and not re.fullmatch(r"-?[0-9]+", value):
                raise FilingFailure("invalid_precision")
        work.account(element.tag)
        work.account(raw)
        facts.append(
            XmlFact(
                element.tag,
                context_id,
                unit_id,
                None if nil else raw,
                raw,
                decimals,
                precision,
                nil,
                f"/xbrl/child[{index}]",
            )
        )
    if not facts:
        raise FilingFailure("empty_filing")
    return tuple(contexts.values()), tuple(units.values()), tuple(facts)
