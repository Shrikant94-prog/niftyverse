# Membership audits, corrections and publication

The Phase 06 interfaces are explicit local operations. Importing the modules
does not read files, open a store or acquire data. The original owner CSV stays
at its supplied path; it is never rewritten or bundled into tests.

## Audit a supplied file

```text
uv run --frozen python tools/audit_membership.py <original.csv> --require-original
```

`membership_audit.audit_membership(path, source_statement=..., imported_at=...)`
returns an immutable report. The source statement is attributed, not certified.
The file's native comma-separated fields and explicitly JSON-encoded owned
fixtures are supported. Outer token whitespace is stripped; internal whitespace,
spelling, duplicates and unresolved literal strings remain visible. There is no
fuzzy matching. A different hash gets its own report and never inherits the
original file's expected counts. The optional command gate requires the recorded
hash, all inherited audit figures, notice conflicts and unchanged bytes.

`review_csv()` and `review_markdown()` return text for explicit caller export;
they do not write over the source. Issues can coexist on one row. Weekend flags
require dated calendar evidence and do not establish errors. The targeted notice
checks are manually reviewed comparisons, not a historical event discovery tool.

## Resolve and replay

`membership_identity.resolve_tokens` requires a supplied dated Phase 05
catalogue and explicit temporary aliases. It retains each original token, all
ambiguous/unresolved states and evidence locators. Renames resolve to stable
instrument IDs only where the catalogue establishes them. Retain that catalogue
version/hash alongside any reviewed identity evidence used for a recipe.

`membership.replay` takes an exact original hash, an explicit scope and half-open
date window, a starting `Snapshot`, `Event` records, a separate correction ledger,
independent snapshot checks, reviewed event `Coverage` and a UTC knowledge cutoff.
See [owned examples](../tests/test_membership.py) and the
[integrated example](../tests/test_phase06_gate.py).

Each `Correction` preserves original/replacement records, affected dates,
evidence hashes/locators, rationale, author, proposal time and review decision.
Pending/rejected corrections remain in the recipe without being applied.
Accepted corrections apply only once their review and evidence are known.
Chained changes follow explicit ledger order and must match the exact preceding
record. Missing events can be proposed separately; raw inconsistencies are never
automatically rewritten. Same-date events require distinct explicit ordering.
Announcement dates retain date precision; no midnight publication is invented.

Independent verification requires matching externally evidenced snapshots that
bound the interval, reviewed event completeness for the **same declared scope**,
resolved member identities, and verified replay events. Matching endpoints alone
cannot certify unverified intervening events. A reference whose hash is the
original raw input cannot be its own independent check or event evidence.
Evidence assertions are supplied by a reviewer; the library validates their
structure, lineage, timing and consistency, not the truth of an arbitrary URL.

`Coverage` is a substantive reviewed inventory assertion. One component's notice
cannot establish complete NIFTY 500 coverage. Do not relabel a component scope as
a full index. An undated current list does not establish a historical effective
date. An unknown, contradicted or uncovered region remains quarantined with
reason codes even when processing exits successfully.

Temporary components have a separate stable component identity and no linked
tradable instrument. Later listing is not inferred as a price series.
`security_instrument_ids(on)` returns only evidenced security identities;
listing, session, and price eligibility still require their own checks. Missing
prices never remove an established member or create a terminal zero.

Raw input, structural validation, identity resolution and event reconciliation
are distinct stages. Only computed `independently_verified` intervals permit
`strict_members(on)`; quarantined regions raise `ValidationError`. No exploratory
unverified-universe policy is added here. Full-history readiness remains a later
evidence exercise, separate from this software foundation.

## Publish and retain older versions

`storage.membership.publish_membership(result, new_directory, previous=...,
encoding="parquet")` uses the existing atomic immutable bundle writer. CSV is
also supported. It recomputes the retained recipe before any destination write;
forged result statuses and mismatched pinned parents fail. Blocked regions are
published with explicit reasons and manifest `status="partial"`. A complete
bundle applies only to its exact declared scope/window.

Every bundle retains `recipe.json`, typed interval data, original input hash,
knowledge cutoff, code fingerprints and environment. Accepted corrections create
new membership/output identities, link the previous bundle, and report affected
date spans and membership/verification/evidence changes. That lineage records
supersession without mutating the older bundle. Consumers must pin a bundle ID
and invalidate dependent selections using the recorded spans.

`load_membership(directory)` verifies artifacts and recomputes the recipe before
returning the same strict membership interface. Retained recipes allow logical
replay with pinned code/environment, including older corrected versions, without
reopening or modifying the original CSV. Original/source evidence availability
and authenticity remain separate. Byte-identical regeneration across code,
dependency versions or platforms is not promised. Bundles are small interval
artifacts; this phase adds no production historical provider or research engine.
