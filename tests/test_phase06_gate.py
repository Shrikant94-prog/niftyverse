"""Integrated owned negative input -> reviewed correction -> immutable outputs."""

import socket
from dataclasses import replace
from pathlib import Path

import pytest
from test_membership import CHECKS, COVERAGE, D1, D4, EARLY, LATE, REF, A, B
from test_membership_audit import IMPORTED, write_input

from niftyverse.core import ValidationError
from niftyverse.membership import Correction, Replay, Snapshot, replay
from niftyverse.membership_audit import audit_membership
from niftyverse.storage.membership import load_membership, publish_membership


def test_phase06_integrated_offline_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def denied(*args: object, **kwargs: object) -> None:
        raise AssertionError("membership verification performed hidden acquisition")

    monkeypatch.setattr(socket, "socket", denied)
    source = tmp_path / "owned.csv"
    raw = write_input(
        source,
        [
            [str(D1), "Nifty500", "B", "A", "B"],
            [str(D4), "Nifty500", "A,A", "B", "A"],
        ],
    )
    audit = audit_membership(source, source_statement="owned negative input", imported_at=IMPORTED)
    baseline = Snapshot("baseline", D1, (B,), replace(REF, sha256=audit.sha256))
    corrected = replace(baseline, members=(A,), evidence=REF)
    ledger = Correction(
        "start-fix",
        baseline,
        corrected,
        D1,
        D4,
        (REF,),
        "independent starting snapshot contradicts raw token",
        "author",
        "accepted",
        EARLY,
        "reviewer",
        LATE,
    )

    def build(corrections: tuple[Correction, ...]) -> Replay:
        return replay(
            original_sha256=audit.sha256,
            scope="Nifty500 owned fixture",
            start=D1,
            end=D4,
            baseline=baseline,
            events=(),
            checks=(CHECKS[0], replace(CHECKS[1], members=(A,))),
            coverage=(COVERAGE,),
            known_at=LATE,
            corrections=corrections,
        )

    before = build(())
    after = build((ledger,))
    old = publish_membership(before, tmp_path / "v1")
    new = publish_membership(after, tmp_path / "v2", previous=old)
    assert old.manifest["status"] == "partial"
    assert new.manifest["status"] == "complete"
    assert new.manifest["invalidation"][0]["correction_ids"] == ["start-fix"]
    assert load_membership(new.path).strict_members(D1) == (A,)
    with pytest.raises(ValidationError, match="unverified"):
        load_membership(old.path).strict_members(D1)
    assert source.read_bytes() == raw and audit.duplicate_event_rows == 1
