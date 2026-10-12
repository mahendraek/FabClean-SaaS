# Location-aware taxes

Status: ACCEPTED AND MERGED at `9e68ce3` — deployment pending Render credential/network access.
Priority: P2 — current sequential roadmap item.
PR: https://github.com/mahendraek/FabClean-SaaS/pull/9
Implementation branch: `codex/pr-9-location-taxes`, based on accepted main `04a6d8e`.
Implemented: 12 October 2026.
Publication: implementation `7b95598`, planning merge `33eb31c`; both branches and PR #9 head verified at `33eb31c`. A documentation-only follow-up records publication; GitHub title/body editing returned Forbidden.
Fresh verification: both branches and PR #9 head at `7d610ae` on 12 October 2026; the full local gate passed again on a fresh PostgreSQL 17 database. Includes the CI browser-cache correction. Main remains `04a6d8e`; no merge or deployment was performed.

## Delivered scope

Effective-dated service-store state/local rules, jurisdiction specificity, server-calculated estimates/orders, taxable/exempt items and fee policy, saved rate/location/line breakdowns, proportional refund tax credits and scoped reporting. Responsive administration, counter/order estimates and receipts display tax evidence. Legacy order totals and unclassified historic refunds are retained; client location/tax fields cannot choose the jurisdiction or override calculated tax.

See [design, migration, API and validation](../PR9_IMPLEMENTATION.md).

## Validation and boundaries

119 backend tests without skips, 26 frontend tests, clean TypeScript, 30-route export, five desktop/mobile-web browser suites and a zero-error local load gate pass. New rules use forced RLS; existing payment/operational/custody policies remain intact. Native devices, printer hardware and authenticated production tax execution remain unperformed. Hosted CI/review metadata remains unavailable through the Forbidden GitHub API.

Only mahendraek/FabClean-SaaS changes. Production remains on PR #8. Rates are configured manually against the saved service-store location; destination sourcing, automatic rate providers and item-specific credit notes are outside this implementation. PR #10–#12 remain planned. This development authorization does not authorize merge/deployment; explicit approval is required.
