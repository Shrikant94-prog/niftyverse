"""Explicit, process-owned direct HTTP sessions; no acquisition at import time.

Use one active acquisition owner per provider/account/IP context. Limits are
process-local; launching more processes is not a supported way to multiply them.
Only read-only GET is exposed. Redirects are deliberately rejected: callers must
submit an independently approved target through the same budgets.
"""

import asyncio
import math
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import ClassVar, Self
from urllib.parse import urlsplit

import httpx

from niftyverse.recon import HOSTS


class TransportFailure(RuntimeError):
    """Safe diagnostic: never contains request/response text or credentials."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class FamilyPolicy:
    name: str = "nse"
    hosts: frozenset[str] = HOSTS
    concurrency: int = 2
    pending: int = 8
    max_requests: int = 100
    max_body_bytes: int = 32 * 1024 * 1024
    max_total_bytes: int = 128 * 1024 * 1024
    deadline: float = 120
    spacing: float = 2

    def __post_init__(self) -> None:
        if (
            not self.name
            or not self.hosts
            or not self.hosts <= HOSTS
            or min(self.concurrency, self.max_requests, self.max_body_bytes, self.max_total_bytes)
            <= 0
            or self.pending < 0
            or not math.isfinite(self.deadline)
            or self.deadline <= 0
            or not math.isfinite(self.spacing)
            or self.spacing < 0
        ):
            raise ValueError("invalid family policy")


@dataclass
class TransportStats:
    requests: int = 0
    bytes_read: int = 0
    active: int = 0
    peak_active: int = 0
    admitted: int = 0
    peak_admitted: int = 0
    http1_fallbacks: int = 0
    cancelled: int = 0


@dataclass(frozen=True)
class Download:
    body: bytes
    content_type: str
    http_version: str


class _Family:
    def __init__(self, policy: FamilyPolicy, transport: httpx.AsyncBaseTransport | None) -> None:
        self.policy = policy
        self.stats = TransportStats()
        self.slots = asyncio.Semaphore(policy.concurrency)
        self.rate_lock = asyncio.Lock()
        self.next_start = 0.0
        self.http1 = False
        self.client = httpx.AsyncClient(
            http2=True,
            follow_redirects=False,
            trust_env=False,
            transport=transport,
            timeout=httpx.Timeout(connect=10, read=30, write=30, pool=10),
            limits=httpx.Limits(
                max_connections=policy.concurrency, max_keepalive_connections=policy.concurrency
            ),
        )
        self.fallback: httpx.AsyncClient | None = None
        self.transport = transport

    def http1_client(self) -> httpx.AsyncClient:
        if self.fallback is None:
            self.fallback = httpx.AsyncClient(
                http2=False,
                follow_redirects=False,
                trust_env=False,
                transport=self.transport,
                timeout=httpx.Timeout(connect=10, read=30, write=30, pool=10),
                limits=httpx.Limits(
                    max_connections=self.policy.concurrency,
                    max_keepalive_connections=self.policy.concurrency,
                ),
            )
        self.fallback.cookies.update(self.client.cookies)
        return self.fallback

    async def close(self) -> None:
        await self.client.aclose()
        if self.fallback is not None:
            await self.fallback.aclose()


class DirectTransport:
    """One owner shares family pools, admission and budgets across all adapters.

    Admission fails immediately at capacity rather than allocating an unbounded
    internal queue. Counters include failed attempts and consumed over-limit chunks;
    a chunk may cross a byte ceiling, but is never appended to the returned body.
    The deadline includes queue, rate waits, connection and stream time.
    """

    _owned: ClassVar[bool] = False

    def __init__(
        self,
        *policies: FamilyPolicy,
        transport: httpx.AsyncBaseTransport | None = None,
        global_concurrency: int = 4,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.policies = policies or (FamilyPolicy(),)
        if global_concurrency <= 0:
            raise ValueError("invalid global concurrency")
        seen: set[str] = set()
        for policy in self.policies:
            if seen & policy.hosts:
                raise ValueError("family hosts overlap")
            seen.update(policy.hosts)
        if len({p.name for p in self.policies}) != len(self.policies):
            raise ValueError("duplicate family name")
        self._transport = transport
        self._clock = clock
        self._sleep = sleep
        self._global_limit = global_concurrency
        self._families: list[_Family] = []
        self._tasks: set[asyncio.Task[object]] = set()
        self._open = False

    @property
    def stats(self) -> TransportStats:
        """Counters for the first family; use family_stats for multi-family owners."""
        return self._families[0].stats

    @property
    def family_stats(self) -> dict[str, TransportStats]:
        return {f.policy.name: f.stats for f in self._families}

    async def __aenter__(self) -> Self:
        if DirectTransport._owned or self._open or self._families:
            raise RuntimeError("an acquisition owner is already active")
        DirectTransport._owned = True
        try:
            self._global = asyncio.Semaphore(self._global_limit)
            for policy in self.policies:
                self._families.append(_Family(policy, self._transport))
            self._open = True
        except BaseException:
            for family in self._families:
                await family.close()
            DirectTransport._owned = False
            raise
        return self

    async def __aexit__(self, *args: object) -> None:
        self._open = False
        tasks = tuple(self._tasks)
        for task in tasks:
            task.cancel()
        try:
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            for family in self._families:
                await family.close()
        finally:
            DirectTransport._owned = False

    def _family(self, url: str) -> _Family:
        try:
            parts = urlsplit(url)
            valid = (
                parts.scheme == "https"
                and parts.port in {None, 443}
                and not parts.username
                and not parts.password
                and not parts.fragment
            )
        except ValueError:
            raise TransportFailure("unapproved_url") from None
        for family in self._families:
            if valid and parts.hostname in family.policy.hosts:
                return family
        raise TransportFailure("unapproved_url")

    async def get(self, url: str) -> Download:
        if not self._open:
            raise RuntimeError("transport owner is closed")
        family = self._family(url)
        stats, policy = family.stats, family.policy
        if stats.admitted >= policy.concurrency + policy.pending:
            raise TransportFailure("queue_full")
        stats.admitted += 1
        stats.peak_admitted = max(stats.peak_admitted, stats.admitted)
        task = asyncio.current_task()
        assert task is not None
        self._tasks.add(task)
        try:
            async with asyncio.timeout(policy.deadline):
                try:
                    return await self._attempt(family, url)
                except httpx.RemoteProtocolError:
                    # HTTPX negotiates HTTP/1 via ALPN normally. One counted
                    # read-only fallback also handles a broken HTTP/2 handshake.
                    if family.http1:
                        raise TransportFailure("protocol_error") from None
                    family.http1 = True
                    stats.http1_fallbacks += 1
                    return await self._attempt(family, url)
        except TimeoutError:
            raise TransportFailure("deadline") from None
        except httpx.TimeoutException:
            raise TransportFailure("timeout") from None
        except httpx.HTTPError:
            raise TransportFailure("network_error") from None
        except asyncio.CancelledError:
            stats.cancelled += 1
            raise
        finally:
            stats.admitted -= 1
            self._tasks.discard(task)

    async def _attempt(self, family: _Family, url: str) -> Download:
        stats, policy = family.stats, family.policy
        async with family.slots, self._global:
            async with family.rate_lock:
                delay = max(0.0, family.next_start - self._clock())
                if delay:
                    await self._sleep(delay)
                if stats.requests >= policy.max_requests:
                    raise TransportFailure("request_budget")
                if stats.bytes_read >= policy.max_total_bytes:
                    raise TransportFailure("byte_budget")
                stats.requests += 1
                family.next_start = self._clock() + policy.spacing
            return await self._send(family, url)

    async def _send(self, family: _Family, url: str) -> Download:
        stats, policy = family.stats, family.policy
        stats.active += 1
        stats.peak_active = max(stats.peak_active, stats.active)
        try:
            client = family.http1_client() if family.http1 else family.client
            async with client.stream(
                "GET", url, headers={"accept-encoding": "identity"}
            ) as response:
                if 300 <= response.status_code < 400:
                    raise TransportFailure("redirect_blocked")
                if response.status_code != 200:
                    raise TransportFailure(f"http_{response.status_code}")
                if response.headers.get("content-encoding", "identity").lower() != "identity":
                    raise TransportFailure("unsupported_content_encoding")
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    stats.bytes_read += len(chunk)
                    if stats.bytes_read > policy.max_total_bytes:
                        raise TransportFailure("byte_budget")
                    if len(body) + len(chunk) > policy.max_body_bytes:
                        raise TransportFailure("body_limit")
                    body.extend(chunk)
                return Download(
                    bytes(body), response.headers.get("content-type", ""), response.http_version
                )
        finally:
            stats.active -= 1
