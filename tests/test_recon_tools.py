"""The research supervisor self-test launches only local stdlib children."""

import subprocess
import sys
from pathlib import Path


def test_yahoo_research_supervisor() -> None:
    script = Path(__file__).resolve().parents[1] / "tools" / "probe_yahoo.py"
    result = subprocess.run(
        [sys.executable, str(script), "--self-test"],
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    )
    assert "deadline/kill/wait, error, success pass; no SDK/network" in result.stdout
