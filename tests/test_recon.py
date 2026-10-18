"""Deterministic evidence boundaries; these tests never establish source support."""

import asyncio
import json
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from niftyverse.recon import Budget, Probe, capture

_loop: asyncio.AbstractEventLoop


@pytest.fixture(scope="module", autouse=True)
def capture_loop() -> Iterator[None]:
    # Windows loop creation uses a local socketpair. Create it before the
    # function-scoped network guard; all capture execution remains guarded.
    global _loop
    _loop = asyncio.new_event_loop()
    yield
    _loop.close()


def run_capture(
    tmp_path: Path, handler: object, probes: list[Probe], **limits: int
) -> list[dict[str, object]]:
    transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
    return _loop.run_until_complete(
        capture(
            probes, tmp_path / "capture", Budget(spacing_seconds=0, **limits), transport=transport
        )
    )


def test_capture_identity_and_not_completeness(tmp_path: Path) -> None:
    def reply(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"data": [{"price": "12.3400"}]}, headers={"set-cookie": "secret"}
        )

    results = run_capture(
        tmp_path,
        reply,
        [
            Probe(
                "price",
                "https://www.nseindia.com/api/test?token=secret&symbol=ABC",
                "ABC; 2026-10-15",
                "json",
            )
        ],
    )
    record = results[0]
    assert record["outcome"] == "observed_unverified"
    assert record["complete"] is False
    assert record["schema"] == {"data": [{"price": "str"}]}
    assert record["sha256"]
    assert record["observed_at"]
    assert (tmp_path / "capture/price.body").read_bytes() == b'{"data":[{"price":"12.3400"}]}'
    assert "secret" not in (tmp_path / "capture/evidence.json").read_text()


@pytest.mark.parametrize(
    "status,outcome",
    [(403, "challenge"), (429, "throttled"), (404, "missing"), (500, "http_error")],
)
def test_failed_stays_failed(tmp_path: Path, status: int, outcome: str) -> None:
    results = run_capture(
        tmp_path,
        lambda r: httpx.Response(status, text="token=secret"),
        [Probe("bad", "https://www.nseindia.com/api/test", "negative", "json")],
    )
    assert results[0]["outcome"] == outcome
    assert results[0]["complete"] is False
    assert not list(tmp_path.rglob("*.body"))
    assert "secret" not in (tmp_path / "capture/evidence.json").read_text()


def test_timeout_is_sanitized(tmp_path: Path) -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("secret", request=request)

    result = run_capture(
        tmp_path,
        timeout,
        [Probe("timeout", "https://www.nseindia.com/api/test", "negative", "json")],
    )
    assert result[0]["outcome"] == "timeout"
    assert "secret" not in json.dumps(result)


def test_bounds_and_no_followup_on_challenge(tmp_path: Path) -> None:
    calls: list[str] = []

    def reply(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(403)

    probes = [
        Probe(str(n), "https://www.nseindia.com/api/test", "negative", "json") for n in range(3)
    ]
    result = run_capture(tmp_path, reply, probes, max_requests=2)
    assert calls == [probes[0].url]
    assert [r["outcome"] for r in result] == ["challenge", "circuit_open", "circuit_open"]


def test_byte_and_request_limits(tmp_path: Path) -> None:
    probes = [
        Probe(str(n), "https://nsearchives.nseindia.com/test.csv", "negative", "csv")
        for n in range(2)
    ]
    result = run_capture(
        tmp_path,
        lambda r: httpx.Response(200, content=b"x" * 11),
        probes,
        max_bytes=10,
        max_requests=1,
    )
    assert [r["outcome"] for r in result] == ["byte_limit", "request_limit"]
    assert not list(tmp_path.rglob("*.body"))


@pytest.mark.parametrize(
    "body,outcome",
    [
        (b"<html>challenge</html>", "format_mismatch"),
        (b"{}", "empty"),
        (b"not json", "invalid_json"),
    ],
)
def test_json_negative(tmp_path: Path, body: bytes, outcome: str) -> None:
    result = run_capture(
        tmp_path,
        lambda r: httpx.Response(200, content=body),
        [Probe("bad", "https://www.nseindia.com/api/test", "negative", "json")],
    )
    assert result[0]["outcome"] == outcome
    assert result[0]["complete"] is False


def test_unapproved_host_and_redirect_never_fetched(tmp_path: Path) -> None:
    calls: list[str] = []

    def reply(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(302, headers={"location": "https://evil.invalid/secret"})

    result = run_capture(
        tmp_path,
        reply,
        [Probe("redirect", "https://www.nseindia.com/api/test", "negative", "json")],
    )
    assert result[0]["outcome"] == "redirect"
    assert len(calls) == 1
    with pytest.raises(ValueError, match="official HTTPS"):
        run_capture(
            tmp_path / "unapproved",
            reply,
            [Probe("evil", "https://evil.invalid/", "negative", "json")],
        )
    assert not (tmp_path / "unapproved").exists()


def test_window_and_names_validated_before_io(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="window"):
        run_capture(
            tmp_path / "wide",
            lambda r: httpx.Response(200),
            [
                Probe(
                    "wide", "https://www.nseindia.com/api/test", "negative", "json", window_days=32
                )
            ],
        )
    with pytest.raises(ValueError, match="unique safe"):
        run_capture(
            tmp_path / "path",
            lambda r: httpx.Response(200),
            [Probe("../escape", "https://www.nseindia.com/api/test", "negative", "json")],
        )
    assert not (tmp_path / "wide").exists()
    assert not (tmp_path / "path").exists()


def test_job_deadline(tmp_path: Path) -> None:
    async def reply(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.1)
        return httpx.Response(200, json={"data": [1]})

    result = run_capture(
        tmp_path,
        reply,
        [Probe("slow", "https://www.nseindia.com/api/test", "negative", "json")],
        deadline_seconds=0,
    )
    assert result[0]["outcome"] == "deadline"


def test_carried_circuit_and_existing_destination(tmp_path: Path) -> None:
    def unexpected(request: httpx.Request) -> httpx.Response:
        raise AssertionError("carried circuit made a request")

    result = _loop.run_until_complete(
        capture(
            [Probe("blocked", "https://www.nseindia.com/api/test", "prior 403", "json")],
            tmp_path / "capture",
            transport=httpx.MockTransport(unexpected),
            blocked_hosts=frozenset({"www.nseindia.com"}),
        )
    )
    assert result[0]["outcome"] == "circuit_open"
    before = (tmp_path / "capture/evidence.json").read_bytes()
    with pytest.raises(FileExistsError):
        _loop.run_until_complete(capture([], tmp_path / "capture"))
    assert (tmp_path / "capture/evidence.json").read_bytes() == before


def test_total_bytes_stop_further_requests(tmp_path: Path) -> None:
    calls: list[str] = []

    def reply(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, content=b"a,b\n1,2\n")

    probes = [
        Probe(str(n), "https://nsearchives.nseindia.com/test.csv", "negative", "csv")
        for n in range(3)
    ]
    result = run_capture(tmp_path, reply, probes, max_total_bytes=8)
    assert len(calls) == 1
    assert [r["outcome"] for r in result] == [
        "observed_unverified",
        "total_byte_limit",
        "total_byte_limit",
    ]


def test_deep_json_is_failed_evidence(tmp_path: Path) -> None:
    result = run_capture(
        tmp_path,
        lambda r: httpx.Response(200, content=b"[" * 2000 + b"]" * 2000),
        [Probe("deep", "https://www.nseindia.com/api/test", "negative", "json")],
    )
    assert result[0]["outcome"] == "invalid_json"
    assert not list(tmp_path.rglob("*.body"))


def test_sensitive_json_not_retained_or_hashed(tmp_path: Path) -> None:
    result = run_capture(
        tmp_path,
        lambda r: httpx.Response(200, json={"data": [1], "access_token": "secret"}),
        [Probe("sensitive", "https://www.nseindia.com/api/test", "negative", "json")],
    )
    assert result[0]["outcome"] == "sensitive_payload"
    assert "sha256" not in result[0]
    assert not list(tmp_path.rglob("*.body"))
    assert "secret" not in (tmp_path / "capture/evidence.json").read_text()


@pytest.mark.parametrize("depth,outcome", [(64, "observed_unverified"), (65, "invalid_json")])
def test_json_depth_boundary(tmp_path: Path, depth: int, outcome: str) -> None:
    body = b"[" * depth + b"0" + b"]" * depth
    result = run_capture(
        tmp_path,
        lambda r: httpx.Response(200, content=body),
        [Probe("depth", "https://www.nseindia.com/api/test", "boundary", "json")],
    )
    assert result[0]["outcome"] == outcome


@pytest.mark.parametrize(
    "leaves,outcome", [(99999, "observed_unverified"), (100000, "invalid_json")]
)
def test_json_node_boundary(tmp_path: Path, leaves: int, outcome: str) -> None:
    body = json.dumps([0] * leaves).encode()
    result = run_capture(
        tmp_path,
        lambda r: httpx.Response(200, content=body),
        [Probe("nodes", "https://www.nseindia.com/api/test", "boundary", "json")],
    )
    assert result[0]["outcome"] == outcome
