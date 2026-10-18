# Canonical identity, facts, and time

**Read when:** Changing schemas, identities, assertion versions, listing selection, or historical eligibility.

**Authority:** detailed product contract, revision 18 October 2026. Implementation and dataset support are not claimed. Progress belongs only in root STATE.

## Section lookup

- [7.1 Logical tables and keys](#s7-1)
- [7.2 Representation rules](#s7-2)
- [7.3 Temporal selection algorithm](#s7-3)
- [7.4 Delisted securities](#s7-4)

Read the selected section and its necessary dependencies; this lookup is not a full-file reading checklist. Original section numbers are retained as stable references.

<a id="s7"></a>
## 7. Canonical models, identity, and time

<a id="s7-1"></a>
### 7.1 Logical tables and keys

Every fact table includes a stable business key, immutable `version_id`, `content_hash`, `source_id`, raw reference/row locator, schema/normalizer version, and collection time. Keep shared provenance in referenced records rather than duplicating large payloads in every row.

Here a raw reference resolves to the declared acquisition boundary: original source bytes for direct adapters or the retained yfinance result for Yahoo. Preserve the capture kind through facts, snapshots, exports and quality reports; neither a decimal cast nor normalization upgrades SDK evidence to original-wire provenance.

| Table family | Grain / business identity | Essential semantics |
|---|---|---|
| `instruments`, `issuers`, `listings` | Stable internal IDs; separate issuer/security/listing | Exchange, ISIN where known, asset class, series, dated listing status |
| `instrument_aliases` | Identifier + namespace + validity interval | Symbols/ISINs may change; collisions cannot auto-resolve |
| `trading_sessions` | Venue/segment/session date | Open/close instants, holiday/special-session evidence |
| `index_definitions`, `index_membership` | Index/component/effective interval/version | Announcement/availability separate from effective membership |
| `derivative_contracts` | Stable internal contract/listing identity plus immutable terms version | Underlying/type/right; dated decimal strike, actual expiry, settlement specification, multiplier/lot and source-token aliases; mutable terms are not the sole stable ID |
| `equity_daily` | Listing/series/session/version | Raw OHLC, previous close, quantity/turnover/trades and their units |
| `etf_daily`, `etf_metadata` | Dated ETF listing/session or metadata validity/assertion version | Traded-price OHLC, fund units/turnover, evidenced scheme attributes; no NAV substitution |
| `equity_delivery` | Listing/series/session/version | Delivered quantity, total comparable quantity, fraction and source basis |
| `market_state_observations` (optional, additive) | Listing/segment/state kind/source observation/effective interval/version | Evidenced ASM/GSM stage, trade-for-trade or price-band/operating-range facts; publication/collection precision, nullable bounds and source rule/basis; overlapping state kinds remain separate |
| `index_daily`, `index_valuations` | Index variant/session/version | Price versus gross/net TRI; PE/PB/dividend yield are separate measures |
| `derivative_daily` | Contract/session/version | OHLC/settlement, OI/change, quantity/turnover with contracts/units distinguished |
| `participant_reports` | Segment/session/category/measure/version | Long/short, stock/index, futures/options; no fabricated participant identities |
| `market_flows`, `large_deals` | Published aggregate/event identity/version | Gross buy/sell/net, provisional/final, units, buyer/seller detail only if supplied |
| `corporate_actions` | Security/action/source event/version | Ex/record/announcement/payment dates, action type, verified ratio, status |
| `announcements`, `corporate_events` | Source event/security/version | Event time, publication time, classification, attachment metadata |
| `filings` | Source filing/security/period/basis/version | Period boundaries, filing type, revision links, publication precision |
| `filing_documents`, `filing_source_assertions` | Source document/hash/format/parser/taxonomy and assertion/context identity | Namespaced concepts, original text/decimal, nil, unit/precision, entity/period/dimensions, document locator and mapping status |
| `financial_facts` | Source assertion: filing/concept/period/unit/dimensions; separate analytical selection key below | Decimal value, standalone/consolidated, instant/duration, cumulative/discrete, additivity, reported/derived provenance and original label |
| `ownership_facts` | Filing/category/share class/denominator | Shares/percent as different facts; taxonomy version |
| `global_observations` | Provider/series/session date/assertion version | Price-index close, SDK float provenance and documented decimal conversion, missing code and timing evidence; version is locally retained, not an implied provider vintage archive |
| `corrections`, `quality_issues` | Issue/correction ID | Original and replacement, reason, evidence, reviewer, affected interval |
| `builds`, `jobs`, `coverage` | Plan/build/job/partition | Checkpoints, statuses, completeness evidence, last source check |
| `snapshots`, `lineage`, `feature_versions` | Immutable output/input version selection | Reproducibility and correction propagation |

Use normalized typed tables and Arrow schemas, not a single untyped JSON/EAV warehouse for all prices. Financial concepts can use a long-form fact table with typed dimensions. Keep documented SQL views convenient without erasing temporal fields.

**Assertion lifecycle (R3; freeze before Phase 04):** distinguish reusable `content_hash` from assertion/revision occurrence identity and from a source-check record. Preserve source revision IDs and evidenced ordering/availability; ambiguous ties remain conflicts. A → B → A can reuse A's content but must retain the later A occurrence. Unchanged polling adds a check without a false revision. Model evidenced withdrawal and reinstatement as versioned states with known-at time; selection after a withdrawal returns its reason-coded unavailable state rather than resurrecting an older value. Absence from an incomplete response does not prove withdrawal. Test all these cases and preserve old snapshots.

**Financial selection (R5):** physical assertions remain filing-linked. Analytical selection groups by evidenced entity mapping, concept, exact period boundaries, accounting basis/scope, unit and dimensions across filings. Select the reporting period separately from its admissible assertion revision. An explicit restated comparative in a later filing can supersede the original period's assertion when available; it must not displace that later filing's newest quarter or duplicate panel rows. Prefer a valid source-reported quarter to a project-derived quarter under a named policy; unresolved conflicts quarantine the requested fact rather than silently applying latest-upload-wins. Include original Q1 revenue 100 → later restated Q1 90 with Q2 still the newest quarter.

**Derivative term history (R7):** version full effective/known-at terms under stable internal identity, retaining source aliases and original EOD row terms. If continuity cannot be evidenced across an adjustment, retain distinct linked-or-unresolved incarnations instead of inventing a join. Changes to strike, expiry, lot/multiplier or settlement never rewrite earlier sessions. Test pre/post corporate-action strike/lot changes and existing-contract expiry changes in Phase 10; no return reconstruction or advanced option valuation is required.

`market_state_observations` is a companion table, not extra required columns in `equity_daily`. Use the shared immutable provenance and temporal-selection rules. Distinguish explicit removal/absence, observed presence, unknown coverage and not-applicable state. A dated snapshot establishes that observation, not an invented start/end interval; absence proves removal only under a verified complete-source contract. No forward extension past evidenced validity. Capability discovery must establish permitted JSON/CSV/ZIP availability before an adapter is supported; structured local evidence can enter through the existing reviewed correction/import path without extending the scoped filing parsers to surveillance notices or adding PDF parsing.

<a id="s7-2"></a>
### 7.2 Representation rules

- Trading day is a date. Publication/collection instants are timezone-aware UTC; retain source timezone and precision. Display Indian times as Asia/Kolkata.
- Use decimal types for stored prices, strikes, currency values, ratios requiring exact source preservation; choose scale per verified dataset dictionary. Floating-point is allowed in derived numerical features with documented tolerance.
- Quantity is integer only where the source definition supports it. Volume in contracts, units, shares, and currency turnover are different quantities.
- Preserve source currency and unit multipliers. Convert lakh/crore only under a verified field contract and retain the original representation.
- Null, zero, empty string, source dash/missing marker, not applicable, and unavailable are distinct states where relevant. Keep reason codes alongside analytical nulls.
- Canonical IDs do not derive solely from current symbol strings. A rename is not automatically a new security; a reused symbol is not automatically the same security.
- Never enforce a universal 500-row index membership rule; documented temporary components require explicit handling.
- Unknown extra JSON fields can be retained/diagnosed without failing all data. Missing critical keys, incompatible types, or changed economic meaning quarantine the affected partition.

<a id="s7-3"></a>
### 7.3 Temporal selection algorithm

For each research decision time:

1. Resolve the membership interval effective then, using the selected evidence policy.
2. Resolve dated listing aliases and tradability separately.
3. Filter candidate fact versions by acceptable availability evidence at that decision time.
4. Only then select the latest admissible revision for each business fact.
5. Apply reporting-period, comparable-basis, staleness, and feature-warmup rules.
6. Left-join features onto eligible membership; retain missing rows and reasons.
7. Persist the exact selected version IDs and recipe/policy versions in the output snapshot.

**Listing/series selection (R6):** instrument/decision panels apply a versioned dated `ListingSelectionPolicy`. Default selection admits one evidenced ordinary-equity observation per security/session, allowing EQ ↔ BE continuity only when identity evidence establishes the same security; retain original listing/series in lineage. Block-deal, rights-entitlement, partly paid or distinct share-class observations never merge merely by symbol. Multiple plausible observations produce a collision reason until an explicit source/series priority resolves them. An explicit EQ-only request produces a policy-exclusion reason during BE sessions, not a source-fetch failure. Test EQ → BE → EQ plus a concurrent BL observation: no double-counted turnover or duplicate instrument/decision row.

Selecting today's latest revision first and then filtering by publication time is incorrect: it can remove an older version that was legitimately known. Effective time and knowledge time must remain separate even for index membership and corporate actions.

Date-only publication evidence is not an exact timestamp. Strict mode excludes it from a same-day morning decision unless a verified rule establishes availability. A conservative next-session interpretation, if offered, is a named policy assumption. Local collection today cannot prove a value was available in 2018.

Quality assessments, anomaly resolutions and manual overrides have their own versions and known-at evidence. Retrospective validation can identify a problem today, but cannot pretend its later explanation or replacement value was known at an earlier decision. Pin the quality policy and issue/resolution selections with the snapshot; distinguish current operational warnings from historical eligibility and expose any retrospective filtering. Never improve a historical sample silently by removing rows later judged inconvenient.

Session shifts use versioned venue/segment calendars with evidenced special sessions, closures and timezone rules. Treat an external calendar package as a candidate implementation aid, not exchange authority; verify historical coverage and overrides before relying on it. A missing observation on an expected session, a non-session, a suspension and unknown calendar coverage are different states. An unverified session boundary blocks dependent strict calculations, not unrelated datasets. New calendar evidence invalidates dependent schedules/windows without rewriting old snapshots.

<a id="s7-4"></a>
### 7.4 Delisted securities

Accept a documented local CSV/Parquet manifest containing supplied identifier, namespace, exchange/series, known validity/listing/delisting dates, optional ISIN/issuer, evidence references, and confidence/status. Dates can be unknown rather than fabricated.

Resolve historical aliases before requests; do not require a successful current quote or current security-master listing to fetch history. Query supported historical routes/reports for the valid intervals. Record `source_unavailable`, `identity_unresolved`, `not_listed`, `not_traded`, and `fetch_failed` distinctly. No stale-price carry to delisting, automatic zero terminal price, or forced removal from the universe. Terminal economic returns remain outside this release.
