# Filing specimen provenance

These are bounded scientific test inputs, not instructions, coverage, economic
mappings or acquisition credentials. Original bytes are preserved; HTML and XML
snapshots are marked binary in Git. Default tests never fetch sources.

- `rendered-2025.html` and `rendered-2026.html`: the two official RELIANCE
  specimens independently inspected in [Phase 02 filing evidence](../../../docs/evidence/02-20261018-filings-yahoo.md).
- `legacy-reliance.html`: owner-supplied [official locator](https://nsearchives.nseindia.com/archives/financial_results/financial_res_RELIANCE_71071.html),
  downloaded explicitly on 18 October 2026 UTC. Content period 31-Dec-2009,
  non-consolidated/quarterly. SHA-256
  `baa0c6c7a6c59ded283c4f0bd118d8a8f9d487048e4c285d2baaaae6834d2556`.
  The lakhs caption does not turn EPS or shares into monetary amounts. Nested
  layout tables are excluded without duplicate facts; source dashes remain dashes.
- `older-indas.xml`: [official source](https://nsearchives.nseindia.com/corporate/xbrl/INDAS_117298_1348254_16012025082021.xml),
  captured 18 October 2026 UTC. SHA-256
  `7a4376e20bcff469a6674116f0e45a76233d6358517d082a0a714ba78e6c2e96`.
  Independent source references: RELIANCE entity, revenue
  `1282600000000.00` / `3966450000000.00`; EPS continuing `6.44` / `17.77`.
  OneD/FourD both explicitly encode 2024-10-01..2024-12-31: preserve both,
  never repair periods or choose facts by context names.

## Closed 2020 taxonomy test inputs

`taxonomy2020/nse2020.zip` preserves the [official NSE package](https://nsearchives.nseindia.com/web/sites/default/files/inline-files/Financial%20Results_Ind%20AS%20Taxonomy.zip)
with SHA-256 `2760bdcda96c4ed472add9559a7001c215cd2a8aad9cb0db195f69af791c45af`.
The test loads only the nine named XML/schema resources with individual hashes.
There is no filesystem extraction or arbitrary member processing.

`taxonomy2020/standards.zip` contains ten explicitly selected standard schemas
from the resource cache of the official `arelle-release==2.46.1` wheel, downloaded
as research data without installing/importing Arelle or its dependencies. Wheel
SHA-256 `87a5369913471afa02d6d464d48a04a20acc073cc1df1fdaaae14d8b7b5229d0`.
The resource package is a fixed offline input, not the selected runtime processor.
Original resource copyright notices are retained; the distribution's original
[license/notice](taxonomy2020/ARELLE-LICENSE.md) is included.

`taxonomy2020/manifest.json` records original member paths, resource URIs,
individual SHA-256 hashes, version, entry references and the sole explicit alias
for the older package's local standard-schema reference. The URI host
`taxonomy.local.invalid` is a virtual in-memory key, never a network locator.
The full reference closure has 19 resources and 1,601,655 bytes. Unknown references
fail instead of using network, files, global caches or today's taxonomy. This
verifies source assertion/reference syntax only; it is not full XBRL calculation,
formula, dimensional or economic-statement validation.

## Real inline verification and quarantined specimens

`xii-2023.html` preserves XBRL International's actual
[2023 financial statements](https://www.xbrl.org/financialstatements/2023/xii-financial-statements-2023/reports/xii-financial-statements-2023.html),
181,431 bytes, SHA-256 `5de9bdec00b9deaecab2f939c3fad8f1228641e36edc616d39fd08011f6d6f4d`.
The owner authorizes this solely as offline shared-decoder evidence; it adds no
provider or NSE inline-availability claim. There are 316 numeric and 7 text facts,
four continuation elements, 16 negative signs and 81 zero-dash transforms.
Independently inspected f8 is USD cash `942,024` at 2023-06-30; f2 is the period
date `June 30, 2023`. The signature context has a forever period and opaque
signature XML; the decoder preserves it without verifying signatures.

The publisher's [catalog](https://www.xbrl.org/financialstatements/2023/xii-financial-statements-2023/META-INF/catalog.xml)
maps the logical XII schema URL to its packaged resource path. The logical URL
returned 404; the catalog's package location returned the original schema.
`taxonomy-xii/resources.zip` preserves the complete 41-resource dependency set,
33,862,241 expanded bytes, as a bounded offline artifact. Its
[manifest](taxonomy-xii/manifest.json) records member/source URIs, individual
hashes and archive hash. Original schema notices remain intact. Standard cache
resources come from the already pinned Arelle research wheel, whose
[license](taxonomy2020/ARELLE-LICENSE.md) remains included. No Arelle runtime is used.
Research acquisition is separate from production resolution; no parser fetches
the URI keys. The explicit tested profile permits 64 resources, 40 MiB taxonomy,
16 MiB per input/resource, 160,000 cumulative nodes and 64 MiB cumulative text;
all other `FilingLimits` defaults apply, including a 30-second decoder deadline.
The larger profile is needed for the real package's 13,886,233-byte label file.
The default smaller profile remains a valid fail-closed limit.

`missing-taxonomy-2026.xml` preserves the captured official integrated filing
with SHA-256 `5928e8ca820f60f944a66367291a7dc76c8df4536dfaf5627f3d3ff077487bae`.
No acquired 2025 package is substituted: rejection is `taxonomy_unavailable`.
`mismatched-2018.xml` preserves the owner's supplied 37,496-byte file, SHA-256
`0b4f87aee493fd0416e8ede3b8deb7f556ead6693b348425964daa3cf6c50648`.
Its 2018 concept namespace and 2017-named schema reference remain unmodified.
An exact-content quarantine returns `schema_namespace_mismatch`; this is an
evidenced vendor-defect rule, not a generic year-based schema inference.
The owner explicitly binds both as negative/quarantine acceptance cases under
the phase dependency exception. Other unseen versions remain unsupported until
their contracts and local packages are evidenced.
