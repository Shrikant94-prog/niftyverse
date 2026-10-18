"""Explicit invocation only: uv run --frozen python tools/probe_sources.py PLAN OUTPUT."""

import asyncio
import json
import sys
from pathlib import Path

from niftyverse.recon import Budget, Probe, capture


def main() -> None:
    plan = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    probes = [Probe(**item) for item in plan["probes"]]
    result = asyncio.run(
        capture(
            probes,
            Path(sys.argv[2]),
            Budget(**plan["budget"]),
            blocked_hosts=frozenset(plan.get("blocked_hosts", [])),
        )
    )
    for item in result:
        print(item["name"], item["outcome"], item.get("status"), item.get("bytes"))


if __name__ == "__main__":
    main()
