"""The direct and persistent boundary rejects the same deterministic price poison."""

from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pyarrow as pa
import pytest
from test_store_schema import example

from niftyverse.core import ValidationError
from niftyverse.storage.bundles import write_direct
from niftyverse.storage.catalog import Store
from niftyverse.storage.publication import publish


@pytest.mark.parametrize(
    "field,value", [("quantity", -1), ("turnover", Decimal("-1")), ("close", Decimal("-1"))]
)
@pytest.mark.parametrize("encoding", ["csv", "parquet"])
def test_shared_rejection_has_no_destination_or_catalog_effect(
    tmp_path: Path, field: str, value: object, encoding: str
) -> None:
    base = example()
    rows = base.tables[0][1].to_pylist()
    rows[0][field] = value
    with Store(tmp_path / "store") as store:
        publish(store, base)
        with pytest.raises(ValidationError, match="invalid_"):
            bad = replace(
                base,
                check_id="poison",
                tables=(
                    ("equity_daily", pa.Table.from_pylist(rows, schema=base.tables[0][1].schema)),
                ),
            )
        assert store.read_table("equity_daily").num_rows == 1
    with pytest.raises(ValidationError, match="invalid_"):
        bad = replace(
            base,
            check_id="poison",
            tables=(
                ("equity_daily", pa.Table.from_pylist(rows, schema=base.tables[0][1].schema)),
            ),
        )
        write_direct(bad, tmp_path / "bad", encoding=encoding)
    assert not (tmp_path / "bad").exists()
