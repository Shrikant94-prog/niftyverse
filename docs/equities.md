# Raw equity prices, delivery and source reconciliation

All acquisition is explicit. `adapters.equity_json.fetch_equity_windows` accepts
an already owned `DirectTransport` and a half-open date window. It uses the
independently inspected equities archive route, `priceVolumeDeliverable` and ALL
series, inclusive wire end dates and bounded requests. No hidden source switch,
proxy, automatic live probe or current quote lookup is added. Failed windows
retain typed failure outcomes; HTTP success is not session completeness.

`decode_equity_json` and `decode_cm_prices` are independent JSON/report mappings.
Both preserve exact source decimals, raw fields, source hash/locator and generation
in immutable `SourcePrice` records. Close, last, previous close and settlement
are separate fields. Reports validate all source rows before selected-universe
projection. Unknown headers/generations and poisoned rows fail atomically.
The [source observations](capabilities/phase07-equity-observations.json) identify
the exact tested windows, units, request parameters and remaining limitations.

The observed JSON response is a data-only envelope, without a verified cursor
or count protocol. `JsonPage`/`merge_pages` accept **explicit caller page evidence**
for independently established pagination profiles; these are not invented NSE
response fields. Repeated/nonadvancing pages, changed snapshots and conflicting
duplicates fail. Equal overlaps retain evidence and never add volume or turnover.

## Dated identity and sessions

`market_prices.normalize_equities` requires an explicit dated `Catalogue`,
versioned `ListingSelectionPolicy`, evidenced `Calendar`, instrument IDs and UTC
knowledge cutoff. It returns selected observations and reason-coded gaps, not
an implicitly filled price panel. Default ordinary EQ/BE selection can follow
one evidenced security through a series change; BL and distinct classes cannot
be merged by symbol. An EQ-only BE session is policy_exclusion. Multiple plausible
listings/identities and conflicting representations remain blocked.

Missing observations, closed sessions, unknown calendar coverage, source failure,
not-listed/suspended states and policy exclusions remain distinct. Missing price
data does not remove an explicitly requested dead security. Neither a current
listing nor local collection today establishes past identity/publication availability.
Membership-dependent requests additionally require verified Phase 06 coverage;
fixed-universe work does not infer that coverage.

## Delivery

`decode_delivery` recognizes the actual old MTO preamble/record contract and
current combined delivery CSV. Old declared count/total are checked; a current
CSV needs explicit independently established count evidence to appear complete.
Original TURNOVER_LACS decimals/units remain available; rupee conversion is exact.
Missing delivery and a true zero are distinct.

`delivery_fraction` requires compatible symbol/series/session and traded-unit
definitions, optionally checked against a matching price observation. It retains
the numerator, denominator and published percentage separately. Zero/unknown
totals, absent delivery, denominator conflicts, excess delivery and percentage
disagreement return reason-coded nulls. The derived fraction uses half-even
rounding to 12 decimal places; the source percent's two-decimal comparison interval
is 0.005 percentage points. No institutional-buying inference is made.

`normalize_deliveries` reuses the same dated identity/session policy for
quantity-only records. Its null OHLC values are not invented prices; publish it
only through a `security_daily_details` partition.

## Quality and optional states

`QualityPolicy` versions absolute comparison tolerances: default INR price and
turnover tolerance 0.005, published delivery percentage tolerance 0.005 percentage
points; all counts compare exactly. `reconcile_prices` first requires matching
business keys, raw price basis and quantity/monetary units. Explicit representation
priority can choose only after comparable fields agree. Material differences
retain both paths and differing field names; there is no provider-majority vote,
averaging or silent fallback. Source values within tolerance stay unchanged.

`assess_move` preserves plausible extreme source prices. Its configurable warning
threshold (default absolute move 0.5) is an operational warning, not a universal
validity cutoff or split detector. Assessments carry policy, source key and their
own known-at/baseline availability. An unavailable future-known baseline cannot
enter an earlier decision. There is no default clipping, repair or row deletion.

`enrich_market_states` consumes explicit local Phase 05 observations only. Price-only
calls request no states or acquisition. Overlapping ASM/GSM/band states coexist;
missing coverage remains unknown. Only explicit absolute-price band bases can
produce an EOD touch flag; a percentage band-change value is not a price bound.
Touch/surveillance states never establish continuous lock, executable fills or
no trading, and never alter observed volume. Required state coverage can be
partial while the price observation remains intact.

## Shared output boundary

`storage.equity.make_price_batch` creates a `ValidatedBatch` for the existing
database publisher or direct CSV/Parquet writer. A supplemental
`security_daily_details` table retains trades, settlement/last/previous close,
delivery quantities/fraction/source percent/reasons, source units and representation.
Price schema compatibility is preserved. The v4 additive migration creates the
new table with transactional rollback and a retained pre-upgrade backup.

The same validation rejects deterministic OHLC/quantity/monetary poison before
either sink writes. Complete coverage needs explicit source evidence; gaps and
quality assessments remain in partition metadata. One batch binds selected facts
to one matching raw capture. Competing source hashes/locators stay explicit in
metadata; retain or publish each counterpart capture separately for raw replay.
Partial/quarantined output cannot become complete merely because writing succeeds.
This is a bounded dataset foundation, not the Phase 09 full DataPlan builder.
