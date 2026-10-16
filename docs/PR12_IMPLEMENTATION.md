# PR #12 — consolidated reporting and CSV exports

Development authorized 15 October 2026. Implementation is merged and deployed at `ab3a75663f7b2dcd268707df27f2d656b6bf3240` with explicit user approval on 16 October 2026.

## Delivered behavior

- Responsive Reports page with date, store and current order status filters. Brand administrators and selected-brand SuperAdmins can compare all stores within the selected brand or drill into one store. Store managers see only their selected store. Filtering reports does not change operational context.
- Server-calculated currency-separated order values, ledger balances, collections, refunds, adjustments and payment-method totals; per-store comparisons; order pagination; weighted turnaround samples; overdue, estimated-pricing, cancelled and outstanding-balance exceptions.
- Authenticated order-detail CSV and financial/operational summary CSV on web, with native sharing through React Native Share. Both use the same report engine, authorization and filters as the dashboard. Text cells are protected against spreadsheet formula injection. Exports omit customer contact information.
- Invalid or oversized requests fail explicitly. Failed requests clear report results and disable exports. Draft filters require Apply before exporting. CSV downloads retain session and active-context checks.

## Definitions and reconciliation

Dates are inclusive calendar dates in the **brand timezone**, including daylight-saving transitions. The API converts these to a half-open UTC interval. Defaults are the brand's current month through today. Reports are bounded to 366 days, 100 stores, 5,000 orders and 20,000 period transactions; larger requests return a useful error rather than silently truncating. Exported order details contain the whole matching cohort, independently of dashboard pagination.

Order value is the saved total for orders **created in the range**, including cancelled orders. Paid on orders sums the signed ledger for those orders through report generation, including payments posted after the selected creation-date range. Outstanding and overpaid are separately clamped per order before summing. The outstanding financial total includes cancelled orders; the operational “orders with balance” exception excludes cancelled orders.

Collections are signed transactions **posted in the range**, including payments for older orders. Net collected equals payments minus refunds plus adjustments plus other historical transaction types, and equals the sum by payment method. A saved order currency (or archived invoice currency) determines grouping; missing/invalid currency is `UNSPECIFIED`. Current configuration never relabels historical money, and no cross-currency total or exchange-rate conversion is invented.

Turnaround measures order creation to its first ready-for-pickup event, falling back to its first completion/collection/delivery event when no ready event exists. Pre-creation and future events are excluded. The brand average is weighted by individual orders with usable events, not an average of store averages. Missing terminal-order event counts and sample counts are shown. Orders without usable events do not receive a fabricated zero duration. Overdue means due before generation and not completed, collected, delivered or cancelled.

Each report request uses one read-only, repeatable-read PostgreSQL snapshot. Summary, metrics and its first/paginated order rows share that snapshot. Refresh, pagination and export generate fresh snapshots; operational changes between requests can change totals. The summary CSV includes the date range, timezone, status and generation time. Its operational metrics cover all currencies and repeat on each currency row for the same scope; do not sum these repeated metrics.

## Isolation and compatibility

No new tables, migrations, RLS policies or environment settings. Reads retain forced RLS and the non-bypass database role. Only explicitly authorized stores are visited with transaction-local brand/store settings; maintenance mode is never used by reporting. Transaction-local settings revert on exit and the pool resets tenant state. A foreign store produces 404, a manager's brand report produces 403, and unauthenticated requests produce 401. Reports also honor the existing `reports` entitlement and brand/store/session middleware.

Reporting requires PostgreSQL; memory-only development returns 503. Inactive stores of an authorized brand remain available for historical reporting. Opening an order from another reported store requires selecting that store in the operational header. Existing tax removal and archived financial compatibility are preserved; reporting does not calculate taxes.

## Publication

The existing draft [PR #12](https://github.com/mahendraek/FabClean-SaaS/pull/12) contains implementation head `b34a10550e6dc09df61025952ffd25778a575dfc`, whose tree exactly matches local implementation `3013f25`. Publication used the authenticated GitHub Git API because native Git transport is blocked. The commit preserves accepted main `6de9507` and planning head `2246383` as parents; no planning history was discarded. Both initial hosted validation runs subsequently passed (`38723707214` and `38723700931`). This documentation-only follow-up preserves the locally validated application/test tree.

## Validation

The complete `scripts/validate.sh` gate passed on 15 October 2026: **157 backend tests without skips, 39 frontend unit tests, clean TypeScript, a 31-route Expo web export and all eight desktop/mobile browser suites** (context, handoffs, platform, configuration, coverage, admin locations, notifications and reports). The local load gate completed 160 requests with zero errors at 171.29 requests/second; worst p95 was 73.36 ms. A subsequent frontend unit run also passed all 39 tests after strengthening CSV active-context assertions. Coverage includes real PostgreSQL reconciliation and negative authorization, timezone/DST boundaries, CSV safety, current role revocation, report size limits, authenticated CSV responses on web/iOS/Android, and desktop/mobile web browser filters, actual pagination, downloads and failure recovery.

Native device sharing requires manual iOS/Android acceptance; automated mobile checks run mobile web. Production smoke checks and deployment are deferred until merge/deployment approval.

## Current-main integration — 16 October 2026

Continued development explicitly authorized by the user. Merged accepted main `5d8bc3a` into the existing PR branch, preserving published PR #12 head `a6ebef9` and all released PR #13 printing behavior. Resolved API registration, package scripts, fixture/cleanup, workflow-artifact and tracker conflicts by retaining reporting and printing together. This is an update of PR #12; main and production are not changed.

The complete combined gate passed: **164 backend tests without skips, 44 frontend tests, clean TypeScript, 32-route Expo export, all nine desktop/mobile browser suites** and a 160-request load gate with zero errors (176.48 requests/second; worst p95 59.45 ms). Both reporting isolation/reconciliation/exports and physical-print-confirmation/idempotency tests execute in this gate. New-head hosted CI remains a separate check. Native device sharing and production reporting smoke checks remain pending acceptance/merge/deployment authorization.

## Released 16 October 2026

Merge `ab3a75663f7b2dcd268707df27f2d656b6bf3240` is live on both Render services. Both accepted-head hosted checks and all 15 public read-only smoke checks passed; the combined local gate passed 164 backend tests, 44 frontend tests and nine browser suites. See [deployment evidence](DEPLOYMENT_STATUS.md). Signed-in production reporting/native sharing and physical printer acceptance remain manual. No production fixtures or operational writes were used for smoke checks.
