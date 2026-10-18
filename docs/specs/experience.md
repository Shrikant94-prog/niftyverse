# Terminal and notebook experience

**Read when:** CLI/display behavior. Read terminal or notebook sections only as needed.

**Authority:** detailed product contract, revision 18 October 2026. Implementation and dataset support are not claimed. Progress belongs only in root STATE.

## Section lookup

- [14.1 Command surface](#s14-1)
- [14.2 Progress mockup](#s14-2)
- [14.3 Interaction rules](#s14-3)
- [14.4 Definition of done](#s14-4)
- [15.1 Automatic display card](#s15-1)
- [15.2 On-demand explorer](#s15-2)
- [15.3 Notebook build progress](#s15-3)
- [15.4 Notebook acceptance matrix](#s15-4)

Read the selected section and its necessary dependencies; this lookup is not a full-file reading checklist. Original section numbers are retained as stable references.

<a id="s14"></a>
## 14. Terminal experience — a product feature

<a id="s14-1"></a>
### 14.1 Command surface

Executable name: **`niftyverse`**. Commands below are the proposed new CLI, independent of legacy names.

| Command | User outcome |
|---|---|
| `niftyverse init` | Create an example config after checking destination conflicts; no download |
| `niftyverse doctor` | Environment, paths, optional dependencies, store health; network checks opt-in |
| `niftyverse sources inspect` | Capabilities, verified dates, endpoint generations and limitations |
| `niftyverse plan explain research.toml` | Local work graph, estimates, cached/missing inputs, blockers |
| `niftyverse build run research.toml` | Execute acquisition with progress and final readiness |
| `niftyverse build resume BUILD_ID` | Resume compatible incomplete work |
| `niftyverse inspect coverage` / `quality` | Actionable gaps, stale partitions and issues |
| `niftyverse universe validate FILE` | Structural and evidence report without modifying the input |
| `niftyverse universe corrections validate FILE` | Validate correction ledger before publication |
| `niftyverse research build RECIPE` | Materialize a versioned research panel |
| `niftyverse query --snapshot ID --sql-file QUERY` | Explicit read-only analytical query |
| `niftyverse export --snapshot ID --format parquet` | Typed portable export; CSV also supported |
| `niftyverse snapshot diff A B` | Explain changes between research datasets |
| `niftyverse repair --plan FILE` | Re-fetch/reprocess selected gaps with a preview |
| `niftyverse store backup` / `restore` / `check` | Verifiable recovery workflow |

Use explicit `build run` and `build resume` subcommands so file paths cannot collide with command names. A command schema test must exercise every documented example. Consistent flags: `--store`, `--output human|json`, `--no-progress`, `--quiet`, `--offline`, `--log-level`.

<a id="s14-2"></a>
### 14.2 Progress mockup

Illustrative output only; counts and durations are not measured promises.

```text
niftyverse  |  nifty500-research
Store: D:\quant-data\nse     Build: b_...     Mode: incremental

Dataset                  Progress          Status
Equity daily             184 / 240          Fetching 2025-03-12
Delivery                 184 / 240          132 partitions reused
Corporate actions         12 /  12          Committed
Financial facts           --               Partial: 3 concepts unavailable
NIFTY 500 membership      --               Blocked: unverified interval

Network: waiting 1.2s for source budget    Committed rows: 128,442
Elapsed: 00:42    Active: 2    Retries: 1    Quarantined: 0

Completed with limitations
Prices ready: 2025-01-01 .. 2025-03-31
Research panel blocked: membership evidence required
Next: niftyverse inspect quality --build b_...
```

<a id="s14-3"></a>
### 14.3 Interaction rules

- One Rich Live controller owns terminal rendering; worker tasks emit events, never print directly.
- Progress totals can be unknown during discovery. Show a spinner and counts; do not invent ETA or percentages.
- Distinguish attempted, downloaded, staged, committed, cached, skipped, quarantined and blocked work. A downloaded file is not a successful committed partition.
- Display source-budget waits and retry delays without flooding logs. Coalesce routine updates to about four refreshes/second.
- Put human progress/diagnostics on stderr. stdout is clean structured JSON or requested table/export output. JSON mode contains no ANSI codes or progress fragments.
- Respect redirected output, `NO_COLOR`, narrow terminals and Unicode limitations. Provide concise final text when interactive rendering is unavailable.
- Ctrl+C cancels safely and prints the resume ID after cleanup. Exit codes: 0 = all required work complete (optional limitations remain in report), 1 = required work failed/quarantined, 2 = invalid input/config, 3 = required source blocked/deferred, 4 = store lock/recovery problem, 130 = user cancellation. For mixed non-cancellation failures, prefer store/config errors over source blocks over other required failures; preserve every issue in JSON.
- Error messages lead with the dataset/period and next action; technical traceback is opt-in. Never display API keys, cookies or sensitive URL parameters.
- In quiet mode, report actionable errors without hiding failure status. No unsolicited browser opening or notebook launch.

Rich supplies progress/live primitives, including notebook-specific refresh behavior; our event adapter must handle explicit notebook refresh rather than assume terminal behavior transfers unchanged. [Rich progress](https://rich.readthedocs.io/en/stable/progress.html), [Rich live display](https://rich.readthedocs.io/en/stable/live.html)

<a id="s14-4"></a>
### 14.4 Definition of done

Capture and review output at 60/100/160 columns; test a redirected pipe and JSON parsing; simulate slow network, repeated throttling, partial dataset failure, offline cache hit, cancellation and resume. Row counts must reflect committed data. Rendering overhead must remain small relative to work and must not block ingestion; a bounded/coalesced display queue can drop intermediate visual updates, never durable build state.

Add explicit CLI routes for `extract`, `filings parse`, `instruments search` and `trace`, using [§13.7](api.md#s13-7) contracts. Distinguish direct file output from existing snapshot `export`; accept a local bundle/result or snapshot explicitly for inspection. Machine output includes structured coverage/failures; optional parser installation hints are scoped to requested formats. No automatic download from search, trace, help or display.

<a id="s15"></a>
## 15. Jupyter experience — lightweight first, interactive on demand

<a id="s15-1"></a>
### 15.1 Automatic display card

Use IPython's MIME display protocol with a plain-text fallback. Prepare summary/preview data when the result is created; rendering itself performs no SQL, network, or full-table conversion. Escape every source string, namespace CSS, and avoid remote fonts/scripts/CDNs. [IPython integration](https://ipython.readthedocs.io/en/stable/config/integrating.html)

```text
Equity history                                      ✓ Snapshot pinned
INFY, TCS   •   2025-01-01 → 2025-03-31   •   124 rows
Basis: split/bonus    Quality: 2 missing delivery observations
Availability: latest vintage    Source: NSE    Snapshot: s_...

Date         Symbol       Close       Volume      SMA20       Trend
2025-03-31   INFY          ...         ...         ...         ▁▂▅▃▆
2025-03-31   TCS           ...         ...         ...         ▂▃▁▅▆

Preview only • 10 of 124 rows • result.explore() for filters and charts
```

Default bounds: at most 20 rows, 12 columns, 120 characters per cell, 120 points per sparkline, and roughly 64 KiB static MIME payload. Summaries show requested/actual dates, basis, source, snapshot, timing mode and prominent quality limitations. These are initial display budgets, tested and configurable. Static previews remain useful in saved/exported notebooks without an active kernel.

<a id="s15-2"></a>
### 15.2 On-demand explorer

`result.explore()` creates optional widgets bound to an immutable snapshot:

- Dataset/column selection, date and instrument filters, stable sort, pagination, missingness summary, provenance/detail panel.
- Filter controls apply to the full query, not only the current page. SQL values are bound parameters; selectable column names/operators come from an allowlist.
- Default page size 200, maximum 1,000. Keyset pagination over a stable sort/key avoids loading the entire dataset.
- Display total counts only when computed; an expensive count runs explicitly or asynchronously with a visible state.
- Debounce controls (initially 250ms), cancel stale queries, and discard out-of-order responses. Each query has its own scoped connection and configurable time budget.
- Time-series charts: price/volume, selected indicators, index comparisons, ownership/financial histories, coverage heatmap, and EOD option-chain strike/expiry views from stored contracts.
- Chart labels state units, raw/adjusted basis, source, snapshot, and timing mode. Gaps remain gaps. No misleading line across missing data by default.
- Limit chart payloads, initially 2,000 points per series and 10 series; downsample for visualization only and label it. Full-resolution analytics use original data.
- Export the selected table/query result to supported files. Save the query/recipe/snapshot reference to reproduce the view.

Use ipywidgets events for controls and Plotly for charts; verify versions together in the optional extra. FigureWidget may require anywidget. A saved static notebook cannot execute kernel callbacks, so keep a meaningful noninteractive fallback. [ipywidgets events](https://ipywidgets.readthedocs.io/en/8.1.0/examples/Widget%20Events.html), [Plotly FigureWidget](https://plotly.com/python/figurewidget/)

<a id="s15-3"></a>
### 15.3 Notebook build progress

`await client.build(plan)` selects a notebook renderer only when a supported frontend is detected or explicitly requested. Show a compact progress widget fed by the same build event stream as the CLI, refreshing at about two updates/second. Cancellation requests propagate to the same executor; the widget does not implement its own retry logic.

An explicit `start_build()` may return a `BuildHandle` with `await handle.wait()` and `await handle.cancel()`. Register task ownership so closing the client cleans up jobs. Do not spawn orphan background threads or automatically continue downloads after kernel shutdown. Re-running a cell against the same plan/store joins or rejects an active build clearly rather than starting duplicate writers.

<a id="s15-4"></a>
### 15.4 Notebook acceptance matrix

Target JupyterLab 4 and Notebook 7 after version verification; test VS Code notebooks where available and document any frontend limitation. Plain IPython/text environments work without widget dependencies. Missing optional extras produce a short actionable hint, not a broken rich representation.

Tests cover: malicious HTML in source labels, very long strings, decimal/null/timezone display, zero/one/million-row results, disposed connections, missing widgets, saved notebook fallback, canceled/slow queries, stale widget responses, unavailable global timing, and unresolved membership. Rendering must not make HTTP calls. Notebook smoke examples execute offline from synthetic or redistribution-permitted fixtures.
