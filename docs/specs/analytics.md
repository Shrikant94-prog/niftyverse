# Dataset semantics and pure analytics

**Read when:** Dataset meaning, action factors, indicators, resampling, or feature lineage.

**Authority:** detailed product contract, revision 18 October 2026. Implementation and dataset support are not claimed. Progress belongs only in root STATE.

## Section lookup

- [12.1 Equity, index, reports, and contracts](#s12-1)
- [12.2 Corporate actions and adjustment boundary](#s12-2)
- [12.3 Bounded standard indicator catalog](#s12-3)
- [12.4 Derived-data lineage](#s12-4)
- [12.5 Instrument search, ETF semantics and EOD aggregation](#s12-5)
- [12.6 Fact inspection and explanation](#s12-6)

Read the selected section and its necessary dependencies; this lookup is not a full-file reading checklist. Original section numbers are retained as stable references.

<a id="s12"></a>
## 12. Dataset semantics and analytics

<a id="s12-1"></a>
### 12.1 Equity, index, reports, and contracts

Validate nonnegative quantities where appropriate and OHLC relationships with source-specific exceptions explicitly modeled. No automatic forward-fill over missing trading sessions. Preserve trade/settlement/closing-price distinctions. Delivery fraction is derived only from compatible numerator/denominator and checked against published values where supplied.

Delivery quantity/fraction already belongs to EQ-01; it does not replace traded volume or turnover. Require the same listing/series/session and source definition; zero or unknown comparable total yields reason-coded null, not an infinite or invented percentage. A high delivery fraction alone is not evidence of institutional buying or superior predictive value.

Optional surveillance enrichment uses `market_state_observations`. Store actual evidenced restrictions, effective/publication timing and fixed-band versus dynamic-operating-range basis; do not hardcode today's rules into historical sessions. ASM/GSM or a band touch is not a universal no-trade condition. EOD OHLCV cannot establish continuous circuit lock, available counterparties or executable fills. Preserve observed volume and separately flag unknown execution availability. [NSE surveillance measures](https://www.nseindia.com/static/regulations/exchange-market-surveillance-actions), [NSE price bands](https://www.nseindia.com/static/products-services/equity-market-price-bands)

Existing price-only requests have no new mandatory acquisition dependency. Regulatory-sensitive research explicitly requests and requires the relevant state coverage; otherwise label it unknown where not evidenced. Current regulatory lists cannot certify historical states, and incomplete surveillance history must never remove securities from historical membership. Phase 02 verifies formats/coverage; phases 05/07 own the additive schema, normalization and diagnostics under ID-01/EQ-01/QA-01. A blocked optional adapter remains experimental/blocked, not a fictitious ten-year capability.

Keep price indices, gross/net TRI and index valuation measures separate. Do not label an equity split-adjusted price return a total return. Index variants require explicit identifiers; a similarly named ETF is not a fallback index series. Include historical India VIX only after a permitted historical contract is verified; current snapshots do not satisfy this capability.

Contracts use actual source expiry and dated lot/multiplier metadata. Never infer all expiries from a weekday, reuse today's lot size for old contracts, mix option `CE`/`PE`, or aggregate OI with unknown units. A missing historical multiplier is an explicit limitation for notional calculations, not a reason to discard otherwise valid contract prices.

Use [§7.1](data-model.md#s7-1)'s full dated-term contract for adjusted strikes, expiry changes and settlement changes as well as lot/multiplier history. Preserve exchange-reported terms and evidence; do not derive a new derivative price-adjustment or valuation engine from the equity split/bonus routine.

Historical option-chain views can be assembled **on demand from stored EOD contracts** and labeled with session/expiry/coverage; this is not live chain acquisition. Keep absent strikes/contracts distinguishable from zero OI. Participant categories and FII/DII aggregates are separate datasets with separate definitions; do not treat their totals as interchangeable.

<a id="s12-2"></a>
### 12.2 Corporate actions and adjustment boundary

Store all available raw action types, dates, source text, verified structured fields and revisions. Normalize split/bonus ratios only when evidenced; preserve unsupported/unparseable action terms for review. Do not guess ratios from ambiguous free text.

Current-release adjustment is **split/bonus only**:

- Split share factor = new shares / old shares. Bonus `a` new shares per `b` held has factor `1 + a/b`.
- For dates strictly before the ex-date, divide raw price by the applicable cumulative share factor and multiply comparable share volume by it.
- Record adjustment anchor, action-version set, factor series, and basis. Raw values never change.
- A strict historical view uses only actions admissible at its decision time and adjustment anchor; latest-history adjustments are explicitly retrospective.
- Rights/dividends/mergers/demergers can affect return interpretation. Report intervening unsupported actions and mark derived returns incomplete when their economic effect is outside the supported basis. Do not manufacture dividend-inclusive returns.
- Reject zero/negative factors and ambiguous same-day action ordering; compound verified compatible split/bonus factors deterministically.

<a id="s12-3"></a>
### 12.3 Bounded standard indicator catalog

Implement transparent, versioned formulas rather than hundreds of indicators. All feature signatures declare inputs, units, window, warmup, null/gap policy, availability policy, and version.

| Feature | Version-1 mathematical contract |
|---|---|
| Simple price return | `P[t] / P[t-n] - 1`; endpoints must exist on the intended session grid; zero denominator is invalid |
| Log return | `log(P[t]/P[t-1])` for positive values; otherwise reason-coded null |
| SMA | Mean of exactly `n` admissible session observations; require full window |
| EMA | Seed with first complete `n`-observation SMA; then alpha `2/(n+1)`; restart/warmup after a disallowed gap |
| RSI | Wilder smoothing, default 14 changes; initialize gain/loss means from those changes; loss=0/gain>0 yields 100, both=0 yields 50 as an explicit convention |
| MACD | EMA12 minus EMA26; signal EMA9 of valid MACD values; explicit warmup and histogram |
| Realized volatility | Sample standard deviation (`ddof=1`) of `n` one-session log returns; annualization factor is explicit, default 252 |
| Rolling beta | Sample covariance with benchmark / benchmark sample variance on the same `n` aligned admissible returns; zero variance produces null |
| Drawdown | Price / running admissible peak − 1 over a declared window/anchor; basis visible |
| Average traded value | Mean of `n` verified currency-turnover observations; do not silently substitute close × volume |
| Index-relative return | Security simple return minus matching benchmark simple return; same endpoints and declared bases |
| Financial/ownership changes | Comparable concept/category/basis/unit/period only; financial concept additivity/instant-duration and cross-filing selection apply; missing/zero/negative denominator rules documented per feature |

Missing sessions cannot be removed to make a nominal 20-session indicator quietly span 30 sessions. Define calendars first; configurable gap policies generate different recipe identities. Use stable names for the new API; do not reproduce old wrappers' function signatures.

Financial acceptance (R4/R5): revenue YTD 250 minus Q1 100 may yield Q2 150 when compatible. Equal-length quarters with profit 100 each and weighted shares 100 then 200 have Q1 EPS 1, Q2 EPS 0.5 and half-year EPS about 1.3333; subtracting Q1 EPS must not produce a fabricated Q2 EPS of about 0.3333. An instant debt balance cannot become a quarter flow through subtraction. An admissible later restated comparative changes the selected earlier-period assertion while leaving reporting-period ordering and original snapshots intact.

<a id="s12-4"></a>
### 12.4 Derived-data lineage

Every materialized feature references its input fact versions, calendar version, action factors, membership version where relevant, and formula version. Store dependency intervals so a correction invalidates precisely the affected outputs. Recompute and snapshot new results; do not edit old snapshots in place. Pure feature functions must have no network/storage side effects.

Use existing `feature_versions` and snapshots as a bounded offline feature store, materializing only requested recipes. Cache identity includes exact input selection, recipe/code digest and parameters, requested decision/as-of instants and output session grid, adjustment anchor/basis, calendar, membership where relevant, availability/gap/quality policies, and relevant quality/coverage assessment versions. Include any other declared non-fact context affecting the result: unchanged filing values at different decision times can have different ages/staleness outcomes. A feature available today is not necessarily admissible at a historical query time. Keep normalized lineage references per row or output partition with exact row-selection mappings; do not duplicate every ancestor hash in every feature row. Manifest build identity includes package/source digest (and Git revision/dirty-state digest when available), dependency lock/environment and normalizer versions. A Git commit or raw timestamp alone is insufficient evidence of executable identity or public availability.

Standalone recipes validate the supplied schema, units, ordering, duplicate keys, session grid and declared basis, and return diagnostics alongside values. Absent source/availability evidence stays unknown; processing an arbitrary dataframe cannot confer provider-verified or historical point-in-time status. The same recipe/version powers standalone and pipeline calculations. Persisted reuse requires input hashes and metadata, not a dataframe object's in-memory identity.

<a id="s12-5"></a>
### 12.5 Instrument search, ETF semantics and EOD aggregation

Search an explicitly acquired local instrument catalogue by symbol, alias, name, ISIN and asset type, with dated/as-of filters and evidence status. Return ranked matches with stable IDs, listing/series and validity; ambiguity remains multiple matches until explicitly resolved. Never silently choose the first hit or an `-EQ` suffix. Search/rendering does no acquisition; stale/current-only catalogues show their limits. ETF metadata preserves unknown values instead of classifying schemes solely from names. ETF traded prices and fund-unit volume differ from NAV/iNAV, index points and equity-share quantities.

Weekly (Monday–Sunday) and calendar-monthly bars are pure transforms of acquired EOD data using an evidenced venue calendar and a declared input price/adjustment basis. Open/close are the first/last eligible session observations; high/low are extrema; compatible volume/turnover/trades sum; OI, when provided, is last observation, not a sum. Close-only datasets produce close-only aggregation. Do not infer missing OHLC or cross derivative contracts, incompatible listing regimes or adjustment policies. Do not aggregate delivery percentages directly; derive them only from comparable summed quantities.

Default outputs include completed periods only, distinguish missing expected sessions from exchange holidays, and disclose partial/gapped periods. An explicit partial-period option labels provisional status. Period label, actual first/last session and availability are separate: availability cannot precede the latest contributing observation/required close evidence. No forward-fill, hidden download or intraday resampling. Corrections invalidate affected periods through existing lineage; recipes pin calendar, input versions, aggregation rules and gap/availability policies.

<a id="s12-6"></a>
### 12.6 Fact inspection and explanation

Expose `trace` on canonical fact/result identities, resolving to document/row locator, original value/unit/scale, entity/context/dimensions/period, accounting basis, publication precision, revision choice, parser/mapping versions and quality decisions. Derived values include formula identity and exact selected inputs. Tracing reads retained local artifacts or a file bundle only; absent raw bytes/metadata are explicit and never fetched automatically. Custom SQL/dataframe expressions without recorded lineage cannot claim a verified trace. This is deterministic provenance, not a generated financial interpretation.
