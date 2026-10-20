"""Explicit local adapter from literal tokens to dated membership entities."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

from niftyverse.identity import Catalogue
from niftyverse.membership import Member, fingerprint
from niftyverse.temporal import Evidence, day, text, utc


@dataclass(frozen=True)
class TemporaryAlias:
    token: str
    component_id: str
    evidence: Evidence

    def __post_init__(self) -> None:
        text(self.token, self.component_id)
        self.evidence.__post_init__()


@dataclass(frozen=True)
class TokenResolution:
    token: str
    member: Member
    status: Literal["resolved", "ambiguous", "identity_unresolved"]
    evidence_locators: tuple[str, ...]


def resolve_tokens(
    tokens: tuple[str, ...],
    catalogue: Catalogue,
    on: date,
    known_at: datetime,
    *,
    temporary: tuple[TemporaryAlias, ...] = (),
) -> tuple[TokenResolution, ...]:
    day(on)
    utc(known_at)
    result = []
    for token in tokens:
        text(token)
        security = catalogue.resolve(token, "symbol", on, known_at)
        candidates = [
            t for t in temporary if t.token == token and t.evidence.possible(on, known_at)
        ]
        status: Literal["resolved", "ambiguous", "identity_unresolved"] = "identity_unresolved"
        member = Member("unresolved:" + fingerprint(["symbol", token]), "unresolved", None)
        locators = tuple(t.evidence.locator for t in candidates) + tuple(
            m.alias.evidence.locator for m in security.matches if m.alias is not None
        )
        if candidates and security.matches or len(candidates) > 1:
            status = "ambiguous"
        elif len(candidates) == 1 and candidates[0].evidence.admits(on, known_at):
            status = "resolved"
            member = Member(candidates[0].component_id, "temporary", None)
        elif not candidates and security.status == "resolved":
            instrument = security.matches[0].instrument
            member = Member(instrument.instrument_id, "security", instrument.instrument_id)
            status = "resolved"
        elif security.status == "ambiguous":
            status = "ambiguous"
        result.append(TokenResolution(token, member, status, locators))
    return tuple(result)
