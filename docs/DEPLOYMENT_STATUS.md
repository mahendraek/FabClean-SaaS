# Render deployment status

Updated: 12 October 2026.

## Source and validation

PR #6 was accepted and merged into main at `dd031a775d7bd511bf3f82f1d4fa6ee726fd1567` with explicit user approval. Published head `c8cbd1b` and implementation `9ee0362` are in the merge ancestry; the remote main ref was independently verified. The merged tree exactly matches the validated implementation. This release includes earlier tenant isolation, context switching, hierarchy/handoffs and maintenance fixes.

Validation: 61 backend tests without skips on disposable PostgreSQL with a non-bypass owner, 19 frontend tests, clean TypeScript, 27-route Expo export, desktop/mobile context and real local API custody browser checks, and the documented local load gate. The final production-configuration guard also passed its targeted tests. See [security release review](PR6_SECURITY_RELEASE.md) and [load evidence](performance/PR6_BASELINE.md).

## Confirmed deployments

Authenticated Render API reports both services live on `dd031a775d7bd511bf3f82f1d4fa6ee726fd1567`. The user authorized this manual release. Automatic deployment is now **off** on both services: GitHub CI/required-check state remains unavailable through the Forbidden API, so the documented fallback uses complete local validation plus explicit approval. The blueprint retains checksPass as the desired future configuration; it is not the current dashboard setting.

| Service | Public URL | Service ID | Live deployment | Finished (India time) |
| --- | --- | --- | --- | --- |
| Web | https://fabclean-saas-web.onrender.com | `srv-db3nmv60tbcc73895n1g` | `dep-db67bgflot8c73956cm0` | 2026-10-12 11:25:22 IST |
| Api | https://fabclean-saas-api.onrender.com | `srv-db3nmqij9qps738d2qkg` | `dep-db67b3nlk1mc73c6q1i0` | 2026-10-12 11:23:29 IST |

API settings verified: root directory backend, APP_ENV=production, explicit web HTTPS CORS origin, pool size eight, unchanged existing secret database URL, and Uvicorn --no-access-log. Web settings verified: root directory frontend, publish path dist, Node 24, npm ci/export build and the actual deployed API URL. No secrets are stored in this record.

Initial builds failed because new commands were applied while both existing root directories were empty. Directory/publish settings were corrected to match render.yaml and the same merged commit was redeployed. An intermediate web attempt was canceled before retrying with the corrected publish path. Both final deployments succeeded. Build-log API retrieval encountered Cloudflare 403; successful deployment status and public smoke checks provide the final verification evidence.

## Live verification

- API health: HTTP 200, database postgres, production CORS and X-Request-ID present.
- Orders and handoffs without a session: HTTP 401, readable by the approved web origin, with no-store.
- Sign-in preflight from the approved web origin succeeds; untrusted-origin preflight returns HTTP 400 without allow-origin.
- Published API schema includes recurring generation and operational routes.
- Web homepage returns HTTP 200; its fresh exported JavaScript contains PR #6 HTTP recovery/retry guidance and active-store request headers.

The additive authentication-budget migration completed at application startup. No production fixtures, test accounts, sign-in attempts, load traffic, or operational data writes were used in smoke verification. Production database contents/RLS, authenticated session/custody execution, notification-provider staging acceptance and native-device execution remain unperformed. GitHub hosted CI/review flags remain unverified.

The deployment record is a documentation-only follow-up with [skip render]. The running application commit remains `dd031a7`. PR #7 is next; its development has not started.
