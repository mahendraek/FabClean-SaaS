# PR #11 — receipts, consent and location tax completion

Implementation branch: `codex/pr-11-receipts-location-taxes`, based on accepted main `4b983a1`. Development is authorized; merge and deployment are not. Publication and final validation are recorded in the development tracker.

## Behavior

Customers start opted out of both email and SMS. Customer Profile records channel consent, separate receipt/status preferences, a consent note and an append-only audit. Enabling a channel requires an affirmative note. Preferences and notifications belong to the selected store; related customer/order IDs and PostgreSQL forced RLS prevent foreign-store access.

Order creation enqueues order-received messages and order receipts when notifications are enabled. Payment/refund/adjustment transactions enqueue payment receipts; ready-for-pickup transitions enqueue status messages. These writes share the operational database transaction; external provider requests occur only after a durable dispatch claim. An explicit receipt action captures current order/payment totals under the order lock. Repeated requests for the same financial/contact/consent/template snapshot return the same queue rows.

Receipts retain items, saved tax jurisdictions/components, subtotal, discount, delivery fee, tax, total, payment/reference, paid total and balance due. New tax snapshots retain currency, and later configuration changes cannot relabel their currency. Historic records without currency retain an explicit “Recorded amount” label rather than guessing their original currency. Brand templates and store sender overrides use the existing configuration inheritance model. Template placeholders are restricted; receipt totals are always appended by the server.

Dispatch rechecks current consent, notification settings and unchanged valid contact details. Missing credentials/verified senders block dispatch without making a provider request. Claiming is serialized and committed before network I/O. Provider acceptance is separate from delivery. Only definite HTTP 429 rejections retry automatically, after 60/120 seconds and at most three attempts. Ambiguous timeouts, server errors and crashed `sending` claims require provider investigation and are never automatically resent. In-flight sends cannot be recalled by a later opt-out.

Email delivery events require a recent, verified SendGrid ECDSA signature over the exact raw body. Scoped saved IDs/recipients are checked, duplicate provider events are ignored, and unsubscribe/spam reports revoke email consent. SMS delivery can be checked against the authenticated Twilio message resource from the queue. Accepted email messages are not falsely labeled delivered when signed events are unavailable.

The desktop/mobile web screens include customer consent, branded templates/senders, receipt queueing, explicit delivery confirmation/cancellation, attempt/status evidence and provider-rate review. The legacy prepared-message API remains available for historical manual drafts; it cannot bypass outbox consent or send historical text automatically.

## Location taxes and provider limitation

New taxable orders/estimates now fail closed when matching effective location rules are absent. Per-service legacy rates cannot establish the store jurisdiction. Existing recorded and frozen legacy invoices keep their prior tax behavior; exempt services can still be priced without taxable rules. Imported rules retain provenance in immutable order tax snapshots.

An optional ZipTax-compatible v20 adapter previews a US postal/city rate from the saved store location. It requires one exact matching city/state/postal result, finite valid rates, a 24-hour preview cache, and explicit jurisdiction/service-taxability confirmations before import. Store changes and expired/foreign quotes are rejected. An existing effective component must first be ended/voided to prevent adding a combined rate twice. The provider does not decide laundry-service tax treatment. Quotes and rules have forced RLS and repeatable migrations.

**The user's free-provider requirement remains unresolved.** Official provider/pricing sites are blocked by the current cloud policy, no tax-provider credential is configured, and a current free allowance/API contract has not been verified. The adapter is exercised with controlled protocol responses, not a live account. Do not describe it as a confirmed free production integration or register a paid account. Review/save the candidate domain additions in environment settings to allow research. Verify a genuinely free plan, quota and supported API contract before choosing/activating this adapter; use another free provider if necessary. This is an acceptance blocker for the provider portion of PR #11.

Actual CleanandDry store tax configuration remains unverified: an application admin session, actual jurisdiction/address and applicable service treatment/rates are needed. Development fixtures are synthetic and do not establish production tax correctness. No production writes, rates, emails or SMS were performed.

## Runtime configuration

- Install `backend/requirements.txt`; the signed-event verifier explicitly requires `cryptography>=42,<51`.
- Email: `SENDGRID_API_KEY`, verified `SENDGRID_FROM_EMAIL` (or scoped sender override), and `FABCLEAN_SENDGRID_WEBHOOK_PUBLIC_KEY` for signed delivery events. Configure the provider's signed event webhook at `/api/notifications/webhooks/sendgrid`. The verification key is public; API keys remain secret.
- SMS: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, and verified `TWILIO_FROM_NUMBER` (or scoped sender override). Use only provider-authorized senders.
- Optional candidate tax adapter: `FABCLEAN_TAX_PROVIDER_KEY`, sent only to `https://api.zip-tax.com/request/v20`; do not activate until the free allowance and contract are verified.
- Notification worker: run `python tools/notification_worker.py` from `backend`, with securely supplied `FABCLEAN_NOTIFICATION_SESSION`, explicit `FABCLEAN_NOTIFICATION_BRAND` and `FABCLEAN_NOTIFICATION_STORE`, plus optional `FABCLEAN_NOTIFICATION_API` (HTTPS, or loopback for local development). Use a dedicated, revocable staff session per store. The worker uses normal permissions and active-store headers; it cannot scan other stores. `--once` processes one due batch. Due queues are ordered oldest-first so newer terminal history cannot starve pending messages. Supervise the process and renew sessions when needed.
- Enable notifications in Brand Defaults & Overrides only after senders/worker/consent are configured. Saving configuration does not launch workers or send messages.

Required external destinations are `api.sendgrid.com`, `api.twilio.com`, and the chosen verified tax provider. Enter credentials only through secure environment/server settings. Browser bundles and repository files contain no credential values.

## Validation

Run `scripts/validate.sh` from the repository with a disposable local `FABCLEAN_TEST_DATABASE_URL`, `PYTHON_BIN=/workspace/.fabclean-venv/bin/python`, Expo cache overrides from AGENTS.md and `CHROMIUM_EXECUTABLE=/workspace/.fabclean-tools/pg/usr/lib/chromium/chromium`.

The gate includes real PostgreSQL migration/isolation/receipt/consent/concurrency tests, controlled provider requests and signed webhook tests, the load gate, frontend unit tests, TypeScript, Expo web export and eight desktop/mobile browser suites. Notification browser flows use real local API calls for consent, financial receipt totals, cancellation/opt-out and settings; only external provider preview/import UI responses are controlled. Native devices, actual free-provider lookup, authenticated target-store tax execution and real message delivery remain unrun. See the tracker for the final run results.
