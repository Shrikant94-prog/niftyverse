"""Local, deterministic acquisition compilation and research dependency preflight.

Capabilities and calendars are explicit, locally supplied evidence. Compiling
never discovers sources, opens a catalog, or certifies new provider support.
"""

import tomllib
from collections.abc import Mapping
from dataclasses import asdict, dataclass, fields, replace
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from niftyverse.batches import Partition, identity
from niftyverse.calendars import Calendar
from niftyverse.core import ValidationError
from niftyverse.storage.durable import digest_file
from niftyverse.storage.schemas import SCHEMAS


def _strings(value: object, name: str, *, empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or any(
        not isinstance(v, str) or not v.strip() for v in value
    ):
        raise ValidationError(f"{name} requires nonempty strings")
    if (not value and not empty) or len(set(value)) != len(value):
        raise ValidationError(f"{name} requires unique entries")
    return tuple(sorted(value))


def _day(value: object) -> date:
    if type(value) is date:
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    raise ValidationError("invalid interval date")


def _keys(values: Mapping[str, Any], cls: type[object]) -> None:
    unknown = values.keys() - {f.name for f in fields(cls)}  # type: ignore[arg-type]
    if unknown:
        raise ValidationError(f"unknown {cls.__name__} keys: {sorted(unknown)}")


@dataclass(frozen=True)
class DatasetRequest:
    dataset: str
    fields: tuple[str, ...]
    basis: str = "raw"
    required: bool = True
    depends_on: tuple[str, ...] = ()
    membership_scope: str | None = None
    identity_policy: str = "identity-v1"
    quality_policy: str = "quality-v1"
    scope: str = "selected"

    def __post_init__(self) -> None:
        if self.dataset not in SCHEMAS:
            raise ValidationError("unknown dataset")
        object.__setattr__(self, "fields", _strings(self.fields, "fields"))
        object.__setattr__(self, "depends_on", _strings(self.depends_on, "depends_on", empty=True))
        if not set(self.fields) <= set(SCHEMAS[self.dataset].names):
            raise ValidationError("unknown dataset fields")
        if type(self.required) is not bool or self.scope not in {"selected", "whole_market"}:
            raise ValidationError("invalid required/scope policy")
        if any(
            not isinstance(v, str) or not v
            for v in (
                self.basis,
                self.identity_policy,
                self.quality_policy,
            )
        ) or (
            self.membership_scope is not None
            and (not isinstance(self.membership_scope, str) or not self.membership_scope)
        ):
            raise ValidationError("invalid request policy")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DatasetRequest:
        _keys(value, cls)
        try:
            return cls(**value)
        except TypeError as error:
            raise ValidationError(f"invalid dataset request: {error}") from error


@dataclass(frozen=True)
class DataPlan:
    version: int
    start: date
    end: date
    universe: tuple[str, ...]
    datasets: tuple[DatasetRequest, ...]
    mode: str = "build"
    store: Path | None = None
    destination: Path | None = None
    timezone: str = "Asia/Kolkata"
    source_formats: tuple[str, ...] = ("json",)
    encoding: str = "parquet"
    retain_raw: bool = True
    allow_partial: bool = False
    workers: int = 4
    queue_limit: int = 4
    max_jobs: int = 10_000
    max_requests: int = 10_000
    memory_bytes: int = 128 * 1024 * 1024
    batch_bytes: int = 16 * 1024 * 1024
    max_attempts: int = 2
    offline: bool = False
    local_files: tuple[Path, ...] = ()
    operation: str = "build"
    overlap_sessions: int = 7
    repair_partitions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.version) is not int or self.version != 1:
            raise ValidationError("unsupported config version")
        if type(self.start) is not date or type(self.end) is not date or self.start >= self.end:
            raise ValidationError("invalid interval")
        object.__setattr__(self, "universe", _strings(self.universe, "universe"))
        if (
            not isinstance(self.datasets, tuple)
            or not self.datasets
            or any(not isinstance(r, DatasetRequest) for r in self.datasets)
            or len({r.dataset for r in self.datasets}) != len(self.datasets)
        ):
            raise ValidationError("unique immutable dataset requests required")
        for request in self.datasets:
            request.__post_init__()
        object.__setattr__(self, "datasets", tuple(sorted(self.datasets, key=lambda r: r.dataset)))
        object.__setattr__(self, "source_formats", _strings(self.source_formats, "source_formats"))
        if not set(self.source_formats) <= {"json", "csv", "xml", "inline_xbrl"}:
            raise ValidationError("unsupported source_formats")
        for name, upper in (
            ("workers", 32),
            ("queue_limit", 128),
            ("max_jobs", 100_000),
            ("max_requests", 1_000_000),
            ("memory_bytes", 2**31),
            ("batch_bytes", 64 * 1024 * 1024),
            ("max_attempts", 5),
        ):
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= upper:
                raise ValidationError(f"invalid {name} budget")
        if self.batch_bytes > self.memory_bytes:
            raise ValidationError("batch_bytes exceeds memory budget")
        if self.operation not in {"build", "refresh", "repair", "reconcile"}:
            raise ValidationError("unknown incremental operation")
        if self.mode != "build" and self.operation != "build":
            raise ValidationError("incremental operations require persistent build")
        if type(self.overlap_sessions) is not int or not 1 <= self.overlap_sessions <= 10_000:
            raise ValidationError("invalid overlap_sessions")
        object.__setattr__(
            self,
            "repair_partitions",
            _strings(
                self.repair_partitions,
                "repair_partitions",
                empty=self.operation != "repair",
            ),
        )
        if self.operation != "repair" and self.repair_partitions:
            raise ValidationError("repair_partitions require repair operation")
        if any(
            type(v) is not bool
            for v in (
                self.retain_raw,
                self.allow_partial,
                self.offline,
            )
        ):
            raise ValidationError("boolean output/offline policies required")
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, TypeError, ValueError) as error:
            raise ValidationError("unknown timezone") from error
        if self.mode not in {"build", "memory", "files"} or self.encoding not in {
            "csv",
            "parquet",
        }:
            raise ValidationError("invalid output policy")
        if self.mode == "build" and self.store is None:
            raise ValidationError("persistent build requires store")
        if self.mode != "build" and self.store is not None:
            raise ValidationError("direct extraction must not specify store")
        if (self.mode == "files") != (self.destination is not None):
            raise ValidationError("file output requires destination; other modes must omit it")
        for name in ("store", "destination"):
            path = getattr(self, name)
            if path is not None:
                if not isinstance(path, Path):
                    raise ValidationError(f"invalid {name} path")
                object.__setattr__(self, name, path.expanduser().resolve())
        if self.destination is not None and self.destination.exists():
            raise ValidationError("destination already exists; choose a new bundle")
        if not isinstance(self.local_files, tuple) or any(
            not isinstance(p, Path) for p in self.local_files
        ):
            raise ValidationError("invalid local_files")
        object.__setattr__(
            self,
            "local_files",
            tuple(
                sorted(
                    {p.expanduser().resolve() for p in self.local_files},
                    key=str,
                )
            ),
        )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DataPlan:
        _keys(value, cls)
        values = dict(value)
        try:
            for key in ("start", "end"):
                values[key] = _day(values[key])
            values["datasets"] = tuple(DatasetRequest.from_mapping(v) for v in values["datasets"])
            for key in ("store", "destination"):
                if values.get(key) is not None:
                    if not isinstance(values[key], (str, Path)) or not str(values[key]).strip():
                        raise ValidationError(f"invalid {key} path")
                    values[key] = Path(values[key])
            if "local_files" in values:
                values["local_files"] = tuple(
                    Path(p)
                    for p in _strings(
                        values["local_files"],
                        "local_files",
                        empty=True,
                    )
                )
            return cls(**values)
        except (KeyError, TypeError, AttributeError) as error:
            raise ValidationError(f"invalid config: {error}") from error

    @classmethod
    def from_toml(cls, value: str) -> DataPlan:
        try:
            return cls.from_mapping(tomllib.loads(value))
        except tomllib.TOMLDecodeError as error:
            raise ValidationError(f"invalid TOML: {error}") from error


@dataclass(frozen=True)
class Capability:
    dataset: str
    source_id: str
    contract_version: str
    parser_version: str
    schema_version: str
    formats: tuple[str, ...]
    fields: tuple[str, ...]
    bases: tuple[str, ...]
    start: date
    end: date
    requests_per_job: int = 1
    paginated: bool = False

    def __post_init__(self) -> None:
        if self.dataset not in SCHEMAS or any(
            not isinstance(v, str) or not v
            for v in (
                self.source_id,
                self.contract_version,
                self.parser_version,
                self.schema_version,
            )
        ):
            raise ValidationError("invalid capability identity")
        for name in ("formats", "fields", "bases"):
            object.__setattr__(self, name, _strings(getattr(self, name), name))
        if type(self.start) is not date or type(self.end) is not date or self.start >= self.end:
            raise ValidationError("invalid capability interval")
        if type(self.requests_per_job) is not int or not 1 <= self.requests_per_job <= 1000:
            raise ValidationError("invalid request estimate")
        if type(self.paginated) is not bool:
            raise ValidationError("invalid pagination contract")


@dataclass(frozen=True)
class CacheEntry:
    partition: Partition
    source_id: str
    schema_version: str
    parser_version: str
    snapshot_kind: str

    def satisfies(self, job: Job) -> bool:
        return bool(
            job.capability
            and self.snapshot_kind == "history_bundle"
            and self.partition.identity == job.partition.identity
            and (self.source_id, self.schema_version, self.parser_version)
            == (
                job.capability.source_id,
                job.capability.schema_version,
                job.capability.parser_version,
            )
        )


@dataclass(frozen=True)
class Job:
    id: str
    partition: Partition
    capability: Capability | None
    source_format: str | None
    dependencies: tuple[str, ...]
    required: bool
    blocked: tuple[str, ...]
    reuse: bool = False


@dataclass(frozen=True)
class WorkGraph:
    plan: DataPlan
    plan_hash: str
    jobs: tuple[Job, ...]
    request_estimate: int
    local_hashes: tuple[tuple[str, str], ...]
    calendar_hash: str | None

    def explain(self) -> dict[str, Any]:
        return {
            "plan_hash": self.plan_hash,
            "mode": self.plan.mode,
            "requests_estimate": self.request_estimate,
            "requests_upper_bound": self.request_estimate * self.plan.max_attempts,
            "unresolved_estimates": [j.id for j in self.jobs if j.capability is None],
            "requested_interval": (str(self.plan.start), str(self.plan.end)),
            "jobs": [
                dict(
                    id=j.id,
                    dataset=j.partition.dataset,
                    start=str(j.partition.start),
                    end=str(j.partition.end),
                    dependencies=j.dependencies,
                    blocked=j.blocked,
                    reuse=j.reuse,
                    source_format=j.source_format,
                )
                for j in self.jobs
            ],
            "discovery_required": any("discovery_required" in j.blocked for j in self.jobs),
            "local_hashes": self.local_hashes,
        }


def compile_plan(
    plan: DataPlan,
    capabilities: tuple[Capability, ...],
    *,
    calendar: Calendar | None = None,
    cache: tuple[CacheEntry, ...] = (),
    membership_coverage: tuple[tuple[str, date, date, str], ...] = (),
) -> WorkGraph:
    """Compile daily atomic units; unknown calendar days stay blocked, not holidays.

    Exact reuse is deliberately conservative: no subset, parser/policy projection,
    or resolved-result snapshot is promoted into a complete history bundle.
    Membership evidence tuples are scope/start/exclusive-end/verification hash.
    """
    plan.__post_init__()
    caps = {c.dataset: c for c in capabilities}
    if len(caps) != len(capabilities):
        raise ValidationError("choose one explicit capability per dataset")
    requests = {r.dataset: r for r in plan.datasets}
    if "security_daily_details" in requests and "equity_daily" not in requests:
        r = requests["security_daily_details"]
        requests["equity_daily"] = DatasetRequest(
            "equity_daily",
            ("close", "quantity"),
            required=r.required,
            membership_scope=r.membership_scope,
            identity_policy=r.identity_policy,
            quality_policy=r.quality_policy,
        )
    if "security_daily_details" in requests:
        r = requests["security_daily_details"]
        requests[r.dataset] = replace(
            r,
            depends_on=tuple(
                sorted(
                    set(r.depends_on) | {"equity_daily"},
                )
            ),
        )
    order: list[str] = []
    visiting: set[str] = set()

    def visit(name: str) -> None:
        if name in visiting:
            raise ValidationError("dataset dependency cycle")
        if name in order or name not in requests:
            return
        visiting.add(name)
        for dependency in requests[name].depends_on:
            visit(dependency)
        visiting.remove(name)
        order.append(name)

    for name in sorted(requests):
        visit(name)
    for name in reversed(order):
        if requests[name].required:
            for dependency in requests[name].depends_on:
                if dependency in requests:
                    requests[dependency] = replace(requests[dependency], required=True)
    days = (plan.end - plan.start).days
    if days * len(requests) > plan.max_jobs:
        raise ValidationError("job budget exceeded before expansion; narrow dates/datasets")
    if calendar:
        calendar.__post_init__()
        if calendar.source_timezone != plan.timezone:
            raise ValidationError("calendar timezone differs from plan timezone")
    hashes = tuple((str(p), digest_file(p)) for p in plan.local_files)
    calendar_hash = calendar.content_hash if calendar else None
    plan_hash = identity(
        (
            asdict(plan),
            [asdict(c) for c in sorted(capabilities, key=lambda c: c.dataset)],
            hashes,
            calendar_hash,
            membership_coverage,
        )
    )
    jobs: list[Job] = []
    ids: dict[tuple[str, date], str] = {}
    for name in order:
        r, cap = requests[name], caps.get(name)
        for offset in range(days):
            start = plan.start + timedelta(days=offset)
            end = start + timedelta(days=1)
            session = (
                next((s for s in calendar.sessions if s.session_date == start), None)
                if calendar
                else None
            )
            if session and session.eligible is False:
                continue
            blockers = []
            if session is None or session.eligible is None:
                blockers.append("calendar_unknown")
            if r.membership_scope and not any(
                scope == r.membership_scope and low <= start and end <= high and sha
                for scope, low, high, sha in membership_coverage
            ):
                blockers.append(f"membership_unverified:{r.membership_scope}")
            source_format = None
            if not cap:
                blockers.append("discovery_required")
            else:
                source_format = next((f for f in plan.source_formats if f in cap.formats), None)
                if source_format is None:
                    blockers.append("source_format_unavailable")
                if not (cap.start <= start and end <= cap.end):
                    blockers.append("capability_window_unverified")
                if not set(r.fields) <= set(cap.fields) or r.basis not in cap.bases:
                    blockers.append("capability_fields_or_basis_unavailable")
            dependencies = []
            for dependency in r.depends_on:
                dep_id = ids.get((dependency, start))
                if dep_id:
                    dependencies.append(dep_id)
                else:
                    blockers.append(f"missing_dependency:{dependency}")
            partition = Partition(
                name,
                start,
                end,
                plan.universe,
                r.fields,
                r.basis,
                cap.contract_version if cap else "unverified",
                r.identity_policy,
                r.quality_policy,
                "",
                scope=r.scope,  # type: ignore[arg-type]
            )
            job_id = identity((partition.identity, asdict(cap) if cap else None, source_format))
            ids[name, start] = job_id
            job = Job(
                job_id,
                partition,
                cap,
                source_format,
                tuple(dependencies),
                r.required,
                tuple(blockers),
            )
            jobs.append(replace(job, reuse=not blockers and any(c.satisfies(job) for c in cache)))
    if plan.operation == "repair" and not set(plan.repair_partitions) <= {
        j.partition.identity for j in jobs
    }:
        raise ValidationError("repair partition outside requested graph")
    jobs = [replace(j, reuse=j.reuse and not should_recheck(plan, tuple(jobs), j)) for j in jobs]
    reusable_ids: set[str] = set()
    for index, job in enumerate(jobs):
        if job.reuse and all(d in reusable_ids for d in job.dependencies):
            reusable_ids.add(job.id)
        else:
            jobs[index] = replace(job, reuse=False)
    estimate = sum(
        j.capability.requests_per_job
        for j in jobs
        if not j.reuse and not j.blocked and j.capability
    )
    if estimate * plan.max_attempts > plan.max_requests:
        raise ValidationError("request budget exceeded including bounded retry")
    return WorkGraph(plan, plan_hash, tuple(jobs), estimate, hashes, calendar_hash)


def should_recheck(plan: DataPlan, jobs: tuple[Job, ...], job: Job) -> bool:
    if plan.operation == "reconcile":
        return True
    if plan.operation == "repair":
        return job.partition.identity in plan.repair_partitions
    if plan.operation == "refresh":
        sessions = sorted(
            {
                j.partition.start
                for j in jobs
                if j.partition.dataset == job.partition.dataset
                and "calendar_unknown" not in j.blocked
            }
        )
        return job.partition.start in sessions[-plan.overlap_sessions :]
    return False


@dataclass(frozen=True)
class ResearchDependency:
    """Exact research-expanded input scope; callers supply actual warmup endpoints.

    This bridge deliberately does not calculate future research features or
    infer filing admissibility. Those phases supply their explicit missing grid.
    """

    kind: str
    start: date
    end: date
    universe: tuple[str, ...]
    request: DatasetRequest
    required: bool = True
    capability: Capability | None = None

    def __post_init__(self) -> None:
        if self.kind not in {"warmup", "prior_filings", "history", "membership", "actions"}:
            raise ValidationError("unknown research dependency kind")
        if type(self.start) is not date or type(self.end) is not date or self.start >= self.end:
            raise ValidationError("invalid dependency interval")
        object.__setattr__(self, "universe", _strings(self.universe, "dependency universe"))
        self.request.__post_init__()
        if type(self.required) is not bool:
            raise ValidationError("invalid dependency required policy")


@dataclass(frozen=True)
class ResearchPreflight:
    missing: tuple[ResearchDependency, ...]
    acquisition: DataPlan | None
    blocked: bool


def research_preflight(
    template: DataPlan,
    dependencies: tuple[ResearchDependency, ...],
    cache: tuple[CacheEntry, ...],
) -> ResearchPreflight:
    """Report missing history and propose explicit acquisition; never execute it.

    Use only history bundles with matching scopes/policies. A proposed union may
    intentionally overfetch; consumers must explicitly build and repin a new
    immutable snapshot. It never mutates the pinned input snapshot.
    """
    missing = []
    for dep in dependencies:
        dep.__post_init__()
        r = dep.request
        if not dep.capability or not all(
            any(
                c.snapshot_kind == "history_bundle"
                and c.partition.dataset == r.dataset
                and c.partition.start <= dep.start + timedelta(days=offset) < c.partition.end
                and set(dep.universe) <= set(c.partition.universe)
                and set(r.fields) <= set(c.partition.fields)
                and (
                    c.source_id,
                    c.schema_version,
                    c.parser_version,
                    c.partition.source_generation,
                )
                == (
                    dep.capability.source_id,
                    dep.capability.schema_version,
                    dep.capability.parser_version,
                    dep.capability.contract_version,
                )
                and (c.partition.basis, c.partition.identity_policy, c.partition.quality_policy)
                == (r.basis, r.identity_policy, r.quality_policy)
                for c in cache
            )
            for offset in range((dep.end - dep.start).days)
        ):
            missing.append(dep)
    acquisition = None
    if missing:
        requests: dict[str, DatasetRequest] = {}
        for dep in missing:
            r = replace(dep.request, required=dep.required)
            if r.dataset in requests:
                old = requests[r.dataset]
                if replace(old, fields=r.fields, required=r.required) != r:
                    raise ValidationError("incompatible research acquisition policies")
                r = replace(
                    r,
                    fields=tuple(sorted(set(old.fields) | set(r.fields))),
                    required=old.required or r.required,
                )
            requests[r.dataset] = r
        acquisition = replace(
            template,
            start=min(d.start for d in missing),
            end=max(d.end for d in missing),
            universe=tuple(sorted({u for d in missing for u in d.universe})),
            datasets=tuple(requests.values()),
        )
    return ResearchPreflight(tuple(missing), acquisition, any(d.required for d in missing))
