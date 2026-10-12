# Platform administration and tenant onboarding

Status: VALIDATED — awaiting review; not merged or deployed.
Priority: P1 — current sequential roadmap item.
PR: https://github.com/mahendraek/FabClean-SaaS/pull/7
Implementation branch: `codex/pr-7-platform-onboarding`, based on accepted main `76b1bea`.
Implemented: 12 October 2026.
Implementation: `065d1e0`; published planning merge: `e1a8977`, verified at both branch refs and PR #7 head. A documentation-only follow-up records publication. GitHub title/body update returned Forbidden; hosted metadata remains unverified.

## Delivered scope

SuperAdmin brand/initial-store onboarding; editable SaaS plans and per-brand entitlements/resource caps; owner invitation creation/revocation/expiry and single-use acceptance with existing-account identity proof; suspension/reactivation and scoped session revocation; platform health/onboarding readiness; immutable audit history. Responsive administration and owner acceptance screens support web/mobile flows. Automatic invitation delivery and subscription billing are not included.

See [design, migration, APIs and validation](../PR7_IMPLEMENTATION.md).

## Validation and acceptance

80 backend tests without skips, 23 frontend tests, zero TypeScript diagnostics, 28-route web export, local load gate and desktop/mobile-web context/handoff/onboarding browser flows pass. PostgreSQL tests use a disposable database and non-bypass owner; original operational and custody RLS remain intact. Existing brands keep compatibility features/limits. Negative authorization, invite proof/replay, concurrency, quotas, lifecycle and audit checks are automated.

Native devices, actual sharing/email delivery and production onboarding remain unperformed. Hosted CI/review flags are unverified because GitHub API access remains Forbidden. Complete local validation and explicit approval are required for the manual release workflow.

## Boundaries

Only mahendraek/FabClean-SaaS is changed. New global tables contain platform/authentication control state, not shared operational customer records. Unknown historical rows are retained. PR #8–#12 remain planned. This implementation awaits review; earlier PR #6 merge/deploy approval does not authorize PR #7 deployment.
