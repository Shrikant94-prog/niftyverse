"""Explicit bounded local delisted import. Never looks up a current listing.

The manifest supplies stable IDs; import does not manufacture identity from a
symbol. Parsing/validation completes before any immutable catalogue is returned.
"""

import csv
import hashlib
import io
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Literal

import pyarrow as pa
import pyarrow.parquet as pq

from niftyverse.core import ValidationError
from niftyverse.identity import Alias, Catalogue, Instrument, Issuer, Listing
from niftyverse.temporal import Evidence, day, text, utc

COLUMNS = (
    "instrument_id",
    "listing_id",
    "name",
    "asset_type",
    "issuer_id",
    "issuer_name",
    "exchange",
    "series",
    "namespace",
    "isin",
    "listing_date",
    "delisting_date",
    "source_id",
    "evidence_ref",
    "known_at",
    "confidence",
    "status",
    "price_history",
    "identifier",
    "valid_from",
    "valid_to",
)
MAX_BYTES = 8 * 1024 * 1024
MAX_DECODED_BYTES = 32 * 1024 * 1024
MAX_ROWS = 10_000


@dataclass(frozen=True)
class DelistedRecord:
    alias: Alias
    instrument_id: str
    listing_date: date | None
    delisting_date: date | None
    status: Literal["delisted"]
    confidence: Literal["verified"]
    price_history: Literal["available", "source_unavailable", "unknown"]
    isin: str | None


@dataclass(frozen=True)
class HistoricalRequest:
    identity_status: str
    instrument_id: str | None
    listing_id: str | None
    listing_state: Literal["listed", "not_listed", "unknown"]
    price_status: str
    eligible: bool = False


@dataclass(frozen=True)
class DelistedManifest:
    catalogue: Catalogue
    records: tuple[DelistedRecord, ...]
    raw_sha256: str

    def request(
        self, identifier: str, namespace: str, on: date, known_at: datetime
    ) -> HistoricalRequest:
        resolution = self.catalogue.resolve(identifier, namespace, on, known_at)
        if resolution.status != "resolved":
            return HistoricalRequest(
                resolution.status, None, None, "unknown", "identity_unresolved"
            )
        match = resolution.matches[0]
        return _request(
            self, match.instrument.instrument_id, match.listing.listing_id, on, known_at
        )


def _request(
    manifest: DelistedManifest,
    instrument_id: str,
    listing_id: str,
    on: date,
    known_at: datetime,
    *,
    eligible: bool = False,
) -> HistoricalRequest:
    rows = [
        r
        for r in manifest.records
        if r.instrument_id == instrument_id
        and r.alias.listing_id == listing_id
        and r.alias.evidence.known_at <= known_at
    ]
    if not rows:
        return HistoricalRequest(
            "identity_unresolved", instrument_id, None, "unknown", "identity_unresolved", eligible
        )
    first = rows[0]  # Import validates common listing attributes across every alias.
    state: Literal["listed", "not_listed", "unknown"] = "unknown"
    if (first.listing_date is not None and on < first.listing_date) or (
        first.delisting_date is not None and on >= first.delisting_date
    ):
        state = "not_listed"
    elif first.listing_date is not None and first.delisting_date is not None:
        state = "listed"
    return HistoricalRequest(
        "resolved", instrument_id, listing_id, state, first.price_history, eligible
    )


def member_request(
    manifest: DelistedManifest,
    instrument_id: str,
    on: date,
    known_at: datetime,
    *,
    membership_established: bool,
) -> HistoricalRequest:
    """Preserve upstream established membership, independently of price/listing.

    This is an identity request boundary, not a historical membership engine.
    """
    day(on)
    utc(known_at)
    ids = {
        r.alias.listing_id
        for r in manifest.records
        if r.instrument_id == instrument_id and r.alias.evidence.known_at <= known_at
    }
    if len(ids) != 1:
        return HistoricalRequest(
            "ambiguous" if ids else "identity_unresolved",
            instrument_id,
            None,
            "unknown",
            "identity_unresolved",
            membership_established,
        )
    return _request(
        manifest, instrument_id, next(iter(ids)), on, known_at, eligible=membership_established
    )


def _date(value: str | None) -> date | None:
    if value is None:
        return None
    result = date.fromisoformat(value)
    if result.isoformat() != value:
        raise ValidationError("manifest dates require YYYY-MM-DD")
    return result


def import_delisted(path: Path, *, version_id: str, collected_at: datetime) -> DelistedManifest:
    text(version_id)
    utc(collected_at)
    with path.open("rb") as handle:
        body = handle.read(MAX_BYTES + 1)
    if not body or len(body) > MAX_BYTES:
        raise ValidationError("manifest byte limit/empty input")
    try:
        if path.suffix.lower() == ".csv":
            reader = csv.DictReader(io.StringIO(body.decode("utf-8-sig"), newline=""), strict=True)
            if (
                reader.fieldnames is None
                or len(reader.fieldnames) != len(set(reader.fieldnames))
                or set(reader.fieldnames) != set(COLUMNS)
            ):
                raise ValidationError("manifest columns mismatch")
            rows = list(reader)
        elif path.suffix.lower() == ".parquet":
            with pq.ParquetFile(pa.BufferReader(body)) as parquet:
                if (
                    sum(
                        parquet.metadata.row_group(i).total_byte_size
                        for i in range(parquet.num_row_groups)
                    )
                    > MAX_DECODED_BYTES
                ):
                    raise ValidationError("manifest decoded byte limit")
                if (
                    parquet.metadata.num_rows > MAX_ROWS
                    or parquet.metadata.serialized_size > MAX_BYTES
                ):
                    raise ValidationError("manifest row/metadata limit")
                if (
                    set(parquet.schema_arrow.names) != set(COLUMNS)
                    or len(parquet.schema_arrow) != len(COLUMNS)
                    or any(not pa.types.is_string(f.type) for f in parquet.schema_arrow)
                ):
                    raise ValidationError("manifest Parquet requires canonical string columns")
                rows = parquet.read(use_threads=False).to_pylist()
        else:
            raise ValidationError("manifest must be CSV or Parquet")
        if not 0 < len(rows) <= MAX_ROWS:
            raise ValidationError("manifest row limit/empty input")
        normalized = []
        for row in rows:
            if set(row) != set(COLUMNS) or any(
                v is not None and not isinstance(v, str) for v in row.values()
            ):
                raise ValidationError("malformed manifest row")
            normalized.append({k: v if v != "" else None for k, v in row.items()})
        return _validate(normalized, version_id, collected_at, hashlib.sha256(body).hexdigest())
    except (ValueError, TypeError, KeyError, UnicodeError, csv.Error, pa.ArrowException) as error:
        raise ValidationError(f"invalid delisted manifest: {error}") from error


def _validate(
    rows: list[dict[str, str | None]], version_id: str, collected_at: datetime, raw_sha256: str
) -> DelistedManifest:
    issuers: dict[str, Issuer] = {}
    instruments: dict[str, Instrument] = {}
    listings: dict[str, Listing] = {}
    records: list[DelistedRecord] = []
    aliases: list[Alias] = []
    listing_attributes: dict[str, tuple[object, ...]] = {}
    for row in rows:

        def required(key: str, row: dict[str, str | None] = row) -> str:
            value = row[key]
            if value is None:
                raise ValidationError(f"missing required manifest {key}")
            text(value)
            return value

        if required("confidence") != "verified" or required("status") != "delisted":
            raise ValidationError("only verified delisted identity evidence can be imported")
        asset_type = required("asset_type")
        if asset_type not in {"equity", "etf"}:
            raise ValidationError("invalid delisted asset type")
        price_history = required("price_history")
        if price_history not in {"available", "source_unavailable", "unknown"}:
            raise ValidationError("invalid price history availability")
        known_at = datetime.fromisoformat(required("known_at"))
        utc(known_at)
        if known_at > collected_at:
            raise ValidationError("manifest evidence follows collection")
        evidence = Evidence(
            _date(row["valid_from"]),
            _date(row["valid_to"]),
            known_at,
            required("source_id"),
            required("evidence_ref"),
        )
        listing_date, delisting_date = _date(row["listing_date"]), _date(row["delisting_date"])
        if (
            listing_date is not None
            and delisting_date is not None
            and listing_date >= delisting_date
        ):
            raise ValidationError("invalid listing/delisting interval")
        if (
            evidence.valid_from is not None
            and listing_date is not None
            and evidence.valid_from < listing_date
        ) or (
            evidence.valid_to is not None
            and delisting_date is not None
            and evidence.valid_to > delisting_date
        ):
            raise ValidationError("alias extends outside evidenced listing interval")
        issuer_id = row["issuer_id"]
        if issuer_id is not None:
            issuer = Issuer(issuer_id, required("issuer_name"))
            if issuer_id in issuers and issuers[issuer_id] != issuer:
                raise ValidationError("conflicting issuer identity")
            issuers[issuer_id] = issuer
        elif row["issuer_name"] is not None:
            raise ValidationError("issuer name requires supplied stable issuer ID")
        instrument = Instrument(required("instrument_id"), issuer_id, asset_type, required("name"))  # type: ignore[arg-type]
        if (
            instrument.instrument_id in instruments
            and instruments[instrument.instrument_id] != instrument
        ):
            raise ValidationError("conflicting instrument identity")
        instruments[instrument.instrument_id] = instrument
        listing = Listing(
            required("listing_id"),
            instrument.instrument_id,
            required("exchange"),
            required("series"),
            "ordinary",
            "listed",
            Evidence(listing_date, delisting_date, known_at, evidence.source_id, evidence.locator),
        )
        attrs = (
            instrument.instrument_id,
            listing.exchange,
            listing.series,
            listing_date,
            delisting_date,
            price_history,
            row["isin"],
        )
        if (
            listing.listing_id in listing_attributes
            and listing_attributes[listing.listing_id] != attrs
        ):
            raise ValidationError("conflicting listing attributes")
        listing_attributes[listing.listing_id] = attrs
        # Preserve the earliest known listing evidence, not the first input row.
        if (
            listing.listing_id not in listings
            or known_at < listings[listing.listing_id].evidence.known_at
        ):
            listings[listing.listing_id] = listing
        alias = Alias(required("identifier"), required("namespace"), listing.listing_id, evidence)
        records.append(
            DelistedRecord(
                alias,
                instrument.instrument_id,
                listing_date,
                delisting_date,
                "delisted",
                "verified",
                price_history,  # type: ignore[arg-type]
                row["isin"],
            )
        )
        aliases.append(alias)
        if row["isin"] is not None and not (
            alias.namespace == "isin" and alias.identifier.casefold() == row["isin"].casefold()
        ):
            aliases.append(Alias(row["isin"], "isin", listing.listing_id, evidence))
    for i, left in enumerate(aliases):
        for right in aliases[i + 1 :]:
            if (left.namespace.casefold(), left.identifier.casefold()) != (
                right.namespace.casefold(),
                right.identifier.casefold(),
            ):
                continue
            a, b = left.evidence, right.evidence
            overlap = (
                a.valid_to is None or b.valid_from is None or b.valid_from < a.valid_to
            ) and (b.valid_to is None or a.valid_from is None or a.valid_from < b.valid_to)
            if overlap:
                raise ValidationError("ambiguous/duplicate manifest aliases")
    catalogue = Catalogue(
        version_id,
        collected_at,
        collected_at.date(),
        "historical",
        tuple(issuers.values()),
        tuple(instruments.values()),
        tuple(listings.values()),
        tuple(aliases),
    )
    return DelistedManifest(catalogue, tuple(records), raw_sha256)
