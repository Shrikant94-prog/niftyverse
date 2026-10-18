"""Offline acceptance for the explicitly owned direct HTTP boundary."""

import asyncio
from collections.abc import AsyncIterator, Iterator

import httpx
import pytest

from niftyverse.transport import DirectTransport, FamilyPolicy, TransportFailure

_loop: asyncio.AbstractEventLoop


@pytest.fixture(scope="module", autouse=True)
def transport_loop() -> Iterator[None]:
    global _loop
    _loop = asyncio.new_event_loop()
    yield
    _loop.close()


URL = "https://www.nseindia.com/api/test"


def policy(**changes: object) -> FamilyPolicy:
    return FamilyPolicy(spacing=0, **changes)  # type: ignore[arg-type]


def test_stream_budget_and_cleanup() -> None:
    class Stream(httpx.AsyncByteStream):
        closed = False

        async def __aiter__(self) -> AsyncIterator[bytes]:
            yield b"1234"
            yield b"5678"
            pytest.fail("read after exceeding byte limit")

        async def aclose(self) -> None:
            self.closed = True

    stream = Stream()

    async def check() -> None:
        async with DirectTransport(
            policy(max_body_bytes=5),
            transport=httpx.MockTransport(lambda r: httpx.Response(200, stream=stream)),
        ) as client:
            with pytest.raises(TransportFailure) as caught:
                await client.get(URL)
            assert caught.value.code == "body_limit"
            assert client.stats.bytes_read == 8
            assert client.stats.active == 0
        assert stream.closed

    _loop.run_until_complete(check())


def test_admission_concurrency_request_budget_and_cancel() -> None:
    async def check() -> None:
        entered = asyncio.Event()
        release = asyncio.Event()
        active = peak = 0

        async def handle(request: httpx.Request) -> httpx.Response:
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            entered.set()
            try:
                await release.wait()
                return httpx.Response(200, content=b"ok")
            finally:
                active -= 1

        async with DirectTransport(
            policy(concurrency=1, pending=1, max_requests=1), transport=httpx.MockTransport(handle)
        ) as client:
            first = asyncio.create_task(client.get(URL))
            await entered.wait()
            second = asyncio.create_task(client.get(URL))
            await asyncio.sleep(0)
            with pytest.raises(TransportFailure, match="queue_full"):
                await client.get(URL)
            second.cancel()
            with pytest.raises(asyncio.CancelledError):
                await second
            release.set()
            assert (await first).body == b"ok"
            with pytest.raises(TransportFailure, match="request_budget"):
                await client.get(URL)
            assert peak == 1 and client.stats.admitted == 0
            assert client.stats.requests == 1

    _loop.run_until_complete(check())


def test_deadline_and_owner_scope() -> None:
    async def check() -> None:
        async def handle(request: httpx.Request) -> httpx.Response:
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

        async with DirectTransport(
            policy(deadline=0.01), transport=httpx.MockTransport(handle)
        ) as client:
            with pytest.raises(RuntimeError, match="owner"):
                async with DirectTransport(policy()):
                    pass
            with pytest.raises(TransportFailure, match="deadline"):
                await client.get(URL)
            assert client.stats.active == client.stats.admitted == 0
        async with DirectTransport(policy()):
            pass

    _loop.run_until_complete(check())


def test_host_redirect_and_total_bytes() -> None:
    async def check() -> None:
        calls = 0

        def handle(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(200, content=b"1234")

        async with DirectTransport(
            policy(max_total_bytes=5), transport=httpx.MockTransport(handle)
        ) as client:
            for url in [
                "https://evil.test/",
                "http://www.nseindia.com/",
                "https://user:secret@www.nseindia.com/",
                URL + "#secret",
            ]:
                with pytest.raises(TransportFailure, match="unapproved_url"):
                    await client.get(url)
            assert calls == 0
            assert (await client.get(URL)).body == b"1234"
            with pytest.raises(TransportFailure, match="byte_budget"):
                await client.get(URL)
            assert client.stats.bytes_read == 8

        async with DirectTransport(
            policy(),
            transport=httpx.MockTransport(
                lambda r: httpx.Response(302, headers={"location": "https://evil.test/"})
            ),
        ) as client:
            with pytest.raises(TransportFailure, match="redirect_blocked"):
                await client.get(URL)
            assert client.stats.requests == 1

    _loop.run_until_complete(check())


def test_http2_protocol_failure_has_bounded_http1_fallback() -> None:
    async def check() -> None:
        calls = 0

        def handle(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise httpx.RemoteProtocolError("negotiation failed; secret")
            return httpx.Response(200, content=b"ok")

        async with DirectTransport(policy(), transport=httpx.MockTransport(handle)) as client:
            assert (await client.get(URL)).body == b"ok"
            assert client.stats.requests == 2
            assert client.stats.http1_fallbacks == 1

    _loop.run_until_complete(check())


def test_shared_global_limit_and_owner_exit_cancels_work() -> None:
    async def check() -> None:
        entered = asyncio.Event()
        active = peak = 0

        async def handle(request: httpx.Request) -> httpx.Response:
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                active -= 1
            raise AssertionError("unreachable")

        first_policy = policy(hosts=frozenset({"www.nseindia.com"}))
        second_policy = policy(name="indices", hosts=frozenset({"www.niftyindices.com"}))
        async with DirectTransport(
            first_policy,
            second_policy,
            global_concurrency=1,
            transport=httpx.MockTransport(handle),
        ) as client:
            first = asyncio.create_task(client.get(URL))
            await entered.wait()
            second = asyncio.create_task(client.get("https://www.niftyindices.com/test"))
            await asyncio.sleep(0)
        assert first.cancelled() and second.cancelled()
        assert peak == 1 and active == 0
        assert all(s.active == s.admitted == 0 for s in client.family_stats.values())
        assert client.stats.cancelled == 1

    _loop.run_until_complete(check())


def test_virtual_rate_wait_and_invalid_limits() -> None:
    async def check() -> None:
        now = 0.0
        waits: list[float] = []

        async def sleep(delay: float) -> None:
            nonlocal now
            waits.append(delay)
            now += delay

        async with DirectTransport(
            FamilyPolicy(spacing=2, max_requests=100),
            clock=lambda: now,
            sleep=sleep,
            transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b"ok")),
        ) as client:
            for _ in range(100):
                await client.get(URL)
            assert waits == [2.0] * 99
            assert now == 198 and client.stats.peak_admitted == 1
            with pytest.raises(TransportFailure, match="request_budget"):
                await client.get(URL)

    _loop.run_until_complete(check())
    invalid: list[dict[str, object]] = [
        {"deadline": float("nan")},
        {"max_body_bytes": 0},
        {"concurrency": 0},
        {"pending": -1},
    ]
    for changes in invalid:
        with pytest.raises(ValueError):
            policy(**changes)


def test_compressed_http_body_rejected_before_decode() -> None:
    async def check() -> None:
        async with DirectTransport(
            policy(),
            transport=httpx.MockTransport(
                lambda r: httpx.Response(200, headers={"content-encoding": "gzip"})
            ),
        ) as client:
            with pytest.raises(TransportFailure, match="unsupported_content_encoding"):
                await client.get(URL)
            assert client.stats.bytes_read == 0

    _loop.run_until_complete(check())
