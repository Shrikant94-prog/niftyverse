"""Executed inside a clean installed-wheel interpreter, never the source tree."""

import importlib.metadata as metadata
import importlib.util
from pathlib import Path
import socket
import sys


def deny_io(event: str, args: tuple[object, ...]) -> None:
    if event.startswith(("socket.", "subprocess.", "os.system", "os.posix_spawn")):
        raise PermissionError(f"Offline smoke denied {event}")


sys.addaudithook(deny_io)
try:
    socket.create_connection(("127.0.0.1", 9), timeout=0.1)
except PermissionError:
    print("Child socket negative control: denied")
else:
    raise AssertionError("network guard did not deny connection")

import niftyverse  # noqa: E402

assert "site-packages" in niftyverse.__file__, niftyverse.__file__
assert Path(niftyverse.__file__).with_name("py.typed").exists()
assert set(metadata.metadata("niftyverse")["Requires-Python"].split(",")) == {">=3.14", "<3.15"}
for name in ("pandas", "yfinance", "IPython", "ipywidgets", "plotly", "arelle", "xbrl"):
    assert name not in sys.modules, name
lane = sys.argv[1]
if lane == "core":
    for name in ("pandas", "yfinance", "IPython", "ipywidgets", "plotly", "arelle", "xbrl"):
        assert importlib.util.find_spec(name) is None, name
elif lane.startswith("yahoo"):
    import yfinance
    print("Yahoo import:", yfinance.__version__)
elif lane == "notebook":
    import anywidget
    import IPython
    import ipywidgets
    import plotly
    print("Notebook imports:", IPython.__version__, ipywidgets.__version__, plotly.__version__)
elif lane == "pandas":
    import pandas as pd
    import polars as pl
    assert pl.DataFrame({"id": ["001"]}).to_pandas().equals(pd.DataFrame({"id": ["001"]}))
elif lane == "filings":
    from niftyverse.filings import FilingProcessorUnavailable, require_filing_processor
    try:
        require_filing_processor()
    except FilingProcessorUnavailable:
        pass
    else:
        raise AssertionError("unselected filing processor")
print(sys.version)
print("Installed distributions:", sorted((d.metadata["Name"], d.version) for d in metadata.distributions()))
