"""Finite Phase 02 SDK experiment, explicitly invoked; not the Phase 15 adapter.

uv run --frozen --extra yahoo python tools/probe_yahoo.py OUTPUT
uv run --frozen python tools/probe_yahoo.py --self-test
"""

import hashlib
import importlib.metadata
import json
import math
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

OPTIONS = dict(
    interval="1d",
    auto_adjust=False,
    back_adjust=False,
    repair=False,
    rounding=False,
    keepna=True,
    prepost=False,
    actions=False,
    timeout=30,
    raise_errors=True,
)
WINDOWS = [("2016-09-01", "2016-09-07"), ("2025-11-26", "2025-12-02")]


def supervise(command: list[str], timeout: float) -> str:
    try:
        result = subprocess.run(
            command,
            timeout=timeout,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except subprocess.TimeoutExpired:
        # subprocess.run kills and waits for this owned process on timeout.
        return "deadline"
    return "finished" if result.returncode == 0 else "worker_error"


def worker(symbol: str, start: str, end: str, output: Path, cache: str) -> None:
    import yfinance as yf

    yf.set_tz_cache_location(cache)  # Verified 1.7.0: timezone, cookie AND ISIN caches.
    record = dict(
        capture_kind="sdk_result",
        symbol=symbol,
        start=start,
        end=end,
        options=OPTIONS,
        complete=False,
        observed_at=datetime.now(UTC).isoformat(),
        versions={
            name: importlib.metadata.version(name)
            for name in ["yfinance", "pandas", "numpy", "curl-cffi"]
        },
    )
    try:
        ticker = yf.Ticker(symbol)
        frame = ticker.history(start=start, end=end, **OPTIONS)
        if frame is None or frame.empty or frame["Close"].isna().all():
            record.update(outcome="empty_or_all_null")
        elif len(frame) > 31 or len(frame.columns) > 16:
            record.update(outcome="result_limit")
        else:
            # Lossless SDK scalar boundary: float.hex preserves binary floats;
            # nonfinite values are explicitly tagged, never JSON NaN numbers.
            def cell(value: object) -> dict[str, object]:
                if value is None:
                    return {"kind": "null"}
                if isinstance(value, float):
                    return {
                        "kind": "float64",
                        "value": value.hex() if math.isfinite(value) else str(value),
                    }
                return {"kind": type(value).__name__, "value": str(value)}

            metadata = ticker.get_history_metadata()
            record.update(
                outcome="observed_unverified",
                timezone=str(frame.index.tz),
                index_name=frame.index.name,
                columns=[str(c) for c in frame.columns],
                dtypes=[str(t) for t in frame.dtypes],
                index=[{"iso": t.isoformat(), "epoch_ns": str(t.value)} for t in frame.index],
                rows=[[cell(v) for v in row] for row in frame.itertuples(index=False, name=None)],
                metadata={
                    k: metadata.get(k)
                    for k in [
                        "symbol",
                        "instrumentType",
                        "currency",
                        "exchangeTimezoneName",
                        "exchangeName",
                    ]
                },
            )
    except Exception as exc:
        # SDK exceptions may embed transport URLs/tokens. Preserve the category,
        # not unsanitized text; missing timezone never proves delisting.
        record.update(outcome="sdk_error", error_type=type(exc).__name__)
    record["finished_at"] = datetime.now(UTC).isoformat()
    encoded = json.dumps(record, indent=2, allow_nan=False).encode()
    if len(encoded) > 1024 * 1024:
        raise ValueError("SDK capture exceeds 1 MiB")
    output.write_bytes(encoded)


def main() -> None:
    if sys.argv[1] == "--worker":
        worker(sys.argv[2], sys.argv[3], sys.argv[4], Path(sys.argv[5]), sys.argv[6])
        return
    if sys.argv[1] == "--self-test":
        assert supervise([sys.executable, "-c", "import time; time.sleep(5)"], 0.1) == "deadline"
        assert supervise([sys.executable, "-c", "raise SystemExit(2)"], 5) == "worker_error"
        assert supervise([sys.executable, "-c", "pass"], 5) == "finished"
        print("supervisor: deadline/kill/wait, error, success pass; no SDK/network")
        return
    negative = sys.argv[1] == "--negative"
    output = Path(sys.argv[2] if negative else sys.argv[1])
    output.mkdir(parents=True, exist_ok=False)
    results = []
    blocked = False
    for symbol in ["^GSPC", "^IXIC"]:
        for start, end in [("2025-11-27", "2025-11-28")] if negative else WINDOWS:
            identity = dict(
                symbol=symbol,
                start=start,
                end=end,
                sdk_calls=0,
                underlying_http_requests="unknown",
                complete=False,
            )
            if blocked:
                results.append(dict(identity, outcome="circuit_open"))
                continue
            name = f"{symbol[1:]}-{start}.json"
            with tempfile.TemporaryDirectory(prefix="niftyverse-yahoo-") as cache:
                state = supervise(
                    [
                        sys.executable,
                        str(Path(__file__).resolve()),
                        "--worker",
                        symbol,
                        start,
                        end,
                        str((output / name).resolve()),
                        cache,
                    ],
                    120,
                )
            identity["sdk_calls"] = 1
            if state == "finished" and (output / name).is_file():
                data = (output / name).read_bytes()
                record = json.loads(data)
                identity.update(
                    outcome=record["outcome"],
                    artifact=name,
                    sha256=hashlib.sha256(data).hexdigest(),
                    error_type=record.get("error_type"),
                )
                blocked = record.get("error_type") == "YFRateLimitError"
            else:
                identity["outcome"] = state
            results.append(identity)
            print(identity, flush=True)
            time.sleep(2)
    (output / "summary.json").write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
