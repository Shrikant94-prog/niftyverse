# Public API contracts and examples

**Read when:** Implementing a public selector, result lifecycle, local parser, direct extraction, or SQL interface.

**Authority:** detailed product contract, revision 18 October 2026. Implementation and dataset support are not claimed. Progress belongs only in root STATE.

## Section lookup

- [13.1 Declarative acquisition](#s13-1)
- [13.2 Separate bounded derivatives/report plan](#s13-2)
- [13.3 TOML equivalent](#s13-3)
- [13.4 Fluent ad-hoc requests](#s13-4)
- [13.5 Research panels](#s13-5)
- [13.6 Ad-hoc DuckDB SQL and result lifecycle](#s13-6)
- [13.7 Lightweight extraction, local filings and inspection](#s13-7)

Read the selected section and its necessary dependencies; this lookup is not a full-file reading checklist. Original section numbers are retained as stable references.

<a id="s13"></a>
## 13. Public API design

The examples in this section are **proposed interface pseudocode**, not existing executable library code. The implementation agent must turn their intent into documented, typed APIs and executable tests. No legacy public names are retained.

<a id="s13-1"></a>
### 13.1 Declarative acquisition

```python
from niftyverse import (
    Client, DataPlan, Dataset, DateWindow, Universe,
    SourcePolicy, QualityPolicy, StoreConfig,
)

plan = DataPlan(
    name="nifty500-research",
    config_version=1,
    window=DateWindow(start="2016-09-01", end_exclusive="2026-09-01"),
    universe=Universe.index_history(
        index="NIFTY 500",
        membership_file="inputs/nifty500.csv",
        corrections_file="inputs/membership-corrections.csv",
        delisted_file="inputs/delisted.csv",
        required_status="independently_verified",
    ),
    datasets=[
        Dataset.equity_daily(fields="available"),
        Dataset.equity_delivery(),
        Dataset.index_daily(indices=["NIFTY 50", "NIFTY 500"]),
        Dataset.index_valuations(indices=["NIFTY 50", "NIFTY 500"]),
        Dataset.index_total_returns(indices=["NIFTY 50", "NIFTY 500"]),
        Dataset.corporate_actions(),
        Dataset.announcements(),
        Dataset.corporate_events(),
        Dataset.financial_filings(),
        Dataset.financial_facts(
            statements=["profit_loss", "balance_sheet", "cash_flow", "segments"],
            source_formats=["json", "xbrl", "ixbrl", "legacy_html"],
            coverage="available", required=False,
        ),
        Dataset.ownership_filings(),
        Dataset.ownership_facts(
            source_formats=["json", "xbrl", "ixbrl"],
            coverage="available", required=False,
        ),
        Dataset.global_closes(
            series=["SP500_PRICE", "NASDAQ_COMPOSITE_PRICE"],
            provider="yahoo", required=False,
        ),
    ],
    sources=SourcePolicy(official_archives=True, json=True),
    quality=QualityPolicy(unverified_membership="block", conflicts="quarantine"),
    store=StoreConfig(path="D:/quant-data/nse"),
)

async with Client.from_plan(plan) as client:
    explanation = client.explain(plan)       # local only; no hidden fetch
    report = await client.build(plan)        # explicit network/persistence
    report.raise_for_failures()              # required failures only by default
    snapshot = report.snapshot               # partial status remains visible
```

Paths and drive letters are examples, not assumptions about this machine. Local manifest files must exist; missing optional files are omitted from config rather than fabricated. `required=False` in this example allows a price panel to build with visible partial fundamentals/global coverage; users can mark specific concepts/series required. API/module implementation remains required regardless of this per-plan choice.

Membership corrections are accepted through the reviewed ledger, not automatically trusted just because a filename is supplied. Imported identities and membership become versioned dependencies.

<a id="s13-2"></a>
### 13.2 Separate bounded derivatives/report plan

```python
derivatives = DataPlan(
    name="historical-derivatives-workbench",
    window=DateWindow(start="2025-01-01", end_exclusive="2025-04-01"),
    universe=Universe.underlyings(["NIFTY", "BANKNIFTY"]),
    datasets=[
        Dataset.derivative_contracts(types=["index_future", "index_option"]),
        Dataset.derivative_daily(expiries="within_window", strikes="all_listed"),
        Dataset.participant_positions(),
        Dataset.participant_volumes(),
        Dataset.market_flows(coverage="available", required=False),
    ],
    limits={"max_planned_requests": 2000, "max_contracts": 25000},
    store=StoreConfig(path="D:/quant-data/nse"),
)
```

The limits are example budgets, not measured workload size. `within_window` refers to actual expiries in that interval; discovery reports contracts excluded by that selection. To include later expiries traded during the window, the caller explicitly chooses `traded_in_window`. Unsupported historical contract discovery produces a capability error rather than scanning guessed strike grids. Report datasets use their own market-wide scope even when the derivative universe is narrow; explain this in the compiled plan.

<a id="s13-3"></a>
### 13.3 TOML equivalent

```toml
config_version = 1
name = "small-equity-research"

[window]
start = "2025-01-01"
end_exclusive = "2025-04-01"

[universe]
kind = "symbols"
exchange = "NSE"
symbols = ["INFY", "TCS"]

[store]
path = "D:/quant-data/nse"

[sources]
official_archives = true
json = true

[quality]
conflicts = "quarantine"

[[datasets]]
kind = "equity_daily"
required = true

[[datasets]]
kind = "corporate_actions"
required = true

[[datasets]]
kind = "global_closes"
series = ["SP500_PRICE", "NASDAQ_COMPOSITE_PRICE"]
provider = "yahoo"
required = false
```

Reject unknown keys and incompatible dataset parameters with a precise config path. Relative paths resolve against the config file's directory, not an unpredictable working directory. Secrets are excluded from persisted config/fingerprints; include secret-provider identity only where necessary. TOML and Python forms normalize to the same semantic plan hash.

Yahoo examples require the optional `yahoo` extra and no FRED key. Series IDs map through the pinned provider dictionary; provider-specific symbols do not become canonical IDs. A retired FRED provider/key configuration produces an explicit unsupported-provider/configuration error, not a silent source substitution. The source change is approved before implementation; no compatibility wrapper or active FRED dependency is introduced.

<a id="s13-4"></a>
### 13.4 Fluent ad-hoc requests

```python
async with Client(store="D:/quant-data/nse") as client:
    request = (
        client.equities(["INFY", "TCS"])
        .between("2025-01-01", "2025-04-01")
        .with_delivery()
        .adjusted(basis="split_bonus")
        .with_features(sma=[20, 50], rsi=14)
    )
    request.explain()                        # no I/O
    result = await request.fetch()           # explicit work, same compiler/store
    frame = result.to_polars()               # explicit materialization
    table = result.to_arrow()
    result.explore()                         # explicit optional notebook UI
```

Requests are immutable; branching one request does not mutate another. Do not hide I/O in attribute access, `repr`, iteration over metadata, or dataframe conversions. The fetch uses a configured store and returns metadata tied to a published result/snapshot. Large result conversions require an explicit memory/materialization limit override; streaming batches and lazy snapshot scans remain available.

Ad-hoc fetch and DataPlan acquisition use the same normalization, validation, coverage and atomic-publication path, including cache hits. Cached partitions may reuse their recorded validation under the pinned policy; a new policy creates a new assessment/result, not silently different old snapshots. Fetch results promise conformance to the named rules and evidence, with visible warnings/gaps, not perfect market truth. Read-only snapshot queries preserve recorded assessments without re-fetching; arbitrary SQL and external dataframe expressions are user transformations and do not automatically inherit a claim of validated feature semantics.

Provide `build_sync()` / `fetch_sync()` for ordinary scripts. They must raise a clear error in an already-running event loop with instructions to use `await`; never patch notebook event loops with `nest_asyncio`. The native async path is the documented notebook path.

<a id="s13-5"></a>
### 13.5 Research panels

```python
research = ResearchPlan(
    name="monthly-cross-section",
    input_snapshot=snapshot.id,
    universe="NIFTY 500",
    decisions=MonthlySessions(first=True, at="09:00", timezone="Asia/Kolkata"),
    availability="strict_historical_evidence",
    features=[
        PriceReturn(sessions=21, basis="split_bonus"),
        PriceReturn(sessions=252, basis="split_bonus"),
        RealizedVolatility(sessions=63, annualization=252),
        AverageTradedValue(sessions=20),
        FinancialFact(concept="revenue", basis="consolidated", period="quarter"),
        OwnershipChange(category="promoter", comparable_periods=1),
        GlobalReturn(series="SP500_PRICE", observations=21),
    ],
    missing_rows="preserve",
    staleness=StalenessPolicy(report_age=True, exclude_after=None),
)
preflight = client.research.explain(research)  # local; reports missing dependencies
# If required dependencies are missing, explicitly build preflight.acquisition_plan
# and bind its new history_bundle using research.with_input_snapshot(new_snapshot.id).
panel = await client.research.build(research)  # never acquires missing inputs implicitly
panel.readiness
panel.snapshot_id
```

This example reports observation age without imposing an arbitrary age cutoff; a researcher can supply a typed dataset-specific cutoff. Concept/category names are validated against verified dictionaries; an unavailable concept cannot silently become another one. GlobalReturn's observation count and timing policy remain distinct from Indian session windows. Run research inside the owning client's context, as in the acquisition example.

The example's explicit **09:00** schedule is an alternative scenario; [§4.1](product.md#s4-1)'s fixed reference workload remains **10:00 Asia/Kolkata**. They produce different plan/snapshot identities and must not share assumed availability. The older handoff's 09:00 description is not the reference benchmark. Neither time is an implicit default or an execution/fill guarantee, and configured decisions require valid session/timing evidence.

<a id="s13-6"></a>
### 13.6 Ad-hoc DuckDB SQL and result lifecycle

```python
with ResearchStore.open_snapshot(
    snapshot.id, store="D:/quant-data/nse", selection="latest_vintage",
) as db:
    result = db.query(
        """
        SELECT instrument_id, session_date, close
        FROM equity_daily
        WHERE session_date >= ? AND session_date < ?
        ORDER BY instrument_id, session_date
        """,
        parameters=["2025-01-01", "2025-04-01"],
    )
    frame = result.to_polars(max_rows=100_000)
    for batch in result.iter_arrow_batches(batch_size=65_536):
        consume(batch)
```

`open_snapshot` pins version selection and exposes stable views. SQL is for trusted local users, not a multi-tenant security sandbox. Values are parameterized; identifiers are selected through validated metadata. Read-only query connections disable unneeded external access and automatic extension installation. Controlled internal Parquet access is configured by the store, not arbitrary SQL URLs.

The example intentionally resolves a history bundle under `latest_vintage` and labels that query result accordingly. A resolved research snapshot retains its fixed decision selections; callers cannot relabel it with another mode. An all-assertions view is explicitly named and retains version keys. Opening a history bundle without an explicit selection exposes metadata/all-assertions views only, not an implicitly latest price table.

Materialized results remain valid after the connection closes. Streaming results require their owning context to remain open and fail clearly afterward. Notebook explorer actions open their own scoped snapshot read connection. Do not keep a hidden writable connection alive because a cell displayed a result.

Pin a query and snapshot with explicit lifecycle behavior: every `iter_arrow_batches()` invocation opens its own bounded cursor over that immutable selection, or reads a retained materialized result; it never silently consumes a shared exhausted iterator. Thus the documented `to_polars()` followed by batch iteration returns equivalent rows. Each cursor requires its context until exhausted/closed; bounded materialized outputs outlive it. Query cancellation interrupts the owned query/connection and joins its worker before disposal; cancellation near canonical commit follows [§11.2](storage.md#s11-2). Closing/replacing an explorer cancels its pending reads, discards stale callbacks and releases connections. Test repeated materialization, concurrent cursor rejection/ownership, disposed contexts and close-during-query behavior.

`to_pandas()` is optional conversion with nullable/date/decimal behavior documented; absence of its dependency gives a concise installation hint. Core research/analytics does not compute with pandas and no legacy NSE wrapper is imported. The explicit Yahoo worker exception consumes yfinance's pandas result at the acquisition boundary only ([§6.5](architecture.md#s6-5)).

<a id="s13-7"></a>
### 13.7 Lightweight extraction, local filings and inspection

Proposed interface pseudocode; Phase 19 finalizes names/types against the shared contracts:

```python
from niftyverse import Client, DataPlan, Dataset, DateWindow, Universe, OutputTarget

plan = DataPlan(
    name="one-company-results", config_version=1,
    window=DateWindow(start="2024-04-01", end_exclusive="2026-04-01"),
    universe=Universe.symbols(["RELIANCE"]),
    datasets=[Dataset.financial_facts(
        source_formats=["json", "xbrl", "ixbrl", "legacy_html"],
        statements=["profit_loss", "balance_sheet", "cash_flow", "segments"],
        coverage="available",
    )],
    # No store: extract supports this; build must reject a missing store.
)
async with Client() as client:
    report = await client.extract(
        plan, output=OutputTarget.csv("outputs/results", retain_raw=True),
    )
    report.raise_for_failures()
    local = await client.parse_filing("inputs/saved-filing.xml")
    frame = local.to_polars()      # Missing identity/timing metadata stays unknown.
    explanation = local.trace(local.fact_ids[0])  # For a successfully mapped fact.
```

Arrow/Polars and Parquet destinations are alternatives under the same `OutputTarget` contract. Python/TOML express the same output/format/partial/raw-retention policy. Local parsing may accept explicit metadata with origin recorded; it never supplies a guessed issuer or publication timestamp. Empty/unsupported input returns typed diagnostics before fact selection. ETFs use an explicit ETF dataset selector; local search, statement views and EOD aggregation retain sections 12.5/12.6 semantics. Persistent snapshot SQL remains the interface for research builds.
