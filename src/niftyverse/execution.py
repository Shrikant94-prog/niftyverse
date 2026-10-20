"""Bounded DAG coordinator: providers acquire, shared batches validate, sinks publish.

Only the coordinator uses the live store connection. There is no implicit
provider discovery, background scheduler, or database in direct extraction.
"""

import asyncio
import re
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from niftyverse.batches import ValidatedBatch, identity
from niftyverse.core import ValidationError
from niftyverse.planning import Job, WorkGraph, should_recheck
from niftyverse.storage.bundles import publish_bundle, write_direct
from niftyverse.storage.durable import digest_file

if TYPE_CHECKING:
    from niftyverse.storage.catalog import Store


class AcquisitionFailure(Exception):
    """Sanitized provider failure with explicit retry/defer/capability scope."""

    def __init__(
        self,
        code: str,
        *,
        retryable: bool = False,
        source_wide: bool = False,
        deferred: bool = False,
    ) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", code):
            raise ValueError("failure code must be sanitized")
        self.code, self.retryable = code, retryable
        self.source_wide, self.deferred = source_wide, deferred
        super().__init__(code)


@dataclass(frozen=True)
class PageEvidence:
    cursor: str
    next_cursor: str | None
    content_sha256: str
    snapshot_id: str | None
    rows: int


@dataclass(frozen=True)
class Acquired:
    batch: ValidatedBatch
    pages: tuple[PageEvidence, ...] = ()
    expected_source_rows: int | None = None
    reconciliation_evidence: str | None = None


class Provider(Protocol):
    offline_capable: bool

    async def acquire(self, job: Job, *, attempt: int, offline: bool) -> Acquired: ...


@dataclass(frozen=True)
class Event:
    job_id: str
    state: str
    committed_partitions: int
    committed_rows: int
    reason: str | None = None
    attempt: int = 0


@dataclass
class ExecutionResult:
    status: str
    states: dict[str, str]
    reasons: dict[str, str]
    attempts: dict[str, int]
    run_id: str | None
    committed_partitions: int = 0
    committed_rows: int = 0
    warnings: tuple[str, ...] = ()
    batches: tuple[ValidatedBatch, ...] = ()
    retry_limit: int = 1
    resume_limit: str = "bounded re-extract only; no durable cross-run resume"
    peak_active: int = 0
    peak_pending: int = 0
    reused_partitions: int = 0
    history_snapshot_id: str | None = None


def _validate(
    acquired: Acquired, job: Job, byte_budget: int, *, allow_partial: bool = False
) -> None:
    batch, cap = acquired.batch, job.capability
    size = len(batch.capture.body) + sum(t.nbytes for _, t in batch.tables)
    if size > byte_budget:
        raise AcquisitionFailure("batch_budget_exceeded")
    batch.__post_init__()
    if not cap or batch.partition.identity != job.partition.identity:
        raise ValidationError("partition_contract_mismatch")
    if (batch.capture.source_id, batch.normalizer_version, batch.schema_version) != (
        cap.source_id,
        cap.parser_version,
        cap.schema_version,
    ):
        raise ValidationError("source_parser_schema_mismatch")
    partial = allow_partial and batch.coverage == "partial"
    if cap.paginated and not partial:
        pages = acquired.pages
        if not pages or len(pages) > cap.requests_per_job:
            raise ValidationError("pagination_budget_or_missing_pages")
        if (
            len({p.cursor for p in pages}) != len(pages)
            or len({p.content_sha256 for p in pages}) != len(pages)
            or any(not re.fullmatch(r"[0-9a-f]{64}", p.content_sha256) for p in pages)
            or any(type(p.rows) is not int or p.rows < 0 for p in pages)
            or any(p.next_cursor != q.cursor for p, q in zip(pages, pages[1:], strict=False))
            or pages[-1].next_cursor is not None
        ):
            raise ValidationError("pagination_nonadvancing_or_incomplete")
        stable = bool(pages[0].snapshot_id) and all(
            p.snapshot_id == pages[0].snapshot_id for p in pages
        )
        if (not stable and not acquired.reconciliation_evidence) or (
            type(acquired.expected_source_rows) is not int
            or acquired.expected_source_rows != sum(p.rows for p in pages)
        ):
            raise ValidationError("completeness_unverified")
    if batch.coverage not in {"complete", "no_observations"} and not partial:
        raise ValidationError("completeness_unverified")


@dataclass
class _Sink:
    graph: WorkGraph
    store: Store | None
    spool: Path | None
    memory: list[ValidatedBatch] = field(default_factory=list)
    files: list[tuple[Job, int, bool]] = field(default_factory=list)
    retained_bytes: int = 0

    def publish(self, job: Job, batch: ValidatedBatch) -> bool:
        """True when publicly acknowledged; file units wait for run manifest."""
        p = self.graph.plan
        if self.store is not None:
            from niftyverse.storage.publication import publish

            publish(self.store, batch)
            return True
        if p.mode == "memory":
            size = len(batch.capture.body) + sum(t.nbytes for _, t in batch.tables)
            if self.retained_bytes + size > p.memory_bytes:
                raise AcquisitionFailure("memory_budget_exceeded")
            self.memory.append(batch)
            self.retained_bytes += size
            return True
        assert self.spool is not None
        write_direct(
            batch,
            self.spool / job.id,
            encoding=p.encoding,
            retain_raw=p.retain_raw,
            allow_partial=p.allow_partial,
        )
        self.files.append(
            (job, sum(t.num_rows for _, t in batch.tables), batch.coverage == "partial")
        )
        return False

    def finish(self, result: ExecutionResult) -> bool:
        p = self.graph.plan
        if p.mode != "files":
            result.batches = tuple(self.memory)
            return False
        assert self.spool is not None and p.destination is not None
        if result.status in {"failed", "cancelled"} and not p.allow_partial:
            return False
        metadata = {
            "kind": "direct_extract_run",
            "status": result.status,
            "plan_hash": self.graph.plan_hash,
            "jobs": {
                key: "committed"
                if value == "spooled"
                else "partial"
                if value == "spooled_partial"
                else value
                for key, value in result.states.items()
            },
            "failures": result.reasons,
            "retry_limit": p.max_attempts,
            "resume_limit": result.resume_limit,
            "raw_replay_available": p.retain_raw,
        }
        publish_bundle(
            p.destination,
            (),
            metadata,
            encoding=p.encoding,
            raw=(
                (f"partitions/{path.relative_to(self.spool).as_posix()}", path)
                for path in sorted(self.spool.rglob("*"))
                if path.is_file()
            ),
        )
        return True


async def execute(
    graph: WorkGraph,
    providers: dict[str, Provider],
    *,
    store: Store | None = None,
    on_event: Callable[[Event], None] | None = None,
    cancel: asyncio.Event | None = None,
    resume: str | None = None,
) -> ExecutionResult:
    """Run explicitly selected providers with bounded admitted tasks and batches.

    A provider must respect the job's source-format/request/body limits and the
    shared transport family budgets. Offline-capable providers must read only
    locally retained inputs. Non-local providers are never called offline.
    """
    p = graph.plan
    p.__post_init__()
    if any(
        not Path(path).is_file() or digest_file(Path(path)) != sha
        for path, sha in graph.local_hashes
    ):
        raise ValidationError("local input changed since compilation; recompile explicitly")
    if (p.mode == "build") != (store is not None):
        raise ValidationError("persistent execution requires its open store; direct requires none")
    if store is not None and store.root != p.store:
        raise ValidationError("execution store differs from compiled store")
    if resume and store is None:
        raise ValidationError("direct extraction has no durable resume ID; bounded re-extract")
    run = None
    reusable: set[str] = set()
    if store is not None:
        from niftyverse.storage.builds import committed_cache, start_run

        cache = committed_cache(store)
        for job in graph.jobs:
            if not should_recheck(p, graph.jobs, job) and any(c.satisfies(job) for c in cache):
                reusable.add(job.id)
            elif resume and store.connection.execute(
                "SELECT count(*) FROM source_checks WHERE check_id=?",
                [identity((resume, job.id))],
            ).fetchone() == (1,):
                reusable.add(job.id)
        estimate = sum(
            j.capability.requests_per_job * p.max_attempts
            for j in graph.jobs
            if j.capability and not j.blocked and j.id not in reusable
        )
        if estimate > p.max_requests:
            raise ValidationError("actual store request budget exceeded; recompile")
        run = start_run(store, graph, resume)
    elif (
        sum(
            j.capability.requests_per_job * p.max_attempts
            for j in graph.jobs
            if j.capability and not j.blocked
        )
        > p.max_requests
    ):
        raise ValidationError("direct re-extraction request budget exceeded")
    result = ExecutionResult("running", {}, {}, {}, run, retry_limit=p.max_attempts)
    if store is not None:
        result.resume_limit = "persistent run ID; compatible config/source/code/inputs required"
    jobs = {j.id: j for j in graph.jobs}
    stopped: set[str] = set()
    active: dict[asyncio.Task[Acquired], Job] = {}
    # Completed tasks retain at most this many bounded batches. Metadata for the
    # bounded compiled DAG is not a queue of live acquisition tasks.
    limit = min(p.workers, p.queue_limit, max(1, p.memory_bytes // p.batch_bytes))
    stop = cancel if cancel is not None else asyncio.Event()

    def emit(
        job: Job,
        state: str,
        reason: str | None = None,
        batch: ValidatedBatch | None = None,
        rows: int = 0,
    ) -> None:
        result.states[job.id] = state
        if reason:
            result.reasons[job.id] = reason
        if state == "committed":
            result.committed_partitions += 1
            result.committed_rows += rows
        if store is not None and run is not None:
            from niftyverse.storage.builds import record_work

            record_work(
                store,
                run,
                job.id,
                state,
                reason=reason,
                check=batch.check_id if batch else None,
                raw=batch.capture.sha256
                if batch
                and (
                    store.location.paths["raw"] / batch.capture.sha256[:2] / batch.capture.sha256
                ).is_file()
                else None,
                attempts=result.attempts.get(job.id, 0),
            )
        if on_event:
            on_event(
                Event(
                    job.id,
                    state,
                    result.committed_partitions,
                    result.committed_rows,
                    reason,
                    result.attempts.get(job.id, 0),
                )
            )

    async def acquire(job: Job) -> Acquired:
        assert job.capability is not None
        provider = providers.get(job.capability.source_id)
        if provider is None:
            raise AcquisitionFailure("provider_not_configured")
        if p.offline and not provider.offline_capable:
            raise AcquisitionFailure("offline_missing_input", deferred=True)
        for attempt in range(1, p.max_attempts + 1):
            result.attempts[job.id] = attempt
            if stop.is_set():
                raise asyncio.CancelledError
            emit(job, "fetching")
            if stop.is_set():
                raise asyncio.CancelledError
            try:
                return await provider.acquire(job, attempt=attempt, offline=p.offline)
            except ValueError as error:
                raise ValidationError("provider_validation_failed") from error
            except AcquisitionFailure as error:
                if (
                    not error.retryable
                    or error.source_wide
                    or error.deferred
                    or attempt == p.max_attempts
                ):
                    raise
                emit(job, "retry_wait", error.code)
                await asyncio.sleep(0)
        raise AssertionError("bounded attempts exhausted")

    with tempfile.TemporaryDirectory(prefix="niftyverse-extract-") as folder:
        sink = _Sink(graph, store, Path(folder) if p.mode == "files" else None)
        try:
            while (
                len(result.states) < len(jobs)
                or active
                or any(
                    s in {"ready", "fetching", "retry_wait", "staged", "validating"}
                    for s in result.states.values()
                )
            ):
                for job in graph.jobs:
                    if job.id in result.states or len(active) >= limit:
                        continue
                    slots = (p.memory_bytes - sink.retained_bytes) // p.batch_bytes
                    if len(active) >= slots:
                        if not active:
                            emit(job, "failed", "memory_budget_exceeded")
                        continue
                    if stop.is_set():
                        emit(job, "cancelled", "cancel_requested")
                        continue
                    if job.blocked:
                        emit(job, "blocked", ";".join(job.blocked))
                        continue
                    if job.id in reusable:
                        result.reused_partitions += 1
                        emit(job, "skipped_cached")
                        continue
                    if job.capability and job.capability.source_id in stopped:
                        emit(job, "blocked", "source_capability_stopped")
                        continue
                    deps = [result.states.get(d) for d in job.dependencies]
                    if any(
                        d
                        in {
                            "failed",
                            "blocked",
                            "quarantined",
                            "deferred",
                            "cancelled",
                            "partial",
                            "spooled_partial",
                        }
                        for d in deps
                    ):
                        emit(job, "blocked", "dependency_failed")
                        continue
                    if any(d not in {"committed", "skipped_cached", "spooled"} for d in deps):
                        continue
                    emit(job, "ready")
                    task = asyncio.create_task(acquire(job))
                    active[task] = job
                    result.peak_active = max(result.peak_active, len(active))
                    result.peak_pending = max(result.peak_pending, len(active))
                if stop.is_set():
                    for task in active:
                        task.cancel()
                if not active:
                    break
                done, _ = await asyncio.wait(
                    active, return_when=asyncio.FIRST_COMPLETED, timeout=0.05
                )
                for task in done:
                    job = active.pop(task)
                    batch = None
                    try:
                        acquired = task.result()
                        batch = acquired.batch
                        if run:
                            batch = replace(batch, check_id=identity((run, job.id)))
                            acquired = replace(acquired, batch=batch)
                        emit(job, "staged", batch=batch)
                        if stop.is_set():
                            raise asyncio.CancelledError
                        emit(job, "validating", batch=batch)
                        partial = p.allow_partial and store is None and batch.coverage == "partial"
                        _validate(acquired, job, p.batch_bytes, allow_partial=partial)
                        if stop.is_set():
                            raise asyncio.CancelledError
                        if sink.publish(job, batch):
                            if partial:
                                emit(job, "partial", "completeness_unverified", batch)
                            else:
                                emit(
                                    job,
                                    "committed",
                                    batch=batch,
                                    rows=sum(t.num_rows for _, t in batch.tables),
                                )
                        else:
                            emit(
                                job,
                                "spooled_partial" if partial else "spooled",
                                "completeness_unverified" if partial else None,
                                batch=batch,
                            )
                        if not partial:
                            result.reasons.pop(job.id, None)
                    except asyncio.CancelledError:
                        emit(job, "cancelled", "cancel_requested", batch)
                    except AcquisitionFailure as error:
                        if error.source_wide and job.capability:
                            stopped.add(job.capability.source_id)
                        emit(job, "deferred" if error.deferred else "failed", error.code, batch)
                    except ValidationError:
                        if batch is not None and store is not None:
                            from niftyverse.storage.builds import quarantine_raw

                            quarantine_raw(store, batch.capture.body, batch.capture.sha256)
                        emit(job, "quarantined", "validation_failed", batch)
            required_failure = any(
                job.required
                and result.states.get(job.id)
                not in {
                    "committed",
                    "skipped_cached",
                    "spooled",
                }
                for job in graph.jobs
            )
            any_failure = any(
                s not in {"committed", "skipped_cached", "spooled"} for s in result.states.values()
            )
            result.status = (
                "cancelled"
                if stop.is_set()
                else "failed"
                if required_failure
                else "partial"
                if any_failure
                else "complete"
            )
            if p.allow_partial and result.status in {"failed", "cancelled"}:
                result.status = "partial"
            result.warnings = tuple(
                f"{j.id}:{result.reasons[j.id]}"
                for j in graph.jobs
                if not j.required and j.id in result.reasons
            )
            if sink.finish(result):
                for job, rows, partial in sink.files:
                    emit(
                        job,
                        "partial" if partial else "committed",
                        "completeness_unverified" if partial else None,
                        rows=0 if partial else rows,
                    )
            elif p.mode == "files":
                for job, _, _ in sink.files:
                    emit(job, "cancelled", "run_not_published")
            return result
        finally:
            for task in active:
                task.cancel()
            await asyncio.gather(*active, return_exceptions=True)
            if store is not None and run:
                store.connection.execute(
                    "UPDATE build_runs SET status=? WHERE run_id=?",
                    [
                        result.status if result.status != "running" else "interrupted",
                        run,
                    ],
                )
