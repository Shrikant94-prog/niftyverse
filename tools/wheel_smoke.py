"""Executed inside a clean installed-wheel interpreter, never the source tree."""

import asyncio
import importlib.metadata as metadata
import importlib.util
import io
import json
import socket
import subprocess
import sys
import tempfile
import zipfile
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path


def deny_io(event: str, args: tuple[object, ...]) -> None:
    if event.startswith(("socket.", "subprocess.", "os.system", "os.posix_spawn")):
        raise PermissionError(f"Offline smoke denied {event}")


loop = asyncio.new_event_loop() if sys.argv[1] == "filings" else None
sys.addaudithook(deny_io)
try:
    socket.create_connection(("127.0.0.1", 9), timeout=0.1)
except PermissionError:
    print("Child socket negative control: denied")
else:
    raise AssertionError("network guard did not deny connection")
try:
    subprocess.run([sys.executable, "-c", "raise SystemExit(99)"], check=True)
except PermissionError:
    print("Child process-launch negative control: denied")
else:
    raise AssertionError("child process guard failed")

import niftyverse  # noqa: E402
import niftyverse.calendars  # noqa: E402
import niftyverse.adapters.equity_json  # noqa: E402
import niftyverse.adapters.equity_reports  # noqa: E402
import niftyverse.adapters.etf_catalogue  # noqa: E402
import niftyverse.delivery  # noqa: E402
import niftyverse.delisted  # noqa: E402
import niftyverse.equity_quality  # noqa: E402
import niftyverse.etfs  # noqa: E402
import niftyverse.filing_inline  # noqa: E402
import niftyverse.filing_xml  # noqa: E402
import niftyverse.filings  # noqa: E402
import niftyverse.identity  # noqa: E402
import niftyverse.indices  # noqa: E402
import niftyverse.adapters.index_history  # noqa: E402
import niftyverse.ingestion  # noqa: E402
import niftyverse.market_state  # noqa: E402
import niftyverse.market_prices  # noqa: E402
import niftyverse.membership  # noqa: E402
import niftyverse.membership_audit  # noqa: E402
import niftyverse.membership_identity  # noqa: E402
import niftyverse.recon  # noqa: E402
import niftyverse.taxonomy_zip  # noqa: E402
import niftyverse.transport  # noqa: E402

# Exercise new pure models under the same import/network/process audit guard.
from niftyverse.calendars import Calendar, CalendarSnapshot, Session, SourceTime  # noqa: E402

source_time = SourceTime(datetime(2020, 1, 2, 0, 15), "Asia/Kolkata", "instant")
assert source_time.instant == datetime(2020, 1, 1, 18, 45, tzinfo=UTC)
assert SourceTime(date(2020, 1, 2), "Asia/Kolkata", "date").instant is None
calendar = Calendar(
    "installed-calendar",
    "NSE",
    "CM",
    datetime(2020, 1, 1, tzinfo=UTC),
    (Session(date(2020, 1, 2), "closed", None, None, "Asia/Kolkata", "owned", "notice:1"),),
)
assert (
    CalendarSnapshot("installed-snapshot", calendar, datetime(2020, 1, 2, tzinfo=UTC))
    .calendar.session(date(2020, 1, 2))
    .eligible
    is False
)
assert calendar.session(date(2020, 1, 3)).eligible is None

assert "site-packages" in niftyverse.__file__, niftyverse.__file__
assert Path(niftyverse.__file__).with_name("py.typed").exists()
assert set(metadata.metadata("niftyverse")["Requires-Python"].split(",")) == {">=3.14", "<3.15"}
for name in ("pandas", "yfinance", "IPython", "ipywidgets", "plotly", "arelle", "xbrl", "lxml"):
    assert name not in sys.modules, name
lane = sys.argv[1]
if lane == "core":
    for name in (
        "pandas",
        "yfinance",
        "IPython",
        "ipywidgets",
        "plotly",
        "arelle",
        "xbrl",
        "lxml",
    ):
        assert importlib.util.find_spec(name) is None, name
elif lane.startswith("yahoo"):
    import yfinance

    print("Yahoo import:", yfinance.__version__)
elif lane == "notebook":
    import IPython
    import ipywidgets
    import plotly

    print("Notebook imports:", IPython.__version__, ipywidgets.__version__, plotly.__version__)
elif lane == "pandas":
    import pandas as pd
    import polars as pl

    assert pl.DataFrame({"id": ["001"]}).to_pandas().equals(pd.DataFrame({"id": ["001"]}))
elif lane == "filings":
    from niftyverse.filings import require_filing_processor

    require_filing_processor()
    from lxml import etree

    assert etree.LXML_VERSION[:3] == (6, 1, 3)
    print("Bounded rendered-HTML processor:", etree.LXML_VERSION, etree.LIBXML_VERSION)
    from niftyverse.filings import decode_filing

    specimen = Path(__file__).resolve().parents[1] / "tests/fixtures/filings/rendered-2026.html"
    assert loop is not None
    try:
        assertions = loop.run_until_complete(decode_filing(specimen.read_bytes()))
        assert ("Level of rounding used in financial results", "Lakhs") in assertions.metadata
        assert any(
            cell.text == "3,11,85,000.00" for table in assertions.tables for cell in table.cells
        )
        from niftyverse.filing_xml import TaxonomyPackage, TaxonomyResource

        folder = specimen.parent / "taxonomy2020"
        manifest = json.loads((folder / "manifest.json").read_text())
        resources = []
        for uri, record in manifest["resources"].items():
            with zipfile.ZipFile(folder / record["archive"]) as archive:
                resources.append(
                    TaxonomyResource(uri, archive.read(record["member"]), record["sha256"])
                )
        taxonomy = TaxonomyPackage(
            manifest["version"],
            manifest["entrypoint"],
            tuple(manifest["entry_refs"]),
            tuple(resources),
            tuple(manifest["aliases"].items()),
        )
        xml = loop.run_until_complete(
            decode_filing((specimen.parent / "older-indas.xml").read_bytes(), taxonomy=taxonomy)
        )
        assert xml.family == "older_financial_xbrl"
        assert any(fact.value == "1282600000000.00" for fact in xml.facts)
        from niftyverse.filings import FilingLimits
        from niftyverse.taxonomy_zip import TaxonomyMember, load_taxonomy_zip

        folder = specimen.parent / "taxonomy-xii"
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        limits = FilingLimits(
            max_bytes=16 * 1024 * 1024,
            max_resources=64,
            max_taxonomy_bytes=40 * 1024 * 1024,
            max_nodes=160000,
            max_total_text=64 * 1024 * 1024,
        )
        taxonomy = loop.run_until_complete(
            load_taxonomy_zip(
                (folder / "resources.zip").read_bytes(),
                version=manifest["version"],
                entrypoint=manifest["entrypoint"],
                entry_refs=tuple(manifest["entry_refs"]),
                members=tuple(
                    TaxonomyMember(uri, record["member"], record["sha256"])
                    for uri, record in manifest["resources"].items()
                ),
                limits=limits,
            )
        )
        inline = loop.run_until_complete(
            decode_filing(
                (specimen.parent / "xii-2023.html").read_bytes(), taxonomy=taxonomy, limits=limits
            )
        )
        assert inline.family == "inline_xbrl" and len(inline.facts) == 323
        assert next(f for f in inline.facts if f.locator == "#f8").value == "942024"
    finally:
        loop.close()

payload = json.dumps(
    [
        {"instrument_id": "001", "session_date": "2026-09-01", "close": "123.4500", "label": ""},
        {"instrument_id": "002", "session_date": "2026-09-02", "close": None, "label": None},
        {"instrument_id": "003", "session_date": "2026-09-03", "close": "0", "label": "__NULL__"},
    ]
).encode()
expected = [
    {
        "instrument_id": "001",
        "session_date": date(2026, 9, 1),
        "close": Decimal("123.4500"),
        "label": "",
    },
    {"instrument_id": "002", "session_date": date(2026, 9, 2), "close": None, "label": None},
    {
        "instrument_id": "003",
        "session_date": date(2026, 9, 3),
        "close": Decimal("0"),
        "label": "__NULL__",
    },
]
with tempfile.TemporaryDirectory(prefix="niftyverse-installed-slice-") as folder:
    # Fresh installed membership import, correction and retained-recipe replay.
    from dataclasses import replace

    from niftyverse.membership import Correction, Coverage, Member, Reference, Snapshot, replay
    from niftyverse.membership_audit import audit_membership
    from niftyverse.storage.membership import load_membership, publish_membership

    source = Path(folder) / "membership.csv"
    source.write_bytes(b"effective_date,index_type,inclusions,exclusions,symbols\n"
                       b"2020-01-01,Nifty500,A,,A\n")
    known = datetime(2020, 1, 5, tzinfo=UTC)
    audit = audit_membership(source, source_statement="owned installed fixture", imported_at=known)
    assert audit.row_count == 1 and not audit.original_hash_matches
    ref = Reference("owned", "fixture:1", "b" * 64, known, "reviewer")
    a, b = Member("a", "security", "a"), Member("b", "security", "b")
    left, right = date(2020, 1, 1), date(2020, 1, 2)
    initial = Snapshot("seed", left, (a,), ref)
    correction = Correction("fix", initial, replace(initial, members=(b,)), left, right, (ref,),
                            "independent check", "author", "accepted", known, "reviewer", known)

    def membership_result(corrections):
        return replay(original_sha256=audit.sha256, scope="installed owned fixture", start=left,
                      end=right, baseline=initial, events=(), corrections=corrections,
                      checks=(Snapshot("left", left, (b,), ref), Snapshot("right", right, (b,), ref)),
                      coverage=(Coverage(left, right, ref),), known_at=known)

    old = publish_membership(membership_result(()), Path(folder) / "membership-old")
    new = publish_membership(membership_result((correction,)), Path(folder) / "membership-new", previous=old)
    assert old.manifest["status"] == "partial" and new.manifest["status"] == "complete"
    assert load_membership(new.path).strict_members(left) == (b,)
    assert load_membership(old.path) == membership_result(())
    assert new.manifest["invalidation"][0]["correction_ids"] == ["fix"]

    stored = niftyverse.build_fixture(payload, Path(folder) / "slice.duckdb")
    assert stored.to_polars().to_dicts() == expected
    import duckdb

    # Exercise the installed Phase 04 boundaries, including minimal-core mode.
    import pyarrow as pa
    from datetime import UTC, datetime

    from niftyverse.batches import Capture, Partition, ValidatedBatch
    from niftyverse.storage.bundles import read_bundle, write_direct
    from niftyverse.storage.catalog import Store
    from niftyverse.storage.publication import publish
    from niftyverse.storage.schemas import SCHEMAS
    from niftyverse.storage.snapshots import backup, history_bundle, resolve_prices, restore

    row = {"listing_id": "001", "series": "EQ", "session_date": date(2026, 9, 1),
           "open": None, "high": None, "low": None, "close": Decimal("123.4500"),
           "quantity": 1, "quantity_unit": "shares", "turnover": None, "currency": "INR",
           "locator": "owned:1", "missing_reason": None}
    typed = pa.Table.from_pylist([row], schema=SCHEMAS["equity_daily"])
    now = datetime(2026, 9, 2, tzinfo=UTC)
    publication = ValidatedBatch(
        Partition("equity_daily", date(2026, 9, 1), date(2026, 9, 2), ("001",), ("close",),
                  "raw", "synthetic-v1", "identity-v1", "quality-v1", "owned row count 1"),
        Capture(b"owned", "direct_raw", "owned", "local:owned"), "installed", now, now,
        None, "active", None, (("equity_daily", typed),), "complete", "v1", "v1",
    )
    with Store(Path(folder) / "durable") as catalog:
        receipt = publish(catalog, publication)
        assert publish(catalog, publication).reused
        history = history_bundle(catalog, "pinned", recipe="installed-v1", policy="retained-at-cutoff-v1")
        resolved = resolve_prices(history, ("001", "missing"), date(2026, 9, 1), now)
        assert resolved["close"].to_pylist() == [Decimal("123.45"), None]
        assert resolved["occurrence_id"][0].as_py() == receipt.occurrence_id
        backup(catalog, Path(folder) / "backup")
    restore(Path(folder) / "backup", Path(folder) / "restored")
    with Store(Path(folder) / "restored") as catalog:
        assert catalog.read_table("equity_daily").num_rows == 1

    # Installed Phase 07 price/details and ETF contracts under the audit guard.
    from niftyverse.adapters.equity_json import decode_equity_json
    from niftyverse.adapters.etf_catalogue import decode_etf_catalogue
    from niftyverse.identity import ListingSelectionPolicy
    from niftyverse.etfs import build_etf_catalogue
    from niftyverse.market_prices import normalize_equities
    from niftyverse.storage.equity import make_price_batch
    from niftyverse.calendars import Calendar, Session

    day = date(2026, 10, 20)
    known = datetime(2026, 10, 20, 18, tzinfo=UTC)
    raw_price = json.dumps({"data":[{
        "CH_SYMBOL":"OWNED", "CH_SERIES":"BE", "mTIMESTAMP":"20-Oct-2026",
        "CH_OPENING_PRICE":"100", "CH_TRADE_HIGH_PRICE":"102", "CH_TRADE_LOW_PRICE":"99",
        "CH_CLOSING_PRICE":"101.25", "CH_TOT_TRADED_QTY":10, "CH_TOT_TRADED_VAL":"1012.50",
        "COP_DELIV_QTY":4, "COP_DELIV_PERC":"40.00",
    }]}).encode()
    parsed = decode_equity_json(raw_price,source_id="owned",locator="owned:1")
    from dataclasses import replace
    raw_metadata = (
        b"Symbol,Underlying Asset,SecurityName,DateofListing,MarketLot,ISINNumber,FaceValue,"
        b"ETF Underlying,Underlying Key\nOWNED,Gold,Fund,08-Jan-02,1,INF000000001,1,COMMODITY,GOLD\n"
    )
    metadata_snapshot = decode_etf_catalogue(raw_metadata,observed_at=known,source_id="owned")
    etf_cat = build_etf_catalogue(metadata_snapshot,(replace(parsed[0],isin="INF000000001"),),
                                  version_id="installed-etf",listing_known_at=known)
    etf_cal = Calendar("installed-eod","NSE","CM",known,(
        Session(day,"trading",datetime(2026,10,20,3,45,tzinfo=UTC),
                datetime(2026,10,20,10,tzinfo=UTC),"Asia/Kolkata","owned","session:1"),))
    result = normalize_equities(parsed,catalogue=etf_cat,calendar=etf_cal,
                                instrument_ids=(etf_cat.instruments[0].instrument_id,),
                                start=day,end=date(2026,10,21),known_at=known,
                                policy=ListingSelectionPolicy("ordinary"),source_complete=True,asset_type="etf")
    etf_batch = make_price_batch(result,
        partition=Partition("etf_daily",day,date(2026,10,21),(etf_cat.listings[0].listing_id,),
                            ("close","quantity"),"raw_traded","json-v1","installed-etf","v1","owned grid"),
        capture=Capture(raw_price,"direct_raw","owned","owned:1"),check_id="installed-etf",
        checked_at=known,known_at=known)
    assert result.coverage=="complete" and result.rows[0].quantity_unit=="fund_units"
    assert dict(etf_batch.tables)["security_daily_details"]["delivery_fraction"].to_pylist()==[Decimal("0.400000000000")]
    with Store(Path(folder)/"etf") as catalog:
        publish(catalog,etf_batch)
        expected_etf = catalog.read_table("etf_daily").drop(["occurrence_id"])
        assert expected_etf["close"].to_pylist()==[Decimal("101.25000000")]
    write_direct(etf_batch,Path(folder)/"etf-direct",encoding="csv")
    assert read_bundle(Path(folder)/"etf-direct").table("etf_daily").equals(expected_etf)

    # Installed Phase 08 price, valuation and gross/net TRI remain separate.
    from niftyverse.adapters.index_history import (
        assess_vix_capability, decode_index_prices, decode_index_tri, decode_index_valuations,
    )
    from niftyverse.indices import IndexVariant, IndexAlias, IndexCatalogue, index_history
    from niftyverse.storage.indices import make_index_batch
    from niftyverse.temporal import Evidence

    variants = tuple(IndexVariant("installed-"+kind,"installed-index",kind)
                     for kind in ("price","gross_tri","net_tri"))
    index_cat = IndexCatalogue("installed-index-v1",variants,tuple(
        IndexAlias("owned","OWNED INDEX",v.variant_id,Evidence(day,None,known,"owned","alias"))
        for v in variants))
    price_body = b'[{"INDEX_NAME":"OWNED INDEX","HistoricalDate":"20 Oct 2026","OPEN":"100","HIGH":"102","LOW":"99","CLOSE":"100.1250"}]'
    val_body = b'[{"Index Name":"OWNED INDEX","DATE":"20 Oct 2026","pe":"0","pb":"2.00","divYield":"0"}]'
    tri_body = b'[{"Index Name":"OWNED INDEX","Date":"20 Oct 2026","TotalReturnsIndex":"1200.25","NTR_Value":"1100.125"}]'
    decode_args = dict(catalogue=index_cat,source_id="owned",locator="owned:index",start=day,
                       end=date(2026,10,21),known_at=known)
    for dataset,variant,body,decoder,fields in (
        ("index_daily",variants[0],price_body,decode_index_prices,("close",)),
        ("index_valuations",variants[0],val_body,decode_index_valuations,("pe","pb","dividend_yield")),
        ("index_tri",variants[1],tri_body,decode_index_tri,("value",)),
        ("index_tri",variants[2],tri_body,decode_index_tri,("value",)),
    ):
        observations = decoder(body,variant=variant,**decode_args)
        indexed = index_history(observations,variant=variant,start=day,end=date(2026,10,21),
                                calendar=etf_cal,known_at=known,source_complete=True)
        assert indexed.coverage=="complete"
        part = Partition(dataset,day,date(2026,10,21),(variant.variant_id,),fields,
                         "valuation_ratios_percent" if dataset=="index_valuations" else variant.kind,
                         "owned-index-v1","explicit-index","no-fill","owned session grid")
        ibatch = make_index_batch(indexed,partition=part,capture=Capture(body,"direct_raw","owned","owned:index"),
                                  check_id=dataset+variant.kind,checked_at=known,known_at=known)
        label = dataset+variant.kind
        with Store(Path(folder)/(label+"-store")) as catalog:
            publish(catalog,ibatch)
            expected_index = catalog.read_table(dataset).drop(["occurrence_id"])
        write_direct(ibatch,Path(folder)/label)
        assert read_bundle(Path(folder)/label).table(dataset).equals(expected_index)
        index_row = expected_index.to_pylist()[0]
        if dataset=="index_daily": assert index_row["close"]==Decimal("100.1250")
        elif dataset=="index_valuations": assert index_row["pe"]==0 and index_row["dividend_yield"]==0
        elif variant.kind=="gross_tri": assert index_row["value"]==Decimal("1200.25")
        else: assert index_row["value"]==Decimal("1100.125")
    vix_variant = IndexVariant("installed-vix","india-vix","volatility")
    vix_capability = assess_vix_capability(b'{"data":[{"index":"INDIA VIX","last":14}]}',
        catalogue=index_cat,variant=vix_variant,source_id="owned",locator="current",
        start=day,end=date(2026,10,21),observed_at=known,calendar=etf_cal)
    assert vix_capability.status=="blocked" and vix_capability.reason=="current_only_capability"
    assert metadata_snapshot.rows[0].value("classification",on=date(2016,9,1),known_at=known).value is None

    def denied(*args, **kwargs):
        raise AssertionError("direct/render path opened a DB or materialized data")

    duckdb.connect = denied
    for encoding in ("csv", "parquet"):
        target = Path(folder) / f"durable-direct-{encoding}"
        write_direct(publication, target, encoding=encoding)
        assert read_bundle(target).table("equity_daily").equals(typed)
    direct = niftyverse.extract_fixture(payload, Path(folder) / "bundle")
    assert direct.to_polars().to_dicts() == expected
    assert direct.to_polars().schema == stored.to_polars().schema
    if lane == "pandas":
        converted = direct.to_polars().to_pandas()
        assert converted["instrument_id"].tolist() == ["001", "002", "003"]
        assert converted["close"].tolist() == [Decimal("123.4500"), None, Decimal("0.0000")]
    niftyverse.SliceResult.to_polars = denied
    assert "3 committed rows" in direct._repr_html_()
    from rich.console import Console

    stream = io.StringIO()
    Console(file=stream, width=100, height=25, color_system=None).print(direct)
    assert "Preview only: 3 of 3 rows" in stream.getvalue()
    if lane == "notebook":
        from IPython.core.formatters import DisplayFormatter

        formatted, _ = DisplayFormatter().format(direct)
        assert "text/html" in formatted and "text/plain" in formatted
    from click.testing import CliRunner

    from niftyverse.cli import main

    assert CliRunner().invoke(main, ["--help"]).exit_code == 0
    supplied = Path(folder) / "input.json"
    supplied.write_bytes(payload)
    cli_result = CliRunner().invoke(
        main,
        [
            "fixture",
            "--input",
            str(supplied),
            "--output",
            str(Path(folder) / "cli-bundle"),
            "--json",
        ],
    )
    assert cli_result.exit_code == 0, cli_result.output
    assert json.loads(cli_result.stdout)["committed_rows"] == 3
    assert cli_result.stderr == ""
    (entry,) = metadata.entry_points(group="console_scripts", name="niftyverse")
    assert entry.load() is main
print("Installed wheel: msgspec -> Arrow -> DuckDB/CSV -> Polars, MIME and CLI passed offline.")
print(sys.version)
print(
    "Installed distributions:",
    sorted((d.metadata["Name"], d.version) for d in metadata.distributions()),
)
