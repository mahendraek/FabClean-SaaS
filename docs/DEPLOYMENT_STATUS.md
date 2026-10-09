# Render deployment status

Updated: 9 October 2026.

## Source and validation

PR #4 was merged into `main` at `971f2bc84a23281e986b374483bb562ee4314306` with explicit user authorization. The push and remote ancestry were verified. All 26 backend/API/PostgreSQL/migration tests passed on the merge commit; the implementation's Expo web export previously passed all 26 routes.

The repository's Render blueprint defines `fabclean-api` (FastAPI) and `fabclean-web` (Expo static export). The user provided the static-service dashboard: https://dashboard.render.com/static/srv-db3nmv60tbcc73895n1g . The actual API service ID and live service settings are not yet known.

## Deployment state

Not confirmed. Pushing main may trigger Render auto-deploy if configured, but no successful Render deployment or running commit has been observed. Do not report the application as deployed from a Git push alone.

- Render API key/deploy-hook bindings were absent in the cloud instance.
- Requests to the blueprint's onrender.com URLs failed at the network proxy with `403 Forbidden`.
- A cloud configuration draft now declares `RENDER_API_KEY` for `api.render.com` and adds `api.render.com`, `fabclean-api.onrender.com` and `fabclean-web.onrender.com` to the custom network domains. Draft persistence is confirmed; runtime application/publication is not.
- The user must enter the credential securely in environment settings, review/save the draft and publish the environment. Do not place credentials or deploy-hook URLs in chat or repository files.

## Resume deployment

1. Recheck binding presence and non-destructive Render API access after the settings change. Never print keys or service environment values.
2. Inspect service metadata for `srv-db3nmv60tbcc73895n1g` and identify the API service tied to `mahendraek/FabClean-SaaS`. Verify both track `main`, working directories and commands match `render.yaml`, and discover the actual public domains before health checks.
3. Check deployment history first: if auto-deploy already deployed the intended main commit, validate it rather than enqueueing a duplicate deployment.
4. The database role must be `NOSUPERUSER NOBYPASSRLS` and own the application schema for this migration. Confirm database backup/recovery and migration outcome through the available Render controls/logs. No production database has been inspected or modified by this cloud task. Never disable RLS to bypass startup errors.
5. Use the user's existing merge/deploy authorization to deploy the intended main commit when prerequisites are available. Follow Render deployment status and investigate failures.
6. Verify the API health response, unauthenticated operational requests returning 401, the static page/assets, and a representative authenticated store-scoped flow using existing authorized test access. Record actual deployed commits and successful evidence here.

PR #3 is selected next on `codex/pr-3-brand-store-switcher`; no feature implementation is included in this deployment-status update.
