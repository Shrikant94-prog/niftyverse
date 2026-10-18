# Additional candidate leads from NEW_PLAN

Read only for the relevant Phase 02/source-adapter task. These were proposed in NEW_PLAN.md; this bundle does not certify their operation, dates, units, coverage, or provider terms. Preserve a timestamped real response/hash and independently checked meaning before promotion to supported.

| Family | Candidate to investigate | Required distinction |
|---|---|---|
| Catalogues | `EQUITY_L.csv`, `ETF_L.csv`, `SME_EQUITY_L.csv`, `symbolchange.csv`, `namechange.csv` | Current lists do not establish dated identity |
| Reports | `/api/merged-daily-reports`, `/api/all-reports`; legacy CM/F&O versus UDiFF archives | Verify exact official host, filename/date generation, headers and units |
| Delivery | `sec_bhavdata_full_<date>.csv`, `MTO_<date>.DAT`, proposed record-type 20 handling | Verify preamble/record schema and historical availability; do not assume a universal 2019 cutoff |
| Equity | `/api/historicalOR/generateSecurityWiseHistoricalData`, `/api/historical/cm/equity` | Verify filters, pagination, series, dates and field completeness |
| Derivatives | `/api/historicalOR/foCPV`, `/api/NextApi/apiClient/GetQuoteApi` | Verify bounded history versus current-only data and dated terms |
| Indices/VIX | `/api/historicalOR/indicesHistory`, `/api/historicalOR/vixhistory` | No current-value substitution for historical series |
| Filings | Legacy NEAPS HTML, XBRL XML, actual inline XBRL, HTML viewers at `ixbrl` URLs | Dispatch by content/signature; registered financial templates only |
| Archive date guard | Requested session versus `TradDt` / `DATE1` / `TIMESTAMP` | A stale/wrong file is not proof of a holiday; classify using independent calendar/source evidence |
| Derived VWAP | Verified currency turnover / comparable traded quantity | Positive denominator, compatible units, declared precision/rounding and derived provenance; a quotient need not have a finite exact decimal expansion |
| Cross-format financial checks | Monetary scale disagreements, including factors near 10^5 or 10^7 | Compare same filing/concept/context/basis/period/unit first; don't infer a correction solely from similar digits or XBRL `decimals` |

Prefer explicit supported/experimental/blocked capability results to repeated speculative probes. Registered HTML scope may be clarified only against the approved financial-table boundary; do not expand into general market-page scraping.
