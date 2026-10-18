# External input contract

No research datasets are bundled with this clean project. Read inputs only from an explicit owner-supplied path outside the repository; do not search parent folders or move the originals. Keep the active runtime store in OS-local nonsynchronized storage per [PLAN §11.1](specs/storage.md#s11-1). This storage recommendation does not require relocating an owner-held read-only source file. Do not commit the original data as a test fixture.

## Historical NIFTY 500 membership — needed by Phase 06

- Basename: `nifty500_historical_constituents_2010-01-01_to_2026-08-31.csv`
- SHA-256: `f3b4ce4dc430b6e88a302096551e576621fb6bdd45c3a1344a5204bd1957a091`
- Recorded size: 302057 bytes.
- Header: `effective_date,index_type,inclusions,exclusions,symbols`.
- Prior audit: 72 rows; 756 distinct strings; 50 of 71 transition replays fail. These are inherited audit findings to reproduce, not independent historical certification.
- User-reported origin: niftyhistory.in; precise export provenance unverified.
- Known audit references: source CSV lines 71 and 73 contain March 2025/2026 cases discussed in PLAN §8. Official notice links and retained findings are in that section.

When the input is supplied, validate its hash before comparing audit counts. A mismatch is a different input version; retain both identities and do not force the expected counts. Keep the original read-only. Use independently created synthetic fixtures for parser and correction tests. Missing owner input blocks its audit and associated dataset readiness; it does not prevent bootstrap or unrelated implementation.

The earlier RBI workbook is deferred and intentionally absent. Legacy repositories, blueprints and review reports are not implementation dependencies; their adopted decisions are incorporated in the topic specifications.

## Saved filings and representative source evidence

The user may supply a saved filing by explicit path for offline parsing under [PLAN §13.7](specs/api.md#s13-7). Record its hash, origin and supplied metadata; parsing cannot establish issuer authenticity or an unknown publication date. Never overwrite the original or fetch a missing taxonomy implicitly.

During development, retain a local corpus index identifying real document families/taxonomy versions and independently checked values, units, periods and locators. Start with representative examples for the current parser, then broaden coverage and held-out checks as adapters mature under [PLAN §5.7](specs/sources.md#s5-7). Keep provider captures outside Git and use independently authored synthetic edge cases in tests. No complete fifteen-year corpus is required before foundation work starts.


## Fresh-project input availability

No original input, real filing corpus, or taxonomy package is included in this document delivery. Resolve an explicit owner-supplied path when its phase needs it; never scan personal folders. Historical counts above are expected only for the recorded hash.
