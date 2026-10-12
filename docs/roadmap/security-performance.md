# SaaS security, testing and performance

Status: VALIDATED — awaiting review. Not merged or deployed.
Priority: P1 — current sequential roadmap item.
PR: https://github.com/mahendraek/FabClean-SaaS/pull/6
Implementation branch: `codex/pr-6-security-performance`, based on accepted main `d42f80f`.
Prepared and implemented: 12 October 2026.

## Delivered scope

Shared bounded sign-in throttling; versioned PBKDF2 hashes and legacy upgrade; password-reset/deactivation session revocation; role-preserving staff edits; permission-based assembly override; explicit production CORS and startup configuration checks; CORS on authentication errors; safe request logging; bounded tenant-safe PostgreSQL pooling; scoped order lookup; atomic order/payment/assembly updates and creation; recurring-generation conflict protection; frontend HTTP/selection failure recovery; CI and reviewed-release configuration.

See [implementation and release review](../PR6_SECURITY_RELEASE.md), [performance evidence](../performance/PR6_BASELINE.md) and [original implementation plan](../PR6_IMPLEMENTATION_PLAN.md).

## Validation

- 61 backend tests pass without skips using disposable PostgreSQL 16 and a NOSUPERUSER/NOBYPASSRLS owner. Existing negative authorization, migrations, forced RLS and custody concurrency tests remain intact.
- 19 frontend unit tests pass; TypeScript has zero diagnostics; Expo exports 27 routes. Clean npm ci from the new lockfile succeeds.
- Desktop/mobile-web browser checks pass context switching, sign-out/relogin, rate-limit recovery and real local API custody transitions/persistence. Reload checks wait for hydrated authenticated context.
- Local load: 160 requests, eight workers, 50 seeded orders, zero errors. Throughput approximately 43 to 66 requests/second; per-endpoint p95 meets the documented local budget.
- CI workflow and Render checksPass configuration are committed configuration. Hosted CI execution, main-branch required-check enforcement and existing Render dashboard settings have not been verified or changed; GitHub API access returns Forbidden.

## Acceptance and boundaries

The implementation preserves tenant/store isolation and hides secrets in structured logs. Native iOS/Android checks, notification-provider staging acceptance and production load/schema inspection remain unperformed; native acceptance steps are documented. Scheduling capacity reservations are outside this maintenance/security implementation.

Only mahendraek/FabClean-SaaS is changed. PR #7–#12 retain their sequence. Explicit user approval is required before merge/deployment; approval from a previous PR does not apply here.
