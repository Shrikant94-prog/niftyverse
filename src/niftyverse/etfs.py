"""Explicit ETF metadata and observation-dated catalogue construction; no I/O."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from niftyverse.identity import Alias, Catalogue, Instrument, Listing
from niftyverse.market_prices import MarketDataFailure, SourcePrice
from niftyverse.temporal import Evidence, day, text, utc


@dataclass(frozen=True)
class MetadataValue:
    value: str | int | Decimal | date | None
    reason: str | None
    evidence: Evidence


@dataclass(frozen=True)
class EtfMetadata:
    symbol: str
    isin: str
    scheme_name: str | None
    underlying_asset: str | None
    listed_on: date
    market_lot: int | None
    face_value: Decimal | None
    classification: str | None
    underlying_key: str | None
    evidence: Evidence
    raw_sha256: str
    raw_fields: tuple[tuple[str, str], ...]

    def value(self, field: str, *, on: date, known_at: datetime) -> MetadataValue:
        """Unknown fields/intervals never inherit current attributes or defaults."""
        day(on)
        utc(known_at)
        fields = {
            "scheme_name",
            "underlying_asset",
            "listed_on",
            "market_lot",
            "face_value",
            "classification",
            "underlying_key",
            "isin",
            "symbol",
        }
        if field not in fields:
            return MetadataValue(None, "unsupported_field", self.evidence)
        if known_at < self.evidence.known_at:
            return MetadataValue(None, "not_known", self.evidence)
        if not self.evidence.admits(on, known_at):
            return MetadataValue(None, "outside_observed_interval", self.evidence)
        value = getattr(self, field)
        return MetadataValue(value, "source_null" if value is None else None, self.evidence)


@dataclass(frozen=True)
class EtfSnapshot:
    observed_at: datetime
    source_id: str
    raw_sha256: str
    rows: tuple[EtfMetadata, ...]


def build_etf_catalogue(
    snapshot: EtfSnapshot,
    listings: tuple[SourcePrice, ...],
    *,
    version_id: str,
    listing_known_at: datetime,
) -> Catalogue:
    """Join only supplied same-day ISIN/series evidence, never assume EQ.

    This creates current-only one-day identities. Historical lineage, changed
    ISIN continuity and delisting require an independently dated Catalogue.
    Unobserved catalogue members stay in snapshot metadata, without listings.
    """
    text(version_id)
    utc(listing_known_at)
    known_at = max(snapshot.observed_at, listing_known_at)
    on = snapshot.observed_at.date()
    metadata = {r.symbol: r for r in snapshot.rows}
    instruments: dict[str, Instrument] = {}
    dated: dict[str, Listing] = {}
    aliases: list[Alias] = []
    for price in listings:
        price.__post_init__()
        row = metadata.get(price.symbol)
        if row is None:
            continue  # Whole-market input may contain non-ETF securities.
        if price.session_date != on:
            raise MarketDataFailure("dated_listing_evidence_required")
        if price.isin != row.isin:
            raise MarketDataFailure("identity_conflict")
        instrument_id = f"nse:etf:{row.isin}"
        listing_id = f"{instrument_id}:{price.series}"
        evidence = Evidence(
            on,
            row.evidence.valid_to,
            known_at,
            price.source_id,
            f"{price.raw_sha256}:{price.locator}",
        )
        instruments[instrument_id] = Instrument(
            instrument_id, None, "etf", row.scheme_name or row.symbol
        )
        listing = Listing(
            listing_id,
            instrument_id,
            "NSE",
            price.series,
            "block"
            if price.series == "BL"
            else "ordinary"
            if price.series in {"EQ", "BE"}
            else "other",
            "listed",
            evidence,
        )
        if listing_id in dated:
            raise MarketDataFailure("duplicate_listing_evidence")
        dated[listing_id] = listing
        aliases.extend(
            (
                Alias(row.symbol, "symbol", listing_id, evidence),
                Alias(row.isin, "isin", listing_id, evidence),
            )
        )
    return Catalogue(
        version_id,
        known_at,
        on,
        "current_only",
        (),
        tuple(instruments.values()),
        tuple(dated.values()),
        tuple(aliases),
    )
