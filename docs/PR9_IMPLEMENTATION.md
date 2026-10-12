# PR #9 — Location-aware taxes

Implemented: 12 October 2026. Branch `codex/pr-9-location-taxes`, based on accepted main `04a6d8e`; live application remains `7b193db`. Awaiting review; not merged or deployed.

## Calculation and location policy

The server calculates tax from the authorized, selected service store's saved country/state/city/postal code and timezone. Neither customer fulfillment addresses, device location, active-brand request spoofing nor client tax/jurisdiction values choose the rate. This implementation uses manually configured service-store rules; it does not fetch official rates, geocode addresses or implement destination-sourcing rules.

Tax administrators create effective-dated versions with a stable component key, jurisdiction label, country/state, optional city/postal selector and a 0–100 percent rate (up to four decimal places). Start is inclusive and end exclusive, in the store's local calendar day. Components add together; within a component, postal specificity wins over city, then state. Overlapping versions with identical selectors are rejected under the existing brand operation lock. End an old version before adding its replacement; an incorrect rule can be voided with a required reason. Ending/voiding leaves old order snapshots intact. Rate amounts and starting selectors are not edited in place.

Services take their taxable/exempt flag from effective PR #8 configuration. Taxable pricing with configured rules requires a matching effective jurisdiction and country/state; missing location, a gap or all-voided rules returns conflict rather than silently charging zero. Exempt services do not accrue tax. Stores with no rule history retain explicitly labeled legacy service-rate calculation for new orders, preserving existing service configuration without inventing state/local rates. No rates are seeded automatically.

Money uses Decimal, line amounts round HALF_UP to cents, and order discounts allocate proportionally using largest remainder with line-index tie breaking. Each taxable line/component then rounds to cents. Delivery fees are excluded by default; the inherited `delivery_fee_taxable` setting enables taxation through the store rules. Legacy service-rate mode cannot tax delivery fees. Manual unit prices and fees remain part of the existing staff workflow; this PR makes tax server-authoritative, not catalogue-price enforcement.

## Order and refund behavior

New itemized orders, recurring order generation and estimates share the calculation engine. Client `tax` on creation is ignored; order update cannot directly overwrite tax or its snapshot. Saved `tax_snapshot` contains service-store location/date, selected rule versions/rates, line taxability, discount allocation, component amounts and rounding policy. Monetary edits recalculate with the saved rates/location and original service taxability; newly added services use their effective taxability. A quick drop-off captures rates when first priced. An originally exempt invoice with no captured jurisdiction cannot silently become taxable without verified rates.

Legacy orders are not backfilled or repriced during migration. Their recorded tax/total survives notes/status changes and unchanged item submissions. An explicit monetary edit adopts a verified calculation and saves a snapshot. Quotes for unchanged legacy pricing return the recorded totals. Historical printed totals are not silently rewritten by rule changes; an explicit pricing edit can change amounts while retaining captured rates.

Cash refunds remain the existing gross, amount-based workflow, with tax credits derived from the saved invoice, not current rules. Cumulative refund tax rounds once at invoice level and distributes into remaining component balances. This prevents penny drift, ensures tax credit cannot exceed cash refunded, and restores original component tax exactly on a full refund. Refunds cannot exceed net recorded payments or unrefunded order value. Monetary order changes after a refund return conflict. Item-specific credit notes and overpayment-refund workflows are not added; existing adjustments remain a separate ledger operation.

Old refund rows with no recorded tax breakdown stay unchanged. Their unrecorded prior tax is not transferred to a new refund. The report identifies legacy refunds on taxed invoices as unclassified instead of fabricating their tax credits. Inconsistent legacy invoices whose tax exceeds their total require review before refunding.

## Persistence and isolation

Additive migration `location-taxes-v1` runs in the existing startup transaction/advisory lock. `tax_rules` has a composite service-store/brand foreign key and ENABLE/FORCE RLS with matching USING/WITH CHECK. The existing forced-RLS payment ledger gains `tax_amount` and `tax_breakdown`, defaulting to zero/empty for retained history. The migration marker preserves configured rates on repeat startup; no production backfill or fixtures are required.

Management and reporting require Admin for the selected store; estimates require order permission. Financial reporting also observes PR #7 report entitlements. Creation/refund/pricing transactions use brand-before-order/store locks; related-ID checks and operational/custody RLS remain intact. Refund writes and credits commit together under the existing order transaction. Rate creation/end/void appends platform audit metadata, including actor/store and a reason for voiding. No HTTP handler requests maintenance scope.

## API and web/mobile flows

- GET/POST `/api/taxes/rules`: scoped versions, saved location and current service date; create a validated version.
- POST `/api/taxes/rules/{id}/end`: shorten its exclusive end date.
- POST `/api/taxes/rules/{id}/void`: required reason; exclude from future calculation while preserving snapshots.
- POST `/api/taxes/estimate`: items, discount/fees and optional promo/customer; optional scoped `order_id` uses captured rates/legacy totals. No jurisdiction or tax override is accepted.
- GET `/api/financial/taxes?from_date=...&to_date=...`: maximum 366-day range; invoiced service-date tax, local-date recorded refund credits, net known tax, per-jurisdiction/rate amounts and unclassified legacy refund count. This is invoice-based, not partial-payment cash tax allocation.

Admin links to `/taxes` for dated rules, location display, taxable/exempt service overrides, fee policy, previews, confirmations and reporting. Brand-level service treatment and reset remain in PR #8 configuration. Counter creation and order detail show debounced server estimates, with stale responses suppressed; saved receipts display jurisdiction/rate breakdowns. Order payment/refund views and printed receipts show recorded refund tax credits. Store switching remounts the editor/estimate through the existing shared context.

## Validation and release limits

119 backend tests pass without skips on disposable PostgreSQL with a NOSUPERUSER/NOBYPASSRLS owner: 100 accepted baseline plus 19 tax tests. Coverage includes decimal rounding/allocation, specificity/date/timezone boundaries, exempt items, authoritative quotes/orders/receipts, client spoofing, frozen repricing/history, rule overlap/concurrency, missing jurisdiction coverage, foreign IDs, forced RLS/repeatable migration, refund caps/races/cent balancing, legacy unclassified refunds, fee policy, quick-dropoff pricing and legacy adoption.

26 frontend unit tests pass, TypeScript is clean and Expo exports 30 routes. All five desktop/mobile-web suites pass: context, custody, platform onboarding, configuration and real-local-API taxes. Tax browser flows exercise actual counter estimate/order/receipt creation, UI payment/refund credit recording, reports, cancel/void and frozen history/foreign denial. Mobile tax layout was visually inspected. The common `scripts/validate.sh` includes private disposable tax fixtures and the tax suite; [retained local load evidence](performance/pr9-load.json) has zero errors.

Native devices, actual printer output and authenticated production tax execution remain unperformed. Configured rates require business review before use; no automatic rate-provider coverage is claimed. GitHub API hosted CI/review/open/closed metadata remains unverified because access is Forbidden. Render remains on PR #8 with automatic deployment off. Explicit approval is required before merge/deployment. PR #10–#12 remain queued and unstarted.
