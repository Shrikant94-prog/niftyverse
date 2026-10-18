"""Static public-name and result-type examples; also imports without extras."""

from pathlib import Path
from typing import assert_type

import polars as pl

from niftyverse import SliceResult, build_fixture, extract_fixture
from niftyverse.display import PreviewConfig, render_html


def public_types(payload: bytes, database: Path, csv_bundle: Path) -> None:
    stored = build_fixture(payload, database)
    direct = extract_fixture(payload, csv_bundle)
    assert_type(stored, SliceResult)
    assert_type(direct.to_polars(max_rows=10), pl.DataFrame)
    assert_type(render_html(direct, PreviewConfig(max_rows=5)), str)
