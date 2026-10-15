# PR #11 — manual WhatsApp receipts and communication preferences

Updated: 15 October 2026. The user requested deletion of the tax-related implementation. This scope supersedes the earlier location-tax/provider requirements. Existing branch: `codex/pr-11-receipts-location-taxes`; branch name is retained for continuity. No merge or deployment is authorized by this development request.

## Manual WhatsApp sharing

Staff use their own WhatsApp app/Web account. No messaging-provider API key, rented number or worker is needed. In Customer Profile, record WhatsApp consent, enable receipts and record an affirmative consent note. In Order Details, select Preview WhatsApp receipt, review the international number and totals, then select Open WhatsApp. Staff must check the recipient and tap Send in WhatsApp; Cancel closes the preview without opening WhatsApp.

The backend checks selected-store visibility, consent and current contact details for preview and confirmation. A fingerprint covers recipient, consent revision, rendered message and financial snapshot. Changed payments, phone, preferences or branding require a new preview. Numbers require an explicit international country code; spaces/parentheses/dashes are normalized without guessing a country. Oversized receipts are rejected rather than truncated. A successful preparation appends `whatsapp_share_prepared` and the receipt snapshot to the existing forced-RLS, append-only audit. It does not create an automatic send, delivery claim or provider request.

## Optional email/SMS delivery

Existing consent-aware email/SMS delivery remains optional and disabled by default. Customers start opted out of WhatsApp, email and SMS. Channel opt-ins require a consent note; receipt/status preferences are separate. Brand templates and store sender overrides use the existing configuration inheritance model. Placeholders are restricted, and the server appends financial totals.

Order, payment/refund and ready-for-pickup events enqueue messages transactionally when optional notifications are enabled. Dispatch commits a serialized claim before network I/O, rechecks consent and unchanged valid contact details, and blocks when credentials/senders are missing. Accepted is distinct from delivered. Only definite HTTP 429 rejections retry, with backoff and at most three attempts; ambiguous outcomes/crashed claims are never automatically resent. Signed SendGrid delivery events are scoped, timestamp/signature checked and deduplicated; unsubscribe/spam events revoke email consent. SMS delivery can be checked with the authenticated provider resource. An in-flight or manually opened message cannot be recalled by a later opt-out.

## Tax implementation removed

Removed backend tax engine, provider adapter, quote/import storage creation, rule/estimate/report APIs, tax migrations on startup, tax screen/navigation, jurisdiction/taxability controls and tax-estimate requests. The dedicated provider/tax suites and browser fixtures are removed along with their feature. Country/state/postal selectors, store coverage, theme presets and sample records remain independent location/business functionality.

`backend/pricing.py` now validates decimal money, positive quantities, discounts, delivery fees and gross refund limits. New orders have tax zero, no tax snapshot and an independently saved currency. Client-supplied tax fields are ignored; currency is no longer coupled to a tax snapshot. New receipt messages contain ordinary financial totals and no generated tax line. Refunds do not compute new tax credits.

Historical invoice tax/snapshots and prior payment/refund metadata remain readable. Existing tax/provider tables and migration records are not dropped or rewritten; new installations do not create them. Repricing invoices with archived tax snapshots/amounts is rejected so historical amounts cannot be silently altered. Notes/status edits and payment/refund balance guards remain supported. Retained invoice/receipt tax fields are read-only historical compatibility, not an active calculation feature.

The previous free tax-provider requirement is withdrawn; it no longer blocks PR #11. No production database operation, real message, merge or deployment was performed. Cloud environment settings are deliberately untouched while the user's save/publish conflict is unresolved; previously saved tax-related environment notes/domains may therefore remain stale.

## Runtime and validation

Use the existing checkout and setup instructions in AGENTS.md. No new dependency or migration is needed for this removal. WhatsApp sharing requires no environment secrets or worker. Optional SendGrid/Twilio credentials and the scoped worker remain documented by their code and prior Git history; do not request these as prerequisites for WhatsApp development.

Run `scripts/validate.sh` with a disposable local FABCLEAN_TEST_DATABASE_URL, the prepared Python executable and Expo/Chromium overrides from AGENTS.md. The retained gate checks PostgreSQL isolation/migration/consent/receipts/pricing, refund concurrency, archived financial records, frontend unit tests, TypeScript, web export, local load and seven desktop/mobile browser suites. WhatsApp navigation is intercepted and providers use controlled responses; no real messages are sent. Final results are recorded in the development tracker.

Earlier receipt implementations were published at `5388cc3`/`bc2a050`, and manual WhatsApp at `9159585`; later documentation head `81c8d09` preceded this removal. These are historical Git publication facts, not claims that the current change is merged, deployed or reviewed. Main/deployment remain unchanged until an explicitly authorized release.

## Fresh revalidation — 15 October 2026

The published application revision `cae2bc43cc6ae93686ded33ecd266a8084662969` passed the full gate again in a new disposable local PostgreSQL database: 148 backend tests with no skips, 36 frontend tests, TypeScript, 31-route Expo web export, seven desktop/mobile browser suites and 160 load requests with zero errors (60.92 requests/second, worst p95 240 ms). This validates the current published scope, including manual WhatsApp sharing and removal of active tax calculation. No additional application changes were needed. Provider requests remained mocked, WhatsApp navigation was intercepted, and actual external delivery/native-device behavior is unverified. GitHub API access was Forbidden; Git publication does not establish review, hosted CI, merge or deployment state.

## Merge acceptance — 15 October 2026

The user explicitly authorized merge and deployment. GitHub confirms PR #11 merged at `d36b6d6c7efdd84c284f4647460b488991735344` (15:38:27 IST); the merged tree matches accepted head `93e75f80ed5d6fc00b4f3f166286b433ca2656d3`, whose hosted validation checks all succeeded. Earlier “not merged” notes above describe the development stage and are superseded by this acceptance.

Deployment remains pending. The existing Render credential is ready, but the published network policy excludes `api.render.com` and read-only requests to both SaaS services return proxy 403. No deployment request or environment-setting change was made. After access is restored, deploy the approved merge explicitly to `fabclean-saas-api` and `fabclean-saas-web`, preserve existing service configuration/credentials, and verify both deployment commit IDs and smoke checks before calling it live.
