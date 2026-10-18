"""Run the Phase 01 Linux checks under an explicitly selected Linux Python 3.14.

Invoke with `wsl -d Ubuntu -- python3 /mnt/c/.../niftyverse/tools/check_linux.py`
on the local Windows host. Tools and environments stay in a fresh /tmp directory;
the checked-out source and uv.lock are read from the selected project only.
"""

import hashlib
import io
import json
import os
import platform
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path


def main() -> None:
    assert sys.platform == "linux" and sys.version_info[:2] == (3, 14)
    root = Path(__file__).resolve().parents[1]
    print(sys.version, platform.platform(), flush=True)
    with tempfile.TemporaryDirectory(prefix="niftyverse-linux-") as folder:
        work = Path(folder)
        tools = work / "tools"
        tools.mkdir()
        # Ubuntu's Python lacks ensurepip; use the verified official uv wheel binary
        # instead of modifying system Python or installing an OS package.
        with urllib.request.urlopen("https://pypi.org/pypi/uv/0.12.9/json") as response:
            files = json.load(response)["urls"]
        entry = next(f for f in files if "manylinux_2_17_x86_64" in f["filename"])
        with urllib.request.urlopen(entry["url"]) as response:
            wheel = response.read()
        assert hashlib.sha256(wheel).hexdigest() == (
            "5badfd805fd88bf99b4b4f044f6e8f762f1892cab27477f4427bb473e93dd049"
        )
        with zipfile.ZipFile(io.BytesIO(wheel)) as archive:
            (tools / "uv").write_bytes(archive.read("uv-0.12.9.data/scripts/uv"))
        (tools / "uv").chmod(0o700)
        env = os.environ | {
            "PATH": str(tools) + os.pathsep + os.environ["PATH"],
            "UV_PROJECT_ENVIRONMENT": str(work / "project"),
        }
        for command in [
            ["uv", "--version"],
            ["uv", "sync", "--frozen", "--python", sys.executable],
            ["uv", "run", "--frozen", "ruff", "format", "--check", "src", "tests"],
            ["uv", "run", "--frozen", "ruff", "check", "src", "tests"],
            ["uv", "run", "--frozen", "mypy", "--cache-dir", str(work / "mypy"), "src", "tests"],
            ["uv", "run", "--frozen", "pytest", "-q", "-o", "cache_dir=" + str(work / "pytest")],
            ["uv", "run", "--frozen", "python", "tools/check_wheel.py", "--lane", "core"],
        ]:
            subprocess.run(command, cwd=root, env=env, check=True)
    print("PASS Linux behavior and fresh core wheel; temporary environments removed.", flush=True)


if __name__ == "__main__":
    main()
