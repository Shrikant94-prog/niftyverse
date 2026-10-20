"""Immutable local identities and explicit selection policies; no acquisition."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from niftyverse.core import ValidationError
from niftyverse.temporal import Evidence, day, decimal, text, utc


@dataclass(frozen=True)
class Issuer:
    issuer_id: str
    name: str

    def __post_init__(self) -> None:
        text(self.issuer_id, self.name)


@dataclass(frozen=True)
class Instrument:
    instrument_id: str
    issuer_id: str | None
    asset_type: Literal["equity", "etf", "derivative"]
    name: str

    def __post_init__(self) -> None:
        text(self.instrument_id, self.name)
        if self.issuer_id is not None:
            text(self.issuer_id)
        if self.asset_type not in {"equity", "etf", "derivative"}:
            raise ValidationError("unsupported instrument asset type")


@dataclass(frozen=True)
class Listing:
    listing_id: str
    instrument_id: str
    exchange: str
    series: str
    role: Literal["ordinary", "block", "rights", "partly_paid", "other"]
    status: Literal["listed", "delisted", "suspended", "unknown"]
    evidence: Evidence

    def __post_init__(self) -> None:
        text(self.listing_id, self.instrument_id, self.exchange, self.series)
        if self.role not in {
            "ordinary",
            "block",
            "rights",
            "partly_paid",
            "other",
        } or self.status not in {"listed", "delisted", "suspended", "unknown"}:
            raise ValidationError("invalid listing role/status")


@dataclass(frozen=True)
class Alias:
    identifier: str
    namespace: str
    listing_id: str
    evidence: Evidence

    def __post_init__(self) -> None:
        text(self.identifier, self.namespace, self.listing_id)


@dataclass(frozen=True)
class Match:
    instrument: Instrument
    listing: Listing
    alias: Alias | None
    date_status: Literal["dated", "unknown"]
    rank: int


@dataclass(frozen=True)
class SearchResult:
    matches: tuple[Match, ...]
    limitations: tuple[str, ...]


@dataclass(frozen=True)
class Resolution:
    status: Literal["resolved", "ambiguous", "identity_unresolved"]
    matches: tuple[Match, ...]
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class Catalogue:
    version_id: str
    collected_at: datetime
    coverage_through: date
    coverage: Literal["historical", "current_only"]
    issuers: tuple[Issuer, ...]
    instruments: tuple[Instrument, ...]
    listings: tuple[Listing, ...]
    aliases: tuple[Alias, ...]

    def __post_init__(self) -> None:
        text(self.version_id)
        utc(self.collected_at)
        day(self.coverage_through)
        if self.coverage not in {"historical", "current_only"}:
            raise ValidationError("invalid catalogue coverage")
        for rows in (self.issuers, self.instruments, self.listings, self.aliases):
            if not isinstance(rows, tuple):
                raise ValidationError("catalogue rows must be immutable tuples")
            for row in rows:
                row.__post_init__()
        issuer_ids = [r.issuer_id for r in self.issuers]
        instruments = [r.instrument_id for r in self.instruments]
        if len(set(issuer_ids)) != len(issuer_ids) or len(set(instruments)) != len(instruments):
            raise ValidationError("duplicate stable identity")
        if any(
            r.issuer_id is not None and r.issuer_id not in issuer_ids for r in self.instruments
        ):
            raise ValidationError("unknown issuer identity")
        if any(r.instrument_id not in instruments for r in self.listings):
            raise ValidationError("unknown instrument in listing")
        # One listing ID may have several dated states, but cannot change security.
        for listing_id in {r.listing_id for r in self.listings}:
            links = {
                (r.instrument_id, r.exchange, r.series, r.role)
                for r in self.listings
                if r.listing_id == listing_id
            }
            if len(links) != 1:
                raise ValidationError("listing identity changes security/series")
        if any(a.listing_id not in {r.listing_id for r in self.listings} for a in self.aliases):
            raise ValidationError("alias references unknown listing")

    def search(
        self,
        query: str,
        *,
        on: date,
        known_at: datetime,
        asset_type: str | None = None,
        namespace: str | None = None,
    ) -> SearchResult:
        text(query)
        day(on)
        utc(known_at)
        needle = query.casefold()
        matches = []
        instruments = {r.instrument_id: r for r in self.instruments}
        for listing in self.listings:
            evidence = listing.evidence
            if not evidence.possible(on, known_at):
                continue
            instrument = instruments[listing.instrument_id]
            if asset_type is not None and instrument.asset_type != asset_type:
                continue
            aliases = [
                a
                for a in self.aliases
                if a.listing_id == listing.listing_id
                and (namespace is None or a.namespace == namespace)
                and a.evidence.possible(on, known_at)
                and needle in a.identifier.casefold()
            ]
            for alias in aliases:
                matches.append(
                    Match(
                        instrument,
                        listing,
                        alias,
                        "unknown"
                        if evidence.valid_from is None or alias.evidence.valid_from is None
                        else "dated",
                        0 if alias.identifier.casefold() == needle else 2,
                    )
                )
            if namespace is None and needle in instrument.name.casefold():
                matches.append(
                    Match(
                        instrument,
                        listing,
                        None,
                        "unknown" if evidence.valid_from is None else "dated",
                        1 if instrument.name.casefold() == needle else 3,
                    )
                )
        limitations = []
        if self.coverage == "current_only":
            limitations.append("current_only")
        if on > self.coverage_through:
            limitations.append("stale")
        return SearchResult(
            tuple(
                sorted(
                    matches,
                    key=lambda m: (
                        m.rank,
                        m.instrument.instrument_id,
                        m.listing.listing_id,
                        m.alias.identifier if m.alias else "",
                    ),
                )
            ),
            tuple(limitations),
        )

    def resolve(self, identifier: str, namespace: str, on: date, known_at: datetime) -> Resolution:
        result = self.search(identifier, on=on, known_at=known_at, namespace=namespace)
        matches = tuple(
            m
            for m in result.matches
            if m.alias is not None and m.alias.identifier.casefold() == identifier.casefold()
        )
        return Resolution(
            "identity_unresolved"
            if not matches or any(m.date_status == "unknown" for m in matches)
            else "resolved"
            if len(matches) == 1
            else "ambiguous",
            matches,
            result.limitations,
        )


@dataclass(frozen=True)
class ListingSelectionPolicy:
    version_id: str
    allowed_series: tuple[str, ...] = ("EQ", "BE")
    listing_priority: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        text(self.version_id, *self.allowed_series, *self.listing_priority)
        if (
            not isinstance(self.allowed_series, tuple)
            or not isinstance(self.listing_priority, tuple)
            or not self.allowed_series
            or len(set(self.listing_priority)) != len(self.listing_priority)
        ):
            raise ValidationError("invalid immutable listing policy")


@dataclass(frozen=True)
class ListingSelection:
    status: Literal["selected", "collision", "policy_exclusion", "identity_unresolved"]
    listing: Listing | None
    policy_version: str
    candidates: tuple[Listing, ...]


def select_listing(
    catalogue: Catalogue,
    instrument_id: str,
    on: date,
    known_at: datetime,
    available_listing_ids: tuple[str, ...],
    policy: ListingSelectionPolicy,
) -> ListingSelection:
    day(on)
    utc(known_at)
    candidates = tuple(
        r
        for r in catalogue.listings
        if r.instrument_id == instrument_id
        and r.listing_id in available_listing_ids
        and r.evidence.admits(on, known_at)
    )
    if len({r.listing_id for r in candidates}) != len(candidates):
        return ListingSelection("collision", None, policy.version_id, candidates)
    eligible = tuple(
        r
        for r in candidates
        if r.role == "ordinary" and r.series in policy.allowed_series and r.status == "listed"
    )
    if len(eligible) > 1 and policy.listing_priority:
        prioritized = [
            r for key in policy.listing_priority for r in eligible if r.listing_id == key
        ]
        if prioritized and sum(r.listing_id == prioritized[0].listing_id for r in eligible) == 1:
            eligible = (prioritized[0],)
    status: Literal["selected", "collision", "policy_exclusion", "identity_unresolved"] = (
        "selected"
        if len(eligible) == 1
        else "collision"
        if eligible
        else "policy_exclusion"
        if candidates
        else "identity_unresolved"
    )
    return ListingSelection(
        status, eligible[0] if len(eligible) == 1 else None, policy.version_id, candidates
    )


@dataclass(frozen=True)
class Contract:
    contract_id: str
    underlying_id: str
    contract_type: Literal["future", "option"]
    right: Literal["CE", "PE"] | None
    continuity: Literal["evidenced", "unresolved"]
    prior_contract_id: str | None
    evidence_ref: str

    def __post_init__(self) -> None:
        text(self.contract_id, self.underlying_id, self.evidence_ref)
        if (
            self.contract_type not in {"future", "option"}
            or self.continuity not in {"evidenced", "unresolved"}
            or (self.contract_type == "future" and self.right is not None)
            or (self.contract_type == "option" and self.right not in {"CE", "PE"})
            or self.prior_contract_id == self.contract_id
        ):
            raise ValidationError("invalid derivative identity/continuity")


@dataclass(frozen=True)
class ContractTerms:
    contract_id: str
    version_id: str
    evidence: Evidence
    strike: Decimal | None
    expiry: date | None
    lot: int | None
    multiplier: Decimal | None
    settlement: str | None

    def __post_init__(self) -> None:
        text(self.contract_id, self.version_id)
        decimal(self.strike)
        decimal(self.multiplier)
        if self.expiry is not None:
            day(self.expiry)
        if (
            (self.strike is not None and self.strike < 0)
            or (self.multiplier is not None and self.multiplier <= 0)
            or (self.lot is not None and (type(self.lot) is not int or self.lot <= 0))
        ):
            raise ValidationError("invalid derivative terms")
        if self.settlement is not None:
            text(self.settlement)


def select_terms(
    contract: Contract, terms: tuple[ContractTerms, ...], on: date, known_at: datetime
) -> ContractTerms | None:
    day(on)
    utc(known_at)
    candidates = [
        r
        for r in terms
        if r.contract_id == contract.contract_id and r.evidence.admits(on, known_at)
    ]
    if len(candidates) > 1:
        raise ValidationError("ambiguous derivative terms")
    return candidates[0] if candidates else None
