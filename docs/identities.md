# Local identities, delisted inputs and calendars

These Phase 05 interfaces consume explicitly supplied local evidence. They do
not acquire security masters, quotes, price history or exchange calendars.
The test timelines are synthetic; source coverage remains in the capability
records. Public acquisition/builder features belong to later phases.

## Identity and selection

`niftyverse.identity` separates `Issuer`, `Instrument`, `Listing` and `Alias`.
Supply stable internal IDs from reviewed evidence; symbols alone never create
or join securities. A listing ID fixes instrument, exchange, series and role;
several dated states may reference it. Names on instruments are catalogue
display metadata; use dated aliases in namespace `name` for historical names.
ISIN is an alias namespace, preserving changes without rewriting identity.

Every alias and listing uses `temporal.Evidence(valid_from, valid_to, known_at,
source_id, locator)`. Validity is half-open `[valid_from, valid_to)`; a missing
start is unknown and never admits a dated resolution. A null end is open only
under the supplied evidence contract. `known_at` is an aware UTC instant of
justified availability, independent of effective dates. Local collection today
cannot establish past availability. Each immutable `Catalogue` has a version,
collection instant, coverage-through date and historical/current-only limit.

`catalogue.search(query, on=day, known_at=cutoff, asset_type=None,
namespace=None)` searches names and aliases locally, with exact aliases ranked
first. It returns all matches, stable instrument/listing IDs, original series,
alias/evidence, rank and dated/unknown status. `limitations` reports stale or
current-only scope. An empty result does not prove historical nonexistence.
Use `resolve(identifier, namespace, day, cutoff)` for exact alias resolution:
one dated match resolves; overlaps are ambiguous; any competing unknown date
remains unresolved. No search operation fetches data or chooses a first hit.

`select_listing` consumes explicit available listing IDs and a versioned
`ListingSelectionPolicy`. Default ordinary series are EQ and BE; the same
instrument must already be evidenced across transitions. BL, rights and partly
paid listings remain separate. EQ-only requests give `policy_exclusion` in BE
periods. Conflicting states or plausible multiple observations give `collision`;
an explicit listing priority can resolve distinct eligible listings. Results
retain the original listing/series, policy version and candidates. This is a
selection foundation, not a panel/turnover aggregation engine.

`Contract` fixes underlying/type/right and explicit evidenced/unresolved
continuity. `ContractTerms` versions full effective/known-at decimal strike,
actual expiry, lot, multiplier and settlement. Missing terms remain null;
`select_terms` returns no terms for unknown intervals and raises on overlaps.
Unresolved adjustments use distinct contract IDs and optional prior links.
Original EOD row terms are not rewritten; the derivative acquisition and
corporate-action examples remain Phase 10 work.

## Delisted CSV and Parquet manifests

Call `delisted.import_delisted(path, version_id=..., collected_at=...)`.
Both encodings use exactly these named columns (Parquet columns are strings
with nulls; CSV uses empty fields for nulls):

```text
instrument_id,listing_id,name,asset_type,issuer_id,issuer_name,
exchange,series,namespace,isin,listing_date,delisting_date,
source_id,evidence_ref,known_at,confidence,status,price_history,
identifier,valid_from,valid_to
```

Dates are `YYYY-MM-DD`, timestamps aware UTC ISO 8601. Optional dates, ISIN,
issuer ID/name may be null. An issuer name requires its supplied stable ID.
`asset_type` is equity or etf; `confidence` must be verified, `status` delisted,
and `price_history` available/source_unavailable/unknown. Delisting dates are
exclusive boundaries. Alias dates must fit evidenced listing bounds; missing
dates never become fabricated listing dates. One row describes one alias
interval; rename rows share stable IDs and consistent listing attributes.
Input limits are 8 MiB encoded, 32 MiB declared uncompressed Parquet row-group
bytes, and 10,000 rows. These limits are not a native decoder memory sandbox.
Malformed rows, contradictory IDs/attributes and overlapping duplicate or
ambiguous identifiers reject the entire import. Import returns immutable
records/catalogue plus the input SHA-256; it writes no destination or store.

`manifest.request(identifier, namespace, day, cutoff)` resolves history using
these records only. Identity, listed/not-listed/unknown state and declared
price availability stay separate. `member_request(...,
membership_established=True)` trusts explicitly established upstream membership
and retains eligibility even when the instrument is dead, listing dates are
unknown, or price history is unavailable. It does not infer membership or
implement universe reconstruction. There is no current quote lookup, stale
price carry, terminal zero or automatic deletion. `fetch_failed`/`not_traded`
remain outcomes for later acquisition adapters, not invented importer results.

## Optional market-state observations

`market_state.MarketStateObservation` and the additive typed
`market_state_observations` publication table preserve listing/segment/kind,
source observation ID, observed date, nullable effective interval, known-at,
publication instant or date with precision/timezone, exact nullable bounds,
state value and source rule/band basis. Capture/occurrence records supply shared
raw hashes, versions and collection lineage under the Phase 04 protocol.
Catalog migration 3 adds the table transactionally; old facts are untouched,
and the store keeps its pre-migration physical backup. Retained v2 backups
restore and migrate on explicit writable open.

States are `present`, `removed`, `unknown` and `not_applicable`. Removal is an
explicit supplied assertion, never inferred from an incomplete list. Use
`state_on` per listing/segment/kind: snapshot-only facts apply solely to their
observed date; an explicit evidenced interval admits only its own dates. Empty
selection means unknown coverage. Overlapping kinds and conflicting observations
remain separate. No default means unrestricted trading or executable fills.
DB and direct CSV/Parquet output share semantic batch validation. Price-only
requests have no market-state dependency or automatic enrichment.

## Evidenced segment calendars

`calendars.Calendar` fixes venue, segment, timezone, version and known-at.
Supply explicit `Session` rows with source/locator: trading and special rows
need exact aware UTC boundaries; closed and unknown rows have none. Sessions
use `[open, close)`. A missing date returns unknown with no invented source.
`eligible` is true/false/null for eligible/closed/unknown. Strict
`sessions_between(start, end)` fails if any date lacks evidence, including
unrecorded weekends. There is no weekday-based closure inference.

`SourceTime(value, source_timezone, precision)` retains the original value,
source date and declared date/instant/unknown precision. Date-only values have
no instant; exact instants convert to UTC without changing their meaning.
Ambiguous or nonexistent naive local clock readings fail; an explicit offset
can establish a fold's instant. Python's installed zoneinfo/tzdata supplies
conversion rules, not exchange-session authority.

`calendar.correct(new_version, later_known_at, replacements)` returns a new
calendar linked to the prior version. `CalendarSnapshot` pins the immutable
calendar and rejects versions not known by its cutoff. Retain the calendar's
version and `content_hash` in downstream recipes/artifacts; old snapshots keep
their original sessions. This phase provides the model boundary, not automatic
schedule/window recomputation or durable research panels from Phase 16.
