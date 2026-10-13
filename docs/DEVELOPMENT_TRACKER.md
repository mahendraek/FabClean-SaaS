# FabClean development tracker

Updated: 13 October 2026. This is the canonical work queue for `mahendraek/FabClean-SaaS`.
Develop one item at a time. Keep future scopes in the backlog; do not implement or merge another roadmap PR as part of the current item.

## Current work

**PR #4 — tenant and store data isolation:** merged into `main` at `971f2bc` with explicit user authorization. The remote main ancestry was verified. Both Render services report live deployments of `a800a73`; public health and authorization checks now pass; see [deployment status](DEPLOYMENT_STATUS.md).

Implementation commit: `b4b621d`. Pushed to `roadmap/tenant-data-isolation`; the remote PR #4 head ref was independently verified at that commit. This confirms branch publication, not GitHub review or merge status.

The implementation adds forced PostgreSQL row-level security on 21 operational tables, scoped catalogs/settings in memory, store-scoped customer histories and metrics, validated related IDs, and scope-aware role checks. Unknown/inconsistent historical ownership is quarantined. See [migration and validation notes](roadmap/tenant-data-isolation.md).

**PR #3 — brand/store experience:** merged into `main` at `cd99661` with explicit user authorization; implementation `ae6d1bb` on `codex/pr-3-brand-store-switcher`, based on merged `main`. Shared header, confirmed store switching, screen refresh, native secure sessions and authorized relogin restoration are implemented. Validation: 27 backend tests, 9 frontend tests, desktop/mobile-web browser checks and 26-route web export passed. Both Render services are live at `cd99661`, with health, unauthenticated authorization and published bundle checks passing; native-device validation remains outstanding. See [implementation notes](roadmap/brand-store-experience.md).

**PR #5 — store hierarchy and operational handoffs:** merged into main at `9753435` with explicit user approval; implementation `324e911` on `codex/pr-5-store-hierarchy`, based on merged main `47e67a9`. Hierarchy/cycle/deactivation guards, scoped staff assignments, an immutable participant-scoped custody journal and a web/mobile handoff screen are implemented. Validation: 38 backend tests, 12 frontend unit tests, real local API browser flows and 27-route web export. Both Render services are live at `9753435`; API health/authentication and published handoff page/bundle checks passed. See [design and validation](roadmap/store-hierarchy.md).

**Current maintenance:** [Pre-PR #6 audit and fixes](PRE_PR6_AUDIT.md) on `codex/pre-pr6-fixes`, based on main `8e783a7`. Session revocation, stale-store write protection, consistent assembly guards and all 34 TypeScript diagnostics are fixed. Validation: 42 backend tests, 15 frontend unit tests, zero TypeScript diagnostics, 27-route export and desktop/mobile browser checks. Accepted and merged into main at `50eeb3d` with explicit user authorization; see [deployment status](DEPLOYMENT_STATUS.md).

**PR #6 — security, testing and performance:** accepted and merged into main at `dd031a7` with explicit user approval. Implementation `9ee0362`, published head `c8cbd1b`, and planning ancestry `19c7742` are retained. At that release, both Render services were live on `dd031a7`; health, production CORS, unauthenticated authorization and fresh web bundle checks pass. Validation: 61 backend tests, 19 frontend tests, clean TypeScript, 27-route export, desktop/mobile browser flows and local load evidence. Automatic Render deployment is off; this authorized release used the documented local-validation/manual-deployment fallback while GitHub CI/required-check state remains Forbidden. See [deployment status](DEPLOYMENT_STATUS.md), [release review](PR6_SECURITY_RELEASE.md) and [performance evidence](performance/PR6_BASELINE.md).

**PR #7 — platform administration/onboarding:** implemented on `codex/pr-7-platform-onboarding`, based on accepted main `76b1bea`; accepted and merged at `43f3cbf` with explicit user approval. At that release, both Render services were live at `43f3cbf`; public smoke checks passed. Implementation `065d1e0`, published planning merge `e1a8977`; both branch refs and PR #7 head independently verified through Git. GitHub rejected title/body editing with Forbidden. Includes atomic brand/store/owner onboarding, secure owner invitations, plans/entitlements/resource limits, suspension/reactivation, platform health/readiness and append-only audit. Validation: 80 backend tests, 23 frontend tests, clean TypeScript, 28-route export, local load gate and desktop/mobile context/handoff/onboarding flows. Native/actual delivery and hosted CI/review verification remain outstanding. See [deployment status](DEPLOYMENT_STATUS.md) and [implementation notes](PR7_IMPLEMENTATION.md).

**PR #8 — brand defaults/store overrides:** implemented on `codex/pr-8-configuration-inheritance`, based on accepted main `be72979`; accepted and merged at `7b193db` with explicit user approval. At that release, both Render services were live at that commit; public smoke checks passed. Implementation `744947a`, planning merge `4590250`, validated fix `7a3696d`; both branch refs and PR #8 head independently verified through Git. GitHub title/body update returned Forbidden. Brand settings/service/pricing/offer defaults, partial store overrides/reset, source metadata, forced-RLS persistence, store-local promotion usage and a responsive editor are implemented. Validation: 100 backend tests without skips, 26 frontend tests, clean TypeScript, 29-route export, four desktop/mobile browser suites and zero-error local load gate. See [deployment evidence](DEPLOYMENT_STATUS.md) and [implementation notes](PR8_IMPLEMENTATION.md).

**PR #9 — location-aware taxes:** accepted with explicit user authorization and merged into main at `9e68ce3`; both Render services confirmed live at that exact commit on 13 October 2026. Implemented on `codex/pr-9-location-taxes`, based on accepted main `04a6d8e`; fully locally validated. Implementation `7b95598`, published planning merge `33eb31c`; both branch refs and PR #9 head independently verified through Git. GitHub title/body editing returned Forbidden. Dated state/local service-store rules, authoritative estimates/orders, saved tax/rate/location breakdowns, exemption/fee policy, capped proportional refund credits, unclassified legacy refund reporting and responsive screens/receipts are implemented. Validation: 119 backend tests without skips, 26 frontend tests, clean TypeScript, 30-route export, five desktop/mobile suites and zero-error local load gate. The merged tree matches validated head `fa45909`. API health/authentication/CORS and published tax routes/web bundle pass; see [deployment evidence](DEPLOYMENT_STATUS.md) and [implementation notes](PR9_IMPLEMENTATION.md).

**CI correction:** public GitHub run metadata confirms earlier hosted failures. The user-supplied log identifies a Playwright install/validation cache mismatch; PR #9 now sets one shared browser directory and checks startup before the gate. See [cause and verification](CI_VALIDATION_FIX.md) and the linked exact-head workflow runs. No application or deployment changes are included.

**Current: PR #10 — OpenStreetMap delivery coverage:** implemented on `codex/pr-10-service-area-maps`, based on accepted main `be01ff3`; validated and awaiting review. Includes selected-store radius/polygon coverage, explicit address pins, miles/kilometres, server order/recurring eligibility checks, saved assessments, forced RLS and a responsive OSM editor/counter flow. Validation: 136 backend tests without skips, 31 frontend tests, clean TypeScript, 31-route export, all six desktop/mobile browser suites and a zero-error local load gate. Live OSM tile access is blocked by the current cloud policy; additional tile/attribution hosts are saved in the environment draft. Main/Render remain on PR #9. See [implementation and rollout notes](PR10_IMPLEMENTATION.md).

**Next after PR #10 acceptance:** PR #11 — email/SMS receipts and preferences. No future item has started.

**PR #9 revalidation:** authenticated Git verified both development branches and PR #9 head at `7d610ae` (including the CI browser-cache fix), while main remains `04a6d8e`. A fresh disposable PostgreSQL 17 run passed the full gate: 119 backend tests without skips, 26 frontend tests, TypeScript, 30-route export, five desktop/mobile browser suites and zero-error load validation. Development is complete; subsequent merge acceptance is recorded above. Hosted CI/review metadata remains Forbidden. See [fresh verification](PR9_IMPLEMENTATION.md#fresh-checkout-verification).

## Sequential PR queue

| Order | PR | Priority | Scope | Development status | Depends on |
| --- | --- | --- | --- | --- | --- |
| 1 | [#4](https://github.com/mahendraek/FabClean-SaaS/pull/4) | P0 | [Tenant/store data isolation](roadmap/tenant-data-isolation.md) | Merged at `971f2bc`; Render live at `a800a73` | Existing context persistence |
| 2 | [#3](https://github.com/mahendraek/FabClean-SaaS/pull/3) | P0 | [Shared brand/store switcher](roadmap/brand-store-experience.md) | Merged at `cd99661`; Render live and smoke checks passed | #4 |
| 3 | [#5](https://github.com/mahendraek/FabClean-SaaS/pull/5) | P1 | [Store hierarchy and operational handoffs](roadmap/store-hierarchy.md) | Merged at `9753435`; Render live and smoke checks passed | #4, #3 |
| 4 | [#6](https://github.com/mahendraek/FabClean-SaaS/pull/6) | P1 | [Security, testing and performance](roadmap/security-performance.md) | Merged at `dd031a7`; both Render services live; smoke checks passed | #4, #3, #5 |
| 5 | [#7](https://github.com/mahendraek/FabClean-SaaS/pull/7) | P1 | [Platform administration/onboarding](roadmap/platform-management.md) | Merged at `43f3cbf`; both Render services live; smoke checks passed | #4, #6 |
| 6 | [#8](https://github.com/mahendraek/FabClean-SaaS/pull/8) | P2 | [Brand defaults/store overrides](roadmap/configuration-inheritance.md) | Merged at `7b193db`; both Render services live; smoke checks passed | #4, #5, #7 |
| 7 | [#9](https://github.com/mahendraek/FabClean-SaaS/pull/9) | P2 | [Location-aware taxes](roadmap/location-taxes.md) | Merged and Render live at `9e68ce3` | #8 |
| 8 | [#10](https://github.com/mahendraek/FabClean-SaaS/pull/10) | P2 | [OpenStreetMap delivery coverage](roadmap/service-area-maps.md) | Validated; awaiting review | #5, #8 |
| 9 | [#11](https://github.com/mahendraek/FabClean-SaaS/pull/11) | P2 | [Email/SMS receipts and preferences](roadmap/notifications-receipts.md) | Planned | #4, #8, #9 |
| 10 | [#12](https://github.com/mahendraek/FabClean-SaaS/pull/12) | P2 | [Consolidated reporting/exports](roadmap/cross-store-reporting.md) | Planned | #4, #5, #9 |

The sequence follows the scope documents' P0/P1/P2 priorities and prerequisite work. It is a development sequence, not permission to merge or deploy. PR #3 is listed second because the user selected #4 first.

## PR inventory and evidence

- #1: context refresh fix is included in `main` via commit `07c3097`, whose subject references #1.
- #2: context persistence fix was merged into `main` at `f674aa4` (explicit merge commit).
- #4: implementation merged into main with normal Git merge commit `971f2bc`, independently verified from the remote; GitHub API review flags remain unavailable.
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
| Engineering follow-ups | Frontend TypeScript baseline fixed in pre-PR #6 maintenance (accepted and merged); native iOS/Android validation; hosted CI/required-check and Render gate verification; larger staging load and notification-provider acceptance. PR #6 includes local session/load/concurrency checks and migration CI tooling. |

## How to maintain the queue

1. Read this tracker and the selected scope before changing code. Use the existing isolated cloud checkout; do not create a worktree unless requested.
2. Check remote heads and local changes. Preserve user work. Rebase the next item on accepted work rather than replacing prior fixes.
3. Update the active item's status: planned → in development → validated/awaiting review → merged (only with evidence and explicit approval).
4. Record the implementation commit/branch, concrete behavior, tests executed, failures/skips and limitations. Do not treat a planning document as a delivered feature.
5. Keep only one item in development. Finish its review step before beginning the next numbered item. Do not discard deferred phases or silently renumber GitHub PRs.
6. Preserve tenant-isolation tests for every future feature, including negative authorization checks and relevant PostgreSQL integration checks.

Publication, deployment, GitHub review state and merge state must be reported separately from local validation.
