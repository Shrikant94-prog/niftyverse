# Phase 02 initial source capability report — v1

Observed 18 October 2026. [Minimum targets](manifest-v1.json),
[partition/completeness contracts](partitions.md),
[metadata and hashes](observations.json), and [exact finite plans](probes/01.json)
are research contracts. No production adapter is certified by this phase.
`experimental` means usable bounded observations needing implementation and
validation; `blocked` means the stated access/format/semantic evidence is missing.
Software readiness, source accessibility, dataset coverage and human acceptance
are separate. No row below asserts complete ten-year coverage.

| Family / source format | Status and measured evidence | Timing/completeness limitations | Dependent phase / next action |
|---|---|---|---|
| Equity JSON, actions, events, announcement metadata, ASM JSON | blocked; landing 403, dependent probes unsent under circuit | Filters/windows/session refresh, schema, ex/effective/publication precision and stable pagination unverified | 03 transport; 07 equity; 12 events. Recheck ordinary access later or obtain explicit source inputs; never bypass. |
| GSM CSV, CM report ZIP candidate | blocked; candidate 404, no absence inference | No historical/current regime interval evidence | 05/07 optional enrichment only; verify official locators before adapter. |
| Band-change CSV | experimental; 3 rows on 2016-09-01, 7 on 2026-10-16 | Filename date only, no effective/publication instant; fixed-vs-dynamic meaning provisional; no continuity | 05/07 verify rules/intervals; price-only requests unchanged. |
| CM legacy/UDiFF CSV-in-ZIP | experimental; 2016-09-01 and 2026-10-16 actual distinct headers/member dates | Source rows observed; full validation/units and exact transition boundary not certified | 03 decoder safety and registry; 07 reconciliation. No legacy path-only support claim. |
| FO legacy/UDiFF CSV-in-ZIP, dated terms | experimental report samples on same sessions; blocked full old-term history | Actual row expiry/strike/type retained; old lot, multiplier, adjusted strike/settlement rule history unresolved | 05/10 full dated-term contract. Unknown notional does not erase valid price evidence. |
| Delivery current CSV / old MTO DAT | experimental current 2026-10-16; old 2016-09-01 response rejected by CSV preamble guard | Current turnover caption lacs; old record types/schema unverified, not absent | 03/07 verify preamble/records/units and match series/session. |
| Participant OI / participant volume CSV | experimental; distinct 2026-10-16 captions/category columns, contract counts | Only one session; do not interchange OI/flow or infer FII/DII cash data | 11 report registry/validation, expand periods. |
| Bulk/block/short/FII-DII JSON, VIX historical JSON | blocked under NSE circuit; representative scopes declared | No historical fields/units/session completeness established; current substitutes prohibited | 08/11 verify actual report/API responses before support. |
| NIFTY price/TRI/valuation JSON POST | blocked; three candidate routes return 302, no follow | Price/gross/net TRI/PE/PB/yield variant identity and history unverified | 08 approve evidenced redirect/route, verify variants/calendar/units. No ETF substitution. |
| Renamed/delisted historical equity | blocked API; current lists and change events observed | Current absence is not historical absence; delisting intervals/identity continuity unknown | 05/07 dated master and delisted samples, retain unknowns. |
| Financial/ownership catalogues | blocked under circuit, stable pagination/revisions unverified | Catalogues cannot certify numerical detail; failed/revised/mutating pages incomplete | 03/13/14 acquire stable detail locators and reconciliation evidence. |
| Rendered integrated financial HTML | experimental; two RELIANCE consolidated filings, 2025 year and 2026 Q1; four statement families inspected | Actuals vs lakhs/per-share contexts; no QName/taxonomy or universal cutoff inferred; prior publication unknown | 03 exact financial-table signature/processor tests; 13 basis/concept/sector expansion. |
| Rendered ownership HTML | blocked for decoding; NETWORK18 2025-09-30 numerical research reference | No arbitrary ownership HTML scope; share/percent/hierarchy/denominator examples only | 03/14 get linked XML/genuine-inline and taxonomy mappings. |
| Older/integrated/bank XML, legacy financial HTML, genuine inline | blocked: real XML/closed taxonomies/older legacy locators not obtained | Prior endpoint/namespace observations are leads; rendered ixbrl URL is not inline evidence | 03 progressive sample acquisition and finite tested decoder limits; block each unsupported family independently. No 15-year corpus gate. |
| Yahoo ^GSPC/^IXIC SDK-result | experimental; both symbols return three sessions in each of two old/recent windows; holiday-only errors retained | End exclusive, daily Close/index points; latest-vintage, collection availability only; final-bar/refresh corrections/DST transition untested | 15 supervised production worker/calendar/15-minute operational-buffer tests; 18 SDK-boundary replay. Internal HTTP count/bytes unknown. |
| ETF catalogue CSV, report EOD | experimental; 355 current rows; NIFTYBEES/GOLDBEES EQ rows on 2016-09-01 and 2026-10-16 | Source classification now, changed ISINs; unknown mandate/dated identity and untested ranges. ETF_L dead candidate retained | 05 identity, 07 EOD, 19 discovery. Preserve fund units; no NAV/index replacement. |
| Equity/SME/change CSV and chart discovery JSON | experimental current lists/change events; chart returns 20 indices despite candidate query | Exact symbol/ISIN vs ambiguous names/aliases; stale/undated validity. Chart has no ISIN/date and certifies no intraday feature | 05/19 explicit ambiguous results and dated reconciliation; no first-match inference. |

Capture research totals: **27 direct HTTP requests across 46 declared probes**,
including 19 deliberately unsent under the carried circuit; 19 responses retained
as `observed_unverified`, 3 missing, 3 redirects, 1 format mismatch, 1 challenge.
Six Yahoo outer SDK calls are counted separately; internal requests unknown.
Published-page web research supplied context/locators, not runtime API support;
its underlying request count is not represented by the direct-capture count.

Every capture starts `complete=false`. Headers/signatures, exact body hashes,
scope and retrieval instants identify evidence; manual numerical/schema examples
are in checkpoint evidence, not inferred from mock fixtures. Current catalogues
cannot establish historical intervals. Unknown/missing/unavailable/unsupported
and parse/semantic errors remain distinct. No provider or access-scope change is
justified yet: independent foundation work can proceed while dependent family
acceptance waits for valid evidence. No R1 acquisition-permission gate is added.

The capture utility is a research tool: GET/explicit POST only, official allowlist,
one attempt, shared session, at least 2s start spacing per set, finite deadlines,
decoded-body/request/declared-window limits, no redirects and a carried challenge
circuit. No production transport, archive extraction, filing processor, canonical
mapper, writer, calendar filter or acquisition-on-import is implemented here.
Incoming decoded bytes can exceed a limit by the final <=64 KiB stream chunk;
that body is rejected and no further request starts after the total budget is
exhausted. JSON depth 64/node count 100,000 and sensitive-key rejection are
capture safeguards, not a general claim of secret detection in arbitrary bodies.
Only named public market/filing specimens belong in this local workflow.
