# Render deployment status

Updated: 12 October 2026.

## PR #9 — merged; deployment pending

On 12 October 2026, the user explicitly authorized merge and deployment. PR #9 was merged into main at `9e68ce3d43eea0ea12a1fc9b1d2d36bd6a70a28f`; authenticated Git independently verified remote main. The merged tree exactly matches validated head `fa45909`: 119 backend tests without skips, 26 frontend tests, clean TypeScript, 30-route export, five desktop/mobile browser suites and zero-error load validation. See [implementation evidence](PR9_IMPLEMENTATION.md).

Deployment is blocked in the current environment: no Render credential binding is present, and HTTPS CONNECT requests to `api.render.com` and the API public URL return proxy 403. No deployment was triggered. Current live service state is unverified; PR #8 below is the last confirmed deployment. GitHub API hosted review/merge/CI metadata also remains Forbidden; the main Git merge is independently verified.

The saved environment draft adds `api.render.com`, `fabclean-saas-api.onrender.com`, and `fabclean-saas-web.onrender.com` and declares `RENDER_API_KEY` for the Render API. Enter the credential securely in environment settings, save the changes and publish the environment, then retry authenticated Render access. Deploy both existing services to `9e68ce3` and verify their exact live commit, API health/authentication/CORS, OpenAPI tax routes and the fresh web tax screen/bundle. Do not use production fixtures or operational writes for smoke checks.

## Last confirmed live release — PR #8

The user explicitly authorized merge and deployment. PR #8 was merged into main at `7b193dbb7f3c148acf2c556947f7528759d1fe23`, independently verified through authenticated Git. Implementation `744947a`, planning merge `4590250`, validated compatibility fix `7a3696d` and published head `7ed2213` are retained in the merge ancestry. The merged tree exactly matches the locally validated branch. GitHub hosted CI/review/open/closed metadata remains unverified because API access is Forbidden; this release used the explicitly approved local-validation/manual-deployment fallback.

Validation: 100 backend tests without skips on disposable PostgreSQL with a non-bypass owner, 26 frontend tests, clean TypeScript, 29-route Expo export, all four desktop/mobile context/custody/platform/configuration browser suites, and a zero-error local load gate. See [implementation and acceptance notes](PR8_IMPLEMENTATION.md).

Authenticated Render API confirms both services **live** at `7b193dbb7f3c148acf2c556947f7528759d1fe23`. Automatic deployment remains off; service configuration and environment bindings were preserved.

| Service | Public URL | Service ID | Live deployment | Finished (India time) |
| --- | --- | --- | --- | --- |
| API | https://fabclean-saas-api.onrender.com | `srv-db3nmqij9qps738d2qkg` | `dep-db6b3j2d0e5s73a31veg` | 2026-10-12 15:40:28 IST |
| Web | https://fabclean-saas-web.onrender.com | `srv-db3nmv60tbcc73895n1g` | `dep-db6b3j5ckfvc73cqjh2g` | 2026-10-12 15:41:37 IST |

Public verification passed: API health reports PostgreSQL, request IDs and approved CORS; unauthenticated configuration, orders, handoffs and platform plans/health/audit return 401 with no-store; configuration PUT preflight accepts the web origin and rejects an untrusted origin; published OpenAPI contains configuration read/write and earlier platform routes; the homepage and configuration route return 200, and freshly fetched JavaScript contains the PR #8 inheritance editor, source labels and configuration endpoint code. Startup completed successfully; production migration rows and RLS were not directly inspected.

No production fixtures, sign-in attempts, configuration/operational writes or load traffic were used for smoke checks. Authenticated production inheritance and native-device acceptance remain unperformed. This deployment record is a documentation-only follow-up [skip render]; the live application commit remains `7b193db`. PR #9 is next and has not started.

## Previous release — PR #7 (historical evidence)

The user explicitly authorized merge and deployment. PR #7 was merged into main at `43f3cbfd6db1183525bf1207700bfa9890fe83fa`; authenticated Git independently verified the remote main ref. Implementation `065d1e0`, planning merge `e1a8977` and published head `59b4fc9` are retained in the merge ancestry. The merged tree exactly matches the locally validated branch. GitHub API review/CI/open/closed metadata remains unverified because access is Forbidden; this is the approved manual-release fallback.

Validation: 80 backend tests without skips on disposable non-bypass PostgreSQL, 23 frontend tests, zero TypeScript diagnostics, 28-route Expo export, desktop/mobile context, custody and onboarding/store-recovery browser flows, and a local load gate with zero errors. See [implementation and acceptance notes](PR7_IMPLEMENTATION.md).

At the PR #7 release, authenticated Render API confirmed both deployments **live** at `43f3cbfd6db1183525bf1207700bfa9890fe83fa`. Automatic deployment remains off; service roots, commands and environment configuration were preserved.

| Service | Public URL | Service ID | Live deployment | Finished (India time) |
| --- | --- | --- | --- | --- |
| API | https://fabclean-saas-api.onrender.com | `srv-db3nmqij9qps738d2qkg` | `dep-db6ajg3bc2fs73bedt00` | 2026-10-12 15:06:09 IST |
| Web | https://fabclean-saas-web.onrender.com | `srv-db3nmv60tbcc73895n1g` | `dep-db6ajgajnfac73d2bdrg` | 2026-10-12 15:07:20 IST |

Public verification passed: API health reports PostgreSQL with request IDs and the approved CORS origin; unauthenticated orders, handoffs, platform plans/health/audit return 401 with no-store; invitation preflight accepts the web origin and rejects an untrusted origin; published OpenAPI contains the new platform/invitation endpoints; the homepage and invitation route return 200 and their freshly fetched JavaScript contains PR #7 acceptance and platform/store-recovery code. Startup completed successfully; production migration rows and RLS were not directly inspected.

No production test identities, invitations, authentication attempts, operational writes or load traffic were used. Authenticated production onboarding, actual sharing/delivery and native-device acceptance remain unperformed. This deployment record is a documentation-only follow-up [skip render]; the running application commit remains `43f3cbf`. At that release, PR #8 had not started; its current release evidence appears above.

## Previous release — PR #6 (historical evidence)

PR #6 was accepted and merged into main at `dd031a775d7bd511bf3f82f1d4fa6ee726fd1567` with explicit user approval. Published head `c8cbd1b` and implementation `9ee0362` are in the merge ancestry; the remote main ref was independently verified. The merged tree exactly matches the validated implementation. This release includes earlier tenant isolation, context switching, hierarchy/handoffs and maintenance fixes.

Validation: 61 backend tests without skips on disposable PostgreSQL with a non-bypass owner, 19 frontend tests, clean TypeScript, 27-route Expo export, desktop/mobile context and real local API custody browser checks, and the documented local load gate. The final production-configuration guard also passed its targeted tests. See [security release review](PR6_SECURITY_RELEASE.md) and [load evidence](performance/PR6_BASELINE.md).

### PR #6 confirmed deployments

At the PR #6 release, authenticated Render API reported both services live on `dd031a775d7bd511bf3f82f1d4fa6ee726fd1567`. The user authorized this manual release. Automatic deployment is now **off** on both services: GitHub CI/required-check state remains unavailable through the Forbidden API, so the documented fallback uses complete local validation plus explicit approval. The blueprint retains checksPass as the desired future configuration; it is not the current dashboard setting.

| Service | Public URL | Service ID | Live deployment | Finished (India time) |
| --- | --- | --- | --- | --- |
| Web | https://fabclean-saas-web.onrender.com | `srv-db3nmv60tbcc73895n1g` | `dep-db67bgflot8c73956cm0` | 2026-10-12 11:25:22 IST |
| Api | https://fabclean-saas-api.onrender.com | `srv-db3nmqij9qps738d2qkg` | `dep-db67b3nlk1mc73c6q1i0` | 2026-10-12 11:23:29 IST |

API settings verified: root directory backend, APP_ENV=production, explicit web HTTPS CORS origin, pool size eight, unchanged existing secret database URL, and Uvicorn --no-access-log. Web settings verified: root directory frontend, publish path dist, Node 24, npm ci/export build and the actual deployed API URL. No secrets are stored in this record.

Initial builds failed because new commands were applied while both existing root directories were empty. Directory/publish settings were corrected to match render.yaml and the same merged commit was redeployed. An intermediate web attempt was canceled before retrying with the corrected publish path. Both final deployments succeeded. Build-log API retrieval encountered Cloudflare 403; successful deployment status and public smoke checks provide the final verification evidence.

### PR #6 live verification

- API health: HTTP 200, database postgres, production CORS and X-Request-ID present.
- Orders and handoffs without a session: HTTP 401, readable by the approved web origin, with no-store.
- Sign-in preflight from the approved web origin succeeds; untrusted-origin preflight returns HTTP 400 without allow-origin.
- Published API schema includes recurring generation and operational routes.
- Web homepage returns HTTP 200; its fresh exported JavaScript contains PR #6 HTTP recovery/retry guidance and active-store request headers.

The additive authentication-budget migration completed at application startup. No production fixtures, test accounts, sign-in attempts, load traffic, or operational data writes were used in smoke verification. Production database contents/RLS, authenticated session/custody execution, notification-provider staging acceptance and native-device execution remain unperformed. GitHub hosted CI/review flags remain unverified.

The deployment record is a documentation-only follow-up with [skip render]. The running application commit remains `dd031a7`. At that release, PR #7 had not started; the current release above supersedes that status.
