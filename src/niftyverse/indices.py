"""Pure explicit index identities, exact observations and evidenced session coverage."""

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from niftyverse.calendars import Calendar
from niftyverse.core import ValidationError
from niftyverse.temporal import Evidence, day, decimal, text, utc

VariantKind = Literal["price", "gross_tri", "net_tri", "volatility"]


@dataclass(frozen=True)
class IndexVariant:
    variant_id: str
    index_id: str
    kind: VariantKind

    def __post_init__(self) -> None:
        text(self.variant_id, self.index_id)
        if self.kind not in {"price", "gross_tri", "net_tri", "volatility"}:
            raise ValidationError("unsupported index variant")


@dataclass(frozen=True)
class IndexAlias:
    source_id: str
    alias: str
    variant_id: str
    evidence: Evidence

    def __post_init__(self) -> None:
        text(self.source_id, self.alias, self.variant_id)
        self.evidence.__post_init__()


@dataclass(frozen=True)
class IndexCatalogue:
    version_id: str
    variants: tuple[IndexVariant, ...]
    aliases: tuple[IndexAlias, ...]

    def __post_init__(self) -> None:
        text(self.version_id)
        if not isinstance(self.variants, tuple) or not isinstance(self.aliases, tuple):
            raise ValidationError("index catalogue requires immutable tuples")
        for variant in self.variants:
            variant.__post_init__()
        for alias in self.aliases:
            alias.__post_init__()
        ids = {v.variant_id for v in self.variants}
        if len(ids) != len(self.variants) or any(a.variant_id not in ids for a in self.aliases):
            raise ValidationError("duplicate or unknown index variant identity")
        if len({(v.index_id, v.kind) for v in self.variants}) != len(self.variants):
            raise ValidationError("duplicate index/kind identity")

    def resolve(
        self, source_id: str, alias: str, kind: VariantKind, on: date, known_at: datetime
    ) -> IndexVariant:
        text(source_id, alias)
        day(on)
        utc(known_at)
        variants = {v.variant_id: v for v in self.variants}
        matches = {
            a.variant_id
            for a in self.aliases
            if a.source_id == source_id
            and a.alias.casefold() == alias.casefold()
            and a.evidence.admits(on, known_at)
            and variants[a.variant_id].kind == kind
        }
        if len(matches) != 1:
            raise ValidationError("ambiguous index alias" if matches else "unresolved index alias")
        return variants[next(iter(matches))]


@dataclass(frozen=True)
class SourceLineage:
    source_id: str
    raw_sha256: str
    locator: str
    representation: str
    raw_fields: tuple[tuple[str, str | None], ...]

    def __post_init__(self) -> None:
        text(self.source_id, self.locator, self.representation)
        if not re.fullmatch(r"[0-9a-f]{64}", self.raw_sha256):
            raise ValidationError("invalid index source hash")
        if not isinstance(self.raw_fields, tuple) or any(
            not isinstance(pair, tuple)
            or len(pair) != 2
            or not isinstance(pair[0], str)
            or (pair[1] is not None and not isinstance(pair[1], str))
            for pair in self.raw_fields
        ):
            raise ValidationError("immutable raw index fields required")


@dataclass(frozen=True)
class IndexPrice:
    variant: IndexVariant
    session_date: date
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    close: Decimal | None
    lineage: SourceLineage

    @property
    def unit(self) -> str:
        return (
            "volatility_percent_annualised"
            if self.variant.kind == "volatility"
            else "index_points"
        )

    def __post_init__(self) -> None:
        self.variant.__post_init__()
        self.lineage.__post_init__()
        day(self.session_date)
        if self.variant.kind not in {"price", "volatility"}:
            raise ValidationError("index OHLC requires price variant or volatility")
        for value in (self.open, self.high, self.low, self.close):
            decimal(value)
            if value is not None and value < 0:
                raise ValidationError("negative index level")
        if (
            self.high is not None
            and any(v is not None and v > self.high for v in (self.open, self.low, self.close))
        ) or (
            self.low is not None
            and any(v is not None and v < self.low for v in (self.open, self.high, self.close))
        ):
            raise ValidationError("invalid index OHLC")


@dataclass(frozen=True)
class IndexTRI:
    variant: IndexVariant
    session_date: date
    value: Decimal | None
    lineage: SourceLineage

    def __post_init__(self) -> None:
        self.variant.__post_init__()
        self.lineage.__post_init__()
        day(self.session_date)
        if self.variant.kind not in {"gross_tri", "net_tri"}:
            raise ValidationError("TRI requires gross/net variant")
        decimal(self.value)
        if self.value is not None and self.value < 0:
            raise ValidationError("negative TRI level")


@dataclass(frozen=True)
class IndexValuation:
    variant: IndexVariant
    session_date: date
    pe: Decimal | None
    pb: Decimal | None
    dividend_yield: Decimal | None
    lineage: SourceLineage
    ratio_unit: Literal["ratio"] = "ratio"
    yield_unit: Literal["percent"] = "percent"

    def __post_init__(self) -> None:
        self.variant.__post_init__()
        self.lineage.__post_init__()
        day(self.session_date)
        if self.variant.kind != "price":
            raise ValidationError("valuation requires underlying price variant")
        for value in (self.pe, self.pb, self.dividend_yield):
            decimal(value)
        if self.dividend_yield is not None and self.dividend_yield < 0:
            raise ValidationError("negative dividend yield")
        if self.ratio_unit != "ratio" or self.yield_unit != "percent":
            raise ValidationError("incompatible valuation units")

    @property
    def missing_fields(self) -> tuple[str, ...]:
        return tuple(k for k in ("pe", "pb", "dividend_yield") if getattr(self, k) is None)

    @property
    def assumptions(self) -> tuple[str, ...]:
        """Nonpositive ratios cannot silently enter positive-ratio assumptions."""
        return tuple(
            f"{k}_unavailable" if getattr(self, k) is None else f"{k}_nonpositive"
            for k in ("pe", "pb")
            if getattr(self, k) is None or getattr(self, k) <= 0
        )


type IndexObservation = IndexPrice | IndexTRI | IndexValuation


@dataclass(frozen=True)
class HistoricalIndexCapability:
    source_id: str
    variant: IndexVariant
    start: date
    end: date
    observed_at: datetime
    raw_sha256: str
    status: Literal["experimental", "blocked"]
    verified_sessions: tuple[date, ...]
    reason: str | None


@dataclass(frozen=True)
class IndexHistory[T: IndexObservation]:
    variant: IndexVariant
    rows: tuple[T, ...]
    gaps: tuple[tuple[date, str], ...]
    coverage: Literal["complete", "partial", "no_observations"]
    calendar_version: str


def index_history[T: IndexObservation](
    rows: tuple[T, ...],
    *,
    variant: IndexVariant,
    start: date,
    end: date,
    calendar: Calendar,
    known_at: datetime,
    source_complete: bool,
) -> IndexHistory[T]:
    """Project no dates; validate actual rows and compare to an evidenced grid.

    Empty source data never establishes absence on a trading date. The caller's
    complete-source assertion is necessary, but missing rows still prevent completeness.
    """
    variant.__post_init__()
    utc(known_at)
    if calendar.known_at > known_at:
        raise ValidationError("index calendar not known at selection time")
    sessions = calendar.sessions_between(start, end, require_complete=False)
    if not isinstance(rows, tuple):
        raise ValidationError("index history requires immutable rows")
    if len({type(r) for r in rows}) > 1:
        raise ValidationError("mixed index dataset history")
    seen = set()
    for row in rows:
        row.__post_init__()
        if row.variant != variant:
            raise ValidationError("incompatible requested index variant")
        if not start <= row.session_date < end:
            raise ValidationError("index row outside requested dates")
        if row.session_date in seen:
            raise ValidationError("duplicate index session")
        if calendar.session(row.session_date).eligible is False:
            raise ValidationError("index observation on closed session")
        seen.add(row.session_date)
    gaps = []
    by_date = {r.session_date: r for r in rows}
    for session in sessions:
        if session.eligible is None:
            gaps.append((session.session_date, "unknown_session"))
        elif session.eligible:
            observation = by_date.get(session.session_date)
            if not source_complete:
                gaps.append((session.session_date, "source_unverified"))
            elif observation is None:
                gaps.append((session.session_date, "missing_observation"))
            elif isinstance(observation, IndexValuation):
                gaps.extend(
                    (session.session_date, f"source_null:{field}")
                    for field in observation.missing_fields
                )
            elif isinstance(observation, IndexTRI):
                if observation.value is None:
                    gaps.append((session.session_date, "source_null"))
            elif any(
                v is None
                for v in (observation.open, observation.high, observation.low, observation.close)
            ):
                gaps.append((session.session_date, "source_null"))
    coverage: Literal["complete", "partial", "no_observations"] = (
        "partial" if gaps or not source_complete else "complete" if rows else "no_observations"
    )
    return IndexHistory(
        variant,
        tuple(sorted(rows, key=lambda r: r.session_date)),
        tuple(gaps),
        coverage,
        calendar.version_id,
    )


@dataclass(frozen=True)
class IndexJoin:
    session_date: date
    price: IndexPrice | None
    valuation: IndexValuation | None
    gross_tri: IndexTRI | None
    net_tri: IndexTRI | None


def join_index_datasets(
    *,
    variant: IndexVariant,
    prices: tuple[IndexPrice, ...],
    valuations: tuple[IndexValuation, ...],
    tri: tuple[IndexTRI, ...],
) -> tuple[IndexJoin, ...]:
    """Full outer date join retaining typed input records; never fills values."""
    variant.__post_init__()
    if variant.kind != "price":
        raise ValidationError("join requires price index variant")
    groups: dict[str, dict[date, IndexObservation]] = {
        "price": {},
        "valuation": {},
        "gross_tri": {},
        "net_tri": {},
    }
    for rows, expected in ((prices, IndexPrice), (valuations, IndexValuation), (tri, IndexTRI)):
        if not isinstance(rows, tuple):
            raise ValidationError("immutable index join inputs required")
        for row in rows:
            if not isinstance(row, expected):
                raise ValidationError("incompatible index join dataset")
            row.__post_init__()
            if row.variant.index_id != variant.index_id or (
                not isinstance(row, IndexTRI) and row.variant != variant
            ):
                raise ValidationError("incompatible index variant in join")
            group = "valuation" if isinstance(row, IndexValuation) else row.variant.kind
            if row.session_date in groups[group]:
                raise ValidationError("duplicate index join date/variant")
            groups[group][row.session_date] = row
    dates = sorted({on for rows in groups.values() for on in rows})
    p = {r.session_date: r for r in prices}
    v = {r.session_date: r for r in valuations}
    gross = {r.session_date: r for r in tri if r.variant.kind == "gross_tri"}
    net = {r.session_date: r for r in tri if r.variant.kind == "net_tri"}
    return tuple(
        IndexJoin(
            on,
            p.get(on),
            v.get(on),
            gross.get(on),
            net.get(on),
        )
        for on in dates
    )


def validate_index_record(
    dataset: str,
    row: dict[str, Any],
    *,
    source_id: str,
    raw_sha256: str,
    universe: tuple[str, ...],
    scope: str,
    basis: str,
    fields: tuple[str, ...],
    complete: bool,
) -> None:
    """Shared DB/direct boundary for typed index records, identity, basis and nulls."""
    variant = IndexVariant(row["variant_id"], row["index_id"], row["variant_kind"])
    lineage = SourceLineage(source_id, row["raw_sha256"], row["locator"], "index-v1", ())
    if row["raw_sha256"] != raw_sha256:
        raise ValidationError("index capture mismatch")
    if scope != "selected" or variant.variant_id not in universe:
        raise ValidationError("index row outside explicit variant scope")
    expected_basis = "valuation_ratios_percent" if dataset == "index_valuations" else variant.kind
    if basis != expected_basis:
        raise ValidationError("index partition variant/basis mismatch")
    available: tuple[str, ...]
    nullable: tuple[str, ...]
    if dataset == "index_daily":
        IndexPrice(
            variant,
            row["session_date"],
            row["open"],
            row["high"],
            row["low"],
            row["close"],
            lineage,
        )
        available = ("open", "high", "low", "close")
        nullable = ("close",)
    elif dataset == "index_tri":
        IndexTRI(variant, row["session_date"], row["value"], lineage)
        available = nullable = ("value",)
    elif dataset == "index_valuations":
        IndexValuation(
            variant,
            row["session_date"],
            row["pe"],
            row["pb"],
            row["dividend_yield"],
            lineage,
            row["ratio_unit"],
            row["yield_unit"],
        )
        available = nullable = ("pe", "pb", "dividend_yield")
    else:
        raise ValidationError("incompatible index dataset")
    expected_unit = (
        "volatility_percent_annualised" if variant.kind == "volatility" else "index_points"
    )
    if dataset != "index_valuations" and row["unit"] != expected_unit:
        raise ValidationError("incompatible index unit")
    if set(fields) - set(available):
        raise ValidationError("unsupported index requested field")
    # Validate reasons before completeness so malformed nulls have a stable diagnostic.
    for field in nullable:
        reason = row[field + "_reason"] if dataset == "index_valuations" else row["missing_reason"]
        if reason != ("source_null" if row[field] is None else None):
            raise ValidationError("index null/reason mismatch")
    if complete and any(row[f] is None for f in fields):
        raise ValidationError("null index requested field cannot be complete")
