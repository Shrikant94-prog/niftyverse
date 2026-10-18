# Phase 02 checkpoint 04 observations — 18 October 2026

Historical evidence; [STATE](../../STATE.md) owns status. Base `532b30c`;
same CPython 3.14.7/uv 0.12.9/unchanged frozen lock. Commands exit 0:

```text
uv run --frozen python tools/probe_sources.py docs/capabilities/probes/04.json .local/phase02/04
uv run --frozen python tools/probe_sources.py docs/capabilities/probes/04-linked.json .local/phase02/04-linked
```

First plan: six actual requests, nine declared, three unsent under carried NSE
circuit; 10-request/180s ceiling. One additional evidence-backed archive request
under a 1-request/30s ceiling after inspecting the explicit ETF CSV link on the
[official source page](https://www.nseindia.com/static/market-data/securities-available-for-trading).
No speculative path sweep: `ETF_L.csv` returned 404; the linked
`eq_etfseclist.csv` returned 200. The blocked API host was not retried. Both sets
use one attempt, 8 MiB/body and 48 MiB total decoded-byte budgets, 2s spacing
within a set, 31-day declared window ceiling, no redirects. Source raw bytes
stay local; [observations](../capabilities/observations.json) retain hashes/times.

## ETF references and validity

NV-02-04-AC1: independent `csv.DictReader` reads of retained bytes find 355 current
ETF catalogue rows, 37,957 bytes, SHA-256
`9d90ef6e4b7aa1f23a1b493677191f5a17615d088c377ac7b1999f653e9bbac2`.
Headers: Symbol, Underlying Asset, SecurityName, DateofListing, MarketLot,
ISINNumber, FaceValue, ETF Underlying, Underlying Key. Current rows:

- NIFTYBEES: Nifty 50, listing `08-Jan-02`, lot 1, ISIN `INF204KB14I2`, face 1,
  category EQUITY, underlying key Nifty 50.
- GOLDBEES: Gold, listing `19-Mar-07`, lot 1, ISIN `INF204KB17I5`, face 1,
  category COMMODITY, underlying key GOLD.

Categories above come from actual source fields, never name inference. Catalogue
has no series column; report rows independently supply EQ. Listing dates are
source assertions observed now, not proof that today's ISIN/mandate applied for
the whole interval. Current classification/lot/face values have observation-time
validity only; expense ratios, tracking-error/holdings/NAV histories unknown.

Historical/current traded EOD comes from the already captured official CM
reports, not a new download, copied clone logic, index series or NAV:

| Source session | Symbol/series | Source ISIN | Traded Close | Traded quantity | Source turnover |
|---|---|---|---|---|---|
| 2016-09-01 legacy | NIFTYBEES/EQ | INF732E01011 | 894.34 | 44842 | 40127740.71 |
| 2016-09-01 legacy | GOLDBEES/EQ | INF732E01102 | 2782.4 | 17826 | 49705868.05 |
| 2026-10-16 UDiFF | NIFTYBEES/EQ | INF204KB14I2 | 263.90 | 12464569 | 3284203933.97 |
| 2026-10-16 UDiFF | GOLDBEES/EQ | INF204KB17I5 | 120.20 | 25676862 | 3085663311.55 |

Prices are exchange-traded security prices, quantities fund units, distinct from
NAV/index points; source monetary strings retained. The
[NSE ETF explanation](https://nsearchives.nseindia.com/content/press/04102013.htm)
distinguishes exchange trading from NAV. Exact versioned report monetary scaling
still needs schema documentation before canonical conversion. ISIN changes
demonstrate why symbol equality cannot close continuity, split/unit changes or
dated classification. Only those two sessions inspected; intervening, earlier
and later history untested. Security-history/quote metadata APIs remain unsent
and blocked; successful archives are independent source representations.

## Discovery references and ambiguity

NV-02-04-AC2: current equity CSV has 2,605 rows, SME 580, symbol-change CSV
1,067, name-change CSV 2,329. Checked source column headers, listing dates,
series and exact identifiers rather than names alone. Querying saved catalogue
rows independently gives:

- Exact ISIN `INE002A01018` → RELIANCE; case-insensitive company-name substring
  Reliance → RCOM, RELCHEMQ, RELIANCE, RELINFRA, RHFL, RIIL, RPOWER. Return
  candidates with match type/ambiguity; no automatic first-match resolution.
- Exact current symbol MCDOWELL-N is absent; source symbol-change event says
  MCDOWELL-N → UNITDSPR effective 07-JUN-2024. UNITDSPR is present with
  `INE854D01024`. Current absence is not unknown historical identity or no history.
- LTI → LTIM effective 05-DEC-2022; LTIM → LTM effective 27-FEB-2026; current
  exact LTM exists. The event chain requires separate identity/ISIN reconciliation.
- Current DHFL absent; change file contains DEWANHOUS → DHFL 22-MAY-2012.
  Neither absence nor rename event establishes delisting date or unavailable
  old prices; historical API remained blocked in checkpoint 02.

The chart candidate returns JSON status true and 20 index entries despite
`search=RELIANCE`, with no RELIANCE match; the candidate search parameter is not
verified. Fields include symbol, instrumentType, scripcode, description, exchange,
fullname and type, with no ISIN or effective/publication interval. Current chart
discovery does not prove historic identity, complete catalogue, supported filters
or any intraday scope. No chart-price request was made.

NV-02-04-AC3: exact plans, retrieval instants and content/metadata hashes published;
expected rows above independently checked from captured official CSV/ZIP bytes.
No production discovery/ETF adapter, scheme-history reconstruction or continuous
ten-year claim. [Partition contracts](../capabilities/partitions.md) keep the
catalogue, metadata attributes, dated EOD listing and discovery matches separate.
Source blockers have explicit phase impacts in the [capability report](../capabilities/README.md).
