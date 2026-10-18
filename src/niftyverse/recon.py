"""Explicit Phase 02 research capture, not a production provider or completeness claim.

No import-time I/O. One owning process/session, one attempt, no redirects or bypass.
Raw market/filing samples stay in the caller's controlled local directory.
"""

import asyncio
import hashlib
import json
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

HOSTS = frozenset(
    {
        "www.nseindia.com",
        "nsearchives.nseindia.com",
        "archives.nseindia.com",
        "www.niftyindices.com",
        "niftyindices.com",
        "charting.nseindia.com",
    }
)
PUBLIC_PARAMS = frozenset(
    {
        "symbol",
        "series",
        "from",
        "to",
        "from_date",
        "to_date",
        "index",
        "indexType",
        "instrumentType",
        "expiryDate",
        "type",
        "csv",
        "market",
        "period",
        "id",
    }
)


@dataclass(frozen=True)
class Budget:
    max_requests: int = 12
    max_bytes: int = 8 * 1024 * 1024
    max_total_bytes: int = 48 * 1024 * 1024
    deadline_seconds: float = 180
    spacing_seconds: float = 2
    max_window_days: int = 31


@dataclass(frozen=True)
class Probe:
    name: str
    url: str
    scope: str
    format: Literal["json", "csv", "zip", "xml", "html", "bootstrap"]
    window_days: int = 1
    post_json: str | None = None


def _public_url(url: str) -> str:
    parts = urlsplit(url)
    query = urlencode(
        [
            (key, value if key in PUBLIC_PARAMS else "REDACTED")
            for key, value in parse_qsl(parts.query)
        ]
    )
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))


def _schema(value: object, depth: int = 0) -> object:
    if depth >= 4:
        return type(value).__name__
    if isinstance(value, dict):
        return {str(k): _schema(v, depth + 1) for k, v in list(value.items())[:80]}
    if isinstance(value, list):
        return [_schema(value[0], depth + 1)] if value else []
    return type(value).__name__


def _inspect(body: bytes, kind: str) -> tuple[str, object]:
    head = body.lstrip()[:200].lower()
    if kind == "bootstrap":
        return "bootstrap_only", None
    if not body:
        return "empty", None
    if kind == "json":
        if head.startswith((b"<", b"<!")):
            return "format_mismatch", None
        try:
            value = json.loads(body)
        except ValueError, UnicodeDecodeError:
            return "invalid_json", None
        return ("observed_unverified" if value else "empty"), _schema(value)
    if kind == "zip" and not body.startswith(b"PK\x03\x04"):
        return "format_mismatch", None
    if kind == "csv" and (head.startswith(b"<") or b"," not in body.split(b"\n")[0]):
        return "format_mismatch", None
    if kind in {"xml", "html"} and not head.startswith(b"<"):
        return "format_mismatch", None
    return "observed_unverified", None


async def capture(
    probes: list[Probe],
    destination: Path,
    budget: Budget | None = None,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    blocked_hosts: frozenset[str] = frozenset(),
) -> list[dict[str, object]]:
    """Capture finite, named official samples; every result starts incomplete.

    A valid response is only an observation. Independent semantic inspection is
    required before recording usable facts. No retry, automatic session refresh,
    archive extraction, filing decoding, or canonical publication happens here.
    """
    budget = budget if budget is not None else Budget()
    if (
        min(budget.max_requests, budget.max_bytes, budget.max_total_bytes, budget.max_window_days)
        <= 0
        or min(budget.deadline_seconds, budget.spacing_seconds) < 0
    ):
        raise ValueError("invalid capture budget")
    names: set[str] = set()
    for probe in probes:
        parts = urlsplit(probe.url)
        if (
            parts.scheme != "https"
            or parts.hostname not in HOSTS
            or parts.username
            or parts.password
            or parts.port not in {None, 443}
        ):
            raise ValueError("probe must use an approved official HTTPS host")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", probe.name) or probe.name in names:
            raise ValueError("probe names must be unique safe identifiers")
        if not 0 < probe.window_days <= budget.max_window_days:
            raise ValueError("probe window exceeds budget")
        names.add(probe.name)
    destination.mkdir(parents=True, exist_ok=False)
    results: list[dict[str, object]] = []
    started = time.monotonic()
    previous_start: float | None = None
    requests = 0
    total_bytes = 0
    blocked = set(blocked_hosts)
    timeout = httpx.Timeout(10, read=20, write=20, pool=10)
    async with httpx.AsyncClient(
        transport=transport,
        timeout=timeout,
        follow_redirects=False,
        headers={"User-Agent": "niftyverse/0.1 source-contract-research", "Accept": "*/*"},
    ) as client:
        for probe in probes:
            host = urlsplit(probe.url).hostname or ""
            record: dict[str, object] = {
                "name": probe.name,
                "url": _public_url(probe.url),
                "scope": probe.scope,
                "format": probe.format,
                "window_days": probe.window_days,
                "method": "POST" if probe.post_json else "GET",
                "observed_at": datetime.now(UTC).isoformat(),
                "complete": False,
                "attempts": 0,
            }
            results.append(record)
            if host in blocked:
                record["outcome"] = "circuit_open"
                continue
            if requests >= budget.max_requests:
                record["outcome"] = "request_limit"
                continue
            remaining = budget.deadline_seconds - (time.monotonic() - started)
            if remaining <= 0:
                record["outcome"] = "deadline"
                continue
            try:
                async with asyncio.timeout(remaining):
                    if previous_start is not None:
                        await asyncio.sleep(
                            max(0, budget.spacing_seconds - (time.monotonic() - previous_start))
                        )
                    previous_start = time.monotonic()
                    requests += 1
                    record["attempts"] = 1
                    async with client.stream(
                        "POST" if probe.post_json else "GET",
                        probe.url,
                        content=probe.post_json,
                        headers={"Content-Type": "application/json"} if probe.post_json else None,
                    ) as response:
                        record["status"] = response.status_code
                        record["content_type"] = response.headers.get("content-type", "")
                        status = response.status_code
                        if status != 200:
                            record["outcome"] = {
                                401: "session_required",
                                403: "challenge",
                                404: "missing",
                                429: "throttled",
                            }.get(status, "redirect" if 300 <= status < 400 else "http_error")
                            if status in {401, 403, 429}:
                                blocked.add(host)
                            continue
                        body = bytearray()
                        async for chunk in response.aiter_bytes(chunk_size=64 * 1024):
                            total_bytes += len(chunk)
                            if (
                                len(body) + len(chunk) > budget.max_bytes
                                or total_bytes > budget.max_total_bytes
                            ):
                                record["outcome"] = "byte_limit"
                                break
                            body.extend(chunk)
                        else:
                            payload = bytes(body)
                            outcome, schema = _inspect(payload, probe.format)
                            record.update(outcome=outcome, schema=schema, bytes=len(payload))
                            if outcome == "observed_unverified":
                                record["sha256"] = hashlib.sha256(payload).hexdigest()
                                (destination / f"{probe.name}.body").write_bytes(payload)
            except httpx.TimeoutException, TimeoutError:
                record["outcome"] = (
                    "deadline"
                    if time.monotonic() - started >= budget.deadline_seconds
                    else "timeout"
                )
            except httpx.HTTPError:
                record["outcome"] = "transport_error"
    (destination / "evidence.json").write_text(
        json.dumps(
            {
                "budget": budget.__dict__,
                "requests": requests,
                "received_bytes": total_bytes,
                "results": results,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return results
