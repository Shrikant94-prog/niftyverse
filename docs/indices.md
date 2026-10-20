# Explicit historical index datasets

`niftyverse.indices` keeps `IndexVariant` identity separate from source aliases.
Each variant has a stable `variant_id`, a parent `index_id`, and exactly one of
`price`, `gross_tri`, `net_tri`, or `volatility`. An `IndexCatalogue` resolves
reviewed source aliases at a session date and known-at time; collisions fail.
No ETF or current snapshot serves as a historical series.

`niftyverse.adapters.index_history.fetch_nifty_history` explicitly downloads
one `price`, `valuations`, or `tri` window using a caller-owned `DirectTransport`.
Pass `start` inclusive and `end` exclusive, at most 366 days. It returns raw
`Download` bytes; it does not open storage, resolve identity or claim coverage.
The transport allows only the three verified read-only Nifty query POST routes
with bounded JSON bodies and its shared acquisition budgets. Redirects fail.

Decode retained bytes with `decode_index_prices`, `decode_index_valuations`, or
`decode_index_tri`. Supply the explicit catalogue, requested variant, source ID,
locator, dates and known-at instant. Source dates, exact decimals, null markers,
SHA-256 and row locators survive. Only the observed list schema generation is
supported; errors, current snapshots, incompatible variants and poisoned rows
raise `ValidationError` before returning a partition.

`IndexPrice` holds price OHLC in index points, or volatility OHLC in
`volatility_percent_annualised` for a volatility variant. `IndexTRI` holds one gross or net level
in index points. `IndexValuation` holds PE/PB ratios and dividend yield in percent
(1.52 means 1.52%, not .0152). A genuine zero stays zero; null values retain a
`source_null` reason on publication. Signed source PE/PB remain signed;
`assumptions` flags unavailable/nonpositive ratios for consumers requiring
positive valuations. The library does not calculate prices from valuation data.

Use `index_history` with an evidenced `Calendar`, explicit dates, known-at and
source-completeness evidence to compare each dataset independently with expected
sessions. Missing observations, unknown sessions, null fields and incomplete
source windows remain partial. Closed days have no invented observations.
An empty response on a trading day cannot certify no-data. A calendar known only
later cannot enter an earlier selection.

`join_index_datasets` performs a full outer date join with separate typed
`price`, `valuation`, `gross_tri` and `net_tri` members. A valuation-only date
does not acquire a price; a price-only date does not acquire valuations. Joining
does not upgrade coverage or fill gaps. Incompatible indices or duplicate
date/variant rows fail.

`niftyverse.storage.indices.make_index_batch` maps one source capture and one
dataset to `index_daily`, `index_tri` or `index_valuations`. Partition universe
contains explicit variant IDs; basis is the variant kind for price/TRI and
`valuation_ratios_percent` for valuations. Requested fields must belong to the
dataset. The shared `ValidatedBatch` checks schema, identity, units, basis,
capture linkage, null reasons and completeness for both DB and direct output.
Values exceeding decimal128(38,8) precision fail rather than round.

Publish complete batches with the existing `publish`/`Store` boundary, or use
`write_direct` for CSV/Parquet without DuckDB. Persistent partial partitions stay
staged; direct partial exports require explicit `allow_partial=True`. Raw source
bytes and publication metadata preserve collection/check/known-at and immutable
assertion occurrence identity. Schema migration v5 adds only the three index
tables and retains transactional rollback and pre-migration backups.

[Measured source evidence](capabilities/phase08-index-observations.json) covers
only NIFTY 50 on 1–2 September 2016 and 14–16 October 2026. The official
[history page](https://www.niftyindices.com/reports/historical-data),
[factsheet](https://www.niftyindices.com/Factsheet/ind_nifty50.pdf), and
[methodology](https://www.niftyindices.com/Methodology/Method_NIFTY_Equity_Indices.pdf)
separate price and gross/net total return. The adapter preserves reported levels
without reconstructing dividends, tax or historical vintages. No continuous
ten-year coverage or launch-time availability follows from these sampled responses.

`fetch_vix_history` explicitly downloads the verified NSE historical GET route.
`decode_vix_history` requires the historical EOD schema and a volatility variant;
it uses `EOD_TIMESTAMP` for the session date. The source ordering timestamp is
retained raw and never promoted to publication time. `assess_vix_capability`
returns `experimental` only for the exact source/window with nonempty validated
rows and a fully reconciled evidenced calendar; current-only, empty, unknown-grid
and malformed responses return a reason-coded `blocked` capability. A failed
route remains blocked even when another source route works.

NSE VIX GET observations verify the same two sampled windows, with all five OHLC
rows checked independently. The
[NSE definition](https://nsearchives.nseindia.com/s3fs-public/inline-files/white_paper_IndiaVIX.pdf)
specifies annualised percentage, retained without dividing values by 100.
The distinct Nifty historical VIX POST returned redirects and remains blocked.
