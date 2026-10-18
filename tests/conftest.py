"""Offline defaults: provider probes require explicit selection."""

import socket
from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def reject_network(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> Iterator[None]:
    if request.node.get_closest_marker("live"):
        yield
        return

    def denied(*args: object, **kwargs: object) -> None:
        raise AssertionError("offline test attempted network")

    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)
    monkeypatch.setattr(socket, "getaddrinfo", denied)
    yield
