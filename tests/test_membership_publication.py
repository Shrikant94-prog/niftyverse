"""Immutable membership outputs and narrow, explained correction invalidation."""

from dataclasses import replace
from pathlib import Path

import pytest
from test_membership import D1, D2, D3, D4, correction, run

from niftyverse.core import ValidationError
from niftyverse.storage.bundles import read_bundle
from niftyverse.storage.membership import load_membership, publish_membership


@pytest.mark.parametrize("encoding", ["csv", "parquet"])
def test_correction_new_output_old_recipe_and_invalidation(tmp_path: Path, encoding: str) -> None:
    old = run()
    first = publish_membership(old, tmp_path / "old", encoding=encoding)
    old_bytes = {p.name: p.read_bytes() for p in first.path.iterdir() if p.is_file()}
    new = run(corrections=(correction("accepted"),))
    second = publish_membership(new, tmp_path / "new", previous=first, encoding=encoding)
    assert second.manifest["membership_version"] != first.manifest["membership_version"]
    assert second.manifest["parent_bundle_id"] == first.manifest["bundle_id"]
    assert second.manifest["invalidation"] == [
        {
            "start": str(D2),
            "end": str(D3),
            "reasons": ["membership_changed"],
            "correction_ids": ["fix"],
        }
    ]
    assert load_membership(first.path) == old
    assert load_membership(second.path) == new
    assert old_bytes == {p.name: p.read_bytes() for p in first.path.iterdir() if p.is_file()}
    with pytest.raises(FileExistsError):
        publish_membership(new, first.path)
    assert (
        first.table("membership_intervals").to_pylist()
        != second.table("membership_intervals").to_pylist()
    )


def test_blocked_regions_publish_explicitly_without_strict_success(tmp_path: Path) -> None:
    result = run(checks=())
    bundle = publish_membership(result, tmp_path / "blocked")
    assert bundle.manifest["status"] == "partial"
    rows = bundle.table("membership_intervals").to_pylist()
    assert all(r["status"] == "quarantined" and r["reasons"] for r in rows)
    with pytest.raises(ValidationError, match="unverified"):
        load_membership(bundle.path).strict_members(D1)


def test_forged_result_wrong_parent_and_corrupt_recipe_no_success(tmp_path: Path) -> None:
    result = run(checks=())
    forged = replace(result, intervals=run().intervals)
    with pytest.raises(ValidationError, match="replay"):
        publish_membership(forged, tmp_path / "forged")
    assert not (tmp_path / "forged").exists()
    first = publish_membership(run(), tmp_path / "parent")
    with pytest.raises(ValidationError, match="scope"):
        publish_membership(replace(run(), scope="different"), tmp_path / "wrong", previous=first)
    assert not (tmp_path / "wrong").exists()
    (first.path / "recipe.json").write_bytes(b"{}")
    with pytest.raises(ValidationError, match="checksum"):
        load_membership(first.path)


@pytest.mark.parametrize("boundary", ["before_manifest", "before_publish", "after_publish"])
def test_publication_fault_never_exposes_complete_result(tmp_path: Path, boundary: str) -> None:
    def fail(stage: str) -> None:
        if stage == boundary:
            raise OSError("injected membership publication failure")

    destination = tmp_path / "failed"
    with pytest.raises(OSError, match="injected"):
        publish_membership(run(), destination, fault=fail)
    assert not (destination / "manifest.json").exists()
    with pytest.raises(ValidationError, match="manifest"):
        read_bundle(destination)


def test_gap_and_contradiction_survive_successful_publication(tmp_path: Path) -> None:
    from test_membership import CHECKS, COVERAGE, A

    # Coverage exists only through Jan 2; the end check contradicts the replay.
    result = run(
        checks=(CHECKS[0], replace(CHECKS[1], members=(A,))), coverage=(replace(COVERAGE, end=D2),)
    )
    bundle = publish_membership(result, tmp_path / "gaps")
    loaded = load_membership(bundle.path)
    assert loaded == result
    assert loaded.end == D4
    assert "event_coverage_unverified" in loaded.intervals[-1].reasons
    assert bundle.manifest["status"] == "partial"


def test_parent_bundle_must_match_the_pinned_manifest(tmp_path: Path) -> None:
    first = publish_membership(run(), tmp_path / "pinned")
    first.manifest["bundle_id"] = "forged"
    with pytest.raises(ValidationError, match="pinned"):
        publish_membership(
            run(corrections=(correction("accepted"),)), tmp_path / "child", previous=first
        )
    assert not (tmp_path / "child").exists()
