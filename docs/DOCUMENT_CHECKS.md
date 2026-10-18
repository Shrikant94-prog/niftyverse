# Documentation delivery checks

This report concerns the document bundle only. Phase 00 has not been executed, and no software, provider availability, input audit, or historical-coverage result is claimed.

## Verification procedure

Run from the bundle root:

```text
python tools/check_docs.py --self-test --baseline
```

The read-only checker covers local document links and anchors, retained requirement/decision/amendment/outcome/acceptance IDs, all phase gates, dependency order and brief-header consistency, root-file size budgets, unresolved citation placeholders, Markdown fence balance, and delivered static-file fingerprints. Its small positive/negative fixtures exercise broken links, missing anchors, omitted IDs and invalid dependency order.

The baseline fingerprints exclude STATE and this report. They identify the delivered static revision; they do not certify semantics or become another progress register. After an intentional contract change, normal checks still apply; `--baseline` may correctly report divergence from the original delivery.

## Design review scope

- Preserved the original product contracts and stable identifiers while replacing the execution framework, Phase 00 bootstrap, R10 baseline mechanics and the framework part of AM-12 explicitly.
- Checked dependency ordering, including source decoders before local parsing and both derivative and research capabilities before integrated API acceptance.
- Separated bounded source investigation, verified small intervals and full historical readiness; unavailable inputs do not become successful tests.
- Chose shared validated Arrow batches with no DuckDB in direct extraction, and split/bonus-only initial adjustment semantics. Rationale is in [DESIGN_DECISIONS](DESIGN_DECISIONS.md).
- Kept one mutable execution record, selective reading routes and targeted repair review. No installed runtime settings or original repository files were changed.

These checks reduce documentation drift; they do not prove that the agent will execute well. The real selective-loading/resume check belongs to Phase 00. Each implementation phase still requires observed acceptance evidence.

## Observed delivery result — 18 October 2026

The command above completed successfully (exit code 0):

```text
Negative/positive fixtures: link, anchor, omitted ID, and dependency checks passed.
PASS: 48 Markdown files; local links/anchors; 30 requirements; 17 decisions; 26 amendments; 76 outcomes; 259 acceptance IDs; 23 phase gates; dependency order; root-file budgets. Static baseline fingerprints match.
These are documentation checks, not software, source-availability, or historical-coverage tests.
```

| Root file | Whitespace-separated words |
|---|---:|
| AGENTS.md | 627 |
| STATE.md | 597 |
| PLAN.md | 1059 |

The bundle has 14 topic specifications and 23 static phase briefs. Only AGENTS and STATE are mandatory startup reads; PLAN and references are read selectively. These counts are document sizes, not measured runtime token usage.

## Observed revision 2 result — 18 October 2026

The command above completed successfully (exit code 0):

```text
Negative/positive fixtures: link, anchor, omitted ID, and dependency checks passed.
PASS: 48 Markdown files; local links/anchors; 30 requirements; 17 decisions; 26 amendments; 76 outcomes; 259 acceptance IDs; 23 phase gates; dependency order; root-file budgets. Static baseline fingerprints match.
These are documentation checks, not software, source-availability, or historical-coverage tests.
```

| Root file | Whitespace-separated words |
|---|---:|
| AGENTS.md | 714 |
| STATE.md | 597 |
| PLAN.md | 1059 |

The bundle has 14 topic specifications and 23 static phase briefs. Only AGENTS and STATE are mandatory startup reads; PLAN and references are read selectively. These counts are document sizes, not measured runtime token usage.
