"""Local-context/replay boundaries: malformed input never reaches canonical state."""

import json
from dataclasses import asdict
from pathlib import Path

import pytest
from test_execution import batch_for, graph_for
from test_planning import calendar, capability

from niftyverse.acquisition_inputs import BundleProvider, PlanningContext, load_batch
from niftyverse.core import ValidationError
from niftyverse.execution import AcquisitionFailure
from niftyverse.storage.bundles import write_direct


@pytest.mark.parametrize("encoding", ["csv", "parquet"])
def test_typed_replay_exact_values_and_schema(tmp_path: Path, encoding: str) -> None:
    batch = batch_for(graph_for(tmp_path).jobs[0])
    path = tmp_path / "input"
    write_direct(batch, path, encoding=encoding)
    loaded = load_batch(path)
    assert loaded.request_identity == batch.request_identity
    assert loaded.tables[0][1].equals(batch.tables[0][1])
    assert not (tmp_path / "store").exists()


@pytest.mark.parametrize("mutation", ["unknown", "bad_date", "bad_session", "bad_type", "empty"])
def test_context_rejection_is_local_and_preserves_input(tmp_path: Path, mutation: str) -> None:
    values = {"capabilities": [asdict(capability())], "calendar": asdict(calendar())}
    raw = json.loads(json.dumps(values, default=str))
    if mutation == "unknown":
        raw["surprise"] = "ignore?"
    if mutation == "bad_date":
        raw["capabilities"][0]["start"] = "yesterday"
    if mutation == "bad_session":
        raw["calendar"]["sessions"][0]["state"] = "fake"
    if mutation == "bad_type":
        raw["capabilities"] = 5
    if mutation == "empty":
        raw = []
    payload = json.dumps(raw).encode()
    with pytest.raises(ValidationError, match="planning context"):
        PlanningContext.from_json(payload)
    assert payload == json.dumps(raw).encode() and list(tmp_path.iterdir()) == []


def test_omitted_raw_ambiguous_revision_corruption_and_budget_reject(tmp_path: Path) -> None:
    batch = batch_for(graph_for(tmp_path).jobs[0])
    write_direct(batch, tmp_path / "no-raw", retain_raw=False)
    with pytest.raises(AcquisitionFailure, match="raw_replay_unavailable"):
        load_batch(tmp_path / "no-raw")
    write_direct(batch, tmp_path / "a")
    write_direct(batch, tmp_path / "b")
    with pytest.raises(ValidationError, match="ambiguous replay"):
        BundleProvider((tmp_path / "a", tmp_path / "b"))
    manifest = (tmp_path / "a" / "manifest.json").read_bytes()
    raw = tmp_path / "a" / "raw" / batch.capture.sha256
    raw.write_bytes(b"corrupted")
    with pytest.raises(ValidationError, match="checksum"):
        load_batch(tmp_path / "a")
    assert (tmp_path / "a" / "manifest.json").read_bytes() == manifest
    huge = tmp_path / "huge"
    huge.mkdir()
    (huge / "manifest.json").write_bytes(b" " * (1024 * 1024 + 1))
    with pytest.raises(ValidationError, match="manifest byte limit"):
        BundleProvider((huge,))
    assert not (tmp_path / "store").exists()
