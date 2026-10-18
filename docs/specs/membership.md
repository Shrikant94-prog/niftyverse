# Historical membership and corrections

**Read when:** NIFTY 500 input audit, correction evidence, interval replay, or membership-dependent research.

**Authority:** detailed product contract, revision 18 October 2026. Implementation and dataset support are not claimed. Progress belongs only in root STATE.

## Section lookup

- [8.1 Inherited input findings to reproduce](#s8-1)
- [8.2 Independent evidence](#s8-2)
- [8.3 Required workflow](#s8-3)
- [8.4 Publication gates](#s8-4)

Read the selected section and its necessary dependencies; this lookup is not a full-file reading checklist. Original section numbers are retained as stable references.

<a id="s8"></a>
## 8. NIFTY 500 verification and correction workflow

The counts and notice comparisons below are inherited evidence from the previous plan. This fresh project has not rerun the audit. Verify the exact input hash before treating counts as reproduced; no source file is bundled.

<a id="s8-1"></a>
### 8.1 Inherited input findings to reproduce

Input: [nifty500_historical_constituents_2010-01-01_to_2026-08-31.csv](../INPUTS.md). User-reported origin: niftyhistory.in; exact export provenance is not independently established.

| Check | Inherited result to reproduce |
|---|---|
| SHA-256 | `f3b4ce4dc430b6e88a302096551e576621fb6bdd45c3a1344a5204bd1957a091` |
| Header | `effective_date,index_type,inclusions,exclusions,symbols` |
| Rows | 72, all `Nifty500` |
| Recorded dates | 2010-06-04 to 2026-03-31; ascending, no duplicate dates |
| Snapshot sizes | 500 unique symbol strings each |
| Distinct strings | 756; not yet 756 resolved securities |
| Transition replay | 50 of 71 fail literal `previous − exclusions + inclusions = next` |
| Duplicate event tokens | 11 rows contain duplicate inclusion/exclusion tokens |
| Weekend dates | Five; flags for historical-calendar verification, not automatic repairs |

The 21 internally consistent transitions do not prove historical correctness. Causes of mismatches are unknown; renames, omitted events, and bad source data are possibilities, not established explanations. An internal-space token such as `M& M` must not be silently fuzzy-matched.

<a id="s8-2"></a>
### 8.2 Independent evidence

| Event | Supplied row | Official evidence |
|---|---|---|
| March 2025 | March 31; three inclusions/exclusions | March **28**; 30 additions/removals; official identifier `NTPCGREEN` differs from the CSV's `NTPC` |
| September 2025 | Three inclusions/exclusions | 18 additions/removals effective September 30 |
| March 2026 | March 31; three inclusions/exclusions | March **30**; 31 additions/removals |

See [CSV March 2025](../INPUTS.md), [CSV March 2026](../INPUTS.md), and official notices for [February 2025](https://www.niftyindices.com/Press_Release/ind_prs21022025.pdf), [August 2025](https://www.niftyindices.com/Press_Release/ind_prs22082025.pdf), [February 2026](https://www.niftyindices.com/Press_Release/ind_prs23022026.pdf).

An official notice also describes a temporary component represented by `DUMMYHDLVR` and later `KWIL`, with February 2026 exclusion affecting NIFTY 500. Neither string occurs in the input. [Official temporary-component notice](https://niftyindices.com/Press_Release/ind_prs20022026_1.pdf)

**Inference:** a verification process restricted to semiannual rebalances will miss some membership events. Implement event-driven intervals and temporary component entities; do not invent prices or tradability for synthetic/unlisted components.

<a id="s8-3"></a>
### 8.3 Required workflow

1. Preserve original bytes, source statement, hash, and import time. Never overwrite the CSV.
2. Produce an import report with row-level structural issues, duplicate tokens, snapshot/event disagreements, dates and unresolved identifiers.
3. Resolve aliases against dated evidence; represent unresolved tokens explicitly.
4. Establish an independently verified starting snapshot for each claimed coverage interval.
5. Replay all verified membership events, including ad-hoc and temporary-component events, with effective and announcement times.
6. Independently check snapshots; internal set consistency alone is insufficient.
7. Write proposed corrections to a separate ledger with original/replacement values, affected dates, evidence URL/local hash, rationale, author/reviewer, and status.
8. Apply accepted corrections as a new version, re-run replay and independent checks, and publish only verified intervals.
9. Invalidate dependent research outputs for affected intervals; preserve prior snapshots and explain differences.
10. Export unresolved work as a reviewable CSV/Markdown report. Implementation of this workflow must not depend on automating PDF/HTML extraction.

The filename's August 2026 endpoint is not evidence that membership through that date is complete. Do not extrapolate verified coverage beyond established evidence. Weekend flags require actual historical session/effective-date rules, including special sessions.

<a id="s8-4"></a>
### 8.4 Publication gates

Statuses: `raw`, `structurally_valid`, `identity_resolved`, `reconciled`, `independently_verified`, `quarantined`, `superseded`. A single row can carry multiple issue codes; verified intervals are computed from evidence, not manually toggled without trace.

The supplied file is initially a **negative integration fixture and unverified research input**. Verified corrections are substantive data work. Dependent universe builds stop at unverified intervals under strict policy. Independent index/Yahoo/explicit-symbol jobs may continue and report separate readiness. Latest-vintage mode must not pretend unverified membership is verified; permitting exploratory unverified membership requires an explicit policy flag and prominent output label.
