"""Build a fresh wheel and exercise isolated frozen/consumer installs.

Run with the system Python: python tools/check_wheel.py [--lane core|yahoo|...].
Downloads happen during installation only. The smoke child denies Python socket
operations and child-process launches before importing the installed package.
This is Python audit isolation, not a native-code OS firewall.
"""

import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def run(*args: str, cwd: Path = ROOT) -> None:
    subprocess.run(args, cwd=cwd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--lane", default="core",
        choices=["core", "yahoo", "yahoo-consumer", "notebook", "pandas", "filings"],
    )
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="niftyverse-wheel-") as folder:
        work = Path(folder)
        run("uv", "build", "--wheel", "--out-dir", str(work / "dist"))
        wheel, = (work / "dist").glob("*.whl")
        print("FRESH WHEEL", wheel.name, hashlib.sha256(wheel.read_bytes()).hexdigest(), flush=True)
        with zipfile.ZipFile(wheel) as archive:
            assert "niftyverse/py.typed" in archive.namelist()
            assert all(not n.startswith(("tests/", "tools/")) for n in archive.namelist())
        for unsupported in ("3.12", "3.15"):
            rejected = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--dry-run", "--no-deps", "--python-version",
                 unsupported, "--target", str(work / "rejected"), str(wheel)],
                capture_output=True, text=True,
            )
            assert (
                rejected.returncode != 0
                and "requires a different Python" in rejected.stderr
                and "<3.15,>=3.14" in rejected.stderr
            ), rejected.stderr
            assert not (work / "rejected").exists()
            print("Installer rejected Python", unsupported, flush=True)
        run("uv", "venv", "--python", sys.executable, str(work / "venv"))
        python = work / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        extra = None if args.lane == "core" else args.lane.removesuffix("-consumer")
        if args.lane != "yahoo-consumer":
            requirements = work / "requirements.txt"
            command = [
                "uv", "export", "--frozen", "--no-dev", "--no-emit-project",
                "--output-file", str(requirements),
            ]
            if extra:
                command += ["--extra", extra]
            subprocess.run(command, cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
            run("uv", "pip", "install", "--python", str(python), "--only-binary", ":all:",
                "--require-hashes", "-r", str(requirements))
            run("uv", "pip", "install", "--python", str(python), "--no-deps", str(wheel))
        else:
            run("uv", "pip", "install", "--python", str(python), "--only-binary", ":all:",
                f"{wheel}[yahoo]")
        run("uv", "pip", "check", "--python", str(python))
        run(str(python), "-I", str(ROOT / "tools/wheel_smoke.py"), args.lane, cwd=work)
        print("PASS", args.lane, "lock SHA256", hashlib.sha256((ROOT / "uv.lock").read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
