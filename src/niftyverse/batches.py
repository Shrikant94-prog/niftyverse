"""Shared immutable publication contract, independent of network, files and sinks.

Typed Arrow tables are bounded validated partitions, not acquisition engines.
No synthetic batch establishes real provider completeness or economic mapping.
"""

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from typing import Any, Literal

import pyarrow as pa

from niftyverse.core import ValidationError
from niftyverse.delivery import SourceDelivery, delivery_fraction
from niftyverse.indices import validate_index_record, validate_index_scope
from niftyverse.market_prices import MarketDataFailure, number, validate_price_fields
from niftyverse.market_state import MarketStateObservation
from niftyverse.storage.schemas import ANALYTICAL_KEY, KEYS, SCHEMAS

MAX_ROWS = 100_000
MAX_BYTES = 64 * 1024 * 1024


def identity(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()


def utc(value: datetime) -> None:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() != UTC.utcoffset(value)
    ):
        raise ValidationError("timestamps require aware UTC")


def _fact_key(row: dict[str, Any], columns: tuple[str, ...]) -> str:
    values = []
    for name in columns:
        value = row[name]
        if name == "dimensions":
            # Dimension order is source presentation, not analytical identity.
            value = sorted(value, key=identity)
        values.append(value)
    return identity(values)


@dataclass(frozen=True)
class Partition:
    dataset: str
    start: date
    end: date
    universe: tuple[str, ...]
    fields: tuple[str, ...]
    basis: str
    source_generation: str
    identity_policy: str
    quality_policy: str
    completeness_evidence: str
    scope: Literal["selected", "whole_market"] = "selected"
    overlap_policy: str = "same-key-revisions"
    validation_scope: str = "full-source-partition"

    def __post_init__(self) -> None:
        if (
            self.dataset not in SCHEMAS
            or type(self.start) is not date
            or type(self.end) is not date
            or self.start >= self.end
            or not isinstance(self.universe, tuple)
            or not isinstance(self.fields, tuple)
            or not self.fields
            or any(not isinstance(x, str) or not x for x in (*self.universe, *self.fields))
            or len(set(self.universe)) != len(self.universe)
            or len(set(self.fields)) != len(self.fields)
            or self.scope not in {"selected", "whole_market"}
            or (self.scope == "selected" and not self.universe)
            or not all(
                (
                    self.basis,
                    self.source_generation,
                    self.identity_policy,
                    self.quality_policy,
                    self.overlap_policy,
                    self.validation_scope,
                )
            )
        ):
            raise ValidationError("invalid partition scope/fields/basis/identity")
        if self.dataset in {"index_daily", "index_tri", "index_valuations"}:
            validate_index_scope(
                self.dataset, fields=self.fields, basis=self.basis, scope=self.scope
            )

    @property
    def identity(self) -> str:
        values = asdict(self)
        values["universe"] = sorted(self.universe)
        values["fields"] = sorted(self.fields)
        # A different check's completeness explanation is evidence, not scope identity.
        del values["completeness_evidence"]
        return identity(values)


@dataclass(frozen=True)
class Capture:
    body: bytes
    kind: Literal["direct_raw", "sdk_result"]
    source_id: str
    origin: str
    sdk_version: str | None = None
    request_fingerprint: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.body, bytes) or not self.body or len(self.body) > MAX_BYTES:
            raise ValidationError("capture must contain bounded immutable bytes")
        if self.kind not in {"direct_raw", "sdk_result"} or not self.source_id or not self.origin:
            raise ValidationError("capture origin/kind/source required")
        if self.kind == "sdk_result" and not self.sdk_version:
            raise ValidationError("SDK result requires SDK version")

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.body).hexdigest()

    @property
    def identity(self) -> str:
        return identity((self.sha256, self.kind, self.source_id, self.origin, self.sdk_version))


@dataclass(frozen=True)
class ValidatedBatch:
    partition: Partition
    capture: Capture
    check_id: str
    checked_at: datetime
    known_at: datetime
    source_revision: str | None
    state: Literal["active", "withdrawn"]
    reason: str | None
    tables: tuple[tuple[str, pa.Table], ...]
    coverage: Literal["complete", "no_observations", "partial", "quarantined"]
    schema_version: str
    normalizer_version: str

    def __post_init__(self) -> None:
        self.partition.__post_init__()
        self.capture.__post_init__()
        utc(self.checked_at)
        utc(self.known_at)
        if self.known_at > self.checked_at:
            raise ValidationError("known-at cannot follow source check")
        if not self.check_id or not self.schema_version or not self.normalizer_version:
            raise ValidationError("check/schema/normalizer identity required")
        if self.state not in {"active", "withdrawn"}:
            raise ValidationError("invalid assertion state")
        if self.state == "withdrawn" and (not self.reason or self.tables):
            raise ValidationError("evidenced withdrawal needs a reason and no facts")
        if self.coverage not in {"complete", "no_observations", "partial", "quarantined"}:
            raise ValidationError("invalid coverage")
        if (
            self.coverage in {"complete", "no_observations"}
            and not self.partition.completeness_evidence
        ):
            raise ValidationError("complete coverage requires explicit source evidence")
        if not isinstance(self.tables, tuple) or len(dict(self.tables)) != len(self.tables):
            raise ValidationError("tables must be unique immutable entries")
        if (
            sum(t.num_rows for _, t in self.tables) > MAX_ROWS
            or sum(t.nbytes for _, t in self.tables) > MAX_BYTES
        ):
            raise ValidationError(
                "partition batch limit exceeded; use smaller declared partitions"
            )
        rows_by_name = {}
        for name, table in self.tables:
            allowed = {self.partition.dataset}
            if self.partition.dataset == "financial_facts":
                allowed |= {"filing_documents", "filing_source_assertions"}
            elif self.partition.dataset == "filing_source_assertions":
                allowed.add("filing_documents")
            elif self.partition.dataset in {"equity_daily", "etf_daily"}:
                allowed.add("security_daily_details")
            if name not in allowed:
                raise ValidationError("table incompatible with partition dataset")
            if name not in SCHEMAS or not table.schema.equals(SCHEMAS[name], check_metadata=False):
                raise ValidationError("publication schema mismatch")
            if any(table[f.name].null_count for f in table.schema if not f.nullable):
                raise ValidationError("null in required field")
            rows = table.to_pylist()
            rows_by_name[name] = rows
            keys = [_fact_key(r, KEYS[name]) for r in rows]
            if len(set(keys)) != len(keys):
                raise ValidationError("duplicate business key in atomic partition")
            for row in rows:
                if name in {"index_daily", "index_tri", "index_valuations"}:
                    validate_index_record(
                        name,
                        row,
                        source_id=self.capture.source_id,
                        raw_sha256=self.capture.sha256,
                        universe=self.partition.universe,
                        scope=self.partition.scope,
                        basis=self.partition.basis,
                        fields=self.partition.fields,
                        complete=self.coverage == "complete",
                    )
                if name == "security_daily_details":
                    if row["raw_sha256"] != self.capture.sha256:
                        raise MarketDataFailure("details_capture_mismatch")
                    if row["quantity_unit"] not in {"shares", "fund_units"}:
                        raise MarketDataFailure("invalid_quantity_unit")
                    for field in ("settlement_price", "last_price", "previous_close"):
                        number(row[field])
                    number(row["trades"], integer=True)
                    delivery = SourceDelivery(
                        row["listing_id"],
                        row["series"],
                        row["session_date"],
                        row["comparable_quantity"],
                        row["delivered_quantity"],
                        row["published_delivery_percent"],
                        self.capture.source_id,
                        row["representation"],
                        row["raw_sha256"],
                        row["locator"],
                        (),
                        row["source_turnover"],
                        row["source_turnover_unit"],
                        row["quantity_definition"],
                    )
                    fraction = delivery_fraction(delivery)
                    if (row["delivery_fraction"], row["delivery_reason"]) != (
                        fraction.value,
                        fraction.reason,
                    ):
                        raise MarketDataFailure("invalid_delivery_derivation")
                if name in {"equity_daily", "etf_daily"}:
                    validate_price_fields(
                        open=row["open"],
                        high=row["high"],
                        low=row["low"],
                        close=row["close"],
                        quantity=row["quantity"],
                        turnover=row["turnover"],
                    )
                if name == "market_state_observations":
                    MarketStateObservation(**row)
                    if not self.partition.start <= row["observed_on"] < self.partition.end:
                        raise ValidationError("market state outside partition date scope")
                    if (
                        row["known_at"] > self.known_at
                        or row["source_id"] != self.capture.source_id
                    ):
                        raise ValidationError("market state availability/source mismatch")
                if (
                    "listing_id" in row
                    and self.partition.scope == "selected"
                    and row["listing_id"] not in self.partition.universe
                ):
                    raise ValidationError("row outside partition scope")
                if (
                    "session_date" in row
                    and not self.partition.start <= row["session_date"] < self.partition.end
                ):
                    raise ValidationError("row outside partition date scope")
                if name in {"equity_daily", "etf_daily"} and row["quantity_unit"] != (
                    "fund_units" if name == "etf_daily" else "shares"
                ):
                    raise ValidationError("incompatible quantity unit")
                if (
                    name in {"equity_daily", "etf_daily"}
                    and row["close"] is None
                    and not row["missing_reason"]
                ):
                    raise ValidationError("missing price needs a reason")
        price_rows = rows_by_name.get("equity_daily", []) + rows_by_name.get("etf_daily", [])
        prices = {(r["listing_id"], r["series"], r["session_date"]): r for r in price_rows}
        if prices:
            for detail in rows_by_name.get("security_daily_details", []):
                price = prices.get(
                    (detail["listing_id"], detail["series"], detail["session_date"])
                )
                if price is None or (price["quantity"], price["quantity_unit"]) != (
                    detail["comparable_quantity"],
                    detail["quantity_unit"],
                ):
                    raise MarketDataFailure("price_details_quantity_conflict")
        documents = {r["document_id"]: r for r in rows_by_name.get("filing_documents", [])}
        assertions = {
            r["assertion_id"]: r for r in rows_by_name.get("filing_source_assertions", [])
        }
        for doc in documents.values():
            if doc["raw_sha256"] != self.capture.sha256:
                raise ValidationError("document capture mismatch")
        for row in assertions.values():
            if row["document_id"] not in documents or not row["concept"].startswith("{"):
                raise ValidationError("source assertion document/qualified concept missing")
            if row["nil"] != (row["value"] is None):
                raise ValidationError("source nil/value mismatch")
            for dim in row["dimensions"]:
                if not dim["axis"] or (dim["member"] is None) == (dim["typed_xml"] is None):
                    raise ValidationError("invalid dimension identity")
        financial = rows_by_name.get("financial_facts", [])
        keys = [_fact_key(r, ANALYTICAL_KEY) for r in financial]
        if len(keys) != len(set(keys)):
            raise ValidationError("duplicate analytical key; unresolved conflict")
        for row in financial:
            if row["assertion_id"] not in assertions or row["period_kind"] not in {
                "instant",
                "duration",
            }:
                raise ValidationError("financial assertion/period missing")
            if row["additivity"] not in {"additive_duration", "nonadditive", "instant"}:
                raise ValidationError("financial additivity dictionary missing")
            if row["derivation"] != "reported" and (
                row["period_kind"] != "duration" or row["additivity"] != "additive_duration"
            ):
                raise ValidationError("nonadditive/instant subtraction forbidden")
        count = sum(t.num_rows for _, t in self.tables)
        if self.state == "active" and self.coverage == "complete" and not count:
            raise ValidationError("empty data is not complete; use evidenced no_observations")
        if self.coverage == "no_observations" and count:
            raise ValidationError("no_observations cannot contain facts")

    @property
    def content_identity(self) -> str:
        return identity(
            (
                self.capture.identity,
                self.schema_version,
                self.normalizer_version,
                [(n, identity(t.to_pylist())) for n, t in self.tables],
                self.state,
                self.reason,
            )
        )

    @property
    def request_identity(self) -> str:
        return identity(
            (
                self.partition.identity,
                self.content_identity,
                self.source_revision,
                self.known_at,
                self.checked_at,
                self.coverage,
                self.partition.completeness_evidence,
                self.capture.request_fingerprint,
            )
        )
