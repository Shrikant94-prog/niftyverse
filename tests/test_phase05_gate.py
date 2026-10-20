"""PH-05-GATE: one explicit local workflow across identities, death and sessions."""

import socket
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from test_calendars import calendar
from test_delisted import records, write_manifest
from test_identity import CUTOFF, KNOWN, catalogue

from niftyverse.calendars import CalendarSnapshot
from niftyverse.delisted import import_delisted, member_request


def test_phase05_integrated_offline_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "delisted.csv"
    write_manifest(path, records())

    def deny(*args: object, **kwargs: object) -> None:
        raise AssertionError("PH-05-GATE must require no acquisition")

    monkeypatch.setattr(socket, "socket", deny)
    manifest = import_delisted(path, version_id="gate-manifest", collected_at=CUTOFF)
    assert (
        manifest.request("OLDDEAD", "symbol", date(2019, 1, 1), CUTOFF).instrument_id == "dead-a"
    )
    assert (
        manifest.request("NEWDEAD", "symbol", date(2023, 1, 1), CUTOFF).price_status
        == "source_unavailable"
    )
    assert (
        manifest.request("UNKNOWN", "symbol", date(2023, 1, 1), CUTOFF).identity_status
        == "identity_unresolved"
    )
    member = member_request(
        manifest, "dead-a", date(2025, 1, 1), CUTOFF, membership_established=True
    )
    assert member.eligible and member.listing_state == "not_listed"
    cat = catalogue()
    assert (
        cat.resolve("OLD", "symbol", date(2021, 1, 1), CUTOFF).matches[0].instrument.instrument_id
        == "a"
    )
    assert (
        cat.resolve("OLD", "symbol", date(2022, 1, 1), CUTOFF).matches[0].instrument.instrument_id
        == "b"
    )
    assert {
        m.instrument.asset_type
        for m in cat.search("Alpha", on=date(2026, 1, 1), known_at=CUTOFF).matches
    } == {"equity", "etf"}
    assert "stale" in cat.search("Alpha", on=date(2026, 1, 1), known_at=CUTOFF).limitations
    snapshot = CalendarSnapshot("gate-calendar", calendar(), KNOWN)
    session = snapshot.calendar.session(date(2020, 1, 4))
    assert session.state == "special" and session.contains(
        datetime(2020, 1, 4, 12, 30, tzinfo=UTC)
    )
    assert snapshot.calendar.session(date(2020, 1, 3)).eligible is None
    assert set(tmp_path.iterdir()) == {path}
