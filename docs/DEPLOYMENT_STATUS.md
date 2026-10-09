# Render deployment status

Updated: 9 October 2026.

## Source and validation

With explicit user approval, the pre-PR #6 maintenance branch was merged into main at `50eeb3d1b2accd278ffff19484d2f430bcff8346`. Validated implementation `2a21ef8` is in its ancestry; the remote main ref was independently verified. The merge tree exactly matches the validated branch. This release includes PR #3 context switching, PR #4 tenant isolation and PR #5 hierarchy/handoffs, plus session revocation, stale-context write protection, consistent order assembly checks and TypeScript repairs.

Validation: 42 backend tests without skips using disposable PostgreSQL with a non-bypass owner role; 15 frontend tests; zero TypeScript diagnostics; 27-route Expo web export; desktop/mobile context regressions and real local API handoff browser workflows. See [audit details](PRE_PR6_AUDIT.md).

## Confirmed deployments

Authenticated Render API reports both services `live` on `50eeb3d1b2accd278ffff19484d2f430bcff8346`. Both automatically deployed after main was pushed; no duplicate manual deployment was requested.

| Service | Public URL | Service ID | Live deployment | Finished (India time) |
| --- | --- | --- | --- | --- |
| Web | https://fabclean-saas-web.onrender.com | `srv-db3nmv60tbcc73895n1g` | `dep-db48md8ae00c739q9u30` | 2026-10-09 12:08:23 IST |
| API | https://fabclean-saas-api.onrender.com | `srv-db3nmqij9qps738d2qkg` | `dep-db48md8ae00c739q9u60` | 2026-10-09 12:06:42 IST |

## Live verification

- API `/api/health`: HTTP 200, status `ok`, database `postgres`.
- Unauthenticated `/api/orders` and `/api/handoffs`: HTTP 401, requiring staff sign-in.
- Published API schema includes server sign-out and dedicated order-status routes.
- Web homepage: HTTP 200. Its fresh exported JavaScript bundle contains active-store headers, server sign-out and revocation failure feedback.

No production fixtures, test accounts or operational data writes were performed. Authenticated production session/custody execution and native-device execution remain unperformed. Production database contents/RLS were not independently queried; local integration tests validate those protections.

The deployment record is a documentation-only follow-up with `[skip render]` in its commit message. The running application commit remains `50eeb3d`. PR #6 is next; development has not started.
