# FabClean development tracker

Updated: 9 October 2026. This is the canonical work queue for `mahendraek/FabClean-SaaS`.
Develop one item at a time. Keep future scopes in the backlog; do not implement or merge another roadmap PR as part of the current item.

## Current work

**PR #4 — tenant and store data isolation:** implementation and validation complete on `codex/pr-4-tenant-isolation`; awaiting review. Do not merge without explicit approval.

The implementation adds forced PostgreSQL row-level security on 21 operational tables, scoped catalogs/settings in memory, store-scoped customer histories and metrics, validated related IDs, and scope-aware role checks. Unknown/inconsistent historical ownership is quarantined. See [migration and validation notes](roadmap/tenant-data-isolation.md).

**Next:** PR #3 — brand/store experience, after PR #4 review. Rebase each future implementation on the accepted predecessor so security behavior and tests remain intact.

## Sequential PR queue

| Order | PR | Priority | Scope | Development status | Depends on |
| --- | --- | --- | --- | --- | --- |
| 1 | [#4](https://github.com/mahendraek/FabClean-SaaS/pull/4) | P0 | [Tenant/store data isolation](roadmap/tenant-data-isolation.md) | Implemented; awaiting review | Existing context persistence |
| 2 | [#3](https://github.com/mahendraek/FabClean-SaaS/pull/3) | P0 | [Shared brand/store switcher](roadmap/brand-store-experience.md) | Planned; next | #4 |
| 3 | [#5](https://github.com/mahendraek/FabClean-SaaS/pull/5) | P1 | [Store hierarchy and operational handoffs](roadmap/store-hierarchy.md) | Planned | #4, #3 |
| 4 | [#6](https://github.com/mahendraek/FabClean-SaaS/pull/6) | P1 | [Security, testing and performance](roadmap/security-performance.md) | Planned | #4, #3, #5 |
| 5 | [#7](https://github.com/mahendraek/FabClean-SaaS/pull/7) | P1 | [Platform administration/onboarding](roadmap/platform-management.md) | Planned | #4, #6 |
| 6 | [#8](https://github.com/mahendraek/FabClean-SaaS/pull/8) | P2 | [Brand defaults/store overrides](roadmap/configuration-inheritance.md) | Planned | #4, #5, #7 |
| 7 | [#9](https://github.com/mahendraek/FabClean-SaaS/pull/9) | P2 | [Location-aware taxes](roadmap/location-taxes.md) | Planned | #8 |
| 8 | [#10](https://github.com/mahendraek/FabClean-SaaS/pull/10) | P2 | [OpenStreetMap delivery coverage](roadmap/service-area-maps.md) | Planned | #5, #8 |
| 9 | [#11](https://github.com/mahendraek/FabClean-SaaS/pull/11) | P2 | [Email/SMS receipts and preferences](roadmap/notifications-receipts.md) | Planned | #4, #8, #9 |
| 10 | [#12](https://github.com/mahendraek/FabClean-SaaS/pull/12) | P2 | [Consolidated reporting/exports](roadmap/cross-store-reporting.md) | Planned | #4, #5, #9 |

The sequence follows the scope documents' P0/P1/P2 priorities and prerequisite work. It is a development sequence, not permission to merge or deploy. PR #3 is listed second because the user selected #4 first.

## PR inventory and evidence

- #1: context refresh fix is included in `main` via commit `07c3097`, whose subject references #1.
- #2: context persistence fix was merged into `main` at `f674aa4` (explicit merge commit).
- #3–#12: remote PR head refs and matching `roadmap/*` branches were discovered through authenticated Git. All ten scope documents are retained under `docs/roadmap/`.
- GitHub API requests returned `Forbidden` during this audit. Current open/closed/merged flags, review decisions, CI results, comments and issue inventory for #3–#12 are **not verified**. A Git PR ref alone does not establish that a PR is open. Preserve this distinction until API access works.
- No PR numbers above #12 were discovered in the current remote refs. Future, unpublished PRs cannot be enumerated yet; add them when created. PR 45 mentioned in the baseline import belongs to the source project's history and is not a queued FabClean-SaaS PR.

To refresh the inventory, use `git ls-remote origin 'refs/pull/*/head' 'refs/heads/roadmap/*'`; when GitHub API access is available, use `gh pr list --repo mahendraek/FabClean-SaaS --state all --limit 100`. Record the evidence and date, and keep completed items rather than deleting them.

## Backlog without assigned PRs

These items remain required by [the functional specification](FUNCTIONAL_SPEC_V1.md). Listing them does not claim implementation; audit actual behavior before assigning the next PR. [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) is an older foundation snapshot, not an authoritative current completion list.

| Phase | Work retained in the backlog |
| --- | --- |
| V1 | Walk-in/drop-off and optional pickup/delivery; configurable categories, services, variants, modifiers and pricing; order/item barcode lookup and mobile-camera scanning; inspection, stains/damage, notes and photos; offers, rewards, referrals and subscriptions; manual payment tracking; staff/driver workflows; reports; tenant/location enforcement. Existing implementations need acceptance checks, not wholesale rebuilding. |
| Phase 2 — POS/hardware | Physical POS terminals, cash drawers, receipt printers, garment tag printers and heat-seal printers. |
| Phase 2 — payments | Online payments, Apple Pay/Google Pay, gift cards, refunds and automated subscription billing. |
| Phase 2 — delivery | Advanced route optimization, live driver tracking and proof of delivery. |
| Phase 2 — messaging | SMS/WhatsApp/push delivery, consent and preferences; coordinate email/SMS receipts with #11. |
| Phase 2 — operations | Staff clock-in/out, QuickBooks/Xero and stronger multi-location operations. |
| Phase 3+ | Washer/dryer integrations and telemetry, payroll, smart lockers, advanced plant management, automated assembly, complex multi-store management, advanced marketing automation, AI receptionist and RFID. |
| Engineering follow-ups | Existing 19 frontend TypeScript errors; native iOS/Android validation; migration tooling and CI deployment checks; session/load/concurrency testing under #6. |

## How to maintain the queue

1. Read this tracker and the selected scope before changing code. Use the existing isolated cloud checkout; do not create a worktree unless requested.
2. Check remote heads and local changes. Preserve user work. Rebase the next item on accepted work rather than replacing prior fixes.
3. Update the active item's status: planned → in development → validated/awaiting review → merged (only with evidence and explicit approval).
4. Record the implementation commit/branch, concrete behavior, tests executed, failures/skips and limitations. Do not treat a planning document as a delivered feature.
5. Keep only one item in development. Finish its review step before beginning the next numbered item. Do not discard deferred phases or silently renumber GitHub PRs.
6. Preserve tenant-isolation tests for every future feature, including negative authorization checks and relevant PostgreSQL integration checks.

Publication, deployment, GitHub review state and merge state must be reported separately from local validation.
