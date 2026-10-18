# Phase 02 final capture-boundary review — 18 October 2026

Historical observations; current progress is [STATE](../../STATE.md).
Scoped review by the implementation agent, not an independent second reviewer.
Base `532b30c`; the containing commit identifies the fixes and regression tests.
No production provider/normalizer or new source scope was added.

Three demonstrated capture defects violated NV-02-01-AC2 and secret retention:

| Reproducer executed before repair | Actual failing behavior | Repair / observed result |
|---|---|---|
| `test_total_bytes_stop_further_requests` with 8-byte aggregate budget | Three requests started despite first body using entire budget; expected one | Check aggregate budget before starting another request; first valid body retained, following results `total_byte_limit`. |
| `test_deep_json_is_failed_evidence`, 2,000 nested arrays | Classified as `observed_unverified`, expected failed bounded decoding | Finite traversal depth 64/node count 100,000; recursion errors classified invalid JSON. Deep payload rejected with no body capture. |
| `test_sensitive_json_not_retained_or_hashed`, access_token sentinel | Token-bearing JSON body retained and hashed | Reject known sensitive JSON keys before hash/body write, return `sensitive_payload`; no token/body/hash in artifacts. Cookies/SDK exceptions remain separately excluded. |

All three first runs failed for the demonstrated assertions, then all passed.
Focused capture suite: 18 pass. Subsequent full offline suite: 64 pass, including
the earlier 43 regressions, supervisor subprocess tests, plan/capability evidence
consistency and these repairs. Strict mypy on src/tests passes; configured Ruff
format/check pass after splitting one overlong checker print string. No assertion
was weakened, failure hidden or synthetic test used to claim real source support.

Capture byte counting is decoded streaming with <=64 KiB final chunk overshoot;
an oversized body is not saved and total-budget exhaustion prevents further
requests. JSON safeguards are bounded capture validation, not full future parser
semantics or universal secret detection in arbitrary bodies. Existing real JSON
specimens recheck under the repaired guard; all 19 direct specimens and all six
SDK-result/error captures match their committed metadata/hash references via
`uv run --frozen python tools/check_phase02.py .local/phase02` (exit 0, no network).
No additional live probes were needed for these deterministic repairs.
