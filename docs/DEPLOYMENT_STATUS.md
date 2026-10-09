# Render deployment status

Updated: 9 October 2026.

## Source and validation

PR #5 was merged into `main` at `9753435ee3d4c348c9fd181fa3b7ced1fce5b9cf` with explicit user authorization. The validated PR #5 head `79eecb6` is in the merge ancestry; the remote main ref was independently verified. This release includes PR #3 context switching and PR #4 tenant isolation.

On the merged code, all 38 backend/API/PostgreSQL/migration tests and 12 frontend unit tests passed. Expo exported 27 web routes and the desktop/mobile-web context-switcher regression checks passed. The real local API handoff browser workflow passed during PR development. Existing TypeScript diagnostics and native-device limitations remain recorded in the scope document.

## Confirmed deployments

Authenticated Render API access reports both services `live` on commit `9753435ee3d4c348c9fd181fa3b7ced1fce5b9cf`. Both track main with auto-deploy enabled; no duplicate manual deployment was requested.

| Service | Public URL | Service ID | Live deployment | Finished (India time) |
| --- | --- | --- | --- | --- |
| Web | https://fabclean-saas-web.onrender.com | `srv-db3nmv60tbcc73895n1g` | `dep-db46s31srm7s738bpttg` | 2026-10-09 10:04:00 IST |
| API | https://fabclean-saas-api.onrender.com | `srv-db3nmqij9qps738d2qkg` | `dep-db46s31srm7s738bpu0g` | 2026-10-09 10:02:21 IST |

## Live verification

- API `/api/health`: HTTP 200, status `ok`, database `postgres`.
- Unauthenticated `/api/handoffs` and `/api/handoff-destinations`: HTTP 401, requiring staff sign-in.
- Live API schema includes handoff listing/dispatch, destination discovery and custody actions.
- Web `/handoffs`: HTTP 200. A fresh page and exported JavaScript bundle contain the handoff screen, confirmation control and return-receipt workflow.

Deployment runs the incremental store-operations schema migration at startup. No production test fixtures, test accounts or order/custody writes were performed by these smoke checks. Authenticated production handoff execution, physical bag operations and native-device execution remain unperformed. Production schema contents and RLS were not independently queried; the database-backed release started successfully and local integration checks validated the migration and policies.

The deployment record is a documentation-only follow-up with `[skip render]` in its commit message. The running application commit remains `9753435`. PR #6 (security, testing and performance) is next; development has not started.
