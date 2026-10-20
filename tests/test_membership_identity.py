"""Membership token adapters retain dated identity and temporary boundaries."""

from datetime import date

import pytest
from test_identity import CUTOFF, catalogue, ev

from niftyverse.membership_identity import TemporaryAlias, resolve_tokens


def test_dated_literal_and_temporary_resolution_without_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import socket

    def denied(*args: object, **kwargs: object) -> None:
        raise AssertionError("membership resolved via network")

    monkeypatch.setattr(socket, "socket", denied)
    cat = catalogue()
    temporary = (TemporaryAlias("DUMMY", "component", ev("2020-01-01", "2022-01-01")),)
    before = resolve_tokens(
        ("OLD", "DUMMY", "M& M"), cat, date(2021, 12, 31), CUTOFF, temporary=temporary
    )
    assert before[0].member.instrument_id == "a"
    assert before[1].member.kind == "temporary" and before[1].member.instrument_id is None
    assert before[2].token == "M& M" and before[2].status == "identity_unresolved"
    after = resolve_tokens(
        ("OLD", "NEW", "DUMMY", "M&M"), cat, date(2022, 1, 1), CUTOFF, temporary=temporary
    )
    assert [r.member.instrument_id for r in after[:2]] == ["b", "a"]
    assert after[2].status == "identity_unresolved"
    assert before[2].member != after[3].member


def test_ambiguous_temporary_and_security_never_choose_first() -> None:
    cat = catalogue()
    temporary = (TemporaryAlias("NEW", "temp", ev("2020-01-01")),)
    result = resolve_tokens(("NEW",), cat, date(2023, 1, 1), CUTOFF, temporary=temporary)
    assert result[0].status == "ambiguous" and result[0].member.kind == "unresolved"
