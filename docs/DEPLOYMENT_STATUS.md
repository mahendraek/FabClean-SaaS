# Render deployment status

Updated: 9 October 2026.

## Source and validation

PR #4 was merged into `main` at `971f2bc84a23281e986b374483bb562ee4314306` with explicit user authorization. Remote ancestry was verified. All 26 backend/API/PostgreSQL/migration tests passed on the merge commit; the implementation's Expo web export passed all 26 routes.

## Confirmed deployments

Authenticated Render API access succeeded after the user saved `RENDER_API_KEY`. Both services track `main` with auto-deploy enabled. Render reports these deployments as `live`, running commit `a800a7369647c7d39fc1ceb7765c1a17fad64e0c`, which includes the PR #4 merge and deployment documentation.

| Service | Public URL | Service ID | Live deployment | Finished (UTC) |
| --- | --- | --- | --- | --- |
| API | https://fabclean-saas-api.onrender.com | `srv-db3nmqij9qps738d2qkg` | `dep-db451rs9v7es73aa1mc0` | 2026-10-09 02:27:59 |
| Web | https://fabclean-saas-web.onrender.com | `srv-db3nmv60tbcc73895n1g` | `dep-db451rqpubds73ab18a0` | 2026-10-09 02:31:07 |

Auto-deployment already completed; no duplicate deployment was triggered. Service names differ from the repository blueprint's `fabclean-api` and `fabclean-web` names.

## Remaining verification

Direct requests to the actual public domains failed at the cloud network proxy with `403 Forbidden`. This is an access-policy failure, not an observed application response. A saved configuration draft adds `fabclean-saas-api.onrender.com` and `fabclean-saas-web.onrender.com`, preserving existing custom domains. The tool reports `requires_publish: true`: review/save the changes in environment settings and publish the environment to apply them.

After publication, check API health, unauthenticated operational requests returning 401, and the static page/assets. An authenticated store-scoped smoke check requires existing authorized test access. Production database contents, database-role permissions and migration logs have not been independently inspected; Render's live status alone does not establish those checks. Never run integration fixtures on production or disable RLS to bypass errors.

No credentials or service environment values were printed or saved in the repository. PR #3 remains selected on `codex/pr-3-brand-store-switcher`; feature implementation has not started.
