# PR #14 — store tax policies

Development authorized 16 October 2026, based on main `d5dc5cc4734d3ffbebb135884ab956c77868bf81`. This is a new opt-in implementation following the earlier tax removal. Archived policies are never restored or automatically activated.

## Behavior

An administrator reviews and publishes an immutable, effective-dated policy for the selected store. The policy records the store location, timezone and currency, named percentage components, inclusive or exclusive pricing, explicit service classifications, delivery-fee treatment and a verification/source note. Revision checks prevent stale publication. Enabled policies reject unclassified services or changed location/currency until reviewed and republished. Tax is disabled when no enabled policy applies.

The server calculates estimates and invoices using cent-based Decimal rounding and proportional discount allocation. Inclusive tax is extracted from the existing price; exclusive tax is added. New invoices save their policy, location and component breakdown. Unpaid monetary edits retain that saved policy; payments freeze monetary edits. Previously untaxed invoices remain untaxed, and archived taxed invoices remain read-only for repricing. Receipt, manual WhatsApp preview and printing use saved invoice amounts.

Partial refund credits use cumulative proportional rounding, remaining component balances and original-invoice caps. Concurrent refunds retain existing gross-refund locking. Historical refunds without verifiable breakdowns are reported as unclassified rather than assumed zero credits.

Store-scoped JSON and CSV reports use store-local dates, currency groups and separate estimated, cancelled and finalized tax. Refund credits use their posting dates and may relate to an older invoice cohort. Net recorded tax is a reconciliation figure, not a tax-filing liability calculation. Reports disclose unclassified historical bases and refunds, and reject oversized ranges/results rather than silently truncate.

## Persistence and isolation

Startup installs a repeatable additive migration: `store_tax_policy_versions_v2` has forced row-level security, a composite store/brand foreign key, effective-date indexing and append-only history. Refund credit columns remain nullable for historical records. No production policies, rates or customer records are changed by development.

Regression testing reproduced an existing globally unique referral-code collision hidden by store RLS, which could abort an otherwise valid order. Allocation now uses atomic conflict handling and a customer-scoped advisory lock without reading another store's records; existing codes remain unchanged. Tests cover both the cross-store collision and concurrent allocation for one customer.

## Validation

The complete `scripts/validate.sh` gate passed against a fresh PostgreSQL test database using a non-superuser, non-bypass-RLS role:

- 180 backend tests, without skips, including policy immutability, foreign-store denial, related ownership, frozen estimates and concurrent refunds.
- 46 frontend tests, TypeScript and 33 exported routes.
- All ten retained desktop/mobile browser suites. The new tax suite covers review/cancel/publish, failed estimate recovery, checkout, frozen invoice/print rates, partial refund credits, CSV, failed-report recovery and foreign denial.
- Local load check: zero errors, 137.09 requests/second, worst p95 89.79 ms.

Synthetic rates are test data only. Browser checks use local fixtures; no actual messages, printer jobs or production operations were performed. Hosted CI is tracked separately from local validation.

## Acceptance and activation

The starting assumption is manually verified store-sourced rates. The user has not yet confirmed the first jurisdiction or manual versus provider-managed rates. Confirm these and obtain verified rates/service tax treatment before enabling a production policy. Automatic provider lookup, destination sourcing, exemption certificates, compound taxes and filing are outside this starting scope. Physical printer and native-device acceptance remain manual. Merge and deployment require separate user approval; environment settings are untouched.

## Release status — 21 October 2026

User-approved PR #14 merged at `f0c813a2f54c8625d208dc200c145c3a1196e66a`; both services are live at that exact merge. Both accepted-head hosted checks and all 18 public release smoke checks passed. See [deployment evidence](DEPLOYMENT_STATUS.md). No production policy was enabled. Laundry/dry-cleaning tax treatment and signed-in production activation remain pending; the old admin session returns 401.
