# Phase 03 real-inline research and hosted XML verification

Observed 19 October 2026 IST (captures 18 October UTC), source checkpoint
`f8bb373cd814980f98e0d0cf8455f8933067fa96`. This records research observations,
not a completed decoder or a phase completion claim.

## Public NSE findings

The owner requested extensive research after both supplied files proved to be
ordinary XML. Search discovery covered official archive locators, exchange
documentation, issuer disclosures and XBRL International. Direct acquisition
was bounded to twelve additional named bodies: eight NSE HTML, two NSE XML,
one SEC attempt and one XBRL International report. Search-engine/index requests
are separate and are not represented as twelve total network requests.

The eight specimens in [the fixed HTML plan](../capabilities/probes/phase03-inline.json)
span IndAS, non-IndAS, banking, NBFC, life/general insurance and governance.
All returned 200, total 751,445 bytes. Each has zero inline namespace, inline
fact and XBRL context elements. No linked complete Inline XBRL document set
was found in the inspected bodies. These names do not establish genuine inline
support, or new financial-family decoder support. Together with the earlier
two integrated financial HTML and ownership HTML specimens, eleven inspected
public ixbrl-path HTML documents lack genuine inline facts.

The two [announcement probes](../capabilities/probes/phase03-inline-announcements.json)
returned 200, 2,601 and 2,994 bytes. Both have an XBRL instance root and SEBI
capital-market namespaces; neither is an inline document. No event mapper was
implemented. Exact URLs, dates, hashes, budgets and classifications are in
[the observation record](../capabilities/phase03-inline-observations.json).
Raw bodies remain in ignored .local/phase03 captures.

[NSE circular NSE/CML/2023/85](https://nsearchives.nseindia.com/web/sites/default/files/inline-files/NSE%20Circular-%20Filing%20of%20Announcements%20pertaining%20to%20Loss%20and%20Duplicate%20Share%20Certificate%2C%20Trading%20Window%2C%20CIRP%20in%20XBRL%20format%20on%20NEAPS%201.pdf),
dated 8 December 2023, describes XML generation/upload and an iXBRL report
route for listed entities inside NEAPS. This identifies an access distinction;
it does not establish a public genuine-inline export. No login was attempted.
[XBRL International's 27 October 2025 exchange report](https://www.xbrl.org/news/xbrl-powers-transparency-across-indias-capital-markets/)
describes exchange XBRL access and anticipates Inline XBRL. Its date cannot
establish rollout status in October 2026. The observation is **no qualifying
public NSE inline specimen verified by this research**, not proof none exists.

## Genuine-inline alternative located

The [SEC filing index for Infosys fiscal 2025](https://www.sec.gov/Archives/edgar/data/1067491/000095017025091925/0000950170-25-091925-index.htm)
labels the 13,222,304-byte primary report iXBRL and lists its extension schema.
The one direct body request returned 403; no retry, alternate identity or
bypass was used. An NSE PDF referring to this filing is not an inline instance.

[XBRL International's annual-statement index](https://www.xbrl.org/the-consortium/about/annual-financial-statements/)
links its actual [2023 financial statements](https://www.xbrl.org/financialstatements/2023/xii-financial-statements-2023/reports/xii-financial-statements-2023.html).
One direct GET returned 200, **181,431 bytes**, SHA-256
`5de9bdec00b9deaecab2f939c3fad8f1228641e36edc616d39fd08011f6d6f4d`.
Independent standard-library XML inspection found XHTML root, Inline XBRL 1.1
namespace, **316 nonFraction facts, 7 nonNumeric facts and 4 continuations**.
For example the cash fact f8 displays `942,024`, with context c2, unit u1,
decimals 0 and numdotdecimal transformation. This establishes genuine inline
markup; it does not yet establish taxonomy closure, transformed assertions or
decoder correctness. It references the explicit 2023-06-30 XII extension schema.

This is a real issuer report rather than a fabricated example. Using it only
as shared-decoder verification input could resolve the missing format specimen
without creating a provider adapter. It cannot certify NSE inline acquisition.
The phase's prohibition on new provider scope makes that distinction a scope
clarification for the owner before implementation. No acceptance requirement
has been waived or edited. The newer NSE 2026 taxonomy mismatch remains
separate from this alternative.

## Hosted verification observed

All eight jobs for current source `f8bb373` passed in
[run 39157197942](https://github.com/Shrikant94-prog/niftyverse/actions/runs/39157197942).
Windows and Ubuntu each report core **118 passed, 2 optional modules skipped**,
explicit filing subset **24 passed**, strict mypy for 30 source files,
lint/format, fresh installed core wheel and documentation baseline checks.
The filings-extra lane successfully decodes real XML/HTML with the local closed
package from a fresh installed wheel. Yahoo, Yahoo-consumer, notebook, pandas
and macOS core lanes also pass. lxml is 6.1.3; hosted Linux libxml2 2.14.6 differs
from local Windows 2.11.9. Wheel hashes differ across platform/checkout bytes;
artifact identity across platforms is not claimed.

The existing local full-extra result remains **142 passed**. This research
changes no runtime code, dependency or tests, so those unchanged checks were
not rerun. Current green checks certify implemented common/XML/HTML behavior;
they do not certify the unfinished inline/newer-taxonomy gate or authorize
integration of an incomplete phase.

Documentation-only checkpoint verification: the exact staged file set passes
the baseline checker and its positive/negative self-tests: 77 Markdown files,
local links/anchors, dependency order and root budgets. Static requirement,
decision, amendment, outcome, acceptance and gate fingerprints match. Staged
diff whitespace check passes. The owner's untracked Sample_Files remain untouched.
