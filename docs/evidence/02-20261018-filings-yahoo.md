# Phase 02 checkpoint 03 observations — 18 October 2026

Historical evidence; current progress is [STATE](../../STATE.md). Base `b776606`;
the containing checkpoint identifies research scripts, manifest and observations.
Same CPython 3.14.7/uv 0.12.9/unchanged lock as earlier checkpoints. Explicit
`uv sync --frozen --extra yahoo` succeeds with yfinance 1.7.0, pandas 3.0.6,
numpy 2.5.4, curl-cffi 0.16.3. This is frozen Windows reconnaissance, not new
cross-platform or unconstrained-consumer certification.

## Filing procedure and independently inspected examples

`uv run --frozen python tools/probe_sources.py docs/capabilities/probes/03.json .local/phase02/03`
exits 0: 3 archive requests, 3 catalogue probes unsent under the prior circuit.
Ceiling 6 requests/120s, 8 MiB each, 48 MiB total, 2s spacing, no retries.
Explicit official document locators were found by bounded public web research;
no market-page scraping, PDF parser, arbitrary link crawl or inherited data used.

The two financial captures are ordinary XHTML/HTML, with no inline-XBRL fact
elements/namespaces, schemaRef or contextRef. A URL containing `ixbrl` does not
certify inline XBRL. These are rendered integrated financial tables, not evidence
for old XML, bank taxonomies or legacy HTML. No processor is selected.

- `03:filing-2025`: 92,661 bytes, SHA-256
  `2fdffa2d19d0b275b0d3dae9b95ecf515a90c29ad0e84f7fe3134213579e6747`.
  RELIANCE/INE002A01018 consolidated, audited; source caption INR actuals.
  P&L quarter 2025-01-01..03-31 revenue `2645730000000`, annual
  2024-04-01..2025-03-31 revenue `9801360000000`; basic EPS `14.34`/`51.47`
  has its own per-share meaning and is not a monetary-scale/additive concept.
  Balance sheet total assets `19501210000000` at 2025-03-31; annual cash-flow
  operating `1787030000000`, investing `-1375350000000`, financing `-318910000000`.
  Segment revenue Oil and Gas `64400000000`/`252110000000` (quarter/year).
  Segment result/asset/liability tables repeat segment labels with different
  meanings: row label alone cannot be a concept/context key.
- `03:filing-2026`: 51,858 bytes, SHA-256
  `0a22cb0aad493e026a0775fb889341ccbd5f61be355ef3ad194d46592889c629`.
  RELIANCE consolidated unaudited 2026-04-01..06-30. Caption says INR and
  lakhs; monetary revenue source string `3,11,85,000.00`, EPS `15.48`.
  Annual-looking/YTD and quarter columns share the same period for Q1; preserve
  both column contexts instead of deduplicating by value or multiplying EPS.
- `03:ownership-filing`: 541,780 bytes, SHA-256
  `4a2c6577b55fc1c60ed53b0265cfbcdfa6f44b7710bd63075b140de44c4148f1`.
  Content identifies NETWORK18, not RELIANCE; reporting date 2025-09-30,
  despite 2026-02-25 in locator. Summary A promoter/group: 877258759 shares,
  56.891%; B public: 664741259 shares, 43.109%; C: zero. Total shares
  1542000018 and percentages 100.000. Tables contain share counts, voting rights,
  diluted denominators and encumbrances separately; hierarchy cannot be summed
  twice. This is a real numerical reference, not a registered ownership HTML
  decoder or XML-category mapping.

Manual inspection read saved bytes, bounded heading/table snippets and their
unit/period headers. A local BeautifulSoup 4.15.0 research read helped locate
rows; expectations were checked against original table cells, not project parser
output. No such dependency enters the core or selects a production filing parser.
The [minimum manifest](../capabilities/manifest-v1.json) fixes concepts across
all four statement families, bases, units, periods, category hierarchy, reference
intervals, missing taxonomies and next actions. Source assertions require QName,
context, entity, dimensions, instant/duration, unit, decimals/nil/duplicates and
lineage when XML evidence becomes available. HTML contexts are table/column
contexts, never invented XBRL QNames.

## Yahoo procedure and capture boundary

Installed `PriceHistory.history` signature/source inspected: default
`auto_adjust=True`, `actions=True`, `keepna=False`, `raise_errors=False`.
The harness explicitly sets `interval=1d`, start/end, `auto_adjust=False`,
`back_adjust=False`, `repair=False`, `rounding=False`, `keepna=True`,
`prepost=False`, `actions=False`, timeout 30, `raise_errors=True`.
No `download`, guessed endpoint, private transport patch or substitute series.
SDK source still requests event information internally even with `actions=False`;
this option affects returned data and does not prove one HTTP request.

Executed, exit 0:

```text
uv run --frozen python tools/probe_yahoo.py --self-test
uv run --frozen --extra yahoo python tools/probe_yahoo.py .local/phase02/yahoo
uv run --frozen --extra yahoo python tools/probe_yahoo.py --negative .local/phase02/yahoo-negative
```

Six total outer calls, one active child, one attempt per symbol/window, at least
2s between starts, 120s hard child deadline, <=31 returned rows/16 columns/1 MiB
capture. Internal requests/bytes remain unknown; only returned artifact size is
bounded, not the SDK's internal memory/HTTP. Parent stdlib `subprocess.run`
timeout kills and waits; self-test actually exercises timeout, nonzero and success
with stdlib children. Runtime capture self-tests were added alongside this small
research harness, rather than a test-first production worker; production worker,
resource/cancel/Arrow publication tests remain Phase 15. No store writes.

Public `set_tz_cache_location` source forwards to all timezone/cookie/ISIN cache
managers. It is called before Ticker creation into a unique parent-owned temporary
directory; child exit precedes deletion. No persistent SDK cookie directory,
cookie/token hash, raw SDK stderr or unsanitized exception text is retained.
Supported exception mechanism is `raise_errors=True`; inspected errors include
`YFRateLimitError`, `YFTzMissingError`, `YFPricesMissingError`. Default suppressed
errors can return empty frames; missing timezone is not proof of delisting.

Four successful captures each return three sessions:

| Window (end exclusive) | Sessions, independent calendar expectation | Observed both symbols |
|---|---|---|
| 2016-09-01..09-07 | Sep 1, 2, 6; Labor Day Sep 5 closed | Three midnight America/New_York labels with -04 offset |
| 2025-11-26..12-02 | Nov 26, 28, Dec 1; Thanksgiving Nov 27 closed; Nov 28 early close | Three midnight America/New_York labels with -05 offset |
| 2025-11-27..11-28 | Holiday-only request; no usable price rows | Both raise `YFPricesMissingError`, retained as `sdk_error`, never complete |

Calendar expectations checked against [ICE 2016 calendar](https://ir.theice.com/press/news-details/2014/NYSE-Group-2016-Holiday-Calendar-and-Early-Closings/default.aspx)
and [ICE 2025–27 calendar](https://ir.theice.com/press/news-details/2024/NYSE-Group-Announces-2025-2026-and-2027-Holiday-and-Early-Closings-Calendar/default.aspx).
The latter specifies 13:00 Eastern on 2025-11-28. Different observed offsets
test summer/winter labels, not the DST transition itself. Nasdaq-specific
calendar and index publication timing still require their own adapter evidence.

Capture instants start 2026-10-18T17:36:02Z. Metadata identifies INDEX, USD,
America/New_York, ^GSPC/SNP and ^IXIC/NIM. USD is source metadata; canonical
units are price-index points. Sep 1 Close values observed exactly as SDK floats:
^GSPC `2170.860107421875`, ^IXIC `5227.2099609375`. Captures use float.hex,
tagged nonfinite/null, dtype/columns, timezone/ISO/epoch-ns index and selected
metadata before project normalization. They are `sdk_result`, not raw Yahoo wire
bytes or original decimal text; hashes and summary are in
[observations](../capabilities/observations.json). Offline replay cannot undo SDK
transformations, timezone normalization or its own price cleanup.

All sampled sessions were long completed at collection. The initial operational
target is close +15 minutes, including early closes/DST, with collection instant
separate from session date. This is an assumption, not vintage/publication proof.
In-progress bar rejection, corrections/re-fetches, missing/duplicate sessions,
warmup, actual DST transitions and ten-year continuity remain untested here.
Latest-vintage and local capture availability cannot establish strict historical
availability of this exact version.

## Acceptance result

NV-02-03-AC1: concrete manifest published with experimental/blocked targets;
manual numerical examples distinguished from catalogue and decoder support.
AC2: both symbols' exact options, SDK errors/bootstrap/cache boundary, old/recent/
holiday windows and timing limits documented. Pagination/revised catalogues
remain completeness-unverified. AC4: three fresh official filing samples and
independently checked units/period/context examples shape initial schema; missing
XML/bank/legacy families are explicit, not a universal historical feasibility gate.
AC3: exact commands, hashes, environment, artifacts and observed results above;
software checks recorded with the containing checkpoint. No data-readiness or
production-supported filing/Yahoo adapter claim is made.
