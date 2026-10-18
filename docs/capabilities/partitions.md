# Initial partition and completeness contracts — v1

These are Phase 02 contract targets, not implemented adapters or certified
coverage. [Source observations](observations.json) and the
[phase contract](../phases/02.md) govern the distinction. A versioned extension
must retain unmet targets. All intervals are explicit; no oldest-to-newest inference.

Every partition includes provider, dataset/schema generation, requested keys,
universe, fields, basis, source-format policy, identity/quality policy, requested
and effective interval, and collection instant. Store source hash/locator and
publication/effective precision separately. `observed_unverified` is not complete.

| Dataset | Atomic scope / keys | Fields, basis and validation | Required completeness evidence / overlap |
|---|---|---|---|
| equity_eod | One source CM report/session/generation, then selected dated listing/series projection | Source OHLC, close vs settlement, quantity, turnover, trades, ISIN; preserve text decimals/nulls and source units | Validate whole report's header/session, row widths, keys, quantities and expected source scope before projection. A RELIANCE row cannot certify whole market. Legacy and UDiFF reconcile by listing/series/session/field/basis, never union-count duplicates. |
| equity_delivery | Source delivery report/session; join listing/series/session | Delivery quantity, percentage and compatible traded denominator; lacs turnover distinct from rupee-valued fields | Validate preamble/generation, all rows/date and missing markers; no zero inference or arbitrary row-type assumption. Supplemental fields add field coverage only; price coverage cannot certify delivery. |
| corporate_actions | Symbol/series and explicit ex-date interval plus source revision | Split/bonus/dividend/rights text, ex/record/book dates, publication precision | Stable source snapshot or reconciled count/order/boundaries; complete pagination plus compatible revisions. Current catalogue not historical completeness. No return reconstruction in this phase. |
| announcements | Issuer and publication interval, source announcement ID/revision | Metadata, source timestamp precision, attachment locator; no attachment parsing | Stable snapshot or reconciled counts/order/boundaries; attachment presence not numerical statement support. |
| events | Issuer and effective interval, event ID/revision | Purpose, meeting/effective date, publication separately | Current calendar not a historical interval. Same stable-catalogue conditions as actions; unknown history stays unknown. |
| market_state_asm | Source dated ASM list/generation and listing/series | Regime/stage, effective and publication precision | Current list only certifies its observed contents, never all earlier regimes. Historical intervals require evidenced start/end/revisions. Optional; no price-only dependency. |
| market_state_gsm | Source dated GSM list/generation and listing/series | Stage/restrictions as supplied | Same interval requirements; no conversion of current membership to historical restrictions. |
| market_state_bands | Source band-change report/date/generation and listing/series | From/To source band values; fixed band vs dynamic range unresolved until official semantics evidenced | Filename dates insufficient for effective interval or publication instant. Two dated files cannot certify continuous history. Overlapping regimes coexist; never remove historical universe members. |
| derivatives_eod | Whole FO report/session/generation; full contract identity | Instrument, underlying, expiry/actual expiry, strike, CE/PE, settlement vs close, volume/OI with source units | Validate entire session then project contracts; match dated term evidence, not current lot table. Legacy/UDiFF overlap reconciles by contract/session/field. Unknown multipliers block notional calculations only. |
| derivative_terms | Contract and evidenced effective interval/revision | Original/adjusted strike, expiry, lot/multiplier, settlement rules | Dated contract master/circular plus identity continuity; present lot value cannot backfill 2016. A report's dated `NewBrdLotQty` is a sample, not full term-change history. |
| index_price | Provider-neutral index + price variant + session window | Price-index points, explicit index identity/calendar | Expected completed sessions vs observed/null/missing rows and stable window response; keep gross/net TRI separate. |
| index_tri_gross | Index + gross TRI variant + session window | Total-return index points, explicit source variant | Same reconciliation; unverified gross identity cannot be assumed from route name. |
| index_tri_net | Index + net TRI variant + session window | Net total-return index points | Separate evidenced variant; absence cannot be filled with gross TRI or ETFs. |
| index_valuations | Index + PE/PB/yield field basis + session window | Ratios vs percentage units, source definition and timing | Per-field session evidence; a price response supplies no valuation coverage. |
| india_vix | VIX identity + historical session window | Volatility-index points | Historical response/calendar reconciliation; current VIX snapshot insufficient. |
| participant_oi | Whole participant OI report/session/generation | Client/DII/FII/Pro categories, long/short contract counts | Caption date, category set, columns and totals; no interchange with participant volume or FII/DII cash flows. |
| participant_volume | Whole participant volume report/session/generation | Separate contract-flow counts | Same source-scope validation; never substitute OI. |
| fii_dii_flows | Whole dated aggregate report/segment | Gross buy/sell/net with explicit currency scale | Source session/categories/units reconciliation, not participant OI totals. |
| bulk_deals | Market/report/session with deal identity | Symbol/series, buy/sell, price/quantity, client metadata | Whole source report or stable reconciled catalogue; selected client subset incomplete. |
| block_deals | Market/report/session with deal identity | Separate block segment and deal keys | Same whole-report conditions, no substitution with bulk deals. |
| short_selling | Source report/session/generation | Listing/series and source quantity definition | Complete source rows/date/schema, not inferred negative positions. |
| financial_catalogue | Issuer, reporting interval and filing/revision identity | Basis, audit/report/submission/broadcast times, locators | Stable snapshot/cursor or independently reconciled count/order/boundary. Revised/mutating or failed page => `completeness_unverified`. |
| financial_facts | One immutable filing/document-set/representation, issuer, basis, period, statement, concept, dimensions, unit | P&L, balance sheet, cash flow, segments; preserve QName/context/unit/decimals/nil/duplicates and mapping version | Source assertions decoded separately from mapped numerical facts. Validate complete document set and required target concepts; missing concepts stay missing. Restated comparatives and original reporting periods remain separate assertions. Same filing XML/HTML are representations, not corroborating providers. |
| ownership_catalogue | Issuer/reporting interval/source filing revision | Report/submission/revision/broadcast times, detail locators | Same stable catalogue conditions; metadata-only response cannot certify percentages/shares. |
| ownership_facts | Filing, share class, as-of date, category hierarchy, denominator, dimensions and unit | Promoter/public/institution categories; shares vs percentages | Decode/validate full filing scope with separate category mapping. Parent/child categories never sum twice; incompatible denominators never compare. |
| global_observations | One Yahoo symbol/mapping/basis/1d completed-session window | Close only, index points; exact SDK float/null boundary, timezone and collection instant | Expected US completed sessions, early closes/DST/freshness buffer vs rows/nulls/missing; no partial/revised return or nonempty result as completeness proof. Overlapping captures preserve vintage; no historical timing guarantee. |
| etf_catalogue | Source current catalogue/capture or evidenced dated listing interval | Symbol/name/ISIN/series, security unit and listing date as supplied | Current rows do not prove listing end, old mandate or past series. Rename/change files supply events, not automatic identity continuity. |
| etf_metadata | Scheme/security + attribute + evidenced validity interval | Scheme classification, mandate and units only where explicitly supplied | Absent attributes unknown; name matching is not classification. No implied NAV/iNAV/holdings/expense/tracking history. |
| etf_eod | Whole CM report/session then ETF listing/series projection, or evidenced complete security window | Exchange traded OHLC/quantity/turnover of fund units | Same session/schema/dated-identity checks as equity; never substitute NAV or underlying index. Catalogue membership at collection cannot certify old ETF classification. |
| instrument_discovery | Current catalogue/capture or explicit local dated identity set | Exact symbol/ISIN, name and alias candidates with match type/validity | Return all ambiguous matches with provenance and stale/unknown validity. Chart endpoint/current listing cannot certify dated identity or intraday capability. |

For every row: failed page, source mutation, nonadvancing/repeated cursor, poisoned
row, unresolved critical identity/unit or partial-universe cache => no complete
partition. Independent partitions may finish, but required failures remain visible.
Stage partial inputs without publishing canonical coverage. Overlap/supersession
compares exact fields, basis, scope, source generation and revision policy; no
silent replacement, historical zero filling, or sample-to-ten-year promotion.

This freezes the initial contract vocabulary only. Later phases implement and
test these publication rules; Phase 02 implements no DataPlan/store/schema change.
