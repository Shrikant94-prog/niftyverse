# Transport and bounded decoding

**Read when:** HTTP/session/retry changes, archive handling, Yahoo worker lifecycle, or untrusted filing decoding.

**Authority:** detailed product contract, revision 18 October 2026. Implementation and dataset support are not claimed. Progress belongs only in root STATE.

## Section lookup

- [9.1 Concurrency policy](#s9-1)
- [9.2 Session lifecycle](#s9-2)
- [9.3 Error taxonomy and policy](#s9-3)
- [9.4 CSV/ZIP defenses and normalization](#s9-4)
- [9.5 Yahoo SDK boundary and bounded execution](#s9-5)
- [9.6 Filing-document safety and dispatch](#s9-6)

Read the selected section and its necessary dependencies; this lookup is not a full-file reading checklist. Original section numbers are retained as stable references.

<a id="s9"></a>
## 9. Transport, rate limits, and fault handling

<a id="s9-1"></a>
### 9.1 Concurrency policy

For direct NSE/NIFTY adapters, use one scoped `httpx.AsyncClient` per provider/session policy, managed with async context managers. Yahoo uses the explicit SDK boundary in [§9.5](transport.md#s9-5). HTTP/2 is optional negotiation with HTTP/1.1 fallback, not a performance guarantee. [HTTPX HTTP/2 documentation](https://www.python-httpx.org/http2/)

**Initial design budgets:**

| Control | Initial value | Interpretation |
|---|---|---|
| NSE/NIFTY request rate | 0.5 requests/second; burst 1 | Conservative engineering default; not an official safe threshold |
| NSE-family in-flight requests | 2 across related hosts | Shared budget prevents adapters multiplying pressure |
| Global orchestration concurrency | 4 | Direct HTTP requests plus active SDK jobs; SDK internal HTTP counts are not observable as one request |
| Attempts | 3 total per retryable request | Includes the first attempt; no recursive retry |
| HTTP timeouts | Connect 10s, read 30s, write 30s, pool 10s | Per-attempt limits; job also has a total retry/wait budget |
| JSON body limit | 32 MiB | Stream-count bytes before decoding; split windows if possible |
| Archive limits | 128 MiB compressed; 512 MiB expanded; 16 members; ratio 100 | Configurable bounds, reject oversized/deceptive archives |
| Batch target | Up to 65,536 rows or 16 MiB | Flush on either limit; never accumulate whole history |
| Pending normalized batches | 8 | Backpressure reaches fetch workers |
| DuckDB memory budget | 2 GiB initial | DB budget only, not total-process memory guarantee |

No documented universally safe NSE requests/second threshold has been established from the local research. Do not describe these settings as approved, block-proof, or an SLA. Respect `Retry-After`; reduce pressure on throttling. Do not auto-increase rates after short success streaks. Record actual budgets in the build manifest.

Budgets are shared across all clients/adapters within the owning process, not recreated for every dataset. They are not a distributed limiter across computers or unrelated processes. Document one active acquisition process per provider/account/IP context as the supported operating pattern; multiple-store collectors must not be recommended as a way to multiply rate limits. Source discovery/health probes count against the same budget.

HTTP concurrency and CPU parallelism are separate. Coordinate Polars/DuckDB worker budgets to avoid oversubscription. CPU decoding/transforms and DuckDB calls must not block the notebook event loop; use bounded workers with clearly owned connections. Do not create one task per row, contract, or decade of symbol windows eagerly.

<a id="s9-2"></a>
### 9.2 Session lifecycle

- Reuse connection pools and cookie jars for the source session. Headers are documented and minimally required; never randomize identities for bypass.
- Serialize any verified cookie/bootstrap refresh so concurrent requests do not all reinitialize the session.
- At most one session refresh for an appropriate authentication/session failure before normal attempt limits apply.
- Persistent cookie storage is off by default; cookies/tokens are excluded from logs, fixtures, hashes, and exports.
- A repeated 403/challenge response opens the source circuit and returns an actionable blocked status. Do not parse HTML challenge pages as JSON or start a CAPTCHA workaround.
- Explicit corporate proxy configuration may be supported through HTTPX configuration; proxy rotation for access bypass is not a feature.

<a id="s9-3"></a>
### 9.3 Error taxonomy and policy

| Error family | Behavior | Resume/visibility |
|---|---|---|
| Connection reset, bounded timeout, retryable 5xx | Backoff with full jitter within attempt/elapsed budget | Retain attempts; retry only idempotent/read operations |
| 429 | Honor server delay; reduce source pressure | If delay exceeds job budget, persist `deferred_until`; no busy loop |
| 401/session invalid | One contract-supported refresh, then fail | No credentials/cookies in message |
| 403/challenge | Stop affected source circuit | Human-readable blocked reason; other independent sources continue |
| 404 archive | Classify against registry/calendar/publication expectations | Not automatically a valid empty trading day |
| Invalid JSON/CSV/ZIP or supported filing document | Retain bounded raw evidence, quarantine | No indefinite retry of a deterministic parse failure |
| Critical schema drift | Quarantine affected partition, emit contract issue | No silent cast/drop of critical fields |
| Noncritical extra fields | Preserve/diagnose, continue if contract remains valid | Record observed schema fingerprint |
| Identity/unit/financial inconsistency | Quality error; reject or quarantine by rule | Exact keys and remediation provided |
| Disk full, writer lock, migration mismatch | Stop publication safely | Coverage remains unchanged; actionable recovery |
| Cancelled | Stop scheduling; unwind workers; commit completed units or roll back active unit | Report durable completed work and resume ID |

A `BuildReport` contains typed failures. Never return an empty DataFrame to represent every failure, swallow exceptions in broad handlers, or exit the interpreter from library code. `raise_for_failures()` is an explicit convenience for applications that require all requested datasets.

<a id="s9-4"></a>
### 9.4 CSV/ZIP defenses and normalization

Allow only configured official hosts and approved redirect targets. Detect content mismatch before parsing. Read archives with bounds on member count, size and expansion; reject encrypted files, nested archives, traversal paths, absolute paths, and unexpected types. Do not extract arbitrary member paths to disk. Parse selected members through bounded streams or controlled temporary files.

Use explicit dataset encodings, delimiters, header mappings and missing-value tokens. Reject duplicate headers, silent truncated rows, ambiguous dates, and numeric overflow. Retain filename/member/row provenance. Distinguish bhavcopy schema versions by verified registry and header signatures, not only by download date.

<a id="s9-5"></a>
### 9.5 Yahoo SDK boundary and bounded execution

The direct HTTPX session/retry/body limits above apply to NSE/NIFTY adapters. yfinance owns Yahoo HTTP/bootstrap calls, so do not claim the HTTPX limiter sees them or that one SDK invocation equals one HTTP request. Initial Yahoo budgets: one active worker call, minimum two seconds between call starts, one outer attempt per planned window, finite per-request SDK timeout (initially 30 seconds), and a hard job deadline (initially 120 seconds). Measure internal behavior during contract discovery; display SDK-call counts separately, with underlying request counts unknown unless actually observed. A rate-limit/challenge result blocks or defers Yahoo jobs; no retry multiplication or transport fallback added by the project to evade it.

Windows-safe process ownership is required: use a spawn-safe worker entry point, no worker database writes, bounded IPC/artifact sizes and explicit terminate/join on deadline or cancellation. Completed captures pass through normal validation and publication; interrupted captures remain incomplete. The Yahoo extra being absent blocks only requested Yahoo work with an installation hint; independent NSE jobs continue. Offline replay imports no yfinance and performs no network calls.

yfinance documents persistent timezone/cookie caching. Direct its supported cache-location control to a controlled local worker-session directory before first use; verify the pinned release's behavior, exclude cookies/tokens from hashes/logs/fixtures/backups and remove only that owned temporary cache at worker-session end. Persistent SDK cookie caching requires explicit configuration and documentation. SDK error output is captured/redacted into structured diagnostics and must not corrupt CLI stdout. [yfinance caching](https://ranaroussi.github.io/yfinance/advanced/caching.html).

<a id="s9-6"></a>
### 9.6 Filing-document safety and dispatch

Use the same approved-host/redirect, request, retry and raw-capture budgets for official document acquisition. Detect MIME/root/namespace/table signatures; challenge/login/error HTML cannot satisfy a filing contract. No unrestricted document-link recursion. Initial XML/HTML body cap is 32 MiB; additionally bound depth, node/fact/context counts, continuation traversal, expanded text, CPU time and memory. Freeze finite tested limits in the parser contract before declaring support; reject over-budget inputs without partial-success coverage.

Disable external entities, external DTD resolution, XInclude and implicit file/network access. HTML DOCTYPE text is inert; never execute scripts or load page resources. Taxonomy/schema/linkbase references resolve only through an explicitly acquired, hashed, versioned local package with a closed dependency map; unknown references produce `taxonomy_unavailable`. Absolute/relative references cannot escape it. Shared-exchange namespace URIs identify concepts and are not acquisition instructions. Apply archive defenses to taxonomy ZIPs too.

Keep untrusted parsing separate from database writing; use an owned bounded worker when processor isolation is needed, including cancellation/deadline cleanup. Unsupported taxonomy/format/inline constructs, invalid documents, missing dependencies and semantic conflicts have distinct typed diagnostics. Keep raw references for repair/replay; never retry deterministic parser errors indefinitely or silently switch to today's JSON summary.
