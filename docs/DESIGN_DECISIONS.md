# Decisions for the lean fresh start

Recorded 18 October 2026 from the owner's instructions and the delegated design choices. This file explains baseline choices; it is not a status ledger or a document to load every session.

## Workflow and implementation baseline

The owner selected a fresh implementation from Phase 00, one local state record with Git history, and phase-level autonomous goals with sequential internal checkpoints. Remove the GSD runtime requirement and its generated planning/status hierarchy. Keep product requirements and acceptance evidence. Existing code, environments, test results, and visual approvals are historical and do not establish this project's readiness.

Preserve original phase/outcome/acceptance identifiers. Phase 00 criteria, R10, and the framework portion of AM-12 are deliberately revised for a portable multi-file baseline, selective loading, and disk-based resume. No change to the Python 3.14 pin is implied. This is a documentation/runtime amendment, not removal of software correctness requirements.

## Direct extraction: retain no-DuckDB execution

Use one normalization and validation contract producing typed Arrow batches; persistent and direct sinks consume the same validated data. Direct extraction does not create or open DuckDB, even temporarily. Test full value/schema/null/provenance parity and rejected-input side effects across sinks. Implement only sink-specific serialization and publication at the boundary.

The alternative mandatory temporary DuckDB path would change the existing output contract, add disk/connection cleanup to every extraction, and still require explicit CSV encoding and parity tests. It is not needed to fix the observed validation weaknesses. Revisit only if a measured workload demonstrates an advantage and the output contract is deliberately changed. No in-memory/history-sized materialization: direct sinks must batch or spool bounded data.

## Corporate actions: split/bonus first

Retain raw demerger/spin-off/rights/dividend/merger facts and precise evidence. First-release adjusted prices support split/bonus only. Unsupported economic actions flag affected returns as incomplete under the existing quality policy; they must not masquerade as reliable uninterrupted momentum or total-return series.

The proposed spin-off price-ratio basis needs its own verified source, factor availability time, simultaneous-action ordering, price-versus-volume rules, and return interpretation. Do not infer these from an ex-date or mechanically apply a share factor to volume. Defer this additional adjustment basis until those contracts and independent examples are established. Preserving raw events keeps that extension possible.

## Filing processors and source leads

Do not mandate lxml as a complete XBRL processor or silently adopt generic XML scraping. Evaluate a bounded standards-aware implementation against actual NSE families, offline taxonomy resolution, resource limits, and Python 3.14. lxml may be a component if evidence supports it. Content-based dispatch and per-field units remain mandatory.

Use official archives for bulk history where suitable. New-plan route names, archive-era boundaries, MTO layouts, viewer HTML, and alleged CDN behavior are candidate research leads, not verified facts by repetition. A request-date versus internal report-date mismatch must be diagnosed without automatically calling the requested date a holiday. Details are retained in [candidate leads](CANDIDATE_LEADS.md), read only during relevant source discovery.

No TLS/browser impersonation fallback, CAPTCHA workaround, proxy rotation, or new provider is authorized by this rewrite. Date-only effective events and value-publication availability remain distinct; an action becoming effective does not prove every associated factor/value was known before a decision.

## Delivery order and completion

Keep complete phases as goals, avoiding partially completed phases spread across waves. Run 00–09, then 12–18 to obtain the reference research path, then 10–11, then integrated API/UX/release 19–22. Phase 19 still waits for derivatives because its acceptance includes executable derivative examples. Filing decoders remain in Phase 03, so later local parsing has an actual prerequisite.

Phase 06 may remain blocked on the external input while explicit-universe 07–09 work proceeds; that is a scoped dependency exception, not completion of historical membership. Source-specific blocked families never gain support labels. The full release still includes every original requirement. No new delivery-time estimate is asserted.
