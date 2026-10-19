"""Offline, bounded Inline XBRL 1.1 assertions; no provider or economic mapping.

The evidenced profile uses registry 2011 numdotdecimal, zerodash and English
month/day/year. Unsupported constructs fail atomically rather than losing facts.
"""

import copy
import hashlib
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Literal

from niftyverse.filing_xml import (
    TaxonomyPackage,
    XmlContext,
    XmlFact,
    XmlUnit,
    _qname,
    _read_instance,
    _taxonomy,
    _Work,
)
from niftyverse.filings import FilingFailure, FilingLimits, require_filing_processor

if TYPE_CHECKING:
    from lxml import etree

_IX = "{http://www.xbrl.org/2013/inlineXBRL}"
_XBRLI = "{http://www.xbrl.org/2003/instance}"
_LINK = "{http://www.xbrl.org/2003/linkbase}"
_XLINK = "{http://www.w3.org/1999/xlink}"
_XSI = "{http://www.w3.org/2001/XMLSchema-instance}"
_REGISTRY = "{http://www.xbrl.org/inlineXBRL/transformation/2011-07-31}"
_MONTHS = (
    "January February March April May June July August September October November December".split()
)


@dataclass(frozen=True)
class InlineFact(XmlFact):
    format: str | None
    sign: str | None
    scale: int
    continuation_locators: tuple[str, ...]
    source_xml: str


@dataclass(frozen=True)
class InlineAssertions:
    family: Literal["inline_xbrl"]
    source: str
    sha256: str
    taxonomy_version: str
    taxonomy_sha256: str
    contexts: tuple[XmlContext, ...]
    units: tuple[XmlUnit, ...]
    facts: tuple[InlineFact, ...]
    complete: Literal[False] = False


async def _content(element: etree._Element, work: _Work, *, raw: bool) -> str:
    """Bound text before joining; exclude ix:exclude from target values only."""
    pieces: list[str] = []
    stack = [(element, False)]
    size = 0
    while stack:
        node, tail = stack.pop()
        await work.checkpoint()
        if not isinstance(node.tag, str):
            if tail and node.tail:
                size += len(node.tail)
                if size > work.limits.max_text:
                    raise FilingFailure("text_limit")
                pieces.append(node.tail)
            continue
        text = node.tail if tail else node.text
        if not tail:
            if not raw and node.tag == _IX + "exclude":
                continue
            for child in reversed(node):
                stack.append((child, True))
                stack.append((child, False))
        if text:
            size += len(text)
            if size > work.limits.max_text:
                raise FilingFailure("text_limit")
            pieces.append(text)
    return work.account("".join(pieces))


def _transform(value: str, format_name: str | None, numeric: bool) -> str:
    if format_name is None:
        return value.strip() if numeric else value
    if format_name == _REGISTRY + "numdotdecimal" and numeric:
        # Registry 2 permits comma, space and NBSP grouping. Restrict this
        # supported profile to complete groups, never silently repair numbers.
        if not re.fullmatch(
            r"[0-9]{1,3}(?:[, \u00a0]?[0-9]{3})*(?:\.[0-9]+)?", value.strip(" \t\n\r")
        ):
            raise FilingFailure("invalid_transformation")
        return re.sub(r"[, \u00a0]", "", value.strip(" \t\n\r"))
    if format_name == _REGISTRY + "zerodash" and numeric:
        if value.strip(" \t\n\r") not in {
            "-",
            "\u058a",
            "\u05be",
            "\u2010",
            "\u2011",
            "\u2012",
            "\u2013",
            "\u2014",
            "\u2015",
            "\ufe58",
            "\ufe63",
            "\uff0d",
        }:
            raise FilingFailure("invalid_transformation")
        return "0"
    if format_name == _REGISTRY + "datemonthdayyearen" and not numeric:
        match = re.fullmatch(
            r"([A-Za-z]+)[^0-9]+([0-9]{1,2})[^0-9]+([0-9]{1,2}|[0-9]{4})", value.strip()
        )
        if match:
            month_name, day, year_text = match.groups()
            for month, name in enumerate(_MONTHS, 1):
                if month_name in {name, name[:3], name.upper(), name[:3].upper()}:
                    year = int(year_text) + (2000 if len(year_text) < 3 else 0)
                    try:
                        return date(year, month, int(day)).isoformat()
                    except ValueError:
                        break
        raise FilingFailure("invalid_transformation")
    raise FilingFailure("unsupported_transformation")


def _number(value: str, sign: str | None, scale_text: str | None) -> tuple[str, int]:
    if sign not in {None, "-"}:
        raise FilingFailure("invalid_inline_number")
    if scale_text is not None and not re.fullmatch(r"-?[0-9]{1,4}", scale_text):
        raise FilingFailure("inline_scale_limit")
    scale = int(scale_text or "0")
    if abs(scale) > 1000:
        raise FilingFailure("inline_scale_limit")
    if len(value) > 4096 or not re.fullmatch(r"(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)", value):
        raise FilingFailure("invalid_inline_number")
    coefficient = Decimal(value).as_tuple()
    # Tuple construction is exact and independent of the process decimal
    # context; scaleb/multiplication could round long source coefficients.
    assert isinstance(coefficient.exponent, int)
    number = Decimal((int(sign == "-"), coefficient.digits, coefficient.exponent + scale))
    return format(number, "f"), scale


async def decode_inline_filing(
    body: bytes,
    package: TaxonomyPackage | None,
    *,
    source: str = "",
    limits: FilingLimits | None = None,
    clock: Callable[[], float] = time.monotonic,
    _expires: float | None = None,
) -> InlineAssertions:
    require_filing_processor()
    from lxml import etree

    work = _Work(limits or FilingLimits(), clock, _expires)
    root = await work.parse(body)
    if root.tag != "{http://www.w3.org/1999/xhtml}html":
        raise FilingFailure("unsupported_inline")
    headers = list(root.iter(_IX + "header"))
    resources = list(root.iter(_IX + "resources"))
    references = list(root.iter(_IX + "references"))
    if len(headers) != 1 or len(resources) != 1 or len(references) != 1:
        raise FilingFailure("unsupported_inline")
    if resources[0].getparent() is not headers[0] or references[0].getparent() is not headers[0]:
        raise FilingFailure("invalid_inline_structure")
    ids: dict[str, etree._Element] = {}
    facts: list[etree._Element] = []
    supported = {
        "header",
        "references",
        "resources",
        "hidden",
        "nonNumeric",
        "nonFraction",
        "continuation",
        "exclude",
    }
    for element in root.iter():
        await work.checkpoint()
        if not isinstance(element.tag, str):
            continue
        if element.tag.startswith("{http://www.xbrl.org/2008/inlineXBRL}"):
            raise FilingFailure("unsupported_inline")
        identifier = element.get("id")
        if identifier:
            if identifier in ids:
                raise FilingFailure("duplicate_id")
            ids[identifier] = element
        if element.tag.startswith(_IX):
            if element.tag[len(_IX) :] not in supported or element.get("target") not in {None, ""}:
                raise FilingFailure("unsupported_inline")
            if element.tag in {_IX + "nonFraction", _IX + "nonNumeric"}:
                if any(parent.tag == _IX + "nonFraction" for parent in element.iterancestors()):
                    raise FilingFailure("unsupported_inline")
                if len(facts) >= work.limits.max_facts:
                    raise FilingFailure("fact_limit")
                facts.append(element)
    if not facts:
        raise FilingFailure("empty_filing")
    if package is None:
        raise FilingFailure("taxonomy_unavailable")
    refs = list(references[0])
    if not refs or any(
        e.tag != _LINK + "schemaRef" or e.get(_XLINK + "href") not in package.entry_refs
        for e in refs
    ):
        raise FilingFailure("taxonomy_unavailable")
    concepts, digest = await _taxonomy(package, work)
    projected = etree.Element(_XBRLI + "xbrl", nsmap=root.nsmap)
    for element in resources[0]:
        if element.tag not in {_XBRLI + "context", _XBRLI + "unit"}:
            raise FilingFailure("unsupported_inline")
        projected.append(copy.deepcopy(element))
    originals: list[tuple[str, str, str | None, str | None, int, tuple[str, ...], str]] = []
    used_continuations: set[str] = set()
    for index, element in enumerate(facts):
        await work.checkpoint()
        numeric = element.tag == _IX + "nonFraction"
        if element.get("escape") not in {None, "false", "0"}:
            raise FilingFailure("unsupported_inline")
        if numeric and element.get("continuedAt"):
            raise FilingFailure("unsupported_inline")
        segments = [element]
        chain: list[str] = []
        next_id = element.get("continuedAt")
        while next_id:
            await work.checkpoint()
            if next_id in chain:
                raise FilingFailure("continuation_cycle")
            if len(chain) >= 128:
                raise FilingFailure("continuation_limit")
            node = ids.get(next_id)
            if node is None or node.tag != _IX + "continuation":
                raise FilingFailure("unresolved_continuation")
            if next_id in used_continuations:
                raise FilingFailure("shared_continuation")
            chain.append(next_id)
            segments.append(node)
            next_id = node.get("continuedAt")
        used_continuations.update(chain)
        raw_pieces, value_pieces = [], []
        for segment in segments:
            raw_pieces.append(await _content(segment, work, raw=True))
            value_pieces.append(await _content(segment, work, raw=False))
        raw = work.account("".join(raw_pieces))
        text = work.account("".join(value_pieces))
        format_name = _qname(element.get("format", ""), element) if element.get("format") else None
        nil_text = element.get(_XSI + "nil", "false")
        if nil_text not in {"true", "false", "0", "1"}:
            raise FilingFailure("invalid_nil")
        nil = nil_text in {"true", "1"}
        if nil and (text.strip() or format_name or element.get("sign") or element.get("scale")):
            raise FilingFailure("nil_conflict")
        value = "" if nil else _transform(text, format_name, numeric)
        sign, scale = element.get("sign"), 0
        if numeric and not nil:
            value, scale = _number(value, sign, element.get("scale"))
        elif not numeric and any(
            element.get(key) is not None
            for key in ("scale", "sign", "unitRef", "decimals", "precision")
        ):
            raise FilingFailure("unsupported_inline")
        concept = _qname(element.get("name", ""), element)
        fact = etree.SubElement(projected, concept, nsmap=element.nsmap)
        for key in ("contextRef", "unitRef", "decimals", "precision", _XSI + "nil"):
            if element.get(key) is not None:
                fact.set(key, element.get(key, ""))
        if numeric and not element.get("unitRef"):
            raise FilingFailure("unresolved_context_unit")
        fact.text = work.account(value)
        locator = "#" + element.get("id", "") if element.get("id") else f"/inline/fact[{index}]"
        original_xml = work.account(etree.tostring(element, encoding="unicode", with_tail=False))
        originals.append(
            (locator, raw, format_name, sign, scale, tuple("#" + c for c in chain), original_xml)
        )
    contexts, units, decoded = await _read_instance(projected, concepts, work, None)
    assertions = []
    for decoded_fact, original in zip(decoded, originals, strict=True):
        locator, raw, format_name, sign, scale, chain_locators, original_xml = original
        assertions.append(
            InlineFact(
                decoded_fact.concept,
                decoded_fact.context_id,
                decoded_fact.unit_id,
                decoded_fact.value,
                raw,
                decoded_fact.decimals,
                decoded_fact.precision,
                decoded_fact.nil,
                locator,
                format_name,
                sign,
                scale,
                chain_locators,
                original_xml,
            )
        )
    return InlineAssertions(
        "inline_xbrl",
        source,
        hashlib.sha256(body).hexdigest(),
        package.version,
        digest,
        contexts,
        units,
        tuple(assertions),
    )
