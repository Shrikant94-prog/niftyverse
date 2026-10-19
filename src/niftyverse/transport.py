"""Explicit, process-owned direct HTTP sessions; no acquisition at import time.

Use one active acquisition owner per provider/account/IP context. Limits are
process-local; launching more processes is not a supported way to multiply them.
Only read-only GET is exposed. Redirects are deliberately rejected: callers must
submit an independently approved target through the same budgets.
"""

import asyncio
import math
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import ClassVar, Self
from urllib.parse import urlsplit

import httpx

from niftyverse.recon import HOSTS


class TransportFailure(RuntimeError):
    """Safe diagnostic: never contains request/response text or credentials."""

    def __init__(self, code: str, *, deferred_until: float | None = None) -> None:
        self.code = code
        self.deferred_until = deferred_until
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
    attempts: int = 3
    refresh_url: str | None = None

    def __post_init__(self) -> None:
        if (
            not self.name
            or not self.hosts
            or not self.hosts <= HOSTS
            or min(self.concurrency, self.max_requests, self.max_body_bytes, self.max_total_bytes)
            <= 0
            or self.pending < 0
            or not 1 <= self.attempts <= 3
            or not math.isfinite(self.deadline)
            or self.deadline <= 0
            or not math.isfinite(self.spacing)
            or self.spacing < 0
        ):
            raise ValueError("invalid family policy")
        if self.refresh_url is not None:
            try:
                parts = urlsplit(self.refresh_url)
                valid = (
                    parts.scheme == "https"
                    and parts.hostname in self.hosts
                    and parts.port in {None, 443}
                    and not parts.username
                    and not parts.password
                    and not parts.fragment
                )
            except ValueError:
                valid = False
            if not valid:
                raise ValueError("invalid refresh URL")


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
        self.blocked = False
        self.deferred_until = 0.0
        self.spacing = policy.spacing
        self.refresh_lock = asyncio.Lock()
        self.generation = 0
        self.refresh_failed = False
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
        wall_clock: Callable[[], float] = time.time,
        jitter: Callable[[], float] = random.random,
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
        for related in (
            HOSTS - {"www.niftyindices.com", "niftyindices.com"},
            frozenset({"www.niftyindices.com", "niftyindices.com"}),
        ):
            if sum(bool(p.hosts & related) for p in self.policies) > 1:
                raise ValueError("related source hosts must share one family budget")
        if len({p.name for p in self.policies}) != len(self.policies):
            raise ValueError("duplicate family name")
        self._transport = transport
        self._clock = clock
        self._wall_clock = wall_clock
        self._jitter = jitter
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
                return await self._retry(family, url, self._clock() + policy.deadline)
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

    def _check_source(self, family: _Family) -> None:
        if family.blocked:
            raise TransportFailure("source_blocked")
        if family.deferred_until > self._wall_clock():
            raise TransportFailure("deferred", deferred_until=family.deferred_until)

    async def _wait(self, delay: float, expires: float) -> None:
        remaining = expires - self._clock()
        if remaining <= 0 or delay >= remaining:
            raise TransportFailure("deadline")
        if delay > 0:
            await self._sleep(delay)
        if self._clock() >= expires:
            raise TransportFailure("deadline")

    async def _retry(self, family: _Family, url: str, expires: float) -> Download:
        refreshed = False
        for attempt in range(family.policy.attempts):
            self._check_source(family)
            await self._wait(0, expires)
            generation = family.generation
            delay = min(8.0, 2.0**attempt) * min(1.0, max(0.0, self._jitter()))
            try:
                return await self._attempt(family, url, expires)
            except httpx.RemoteProtocolError:
                if family.http1:
                    raise TransportFailure("protocol_error") from None
                family.http1 = True
                family.stats.http1_fallbacks += 1
                delay = 0
            except httpx.TimeoutException, httpx.NetworkError:
                pass
            except _RetryResponse as failure:
                if failure.status == 401:
                    if refreshed or family.policy.refresh_url is None or family.refresh_failed:
                        raise TransportFailure("session_invalid") from None
                    async with family.refresh_lock:
                        if family.refresh_failed:
                            raise TransportFailure("session_invalid") from None
                        if generation == family.generation:
                            # The caller's explicitly configured, verified bootstrap
                            # goes through the same request/byte/time/rate budget.
                            try:
                                await self._attempt(family, family.policy.refresh_url, expires)
                            except TransportFailure, _RetryResponse, httpx.HTTPError:
                                family.refresh_failed = True
                                raise TransportFailure("session_refresh_failed") from None
                            family.generation += 1
                    refreshed = True
                    delay = 0
                elif failure.status == 429:
                    family.spacing = max(2.0, family.spacing * 2)
                    delay = max(delay, failure.retry_after)
                    if delay >= expires - self._clock():
                        family.deferred_until = self._wall_clock() + delay
                        raise TransportFailure(
                            "deferred", deferred_until=family.deferred_until
                        ) from None
                    family.next_start = max(family.next_start, self._clock() + delay)
            if attempt + 1 == family.policy.attempts:
                raise TransportFailure("retry_exhausted") from None
            await self._wait(delay, expires)
        raise AssertionError("finite retry loop")

    async def _attempt(self, family: _Family, url: str, expires: float) -> Download:
        stats, policy = family.stats, family.policy
        async with family.slots, self._global:
            async with family.rate_lock:
                self._check_source(family)
                await self._wait(0, expires)
                while family.next_start > self._clock():
                    await self._wait(family.next_start - self._clock(), expires)
                    self._check_source(family)
                if stats.requests >= policy.max_requests:
                    raise TransportFailure("request_budget")
                if stats.bytes_read >= policy.max_total_bytes:
                    raise TransportFailure("byte_budget")
                stats.requests += 1
                family.next_start = self._clock() + family.spacing
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
                if response.status_code == 403:
                    family.blocked = True
                    raise TransportFailure("source_blocked")
                if response.status_code in {401, 429, 500, 502, 503, 504}:
                    raise _RetryResponse(
                        response.status_code,
                        self._retry_after(response.headers.get("retry-after")),
                    )
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
                head = bytes(body[:8192]).lstrip().lower()
                if head.startswith(b"<") and any(
                    marker in head
                    for marker in (
                        b"access denied",
                        b"captcha",
                        b"verify you are human",
                        b"request rejected",
                    )
                ):
                    family.blocked = True
                    raise TransportFailure("source_blocked")
                return Download(
                    bytes(body), response.headers.get("content-type", ""), response.http_version
                )
        finally:
            stats.active -= 1

    def _retry_after(self, value: str | None) -> float:
        if not value:
            return 0
        try:
            seconds = float(value)
            if math.isfinite(seconds):
                return max(0, seconds)
            return 0
        except ValueError:
            try:
                return max(0, parsedate_to_datetime(value).timestamp() - self._wall_clock())
            except ValueError, TypeError, OverflowError:
                return 0


class _RetryResponse(Exception):
    def __init__(self, status: int, retry_after: float) -> None:
        self.status = status
        self.retry_after = retry_after
