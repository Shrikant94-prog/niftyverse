"""Pure explicit index identities, exact observations and evidenced session coverage."""

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

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
class IndexHistory:
    variant: IndexVariant
    rows: tuple[IndexPrice, ...]
    gaps: tuple[tuple[date, str], ...]
    coverage: Literal["complete", "partial", "no_observations"]
    calendar_version: str


def index_history(
    rows: tuple[IndexPrice, ...],
    *,
    variant: IndexVariant,
    start: date,
    end: date,
    calendar: Calendar,
    known_at: datetime,
    source_complete: bool,
) -> IndexHistory:
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
