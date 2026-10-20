"""Dated listing and independent session-grid expectations for equity output."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from test_equity_json import D1, D2, D3, wire

from niftyverse.adapters.equity_json import decode_equity_json
from niftyverse.calendars import Calendar, Session
from niftyverse.identity import Alias, Catalogue, Instrument, Listing, ListingSelectionPolicy
from niftyverse.market_prices import normalize_equities
from niftyverse.temporal import Evidence

KNOWN = datetime(2026, 10, 20, tzinfo=UTC)
END = D3 + timedelta(days=1)


def catalogue() -> Catalogue:
    def evidence(start: date, end: date | None = None) -> Evidence:
        return Evidence(start, end, KNOWN, "owned", "dated-master:1")

    listings = (
        Listing("a-eq", "a", "NSE", "EQ", "ordinary", "listed", evidence(D1, D2)),
        Listing("a-be", "a", "NSE", "BE", "ordinary", "listed", evidence(D2, D3)),
        Listing("a-eq", "a", "NSE", "EQ", "ordinary", "listed", evidence(D3)),
        Listing("a-bl", "a", "NSE", "BL", "block", "listed", evidence(D1)),
    )
    aliases = tuple(Alias("ALPHA", "symbol", r.listing_id, r.evidence) for r in listings)
    return Catalogue(
        "dated",
        KNOWN,
        D3,
        "historical",
        (),
        (Instrument("a", None, "equity", "Alpha"),),
        listings,
        aliases,
    )


def calendar() -> Calendar:
    return Calendar(
        "calendar",
        "NSE",
        "CM",
        KNOWN,
        tuple(
            Session(
                d,
                "trading",
                datetime(d.year, d.month, d.day, 3, 45, tzinfo=UTC),
                datetime(d.year, d.month, d.day, 10, tzinfo=UTC),
                "Asia/Kolkata",
                "owned",
                "calendar:1",
            )
            for d in (D1, D2, D3)
        ),
    )


def test_eq_be_eq_and_bl_never_duplicate_or_add_turnover() -> None:
    source = tuple(
        row
        for day, series in (
            ("14-Oct-2026", "EQ"),
            ("15-Oct-2026", "BE"),
            ("16-Oct-2026", "EQ"),
            ("15-Oct-2026", "BL"),
        )
        for row in decode_equity_json(wire(day, series), source_id="owned", locator=day + series)
    )
    result = normalize_equities(
        source,
        catalogue=catalogue(),
        calendar=calendar(),
        instrument_ids=("a",),
        start=D1,
        end=END,
        known_at=KNOWN,
        policy=ListingSelectionPolicy("ordinary"),
        source_complete=True,
    )
    assert [(r.listing_id, r.source.session_date) for r in result.rows] == [
        ("a-eq", D1),
        ("a-be", D2),
        ("a-eq", D3),
    ]
    assert sum(r.source.quantity or 0 for r in result.rows) == 30
    assert sum((r.source.turnover or Decimal(0) for r in result.rows), Decimal(0)) == Decimal(
        "3037.5000"
    )
    assert result.coverage == "complete" and not result.gaps
    eq_only = normalize_equities(
        source,
        catalogue=catalogue(),
        calendar=calendar(),
        instrument_ids=("a",),
        start=D1,
        end=END,
        known_at=KNOWN,
        policy=ListingSelectionPolicy("eq-only", ("EQ",)),
        source_complete=True,
    )
    assert len(eq_only.rows) == 2
    assert [(g.on, g.reason) for g in eq_only.gaps] == [(D2, "policy_exclusion")]
    assert all(r.quantity_unit == "shares" for r in eq_only.rows)


def test_missing_closed_unknown_and_source_failure_are_distinct() -> None:
    cal = calendar()
    sessions = (
        replace(cal.sessions[0], state="closed", opens_at=None, closes_at=None),
        cal.sessions[1],
    )
    result = normalize_equities(
        (),
        catalogue=catalogue(),
        calendar=replace(cal, sessions=sessions),
        instrument_ids=("a",),
        start=D1,
        end=END,
        known_at=KNOWN,
        policy=ListingSelectionPolicy("ordinary"),
        source_complete=True,
    )
    assert [(g.on, g.reason) for g in result.gaps] == [
        (D1, "closed_session"),
        (D2, "missing_observation"),
        (D3, "calendar_unknown"),
    ]
    assert result.coverage == "partial"
    failed = normalize_equities(
        (),
        catalogue=catalogue(),
        calendar=cal,
        instrument_ids=("a",),
        start=D1,
        end=END,
        known_at=KNOWN,
        policy=ListingSelectionPolicy("ordinary"),
        source_complete=False,
        source_failed=True,
    )
    assert all(g.reason == "source_unavailable" for g in failed.gaps)


def test_changed_or_ambiguous_identity_does_not_choose_a_row() -> None:
    cat = catalogue()
    source = decode_equity_json(wire(), source_id="owned", locator="p")
    other = replace(cat.listings[0], listing_id="other-eq")
    ambiguous = replace(
        cat,
        listings=cat.listings + (other,),
        aliases=cat.aliases + (Alias("ALPHA", "symbol", "other-eq", other.evidence),),
    )
    result = normalize_equities(
        source,
        catalogue=ambiguous,
        calendar=calendar(),
        instrument_ids=("a",),
        start=D1,
        end=D2,
        known_at=KNOWN,
        policy=ListingSelectionPolicy("ordinary"),
        source_complete=True,
    )
    assert not result.rows and result.gaps[0].reason == "identity_unresolved"


def test_delisted_missing_and_material_conflict_keep_scope_and_evidence() -> None:
    cat = catalogue()
    dead = replace(cat, listings=tuple(replace(r, status="delisted") for r in cat.listings))
    result = normalize_equities(
        (),
        catalogue=dead,
        calendar=calendar(),
        instrument_ids=("a",),
        start=D1,
        end=D2,
        known_at=KNOWN,
        policy=ListingSelectionPolicy("ordinary"),
        source_complete=True,
    )
    assert (
        len(result.gaps) == 1
        and result.gaps[0].instrument_id == "a"
        and result.gaps[0].reason == "not_listed"
    )
    source = decode_equity_json(wire(), source_id="owned", locator="p")[0]
    competitor = replace(source, representation="cm_udiff", raw_sha256="b" * 64, quantity=11)
    conflict = normalize_equities(
        (source, competitor),
        catalogue=cat,
        calendar=calendar(),
        instrument_ids=("a",),
        start=D1,
        end=D2,
        known_at=KNOWN,
        policy=ListingSelectionPolicy("ordinary"),
        source_complete=True,
        preferred_representations=("cm_udiff",),
    )
    assert conflict.coverage == "quarantined" and not conflict.rows
    assert conflict.gaps[0].evidence == (source, competitor) and conflict.source_evidence == (
        source,
        competitor,
    )
