"""ETF-specific source, identity, time and traded-unit expectations."""

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from test_equity_json import D1, D2, D3, wire
from test_equity_selection import KNOWN, calendar, catalogue

from niftyverse.adapters.equity_json import decode_equity_json
from niftyverse.identity import Alias, Catalogue, Instrument, ListingSelectionPolicy
from niftyverse.market_prices import MarketDataFailure, normalize_equities
from niftyverse.temporal import Evidence

HEADER = (
    "Symbol,Underlying Asset,SecurityName,DateofListing,MarketLot,ISINNumber,FaceValue,"
    "ETF Underlying,Underlying Key\n"
)


def body(category: str = "COMMODITY") -> bytes:
    return (
        HEADER
        + f"ALPHA,Gold,Uninformative scheme name,08-Jan-02,1,INF000000001,1,{category},GOLD\n"
    ).encode()


def etf_catalogue() -> Catalogue:
    cat = catalogue()
    return replace(cat, instruments=(Instrument("a", None, "etf", "Fund"),))


def test_current_metadata_never_projects_listing_date_or_name_classification() -> None:
    from niftyverse.adapters.etf_catalogue import decode_etf_catalogue

    snapshot = decode_etf_catalogue(body(""), observed_at=KNOWN, source_id="owned")
    row = snapshot.rows[0]
    assert row.classification is None and row.listed_on.year == 2002
    assert row.market_lot == 1 and row.face_value == Decimal(1)
    assert row.value("classification", on=KNOWN.date(), known_at=KNOWN).reason == "source_null"
    assert row.value("scheme_name", on=D1, known_at=KNOWN).reason == "outside_observed_interval"
    assert row.value("nav", on=KNOWN.date(), known_at=KNOWN).reason == "unsupported_field"
    assert (
        row.value("scheme_name", on=KNOWN.date(), known_at=KNOWN - timedelta(seconds=1)).reason
        == "not_known"
    )
    assert row.evidence.valid_from == KNOWN.date()
    assert row.evidence.valid_to == KNOWN.date() + timedelta(days=1)
    assert row.raw_sha256 == snapshot.raw_sha256


@pytest.mark.parametrize(
    "bad",
    [
        b"symbol,name\nALPHA,Fund\n",
        (HEADER + "ALPHA,Gold,Fund,08-Jan-02,-1,INF000000001,1,EQUITY,Nifty\n").encode(),
        body() + body().split(b"\n", 1)[1],
        body().replace(b"INF000000001", b"bad"),
        body().replace(b"08-Jan-02", b"garbage"),
        body() + b"other,malformed\n",
    ],
)
def test_entire_catalogue_rejects_unsupported_poisoned_or_duplicate_rows(bad: bytes) -> None:
    from niftyverse.adapters.etf_catalogue import decode_etf_catalogue

    with pytest.raises(MarketDataFailure):
        decode_etf_catalogue(bad, observed_at=KNOWN, source_id="owned")


def test_current_catalogue_requires_same_day_isin_and_explicit_series_evidence() -> None:
    from niftyverse.adapters.etf_catalogue import decode_etf_catalogue
    from niftyverse.etfs import build_etf_catalogue

    snapshot = decode_etf_catalogue(body(), observed_at=KNOWN, source_id="owned")
    price = replace(
        decode_equity_json(wire(), source_id="owned", locator="p")[0],
        session_date=KNOWN.date(),
        isin="INF000000001",
        series="BE",
    )
    cat = build_etf_catalogue(snapshot, (price,), version_id="snapshot", listing_known_at=KNOWN)
    assert cat.coverage == "current_only" and cat.instruments[0].asset_type == "etf"
    assert cat.listings[0].series == "BE" and cat.listings[0].role == "ordinary"
    assert cat.resolve("ALPHA", "symbol", D1, KNOWN).status == "identity_unresolved"
    assert cat.resolve("INF000000001", "isin", KNOWN.date(), KNOWN).status == "resolved"
    with pytest.raises(MarketDataFailure, match="dated_listing"):
        build_etf_catalogue(
            snapshot, (replace(price, session_date=D1),), version_id="old", listing_known_at=KNOWN
        )
    with pytest.raises(MarketDataFailure, match="identity"):
        build_etf_catalogue(
            snapshot,
            (replace(price, isin="INF000000002"),),
            version_id="bad",
            listing_known_at=KNOWN,
        )
    late = build_etf_catalogue(
        snapshot, (price,), version_id="late", listing_known_at=KNOWN + timedelta(hours=1)
    )
    assert late.resolve("ALPHA", "symbol", KNOWN.date(), KNOWN).status == "identity_unresolved"


def test_etf_rename_be_and_block_policy_and_fund_units() -> None:
    cat = etf_catalogue()
    aliases = tuple(
        replace(a, identifier="OLD" if a.evidence.valid_from == D1 else "NEW") for a in cat.aliases
    )
    cat = replace(cat, aliases=aliases)
    rows = tuple(
        decode_equity_json(
            wire(day, series).replace(b"ALPHA", symbol), source_id="owned", locator=day
        )[0]
        for day, series, symbol in (
            ("14-Oct-2026", "EQ", b"OLD"),
            ("15-Oct-2026", "BE", b"NEW"),
            ("16-Oct-2026", "EQ", b"NEW"),
            ("15-Oct-2026", "BL", b"OLD"),
        )
    )
    result = normalize_equities(
        rows,
        catalogue=cat,
        calendar=calendar(),
        instrument_ids=("a",),
        start=D1,
        end=D3 + timedelta(days=1),
        known_at=KNOWN,
        policy=ListingSelectionPolicy("ordinary"),
        source_complete=True,
        asset_type="etf",
    )
    assert result.coverage == "complete" and len(result.rows) == 3
    assert {r.quantity_unit for r in result.rows} == {"fund_units"}
    assert sum(r.source.quantity or 0 for r in result.rows) == 30
    assert sum(r.source.turnover or Decimal(0) for r in result.rows) == Decimal("3037.5000")
    assert all(r.source.price_basis == "raw_traded" for r in result.rows)


def test_etf_reused_symbol_isin_conflict_and_missing_are_scoped() -> None:
    cat = etf_catalogue()
    isin = Alias("INF000000001", "isin", "a-eq", Evidence(D1, D2, KNOWN, "owned", "dated:isin"))
    cat = replace(cat, aliases=cat.aliases + (isin,))
    row = decode_equity_json(wire(), source_id="owned", locator="p")[0]
    result = normalize_equities(
        (replace(row, isin="INF000000002"),),
        catalogue=cat,
        calendar=calendar(),
        instrument_ids=("a",),
        start=D1,
        end=D2,
        known_at=KNOWN,
        policy=ListingSelectionPolicy("ordinary"),
        source_complete=True,
        asset_type="etf",
    )
    assert not result.rows and result.gaps[0].reason == "identity_unresolved"
    assert result.coverage == "quarantined"
    missing = normalize_equities(
        (),
        catalogue=cat,
        calendar=calendar(),
        instrument_ids=("a",),
        start=D1,
        end=D2,
        known_at=KNOWN,
        policy=ListingSelectionPolicy("ordinary"),
        source_complete=True,
        asset_type="etf",
    )
    assert not missing.rows and missing.gaps[0].reason == "missing_observation"
    conflict = replace(row, representation="cm_udiff", close=Decimal("101.5"))
    out = normalize_equities(
        (row, conflict),
        catalogue=cat,
        calendar=calendar(),
        instrument_ids=("a",),
        start=D1,
        end=D2,
        known_at=KNOWN,
        policy=ListingSelectionPolicy("ordinary"),
        source_complete=True,
        preferred_representations=("cm_udiff",),
        asset_type="etf",
    )
    assert not out.rows and out.coverage == "quarantined" and len(out.gaps[0].evidence) == 2


def test_etf_metadata_and_prices_persist_as_separate_datasets(tmp_path: Path) -> None:
    from test_equity_persistence import batch

    from niftyverse.storage.bundles import read_bundle, write_direct

    # Same shared validator/output schema, with explicit ETF dataset and unit.
    source = batch()
    import pyarrow as pa

    from niftyverse.storage.schemas import SCHEMAS

    tables = []
    for name, table in source.tables:
        name = "etf_daily" if name == "equity_daily" else name
        rows = table.to_pylist()
        for row in rows:
            row["quantity_unit"] = "fund_units"
        tables.append((name, pa.Table.from_pylist(rows, schema=SCHEMAS[name])))
    etf = replace(
        source, partition=replace(source.partition, dataset="etf_daily"), tables=tuple(tables)
    )
    write_direct(etf, tmp_path / "etf")
    bundle = read_bundle(tmp_path / "etf")
    assert bundle.table("etf_daily").to_pylist()[0]["quantity_unit"] == "fund_units"
    with pytest.raises(KeyError):
        bundle.table("index_daily")


@pytest.mark.parametrize("classification", ["", "COMMODITY"])
def test_metadata_publication_preserves_unknown_and_current_scope(
    tmp_path: Path, classification: str
) -> None:
    from niftyverse.adapters.etf_catalogue import decode_etf_catalogue
    from niftyverse.batches import Capture, Partition
    from niftyverse.core import ValidationError
    from niftyverse.etfs import build_etf_catalogue
    from niftyverse.storage.bundles import read_bundle, write_direct
    from niftyverse.storage.catalog import Store
    from niftyverse.storage.etf import make_metadata_batch
    from niftyverse.storage.publication import publish

    raw = body(classification)
    snapshot = decode_etf_catalogue(raw, observed_at=KNOWN, source_id="owned")
    row = replace(
        decode_equity_json(wire(), source_id="owned", locator="report:2")[0],
        session_date=KNOWN.date(),
        isin="INF000000001",
    )
    cat = build_etf_catalogue(snapshot, (row,), version_id="current", listing_known_at=KNOWN)
    partition = Partition(
        "etf_metadata",
        KNOWN.date(),
        KNOWN.date() + timedelta(days=1),
        (cat.listings[0].listing_id,),
        ("classification", "scheme_name"),
        "observed_metadata",
        "etf_catalogue_v1",
        "current",
        "etf-v1",
        "snapshot rows",
    )
    capture = Capture(raw, "direct_raw", "owned", "owned:metadata")
    batch = make_metadata_batch(
        snapshot,
        catalogue=cat,
        partition=partition,
        capture=capture,
        check_id="metadata",
        checked_at=KNOWN,
        known_at=KNOWN,
    )
    assert batch.coverage == ("complete" if classification else "partial")
    write_direct(batch, tmp_path / "metadata", allow_partial=True)
    actual = read_bundle(tmp_path / "metadata").table("etf_metadata")
    assert actual.to_pylist()[0]["classification"] == (classification or None)
    assert actual.to_pylist()[0]["valid_from"] == KNOWN.date()
    with Store(tmp_path / "store") as store:
        if classification:
            publish(store, batch)
            assert store.read_table("etf_metadata").drop(["occurrence_id"]).equals(actual)
        else:
            with pytest.raises(ValidationError, match="partial partition retained"):
                publish(store, batch)
            assert store.read_table("etf_metadata").num_rows == 0
    with pytest.raises(MarketDataFailure, match="scope"):
        make_metadata_batch(
            snapshot,
            catalogue=cat,
            partition=replace(partition, start=D1),
            capture=capture,
            check_id="bad",
            checked_at=KNOWN,
            known_at=KNOWN,
        )
    assert not (tmp_path / "bad").exists()


def test_etf_delisting_symbol_reuse_and_nav_do_not_create_price_history() -> None:
    cat = etf_catalogue()
    dead_listing = replace(cat.listings[0], status="delisted")
    new_listing = replace(cat.listings[0], listing_id="new", instrument_id="new")
    cat = replace(
        cat,
        instruments=cat.instruments + (Instrument("new", None, "etf", "Other fund"),),
        listings=(dead_listing, new_listing),
        aliases=(
            Alias("ALPHA", "symbol", "a-eq", dead_listing.evidence),
            Alias("ALPHA", "symbol", "new", new_listing.evidence),
        ),
    )
    source = decode_equity_json(wire(), source_id="owned", locator="p")
    kwargs = dict(
        catalogue=cat,
        calendar=calendar(),
        instrument_ids=("a", "new"),
        start=D1,
        end=D2,
        known_at=KNOWN,
        policy=ListingSelectionPolicy("ordinary"),
        source_complete=True,
        asset_type="etf",
    )
    result = normalize_equities(source, **kwargs)  # type: ignore[arg-type]
    assert not result.rows and {g.reason for g in result.gaps} == {"identity_unresolved"}
    dead = normalize_equities((), **kwargs)  # type: ignore[arg-type]
    assert [(g.instrument_id, g.reason) for g in dead.gaps] == [
        ("a", "not_listed"),
        ("new", "missing_observation"),
    ]
    with pytest.raises(MarketDataFailure, match="basis"):
        normalize_equities(
            (replace(source[0], price_basis="nav"),),
            catalogue=etf_catalogue(),
            calendar=calendar(),
            instrument_ids=("a",),
            start=D1,
            end=D2,
            known_at=KNOWN,
            policy=ListingSelectionPolicy("ordinary"),
            source_complete=True,
            asset_type="etf",
        )
