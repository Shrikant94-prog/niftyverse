"""Offline integrity gate for controlled local captures; never fetches providers.

uv run --frozen python tools/check_phase02.py .local/phase02
Scientific interpretation remains in the checkpoint evidence, not this checker.
"""

import hashlib
import json
import sys
from pathlib import Path

from niftyverse.recon import _inspect


def main() -> None:
    corpus = Path(sys.argv[1])
    root = Path(__file__).resolve().parents[1] / "docs" / "capabilities"
    observations = json.loads((root / "observations.json").read_text())
    direct = sdk = 0
    for group in observations["sets"]:
        folder = group["plan"].removesuffix(".json")
        data = (corpus / folder / "evidence.json").read_bytes()
        assert hashlib.sha256(data).hexdigest() == group["capture_sha256"]
        originals = json.loads(data)["results"]
        plan = json.loads((root / "probes" / group["plan"]).read_text())
        for probe, record, original in zip(
            plan["probes"], group["results"], originals, strict=True
        ):
            assert all(original[k] == v for k, v in record.items())
            if record["outcome"] != "observed_unverified":
                continue
            body = (corpus / folder / (record["name"] + ".body")).read_bytes()
            assert hashlib.sha256(body).hexdigest() == record["sha256"]
            assert _inspect(body, probe["format"])[0] == "observed_unverified"
            direct += 1
    for group in observations["yahoo"]["sets"]:
        folder = corpus / group["experiment"]
        data = (folder / "summary.json").read_bytes()
        assert hashlib.sha256(data).hexdigest() == group["summary_sha256"]
        assert json.loads(data) == group["results"]
        for record in group["results"]:
            if "artifact" not in record:
                continue
            data = (folder / record["artifact"]).read_bytes()
            assert hashlib.sha256(data).hexdigest() == record["sha256"]
            captured = json.loads(data)
            assert captured["capture_kind"] == "sdk_result"
            assert captured["complete"] is False
            if captured["outcome"] == "observed_unverified":
                expected = (
                    ["2016-09-01", "2016-09-02", "2016-09-06"]
                    if captured["start"] == "2016-09-01"
                    else ["2025-11-26", "2025-11-28", "2025-12-01"]
                )
                assert [v["iso"][:10] for v in captured["index"]] == expected
                assert captured["metadata"]["symbol"] == captured["symbol"]
                assert captured["metadata"]["instrumentType"] == "INDEX"
            else:
                assert captured["error_type"] == "YFPricesMissingError"
            sdk += 1
    assert (direct, sdk) == (19, 6)
    print(
        f"PASS: {direct} direct specimens and {sdk} SDK-result/error captures "
        "match committed hashes; no network"
    )


if __name__ == "__main__":
    main()
