# Render deployment status

Updated: 9 October 2026.

## Source and validation

PR #3 was merged into `main` at `cd996618bffc37fd55a0c5af812d54afc3889076` with explicit user authorization. Its validated PR head `8b764e7` is in the merge ancestry, verified locally and through remote refs. This includes PR #4 tenant isolation.

The restored checkout initially used a stale planning-branch reference; merge `622731c` contained only planning ancestry. The full implementation was then merged at `cd99661`. The superseded web build was cancelled through Render before the full implementation build proceeded.

Validation on merged code: 27 backend/API/PostgreSQL/migration tests, 9 frontend session/selection tests, desktop/mobile-web browser checks, and the 26-route Expo web export passed. Existing TypeScript baseline errors and native-device limitations remain recorded in the PR #3 scope.

## Confirmed deployments

Authenticated Render API access reports both services `live` on commit `cd996618bffc37fd55a0c5af812d54afc3889076`. Both track `main` with auto-deploy enabled. No additional manual deployment was enqueued.

| Service | Public URL | Service ID | Live deployment | Finished (UTC) |
| --- | --- | --- | --- | --- |
| API | https://fabclean-saas-api.onrender.com | `srv-db3nmqij9qps738d2qkg` | `dep-db46c62pubds73abv5gg` | 2026-10-09 03:59:09 |
| Web | https://fabclean-saas-web.onrender.com | `srv-db3nmv60tbcc73895n1g` | `dep-db46c62177jc73f8pjo0` | 2026-10-09 04:02:00 |

## Live verification

- API `/api/health`: HTTP 200, status `ok`, database `postgres`.
- Unauthenticated `/api/services` and `/api/context`: HTTP 401, requiring staff sign-in.
- Web HTML: HTTP 200. A fresh, cache-busted page and its exported JavaScript bundle contain the shared active-context header, switch control and confirmation. The first root response immediately after deployment still referenced the preceding cached bundle; the fresh response confirmed the new assets.
- The web service's configured backend URL matches `https://fabclean-saas-api.onrender.com`; environment values and credentials were not printed.

Authenticated production store-switching and native-device execution remain unperformed. No production database fixtures or data writes were performed. Production database-role permissions and migration logs were not independently inspected. Do not disable RLS or run integration fixtures on production.

The deployment record is a documentation-only follow-up with `[skip render]` in its commit message; the running application commit remains `cd99661`. PR #5 is next in the sequential queue and implementation has not started.
