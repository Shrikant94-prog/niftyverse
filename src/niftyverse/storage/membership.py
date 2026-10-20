"""Immutable replayable membership bundles using the shared publication boundary."""

import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa

from niftyverse import membership
from niftyverse.calendars import SourceTime
from niftyverse.core import ValidationError
from niftyverse.membership import (
    Correction,
    Coverage,
    Event,
    Member,
    Record,
    Reference,
    Replay,
    Snapshot,
    replay,
)
from niftyverse.storage.bundles import Bundle, publish_bundle, read_bundle, verified_bytes

MEMBERSHIP_INTERVALS = pa.schema(
    [
        pa.field("start", pa.date32(), False),
        pa.field("end", pa.date32(), False),
        pa.field(
            "members",
            pa.list_(
                pa.struct(
                    [
                        pa.field("member_id", pa.string(), False),
                        pa.field("kind", pa.string(), False),
                        pa.field("instrument_id", pa.string()),
                    ]
                )
            ),
            False,
        ),
        pa.field("status", pa.string(), False),
        pa.field("reasons", pa.list_(pa.string()), False),
    ]
)


def _reference(data: dict[str, Any]) -> Reference:
    return Reference(**{**data, "known_at": datetime.fromisoformat(data["known_at"])})


def _snapshot(data: dict[str, Any]) -> Snapshot:
    return Snapshot(
        **{
            **data,
            "on": date.fromisoformat(data["on"]),
            "members": tuple(Member(**m) for m in data["members"]),
            "evidence": _reference(data["evidence"]),
        }
    )


def _event(data: dict[str, Any]) -> Event:
    announced = data["announced"]
    value = announced["value"]
    if value is not None:
        value = (
            datetime.fromisoformat(value)
            if announced["precision"] == "instant"
            else date.fromisoformat(value)
        )
    return Event(
        **{
            **data,
            "effective_date": date.fromisoformat(data["effective_date"]),
            "includes": tuple(Member(**m) for m in data["includes"]),
            "excludes": tuple(Member(**m) for m in data["excludes"]),
            "announced": SourceTime(**{**announced, "value": value}),
            "evidence": _reference(data["evidence"]),
        }
    )


def _record(data: dict[str, Any] | None) -> Record | None:
    if data is None:
        return None
    return _event(data) if "event_id" in data else _snapshot(data)


def replay_recipe(recipe_json: str) -> Replay:
    """Decode a retained, bounded recipe and recompute all verification states."""
    if len(recipe_json.encode()) > 8 * 1024 * 1024:
        raise ValidationError("membership recipe exceeds byte limit")
    try:
        data = json.loads(recipe_json)
        if data.pop("schema_version") != 1:
            raise ValidationError("unsupported membership recipe version")
        corrections = tuple(
            Correction(
                **{
                    **c,
                    "original": _record(c["original"]),
                    "replacement": _record(c["replacement"]),
                    "affected_from": date.fromisoformat(c["affected_from"]),
                    "affected_to": date.fromisoformat(c["affected_to"]),
                    "evidence": tuple(_reference(r) for r in c["evidence"]),
                    "proposed_at": datetime.fromisoformat(c["proposed_at"]),
                    "reviewed_at": datetime.fromisoformat(c["reviewed_at"])
                    if c["reviewed_at"]
                    else None,
                }
            )
            for c in data["corrections"]
        )
        result = replay(
            **{
                **data,
                "start": date.fromisoformat(data["start"]),
                "end": date.fromisoformat(data["end"]),
                "known_at": datetime.fromisoformat(data["known_at"]),
                "baseline": _snapshot(data["baseline"]),
                "events": tuple(_event(e) for e in data["events"]),
                "corrections": corrections,
                "checks": tuple(_snapshot(s) for s in data["checks"]),
                "coverage": tuple(
                    Coverage(
                        date.fromisoformat(c["start"]),
                        date.fromisoformat(c["end"]),
                        _reference(c["evidence"]),
                    )
                    for c in data["coverage"]
                ),
            }
        )
        if result.recipe_json != recipe_json:
            raise ValidationError("membership recipe is not canonical")
        return result
    except (ValueError, KeyError, TypeError, AttributeError, RecursionError) as error:
        raise ValidationError(f"invalid membership recipe: {error}") from error


def _table(result: Replay) -> pa.Table:
    return pa.Table.from_pylist([asdict(r) for r in result.intervals], schema=MEMBERSHIP_INTERVALS)


def invalidation(previous: Replay, current: Replay) -> list[dict[str, Any]]:
    if (previous.scope, previous.start, previous.end, previous.original_sha256) != (
        current.scope,
        current.start,
        current.end,
        current.original_sha256,
    ):
        raise ValidationError("parent scope/input/window differs")
    if current.known_at < previous.known_at:
        raise ValidationError("parent knowledge time is later than new snapshot")
    correction_ids = sorted(set(current.applied_corrections) - set(previous.applied_corrections))
    boundaries = sorted(
        {d for r in (*previous.intervals, *current.intervals) for d in (r.start, r.end)}
    )
    changes = []
    for left, right in zip(boundaries, boundaries[1:], strict=False):
        a = next(r for r in previous.intervals if r.start <= left < r.end)
        b = next(r for r in current.intervals if r.start <= left < r.end)
        reasons = []
        if a.members != b.members:
            reasons.append("membership_changed")
        if (a.status, a.reasons) != (b.status, b.reasons):
            reasons.append("verification_changed")
        if reasons:
            changes.append(
                {
                    "start": str(left),
                    "end": str(right),
                    "reasons": reasons,
                    "correction_ids": correction_ids,
                }
            )
    if not changes and previous.version_id != current.version_id:
        changes.append(
            {
                "start": str(current.start),
                "end": str(current.end),
                "reasons": ["evidence_or_policy_revision"],
                "correction_ids": correction_ids,
            }
        )
    return changes


def publish_membership(
    result: Replay,
    destination: Path,
    *,
    previous: Bundle | None = None,
    encoding: str = "parquet",
    fault: Callable[[str], None] | None = None,
) -> Bundle:
    """Validate before writes; a partial bundle never grants strict membership.

    The retained recipe supports logical replay without the original CSV. Raw
    source authenticity/availability and cross-version byte rebuild are separate.
    """
    if previous is not None and read_bundle(previous.path).manifest != previous.manifest:
        raise ValidationError("pinned parent bundle manifest changed")
    parent = load_membership(previous.path) if previous is not None else None
    if parent is not None and parent.scope != result.scope:
        raise ValidationError("parent scope differs")
    checked = replay_recipe(result.recipe_json)
    if checked != result:
        raise ValidationError("membership result differs from recipe replay")
    changes = invalidation(parent, result) if parent is not None else []
    table = _table(result)
    publish_bundle(
        destination,
        (("membership_intervals", MEMBERSHIP_INTERVALS, table.to_batches()),),
        {
            "kind": "membership_bundle",
            "status": "complete"
            if all(r.status == "independently_verified" for r in result.intervals)
            else "partial",
            "membership_version": result.version_id,
            "membership_code": {
                Path(path).name: hashlib.sha256(Path(path).read_bytes()).hexdigest()
                for path in (__file__, membership.__file__)
            },
            "scope": result.scope,
            "original_sha256": result.original_sha256,
            "known_at": result.known_at.isoformat(),
            "parent_bundle_id": previous.manifest["bundle_id"] if previous is not None else None,
            "applied_corrections": result.applied_corrections,
            "invalidation": changes,
            "raw_source_retained": False,
            "logical_recipe_retained": True,
        },
        encoding=encoding,
        raw=(("recipe.json", result.recipe_json.encode()),),
        fault=fault,
    )
    return read_bundle(destination)


def load_membership(destination: Path) -> Replay:
    bundle = read_bundle(destination)
    if bundle.manifest["kind"] != "membership_bundle":
        raise ValidationError("not a membership bundle")
    try:
        entry = bundle.manifest["artifacts"]["recipe.json"]
        if entry["bytes"] > 8 * 1024 * 1024:
            raise ValidationError("membership recipe exceeds byte limit")
        recipe = verified_bytes(destination, "recipe.json", entry).decode("utf-8")
        result = replay_recipe(recipe)
        expected_status = (
            "complete"
            if all(r.status == "independently_verified" for r in result.intervals)
            else "partial"
        )
        if (
            result.version_id != bundle.manifest["membership_version"]
            or result.scope != bundle.manifest["scope"]
            or result.original_sha256 != bundle.manifest["original_sha256"]
            or result.known_at.isoformat() != bundle.manifest["known_at"]
            or list(result.applied_corrections) != bundle.manifest["applied_corrections"]
            or expected_status != bundle.manifest["status"]
            or not _table(result).equals(bundle.table("membership_intervals"))
        ):
            raise ValidationError("membership bundle disagrees with recipe replay")
        return result
    except (KeyError, UnicodeError) as error:
        raise ValidationError("invalid membership bundle recipe") from error
