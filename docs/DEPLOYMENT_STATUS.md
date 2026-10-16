# Render deployment status

Updated: 16 October 2026.

## Current live release — PR #12 consolidated reporting and exports

The user explicitly authorized merge and deployment on 16 October 2026. PR #12 merged at `ab3a75663f7b2dcd268707df27f2d656b6bf3240`; its tree exactly matches validated head `820a0ea`. Both exact-head hosted checks passed (`38827644888`, `38827639522`). The combined local gate passed 164 backend tests without skips, 44 frontend tests, TypeScript, 32-route export, all nine desktop/mobile browser suites and 160 load requests without errors. This release retains the PR #13 printing implementation.

Authenticated Render API confirms both services **live** at the approved merge:

| Service | Live deployment | Finished (India time) |
| --- | --- | --- |
| API | `dep-db8mng8473hc739d3nsg` | 2026-10-16 05:42:59 IST |
| WEB | `dep-db8mngl9fdbs73913p8g` | 2026-10-16 05:44:05 IST |

All **15 read-only public smoke checks passed**: PostgreSQL API health; reporting OpenAPI routes with printing retained; authentication, no-store, CORS and request IDs on all four reporting endpoints and the print preview; trusted/untrusted reporting preflight; homepage/reports/hardware/print-preview/order-detail HTML; and freshly fetched JavaScript containing reporting, summary export and printing workflows.

Web: https://fabclean-saas-web.onrender.com/reports · API: https://fabclean-saas-api.onrender.com

No production records, authentication attempts, messages or physical prints were created by verification. Production reporting with a signed-in business user, native sharing and physical printer/media checks remain manual. Existing service commands, credentials and automatic deployment off were preserved; no environment settings changed. This documentation-only follow-up leaves the running services at `ab3a75663f7b2dcd268707df27f2d656b6bf3240`.

## Previous release — PR #13 receipt and garment-tag printing

The user explicitly authorized merge and deployment on 16 October 2026. GitHub confirms PR #13 merged at `a1c012e947daeab9158cb6936217aa7ae7334678`; the merged tree exactly matches accepted head `e67186c`. Both exact-head hosted validation runs passed (`38727121787`, `38727116721`). Full local validation passed 155 backend tests without skips, 41 frontend tests, TypeScript, 32-route export, all eight desktop/mobile browser suites and the zero-error load gate.

Authenticated Render API confirms both services **live** at `a1c012e947daeab9158cb6936217aa7ae7334678`:

| Service | Live deployment | Finished (India time) |
| --- | --- | --- |
| API | `dep-db8mfse89jmc73enkpm0` | 2026-10-16 05:26:26 IST |
| WEB | `dep-db8mfsavcj2c73clq9f0` | 2026-10-16 05:27:55 IST |

All 13 read-only public smoke checks passed: PostgreSQL API health; new preview/confirmation OpenAPI routes; authenticated boundaries, no-store, request IDs and CORS on protected orders/preview; trusted and untrusted preflight behavior; six web pages including `/print-preview`; and a fresh JavaScript bundle containing receipt profiles and print-confirmation code. No production records, sign-in attempts, real messages or physical print operations were created during smoke checks. Actual printer/media and native-device acceptance remain manual.

API: https://fabclean-saas-api.onrender.com · Web: https://fabclean-saas-web.onrender.com

Existing service roots/build commands, credentials and automatic deployment off were preserved. No environment settings changed. PR #12 remains an independent open draft and is not included in this release. This documentation-only follow-up leaves the running services at `a1c012e947daeab9158cb6936217aa7ae7334678`.

## Previous release — PR #11 receipts/preferences and tax removal

The user explicitly authorized merge and deployment. PR #11 merged at `d36b6d6c7efdd84c284f4647460b488991735344`; its tree equals accepted head `93e75f8`, whose three hosted checks all passed. After the user restored Render network access, both deployment requests explicitly targeted this exact merge. Existing service roots, build/start commands, credentials and automatic deployment off were preserved. No environment configuration was changed during deployment.

Authenticated Render API confirms both services **live** at the approved merge:

| Service | Public URL | Live deployment | Finished (India time) |
| --- | --- | --- | --- |
| API | https://fabclean-saas-api.onrender.com | `dep-db8aivom7kps73dmrpr0` | 2026-10-15 15:54:08 IST |
| Web | https://fabclean-saas-web.onrender.com | `dep-db8aivtg1s2s739l43sg` | 2026-10-15 15:55:19 IST |

API deployment logs confirm a successful build, application startup completion and Uvicorn listening. Web logs confirm `Exported: dist`, upload and “Your site is live”. The release includes consent-aware manual WhatsApp sharing, optional default-off email/SMS delivery and audit, removal of active tax calculation with historical invoices retained, and the handoff browser-check correction.

After the user enabled access to the public app hostnames, all **11 read-only public smoke checks passed** on 15 October 2026. `/api/health` returned 200 with `status: ok` and `database: postgres`; OpenAPI returned 200, includes the WhatsApp receipt and communication-preference routes, and exposes no `/api/taxes` routes. Unauthenticated `/api/orders` and `/api/notifications/outbox` returned 401 with approved-origin CORS and `Cache-Control: no-store`. The homepage, order-detail, customer-profile, notifications and configuration pages all returned 200 HTML. Trusted preflight returned 200; an untrusted origin returned 400 without an allow-origin header.

No production customer/sample writes or real messages were sent. Authenticated production flows and physical-device sharing remain untested. Environment configuration was not edited by the agent. Documentation-only follow-up leaves both running services at `d36b6d6`.

## Previous PR #11 access blocker — resolved

PR #11 was accepted and merged with explicit user authorization at `d36b6d6c7efdd84c284f4647460b488991735344` on 15 October 2026 at 15:38:27 IST. The merged tree equals accepted head `93e75f8`; all its hosted validation checks passed. This release contains manual WhatsApp receipts, communication preferences, optional email/SMS delivery, active tax removal with historical invoices preserved, and the handoff browser-check correction.

No Render deployment request was sent: the current enforced environment network policy excludes `api.render.com`, and both service-read requests returned proxy 403 despite a ready existing Render credential. Environment settings were left unchanged. Restore API access, then deploy this exact approved merge to the two SaaS services and verify live commit IDs and smoke results. The last verified live deployments remain the maintenance release recorded below; current live status was not reverified during the blocked request.

## Previous release — admin location, taxes and branding maintenance (historical evidence)

The user explicitly approved merge and deployment. Maintenance branch `codex/admin-location-tax-branding` was merged into main at `930a43efd068261c0e6358a2dfecc323641c19ad` and independently verified through authenticated Git. The merged tree exactly matches validated head `4380b4f`: 142 backend tests without skips, 33 frontend tests, TypeScript, 31-route export, seven desktop/mobile suites and zero-error local load validation. See [implementation and outstanding data work](ADMIN_LOCATION_BRANDING.md).

Authenticated Render API confirms both services **live** at that exact merge. Existing credentials, service settings and automatic deployment off were preserved. GitHub hosted review/CI metadata remains unverified; this uses the authorized manual-release fallback.

| Service | Public URL | Service ID | Live deployment | Finished (India time) |
| --- | --- | --- | --- | --- |
| API | https://fabclean-saas-api.onrender.com | `srv-db3nmqij9qps738d2qkg` | `dep-db7gnrqj9qps73cdev90` | 2026-10-14 10:29:39 IST |
| Web | https://fabclean-saas-web.onrender.com | `srv-db3nmv60tbcc73895n1g` | `dep-db7gnrqj9qps73cdevvg` | 2026-10-14 10:30:51 IST |

Public checks pass: API health reports PostgreSQL; OpenAPI publishes location options, postal lookup and the scoped sample endpoint. Unauthenticated calls return 401 with approved-origin CORS and no-store; trusted preflight succeeds and untrusted preflight returns 400. Homepage, store administration, taxes and configuration pages return 200. Fresh published JavaScript contains dependent selectors, postal lookup, theme presets and the explicit sample action.

No production sample records or real tax rates were created. Live CleanandDry location inspection and data changes remain pending an application admin session, which is absent from this environment. An authorized user can select CleanandDry in Schaumburg and use the sample action under Brand Defaults & Overrides. Exact jurisdiction, service tax treatment and rates must be verified before tax-rule changes. Live postal-provider lookup and authenticated production flows remain unverified. Documentation-only follow-up leaves the running application at `930a43e`.

## Previous release — PR #10 (historical evidence)

The user explicitly authorized merge and deployment. PR #10 was merged into main at `bf41434191f7beaf0650600d2d99fa55c965040a`, independently verified through authenticated Git. The merged tree exactly matches validated head `569b746`: 136 backend tests without skips, 31 frontend tests, clean TypeScript, 31-route Expo export, six desktop/mobile browser suites and zero-error load validation. See [implementation and rollout notes](PR10_IMPLEMENTATION.md).

Authenticated Render API confirms both services **live** at that exact approved merge. Existing service settings, application credentials, roots and automatic deployment off were preserved.

| Service | Public URL | Service ID | Live deployment | Finished (India time) |
| --- | --- | --- | --- | --- |
| API | https://fabclean-saas-api.onrender.com | `srv-db3nmqij9qps738d2qkg` | `dep-db6t5m3ncjis73ep2d4g` | 2026-10-13 12:13:41 IST |
| Web | https://fabclean-saas-web.onrender.com | `srv-db3nmv60tbcc73895n1g` | `dep-db6t5mbncjis73ep2e1g` | 2026-10-13 12:14:51 IST |

Public checks pass: API health reports PostgreSQL; published OpenAPI contains coverage GET/PUT and address checks. Unauthenticated GET/PUT policy and POST eligibility calls return 401 with approved-origin CORS and no-store. Policy PUT preflight accepts the web origin and rejects an untrusted origin. The homepage and `/coverage` return 200; freshly fetched JavaScript contains the coverage checker, polygon controls, OSM tile URL and copyright attribution.

Coverage remains opt-in for each store. Brand administrators first save valid store coordinates; store administrators then configure/enable radius or polygon coverage under Admin → Delivery Coverage Map. This release did not enable policies, geocode addresses or change existing delivery rules automatically.

No production fixtures, sign-in attempts, policy writes, address-check records or load traffic were used for smoke verification. Production migration rows/RLS and authenticated coverage execution were not directly inspected; startup completed and local migration/integration tests passed. Actual OSM tile fetches remain unverified from this cloud environment pending its saved network draft; published client URLs and offline fallback are verified. Native-device checks remain unperformed. Hosted GitHub CI/review flags remain unverified. This documentation-only follow-up leaves the live application commit at `bf41434`.

## Previous release — PR #9 (historical evidence)

The user explicitly authorized merge and deployment. PR #9 was merged into main at `9e68ce3d43eea0ea12a1fc9b1d2d36bd6a70a28f`; authenticated Git independently verified remote main. The merged tree exactly matches validated head `fa45909`: 119 backend tests without skips, 26 frontend tests, clean TypeScript, 30-route export, five desktop/mobile browser suites and zero-error load validation. See [implementation evidence](PR9_IMPLEMENTATION.md).

The earlier credential/network blocker was resolved after the user updated the cloud environment. Authenticated Render API confirms both deployments **live** at the exact approved merge `9e68ce3`. Existing settings, service roots, application credentials and automatic deployment off were preserved. The Render deployment key is bound only to `api.render.com`; it is not an application secret.

| Service | Public URL | Service ID | Live deployment | Finished (India time) |
| --- | --- | --- | --- | --- |
| API | https://fabclean-saas-api.onrender.com | `srv-db3nmqij9qps738d2qkg` | `dep-db6sb9om7kps73b6bqk0` | 2026-10-13 11:17:35 IST |
| Web | https://fabclean-saas-web.onrender.com | `srv-db3nmv60tbcc73895n1g` | `dep-db6sba3ncjis73em6og0` | 2026-10-13 11:18:34 IST |

Public checks pass: API health reports PostgreSQL; published OpenAPI contains tax rules, rule end/void, estimates and financial tax reporting. Unauthenticated rules/estimates/reporting return 401 with approved-origin CORS and no-store. Tax-rule POST preflight accepts the web origin and rejects an untrusted origin. The web homepage and `/taxes` return 200; freshly fetched JavaScript contains `/taxes/rules`, `/taxes/estimate` and `/financial/taxes`.

No production fixtures, authentication attempts, tax-rule writes, refunds or load traffic were used. Production migration rows/RLS and authenticated tax execution were not directly inspected; successful API startup and local migration/integration tests supply the current evidence. Native devices and actual printers remain untested. GitHub hosted CI/review metadata remains unverified. This documentation-only follow-up does not change the live application commit.

## Previous release — PR #8 (historical evidence)

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
