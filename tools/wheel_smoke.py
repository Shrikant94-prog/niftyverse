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
from datetime import date
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
import niftyverse.filings  # noqa: E402
import niftyverse.ingestion  # noqa: E402
import niftyverse.recon  # noqa: E402
import niftyverse.transport  # noqa: E402

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
    stored = niftyverse.build_fixture(payload, Path(folder) / "slice.duckdb")
    assert stored.to_polars().to_dicts() == expected
    import duckdb

    def denied(*args, **kwargs):
        raise AssertionError("direct/render path opened a DB or materialized data")

    duckdb.connect = denied
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
