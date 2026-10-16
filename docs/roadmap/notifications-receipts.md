# Manual WhatsApp receipts and communication preferences

Status: MERGED with explicit user approval at `d36b6d6` on 15 October 2026. Receipt workflows retained; active tax implementation removed. Both SaaS Render services are verified live on that merge, and all 11 read-only public smoke checks pass.
Priority: P2 — current PR #11.
Implementation branch: `codex/pr-11-receipts-location-taxes` (existing branch name retained).

## Current scope

Manual WhatsApp receipts with brand templates, explicit consent and preparation audit. Optional email/SMS order/payment receipts and status notifications retain per-store sender settings, preferences and safe retry/delivery audit.

- Record separate WhatsApp consent and receipt preferences in Customer Profile.
- Preview the branded receipt and international recipient number from Order Details, including subtotal, discount, delivery fee, total and payment/balance figures.
- Recheck consent, phone and financial contents before opening WhatsApp. Reject stale previews, foreign-store orders and invalid phone numbers; allow cancellation before opening.
- Staff must tap Send in their own WhatsApp app/Web account. Record share preparation and the receipt snapshot, never an automatic send/delivery claim.
- WhatsApp requires no messaging API credentials, rental number or notification worker. Optional email/SMS providers remain separately configured and disabled by default.

## Tax removal

The user withdrew the location-tax implementation on 15 October 2026. Tax engines, provider lookup/import, tax-rule administration, estimates, reporting, taxable-service controls and their dedicated screens/routes/tests are removed. A free tax-provider account or credential is no longer a PR #11 prerequisite.

New orders use plain server-validated pricing and no tax charge. Client-supplied tax values cannot add a charge. Existing invoice tax/snapshots and previously stored refund metadata are retained only for historical compatibility; no production data or existing tax tables are deleted. Financial repricing of archived tax invoices is blocked to preserve their recorded amounts. Notes/status updates and gross payment/refund controls remain available.

See [current implementation and validation](../PR11_IMPLEMENTATION.md).

## Acceptance and boundaries

Consent/opt-outs are enforced; receipts reconcile with server totals; messages use the selected store's branding; queue claims/retries remain safe; foreign-store access is denied. Tests must verify removed tax APIs stay unavailable, tax-free new orders reconcile, historical invoices remain intact and gross refund caps remain enforced.

Work only in mahendraek/FabClean-SaaS. Maintain web/mobile support. Do not merge or deploy without explicit approval. Actual external message delivery and physical-device WhatsApp handoff remain outside the local automated checks.
