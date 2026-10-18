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


@pytest.mark.parametrize(
    "status,code,calls",
    [
        (403, "source_blocked", 1),
        (500, "retry_exhausted", 3),
        (502, "retry_exhausted", 3),
        (404, "http_404", 1),
        (401, "session_invalid", 1),
    ],
)
def test_retry_policy_and_circuit(status: int, code: str, calls: int) -> None:
    async def check() -> None:
        async def sleep(delay: float) -> None:
            pass

        async with DirectTransport(
            policy(),
            sleep=sleep,
            jitter=lambda: 0.5,
            transport=httpx.MockTransport(
                lambda r: httpx.Response(
                    status, headers={"set-cookie": "secret"}, content=b"password=secret"
                )
            ),
        ) as client:
            with pytest.raises(TransportFailure) as caught:
                await client.get(URL + "?token=secret")
            assert caught.value.code == code
            assert "secret" not in repr(caught.value)
            assert client.stats.requests == calls
            if status == 403:
                with pytest.raises(TransportFailure, match="source_blocked"):
                    await client.get(URL)
                assert client.stats.requests == 1

    _loop.run_until_complete(check())


def test_retry_after_deferred_and_virtual_elapsed_budget() -> None:
    async def check() -> None:
        now = 0.0
        waits: list[float] = []
        calls = 0

        async def sleep(delay: float) -> None:
            nonlocal now
            now += delay
            waits.append(delay)

        def handle(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(429, headers={"retry-after": "4" if calls == 1 else "60"})

        async with DirectTransport(
            policy(deadline=10),
            clock=lambda: now,
            wall_clock=lambda: 1000 + now,
            sleep=sleep,
            jitter=lambda: 0.5,
            transport=httpx.MockTransport(handle),
        ) as client:
            with pytest.raises(TransportFailure) as caught:
                await client.get(URL)
            assert caught.value.code == "deferred"
            assert caught.value.deferred_until == 1064
            assert waits == [4] and calls == 2
            # Source-wide deferral also stops new jobs without another call.
            with pytest.raises(TransportFailure, match="deferred"):
                await client.get(URL)
            assert calls == 2

    _loop.run_until_complete(check())


def test_timeouts_retry_and_cancel_during_backoff() -> None:
    async def check() -> None:
        waiting = asyncio.Event()
        calls = 0

        def handle(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            raise httpx.ReadTimeout("cookie=secret", request=request)

        async def sleep(delay: float) -> None:
            waiting.set()
            await asyncio.Event().wait()

        async with DirectTransport(
            policy(), sleep=sleep, jitter=lambda: 0.5, transport=httpx.MockTransport(handle)
        ) as client:
            job = asyncio.create_task(client.get(URL))
            await waiting.wait()
            job.cancel()
            with pytest.raises(asyncio.CancelledError):
                await job
            assert calls == 1 and client.stats.cancelled == 1
            assert client.stats.active == client.stats.admitted == 0

    _loop.run_until_complete(check())


def test_refresh_is_serial_and_counted() -> None:
    async def check() -> None:
        first_wave = 0
        both = asyncio.Event()
        refreshed = False
        refreshes = 0

        async def handle(request: httpx.Request) -> httpx.Response:
            nonlocal first_wave, refreshed, refreshes
            if request.url.path == "/bootstrap":
                refreshes += 1
                refreshed = True
                return httpx.Response(200, headers={"set-cookie": "session=secret"})
            if not refreshed:
                first_wave += 1
                if first_wave == 2:
                    both.set()
                await both.wait()
                return httpx.Response(401)
            return httpx.Response(200, content=b"ok")

        async with DirectTransport(
            policy(refresh_url="https://www.nseindia.com/bootstrap"),
            transport=httpx.MockTransport(handle),
        ) as client:
            results = await asyncio.gather(client.get(URL), client.get(URL))
            assert [r.body for r in results] == [b"ok", b"ok"]
            assert refreshes == 1 and client.stats.requests == 5

    _loop.run_until_complete(check())


def test_html_challenge_opens_circuit() -> None:
    async def check() -> None:
        async with DirectTransport(
            policy(),
            transport=httpx.MockTransport(
                lambda r: httpx.Response(200, text="<html>Access Denied token=secret</html>")
            ),
        ) as client:
            with pytest.raises(TransportFailure, match="source_blocked"):
                await client.get(URL)
            with pytest.raises(TransportFailure, match="source_blocked"):
                await client.get(URL)
            assert client.stats.requests == 1

    _loop.run_until_complete(check())


@pytest.mark.parametrize(
    "retry_after,expected",
    [("Thu, 01 Jan 1970 00:16:45 GMT", 5), ("invalid", 0.5), ("-1", 0.5), ("nan", 0.5)],
)
def test_retry_after_forms_and_success(retry_after: str, expected: float) -> None:
    async def check() -> None:
        now = 0.0
        calls = 0

        async def sleep(delay: float) -> None:
            nonlocal now
            now += delay

        def handle(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            if calls == 1:
                return httpx.Response(429, headers={"retry-after": retry_after})
            return httpx.Response(200, content=b"ok")

        async with DirectTransport(
            policy(),
            clock=lambda: now,
            wall_clock=lambda: 1000 + now,
            sleep=sleep,
            jitter=lambda: 0.5,
            transport=httpx.MockTransport(handle),
        ) as client:
            assert (await client.get(URL)).body == b"ok"
            assert now == expected and calls == 2

    _loop.run_until_complete(check())


def test_timeout_retry_exhaustion_virtual_time() -> None:
    async def check() -> None:
        now = 0.0

        async def sleep(delay: float) -> None:
            nonlocal now
            now += delay

        def handle(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectTimeout("secret", request=request)

        async with DirectTransport(
            policy(),
            clock=lambda: now,
            sleep=sleep,
            jitter=lambda: 0.5,
            transport=httpx.MockTransport(handle),
        ) as client:
            with pytest.raises(TransportFailure, match="retry_exhausted"):
                await client.get(URL)
            assert client.stats.requests == 3 and now == 1.5

    _loop.run_until_complete(check())


def test_cancel_stream_closes_response() -> None:
    class Stream(httpx.AsyncByteStream):
        closed = False

        async def __aiter__(self) -> AsyncIterator[bytes]:
            yield b"ok"
            started.set()
            await asyncio.Event().wait()

        async def aclose(self) -> None:
            self.closed = True

    async def check() -> None:
        stream = Stream()
        async with DirectTransport(
            policy(), transport=httpx.MockTransport(lambda r: httpx.Response(200, stream=stream))
        ) as client:
            job = asyncio.create_task(client.get(URL))
            await started.wait()
            job.cancel()
            with pytest.raises(asyncio.CancelledError):
                await job
            assert stream.closed and client.stats.active == client.stats.admitted == 0

    started = asyncio.Event()
    _loop.run_until_complete(check())
