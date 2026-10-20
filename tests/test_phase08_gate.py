"""PH-08-GATE: independent source schemas through coverage, joins and publication."""

import json
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from test_index_datasets import tri_wire, valuation_wire
from test_index_price_adapter import wire as price_wire
from test_index_vix import VIX, vix_catalogue
from test_index_vix import wire as vix_wire
from test_indices import D1, D2, D3, GROSS, KNOWN, NET, PRICE, calendar, catalogue

from niftyverse.adapters.index_history import (
    assess_vix_capability,
    decode_index_prices,
    decode_index_tri,
    decode_index_valuations,
    decode_vix_history,
)
from niftyverse.batches import Capture, Partition
from niftyverse.core import ValidationError
from niftyverse.indices import index_history, join_index_datasets
from niftyverse.storage.bundles import read_bundle, write_direct
from niftyverse.storage.catalog import Store
from niftyverse.storage.indices import make_index_batch
from niftyverse.storage.publication import publish
from niftyverse.storage.snapshots import history_bundle


def test_phase08_gate_source_dates_gaps_separate_join_and_both_outputs(tmp_path: Path) -> None:
    end = D3 + timedelta(days=1)
    price_body = json.dumps(
        json.loads(price_wire())
        + json.loads(price_wire(HistoricalDate="16 Oct 2026", CLOSE="22630.00"))
    ).encode()
    val_body = valuation_wire(pe=None, pb="0", divYield="0")
    tri_body = tri_wire()
    args: dict[str, Any] = dict(
        catalogue=catalogue(), source_id="owned", locator="gate", start=D1, end=end, known_at=KNOWN
    )
    prices = decode_index_prices(price_body, variant=PRICE, **args)
    vals = decode_index_valuations(val_body, variant=PRICE, **args)
    gross = decode_index_tri(tri_body, variant=GROSS, **args)
    net = decode_index_tri(tri_body, variant=NET, **args)
    joined = join_index_datasets(variant=PRICE, prices=prices, valuations=vals, tri=gross + net)
    assert tuple(r.session_date for r in joined) == (D1, D2, D3)
    assert joined[0].price is not None and joined[0].price.close == Decimal("22622.70")
    assert joined[0].valuation is not None and joined[0].valuation.pe is None
    assert joined[0].valuation.pb == 0 and joined[0].valuation.dividend_yield == 0
    assert joined[1].price is None and joined[1].valuation is None
    assert joined[1].gross_tri is not None and joined[1].gross_tri.value == Decimal("34948.42")
    assert joined[1].net_tri is not None and joined[1].net_tri.value == Decimal("30346.43")
    assert joined[2].valuation is None and joined[2].gross_tri is None

    for dataset, variant, rows, body, fields in (
        ("index_daily", PRICE, prices, price_body, ("close",)),
        ("index_valuations", PRICE, vals, val_body, ("pe", "pb", "dividend_yield")),
        ("index_tri", GROSS, gross, tri_body, ("value",)),
        ("index_tri", NET, net, tri_body, ("value",)),
    ):
        history = index_history(
            rows,
            variant=variant,
            start=D1,
            end=end,
            calendar=calendar(),
            known_at=KNOWN,
            source_complete=True,
        )
        assert history.coverage == "partial" and history.gaps
        part = Partition(
            dataset,
            D1,
            end,
            (variant.variant_id,),
            fields,
            "valuation_ratios_percent" if dataset == "index_valuations" else variant.kind,
            "owned-v1",
            "explicit-index",
            "no-fill",
            "owned three-session grid",
        )
        batch = make_index_batch(
            history,
            partition=part,
            capture=Capture(body, "direct_raw", "owned", "owned:gate"),
            check_id=variant.variant_id + dataset,
            checked_at=KNOWN,
            known_at=KNOWN,
        )
        target = tmp_path / (variant.variant_id + dataset)
        write_direct(batch, target, allow_partial=True)
        bundle = read_bundle(target)
        assert bundle.manifest["status"] == "partial"
        assert bundle.table(dataset).equals(batch.tables[0][1])
        with Store(tmp_path / "partial-store") as store:
            with pytest.raises(ValidationError, match="partial"):
                publish(store, batch)
            assert store.read_table(dataset).num_rows == 0

    # Independently complete one-session price observation reaches persistent output.
    history = index_history(
        (prices[0],),
        variant=PRICE,
        start=D1,
        end=D2,
        calendar=calendar(),
        known_at=KNOWN,
        source_complete=True,
    )
    part = Partition(
        "index_daily",
        D1,
        D2,
        (PRICE.variant_id,),
        ("close",),
        "price",
        "owned-v1",
        "explicit-index",
        "no-fill",
        "owned one-session grid",
    )
    batch = make_index_batch(
        history,
        partition=part,
        capture=Capture(price_body, "direct_raw", "owned", "owned:gate"),
        check_id="gate-complete",
        checked_at=KNOWN,
        known_at=KNOWN,
    )
    with Store(tmp_path / "complete-store") as store:
        publish(store, batch)
        before = history_bundle(
            store, "before", recipe="index-gate", policy="retained-at-cutoff-v1"
        )
        assert before.table("index_daily")["close"].to_pylist() == [Decimal("22622.70")]
        later = replace(
            batch,
            check_id="gate-later",
            checked_at=KNOWN + timedelta(days=1),
            known_at=KNOWN + timedelta(days=1),
            source_revision="observed-again",
        )
        publish(store, later)
        assert read_bundle(before.path).table("index_daily").equals(before.table("index_daily"))
        expected = store.read_table("index_daily").drop(["occurrence_id"])
        assert expected.num_rows == 2
    write_direct(batch, tmp_path / "complete-direct")
    assert read_bundle(tmp_path / "complete-direct").table("index_daily")["close"].to_pylist() == [
        Decimal("22622.70")
    ]


def test_phase08_gate_never_uses_etf_price_or_current_vix_as_history() -> None:
    with pytest.raises(ValidationError, match="unresolved"):
        decode_index_prices(
            price_wire(INDEX_NAME="NIFTYBEES"),
            catalogue=catalogue(),
            variant=PRICE,
            source_id="owned",
            locator="p",
            start=D1,
            end=D2,
            known_at=KNOWN,
        )
    current = b'{"data":[{"index":"INDIA VIX","last":14.63}]}'
    limitation = assess_vix_capability(
        current,
        catalogue=vix_catalogue(),
        variant=VIX,
        source_id="owned",
        locator="current",
        start=D1,
        end=D2,
        observed_at=KNOWN,
        calendar=calendar(),
    )
    assert limitation.status == "blocked" and limitation.reason == "current_only_capability"
    assert limitation.verified_sessions == ()
    rows = decode_vix_history(
        vix_wire(),
        catalogue=vix_catalogue(),
        variant=VIX,
        source_id="owned",
        locator="historic",
        start=D1,
        end=D2,
        known_at=KNOWN,
    )
    with pytest.raises(ValidationError, match="index"):
        join_index_datasets(variant=PRICE, prices=rows, valuations=(), tri=())
    assert rows[0].session_date == D1 and rows[0].unit == "volatility_percent_annualised"
