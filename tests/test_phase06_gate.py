"""Integrated owned negative input -> reviewed correction -> immutable outputs."""

import socket
from dataclasses import replace
from pathlib import Path

import pytest
from test_membership import CHECKS, COVERAGE, D1, D2, D3, D4, EARLY, LATE, REF, A, B
from test_membership_audit import IMPORTED, write_input

from niftyverse.calendars import SourceTime
from niftyverse.core import ValidationError
from niftyverse.membership import Correction, Coverage, Event, Member, Replay, Snapshot, replay
from niftyverse.membership_audit import audit_membership
from niftyverse.storage.membership import load_membership, publish_membership, replay_recipe


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


def test_full_index_path_keeps_temporary_501st_component(tmp_path: Path) -> None:
    # Independently authored full-cardinality software case, not provider evidence.
    securities = tuple(
        Member(f"security-{i:03}", "security", f"instrument-{i:03}") for i in range(500)
    )
    temporary = Member("temporary-demerger", "temporary", None)
    replacement = Member("security-500", "security", "instrument-500")
    after = securities[1:] + (replacement,)
    announced = SourceTime(None, "Asia/Kolkata", "unknown")
    result = replay(
        original_sha256="a" * 64,
        scope="Nifty500/owned-full-index-case",
        start=D1,
        end=D4,
        baseline=Snapshot("full-start", D1, securities, REF),
        events=(
            Event("ad-hoc-addition", D2, (temporary,), (), announced, REF),
            Event(
                "ad-hoc-removal-and-rebalance",
                D3,
                (replacement,),
                (temporary, securities[0]),
                announced,
                REF,
            ),
        ),
        corrections=(),
        checks=(
            Snapshot("independent-start", D1, securities, REF),
            Snapshot("independent-end", D4, after, REF),
        ),
        coverage=(Coverage(D1, D4, REF),),
        known_at=LATE,
    )
    assert [len(result.strict_members(d)) for d in (D1, D2, D3)] == [500, 501, 500]
    assert len(result.security_instrument_ids(D2)) == 500
    bundle = publish_membership(result, tmp_path / "full-index")
    assert load_membership(bundle.path) == result
    assert bundle.manifest["scope"] == "Nifty500/owned-full-index-case"


def test_retained_real_notice_example_preserves_component_scope(tmp_path: Path) -> None:
    import hashlib
    from datetime import date

    fixtures = Path(__file__).parent / "fixtures" / "membership"
    before = replay_recipe((fixtures / "kwil-before.json").read_text())
    after = replay_recipe((fixtures / "kwil-after.json").read_text())
    note = Path(__file__).parents[1] / "docs/evidence/06-kwil-reviewed-note.json"
    note_hash = hashlib.sha256(note.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    assert note_hash in after.recipe_json
    assert before.scope == after.scope == "Nifty500/component:kwality-walls-demerger"
    assert after.start == date(2026, 2, 23) and after.end == date(2026, 2, 24)
    assert after.security_instrument_ids(after.start) == ()
    assert after.strict_members(after.start) == (
        Member("component:kwality-walls-demerger", "temporary", None),
    )
    first = publish_membership(before, tmp_path / "before")
    second = publish_membership(after, tmp_path / "after", previous=first)
    assert first.manifest["status"] == "partial" and second.manifest["status"] == "complete"
    assert second.manifest["invalidation"][0]["reasons"] == [
        "membership_changed",
        "verification_changed",
    ]
    assert load_membership(first.path) == before
    assert load_membership(second.path) == after
