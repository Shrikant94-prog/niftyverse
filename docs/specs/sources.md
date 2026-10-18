# Source discovery and capability evidence

**Read when:** Implementing or probing a particular provider/dataset family. Read that family and its evidence contract.

**Authority:** detailed product contract, revision 18 October 2026. Implementation and dataset support are not claimed. Progress belongs only in root STATE.

## Section lookup

- [5.1 Allowed acquisition](#s5-1)
- [5.2 Recorded endpoint leads — reference only](#s5-2)
- [5.3 Structured fundamentals and legacy financial tables](#s5-3)
- [5.4 Shareholding](#s5-4)
- [5.5 Reports and format generations](#s5-5)
- [5.6 Yahoo Finance via yfinance — overseas index EOD only](#s5-6)
- [5.7 Progressive capability evidence and representative filings](#s5-7)
- [5.8 ETF source scope](#s5-8)

Read the selected section and its necessary dependencies; this lookup is not a full-file reading checklist. Original section numbers are retained as stable references.

Source observations in this contract are inherited research leads, not fresh verification. Recheck the relevant provider behavior and record the sample date, payload identity and tested interval before claiming support.

<a id="s5"></a>
## 5. Sources and contract discovery

<a id="s5-1"></a>
### 5.1 Allowed acquisition

Public NSE/NSE Indices JSON and official CSV/ZIP; official NSE financial/ownership XBRL XML and genuine inline XBRL; narrowly registered legacy NSE financial-result HTML tables; Yahoo daily index history through [§5.6](sources.md#s5-6); explicit local structured inputs and saved filings of supported families.

Landing-page bootstrap does not authorize extracting its market content. Only evidenced filing links and approved official archive families enter the filing downloader; calendar year or a filename is not a parser contract. No general HTML market scraping, PDF/OCR parsing, browser automation, CAPTCHA solving or rotating-proxy bypass. Do not crawl arbitrary links from a document. Reading a circular during research is evidence gathering, not a production PDF parser. The Yahoo SDK remains the separate scoped transport exception.

<a id="s5-2"></a>
### 5.2 Recorded endpoint leads — reference only

These leads were noted during prior research and remain **Candidates** for current operation. They are not verified current source contracts. Independently verify official hosts, route families, formats and payload semantics in Phase 02. No legacy source checkout, function name, implementation, fixture or session code is needed or approved for reuse.

| Dataset | Route/source lead |
|---|---|
| Equity history/delivery | Routes defined for historical/security price-volume-delivery queries |
| F&O history | `/api/historical/fo/derivatives`; metadata subroute |
| Index prices/PE/PB/TRI | NIFTY `BackPage` routes for historical, valuation, and TRI JSON |
| Financial catalogs | `/api/corporates-financial-results`; `/api/results-comparision` |
| Integrated financial filings | `/api/integrated-filing-results`; official linked XML/HTML documents, verified by content |
| ETF catalogue/history | Independently verify official ETF metadata and historical price-volume-delivery route families, including `/api/historicalOR/generateSecurityWiseHistoricalData` |
| Instrument discovery | Official security/catalogue sources; `charting.nseindia.com/v1/exchanges/symbolsDynamic` is a candidate only, not a historical identity authority |
| Announcements | `/api/corporate-announcements` |
| Events | `/api/event-calendar` |
| FII/DII | `/api/fiidiiTradeReact` |
| Bulk/block/short-selling | `/api/historical/bulk-deals`, `/block-deals`, `/short-selling` |
| Participant OI CSV | Official `fao_participant_oi_<date>.csv` archive family |

Security-master, corporate-action, holiday, delivery-report, participant-volume, historical India VIX, and ownership-detail routes require independent verification. A current VIX value or current lot-size file does not prove historical coverage.

<a id="s5-3"></a>
### 5.3 Structured fundamentals and legacy financial tables

**Verified—published:** NSE directs the quarter ended March 2025 onward to Integrated Filing—Financials; its 2 May 2018 circular introduced Banking and Ind-AS financial-result XBRL using a common exchange taxonomy. These are discovery clues, not universal format cutoffs. [Financial-results notice](https://www.nseindia.com/companies-listing/corporate-filings-financial-results?equityfndatefilter=1), [2018 circular](https://nsearchives.nseindia.com/content/equities/NSE_Circular_02052018.pdf), [NSE taxonomy information](https://www.nseindia.com/static/companies-listing/xbrl-information).

1. Discover both catalogue generations with verified filters and pagination. Retain source filing/document IDs, linked artifacts, period, accounting basis, audit status and submission/publication/revision times separately. A document link is not an ingested statement.
2. Download bounded source bytes, capture their hash and origin, then detect the actual document family. Dispatch using root/namespace, schema/taxonomy references and verified table signatures. Dates/circulars narrow candidates; content verifies them. An `ixbrl` URL can contain ordinary rendered HTML: require actual inline-XBRL elements/namespaces. Unknown XML or HTML remains unsupported, not a guessed table or empty success.
3. Decode syntax into source assertions; map economic concepts separately using versioned dictionaries. XBRL processing preserves namespace-qualified concepts, entity, instant/duration periods, explicit/typed dimensions, units, decimals/precision, nil/duplicates and context identity. Never select a context by names such as `OneD`/`FourD`, strip namespaces to identify concepts, or infer sector from filenames. Inline XBRL additionally applies its documented transformations, sign, scale, fractions and continuations, with unsupported constructs explicit. [Inline XBRL specification](https://www.xbrl.org/specification/inlinexbrl-part1/rec-2013-11-18/inlinexbrl-part1-rec-2013-11-18.html).
4. Register legacy HTML templates with evidenced row/column headers, periods, basis and unit captions. Resolve spans and parentheses/missing markers explicitly. A caption in lakhs/crores does not justify applying the same multiplier to EPS or percentages; XML numeric values may already be rupees despite a presentation-rounding label. Keep original values/labels and per-field conversions. Changed/ambiguous templates quarantine affected facts.
5. Target **P&L, balance sheet, cash flow and segment disclosures** where provided. Preserve segment/product/geography dimensions, consolidated/standalone distinctions and taxonomy-specific concepts; no forced universal bank/industrial-company schema. Unmapped concepts stay inspectable in source assertions with diagnostics instead of disappearing or being forced into a similar label. This is financial-statement extraction, not narrative annual-report/PDF extraction.
6. Distinguish discrete quarter, annual and cumulative YTD periods and instant versus duration. Derive quarters only for explicitly additive duration concepts with compatible fiscal boundaries, unit, scope/basis and admissible revisions. EPS, margins, ratios and balance-sheet instants are not additive. Preserve reported/derived assertions and input lineage; apply sections 7.1/7.3 to restated comparatives.
7. Report discovery, decoding, mapping and validated-fact coverage separately per issuer/period/statement/concept/basis/family. Missing values never become zero; multiple formats of one filing are representations of one provider, not independent corroboration. Surface disagreements under a versioned selection policy.

**Observed examples, not coverage certification:** direct inspection found a legacy RELIANCE HTML filing for December 2016, older XBRL with a 2020 taxonomy namespace and an integrated 2025 XBRL document with dimensional contexts. An inspected URL named `ixbrl` contained rendered HTML without inline-XBRL tags. These observations establish useful parser cases, not all-sector support or 15 years of numerical history; references and limitations are retained in the provenance record. Shared NSE/BSE taxonomy namespaces do not authorize acquiring BSE data.

<a id="s5-4"></a>
### 5.4 Shareholding

Separate filing metadata from numerical facts. Preserve report, submission, revision and broadcast dates independently. [NSE shareholding presentation](https://www.nseindia.com/companies-listing/corporate-filings-shareholding-pattern).

Verify catalogue/detail JSON and linked XBRL/inline-XBRL documents independently; `/api/corporate-share-holdings-master` remains a candidate, not a verified full-facts history API. Reuse the filing decoder, with a separate ownership mapper and taxonomy dictionary. Preserve categories, parent/child hierarchy, share classes, denominator, dimensions and units. Shares and percentages are different facts; no double counting or zero inference. Compare only compatible definitions and retain revisions. Legacy financial HTML support does not imply arbitrary ownership HTML support.

<a id="s5-5"></a>
### 5.5 Reports and format generations

**Verified—published:** NSE identifies July 2024 discontinuation of older common bhavcopy formats and their UDiFF replacement. Legacy paths alone are insufficient. [Derivatives reports](https://www.nseindia.com/all-reports-derivatives)

A report registry specifies dataset, segment, date interval, filename generation, compression, delimiter, headers, units, schema version, publication behavior, and provenance. Prefer a verified JSON catalog; otherwise use independently verified official patterns. No runtime report-page scraping.

Whole-market reports can reduce long-history request counts when their coverage/fields match. JSON can supplement and reconcile. These are two representations from one provider, not independent-source failover. Missing archives require classification: holiday, unpublished, retired path, or failure.

<a id="s5-6"></a>
### 5.6 Yahoo Finance via yfinance — overseas index EOD only

**Owner-selected design:** replace FRED with `yfinance` for S&P 500 (`^GSPC`) and Nasdaq Composite (`^IXIC`). Use provider-neutral series IDs `SP500_PRICE` and `NASDAQ_COMPOSITE_PRICE` and a versioned mapping to Yahoo symbols. These are price-index levels, not investable securities, total-return series or currency amounts. Retain source currency metadata without relabeling index points as USD cash. No SPY/QQQ/ETF substitution. Other overseas indices require an explicit dataset extension; no global equity, options, fundamentals, intraday or live-feed scope is added.

**Published library behavior:** yfinance provides daily history through a pandas-returning API; start is inclusive, end exclusive, and adjustment/repair/missing-row options affect output. Its default automatic adjustment must not determine this project's price basis. [History interface](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.history.html), [download options](https://ranaroussi.github.io/yfinance/reference/api/yfinance.download.html). Yahoo identifies the [S&P 500 as `^GSPC`](https://finance.yahoo.com/quote/%5EGSPC/history/) and [Nasdaq Composite as `^IXIC`](https://finance.yahoo.com/quote/%5EIXIC/history/); operational history/metadata responses remain Phase 02 candidates, not verified support from those links.

Contract for the optional `yahoo` extra:

1. Pin an exact yfinance release and resolved dependencies in `uv.lock` after Python 3.14 wheel/import/behavior checks. Use one bounded ticker/window per call, `interval="1d"`, explicit start/end, `auto_adjust=False`, `back_adjust=False`, `repair=False`, `rounding=False`, `keepna=True`, `prepost=False` and `actions=False`. Prefer `Ticker.history`; if `download` is used, also set `threads=False`, `progress=False`, `ignore_tz=False` and a tested column-layout policy. Verify each option against the pinned release, capture effective values, and use its supported exception mechanism. Empty/None/all-null output or suppressed SDK errors cannot masquerade as complete history.
2. First release normalizes **Close only** into `global_observations`; retained SDK output may contain OHLC/adjusted-close/volume columns but these are not promised analytical fields. Never substitute `Adj Close`, forward-fill holidays or missing sessions, infer index share-volume, or run yfinance price repair. Normalize timezone-aware session labels using evidenced source metadata; reject unresolved timezone/identity/basis instead of guessing.
3. Include completed US sessions only. A date row can contain the current session's unfinished bar; filter using the evidenced US calendar, early closes, DST and collection instant, with an explicit post-close freshness buffer. A buffer is an operational assumption, not historical dissemination evidence. Preserve bar session, collection time and timing precision separately. Latest-vintage is labeled; locally observed mode uses capture time. Strict historical evidence remains unavailable where the exact version's prior public availability cannot be established. No pretense that Yahoo supplies an ALFRED-style vintage archive.
4. The SDK is a synchronous boundary. Run it in a bounded, supervised worker process with one active Yahoo call, finite call/window limits and a hard job deadline. Keep its pandas, sessions and mutable SDK state outside the canonical writer and notebook event loop; return bounded Arrow artifacts plus diagnostics. Parent cancellation terminates/joins the owned worker if graceful completion exceeds its deadline and never publishes partial work. [§9.5](transport.md#s9-5) distinguishes SDK-call budgets from internal HTTP requests.
5. Preserve an immutable **SDK-result capture** before project normalization: lossless returned float/null values, index/timezone and column schema, selected metadata, call parameters, collection time, yfinance/dependency versions and diagnostics. Label `capture_kind="sdk_result"`; it is not Yahoo's original response bytes. Content hashes identify this artifact, and source row locators refer to it. Offline replay begins at that boundary; it cannot reconstruct transformations already performed inside yfinance. Float-to-decimal conversion preserves the documented SDK representation, not unavailable original decimal text. Never use private monkeypatches to claim a raw-wire guarantee.
6. Verify representative old/recent windows, warmup dates, holidays/early closes/DST, duplicate/missing sessions, no-data/errors, column/type drift, final-bar exclusion and refresh corrections for both indices. A successful download does not certify ten-year coverage or historical timing. Do not fall back to FRED, guessed Yahoo endpoints or ETFs silently.

This choice simplifies key setup and supplies a familiar historical-data interface; it does not establish superior accuracy, uptime or complete history. yfinance is an unofficial research/educational tool; retain its personal-use/data-use caveats and source attribution under the existing source-use documentation, without introducing the excluded R1 gate. [yfinance project documentation](https://github.com/ranaroussi/yfinance/blob/main/README.md).

<a id="s5-7"></a>
### 5.7 Progressive capability evidence and representative filings

Before implementing a particular decoder/mapper family, obtain a small representative real sample and independently inspect a few expected facts with their units, contexts and periods. For example, one legacy HTML filing, one older XML and one integrated XML can expose different layouts; a bank or ownership taxonomy needs its own relevant sample when that mapper is developed. These examples are starting cases, not a fixed exhaustive corpus or a guarantee of sector coverage. Synthetic adversarial fixtures complement real evidence; they cannot establish real-source support.

Phase 02 defines an initial versioned **minimum capability manifest**: dataset/family, verified route/document/hash, concept/category targets, statement/basis/unit/dimensions, tested intervals, publication precision, pagination/completeness, parser/taxonomy candidates, supported/experimental/blocked status and next action. Obtain enough early evidence to shape document/assertion schemas. Do not require a ten- or fifteen-year survey or samples of every taxonomy before independent foundation work can proceed. Missing evidence blocks only the dependent family or claim.

Retain general source-contract discovery too: bounded active/renamed/delisted equity, index, derivative, report-generation and both Yahoo-index samples, including failure responses. Record request/response schemas, windows, session/empty semantics, retrieval timestamps, revisions, usage notes and artifact hashes. Freeze each implemented family's concrete targets and independently checked reference interval before accepting it; later families extend the manifest under a new version, never silently replace an unmet target. Access failure does not prove missing source history.

Phases 03, 13 and 14 expand samples alongside implementation across taxonomy generations, sectors, accounting bases, periods, revised filings and all four financial statement families. Each claimed supported family requires real-source evidence and independent numerical expectations before its acceptance closes. Hold out additional filings from parser development for regression/coverage testing. A decoder can work while its economic mapper remains incomplete; report both.

As adapters mature, broaden interval and issuer tests; Phase 22 consolidates reproducible coverage results. Publish tested ranges and gaps, never infer continuity from the oldest and newest successes. Targets remain explicit; `coverage="available"` alone does not close FUND-01/OWN-01. Known absence, access failure, undiscovered history, unsupported format and parse/semantic error are distinct outcomes. The fixed reference workload remains a separate dataset assessment. This is progressive engineering evidence, not the excluded R1 gate.

<a id="s5-8"></a>
### 5.8 ETF source scope

Verify ETF catalogue, dated listing/series identity, EOD prices/volume and available metadata independently. Reuse verified equity-market transport/report infrastructure with ETF-specific capability and unit contracts. Names are search hints, not authoritative scheme classifications. Current metadata cannot establish a past mandate or listing interval; missing classification stays unknown. Commodity ETFs are securities in this scope, while commodity spot feeds are deferred. NAV/iNAV, holdings, expense ratios and tracking-error histories are not promised merely because a live page or sibling library exposes a field.
