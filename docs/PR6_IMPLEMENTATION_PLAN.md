# PR #6 implementation plan

Prepared: 12 October 2026. Status: implemented and validated; awaiting review. See [implementation and release review](PR6_SECURITY_RELEASE.md). Base: accepted main `d42f80f`, with live application merge `50eeb3d`. Scope: [security, testing and performance](roadmap/security-performance.md).

The pre-PR #6 fixes already provide server sign-out, stale-store request rejection, consistent assembly guards and a clean TypeScript baseline. Preserve those behaviors rather than rebuilding them.

## Features and acceptance checks

| Workstream | Planned implementation | Acceptance evidence |
| --- | --- | --- |
| Tenant and role protection | Audit operational and administrative endpoints, related-record IDs, exports and files against the role/store permission matrix; fix discovered gaps while preserving forced PostgreSQL RLS. | Negative tests for anonymous users, insufficient roles, other stores and foreign brands; non-bypass table-owner RLS tests. |
| Authentication and sessions | Add bounded sign-in abuse protection; audit password handling, expiry, disabled-user/role changes and revocation; fix confirmed gaps without weakening existing native secure storage or browser context behavior. | Failed-login limit tests, expired/revoked session rejection, permission-change tests, relogin and cross-tab regressions. Select a shared limiter appropriate to multiple API workers. |
| Deployment security configuration | Configure explicit production CORS origins; validate required production configuration and non-bypass database role at startup; keep local development configuration usable. | Allowed/disallowed origin tests and startup failure tests; documented Render settings and safe migration compatibility. |
| Safe access/audit logging | Add structured request IDs, timing, status and authorized actor/store identifiers where needed; ensure existing login and security logs omit tokens, passwords and request bodies containing private customer data. | Automated redaction tests and role/store-scoped access to audit records. |
| Concurrent operational writes | Audit order, payment, scheduling and custody read/modify/write operations; fix reproduced lost updates or duplicate actions using transactions, locks or conflict responses. | Concurrent requests against disposable PostgreSQL preserve totals, ownership and custody history; stale actions receive a defined conflict. |
| Performance | Add repeatable local load scenarios for order lists, dashboard, context and handoffs; record latency percentiles, throughput, errors and query behavior; optimize measured bottlenecks through bounded queries, indexes or connection reuse. | Reproducible dataset and documented environment/results; explicit thresholds selected from baseline measurements; isolation remains correct under concurrent load. |
| Web/mobile regression coverage | Extend existing browser and session tests for sign-in/out, switching stores, operational permissions and failure recovery; document native device acceptance steps. | Desktop and mobile-web checks pass; native execution reported separately and never inferred from browser tests. |
| CI and deployment guards | Add automated backend/PostgreSQL tests, frontend tests, TypeScript and Expo export checks; test repeatable migrations with a non-bypass owner. Document how Render deployment is gated by validated commits. | Reproducible CI checks; critical failures block the supported release workflow. Verify actual GitHub/Render permissions before claiming remote required checks or deployment gating. |

## Development order

1. Establish the permission matrix, security findings and reproducible load baseline.
2. Implement authentication, configuration and log protections with regression tests.
3. Fix reproduced concurrency issues and measured performance bottlenecks.
4. Integrate CI/release checks and finish browser/native acceptance documentation.
5. Publish implementation and evidence for review. Merge and deployment require explicit user approval.

## Completion requirements

Preserve the current 42 backend and 15 frontend test baseline; add meaningful regressions for each fix. Run the full backend suite against disposable PostgreSQL with a NOSUPERUSER/NOBYPASSRLS owner, frontend tests, TypeScript, Expo web export and browser flows. Never run load fixtures on production. Record load thresholds and results, failures/skips, native limitations and remote guard availability honestly.

PR #7–#12 retain their existing sequence. Platform onboarding, configuration inheritance, taxes, delivery maps, receipts and consolidated reports are outside this implementation.
