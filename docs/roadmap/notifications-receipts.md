# Location-based tax completion, manual WhatsApp receipts and preferences

Status: CORE IMPLEMENTATION LOCALLY VALIDATED — free-provider acceptance remains blocked; not merged or deployed.
Priority: P2 — development authorized by the user on 14 October 2026.
Implementation branch: `codex/pr-11-receipts-location-taxes`.

See [implementation, runtime configuration and remaining blockers](../PR11_IMPLEMENTATION.md). The final local gate including manual WhatsApp passed 166 backend tests without skips, 36 frontend tests, TypeScript, 32-route web export, eight desktop/mobile browser suites and zero-error load validation. Provider lookup/send responses and WhatsApp navigation are controlled in tests; actual free-provider eligibility/contract, live lookup, real message delivery and target-store production tax execution are not verified.

## Scope
Manual WhatsApp receipts with brand templates, explicit consent and preparation audit. Optional email/SMS order/payment receipts and status notifications retain per-store sender settings, preferences and safe retry/delivery audit.

The user selected manual WhatsApp receipt sharing on 14 October 2026 to avoid paid messaging-provider accounts. This is the default receipt-sharing workflow; existing email/SMS delivery remains optional. No SendGrid/Twilio account, API key, phone-number rental or notification worker is needed for WhatsApp sharing.

- Record separate WhatsApp consent and enable receipts in Customer Profile.
- Preview the current branded receipt and international recipient number from Order Details. Include saved jurisdiction/rate/tax evidence and current payment/balance totals.
- Recheck consent, phone and receipt contents before opening WhatsApp. Reject a stale preview, foreign-store order or invalid/ambiguous phone number. Allow staff to cancel before opening.
- Open a prefilled WhatsApp app/Web message; staff must tap Send there. Log only share preparation and the receipt snapshot, never claim automatic sending or delivery.
- Actual WhatsApp transport/account access is outside the server. Browser tests intercept WhatsApp navigation so no real messages are sent.

User-requested addition: complete location-specific tax behavior before considering the receipt workflow complete. Existing PR #9 code and synthetic test rates do not establish that actual store taxes are configured or working. Audit the existing implementation and reuse it where correct; identify and implement the remaining gaps.

- Resolve applicable tax jurisdictions from the saved store location (country, state/region, city and postal/address information as required). Postal lookup alone does not establish a tax rate or jurisdiction.
- Apply verified, effective-dated rates and service-specific taxability/exemptions to server-calculated estimates, orders and payments. Determine any required rate-source integration during the implementation audit; do not invent rates.
- Show the applicable jurisdiction, rate components, taxable amounts and totals consistently in the counter flow, order details and email/SMS receipts.
- Explain missing or incomplete location/rate configuration and prevent misleading tax results. Preserve historical order tax snapshots and tenant/store isolation.
- Verify the actual target store's location, applicable rules and complete order/payment/receipt behavior. Record production configuration and acceptance separately from code implementation; live writes require authorization and application access.

## Acceptance criteria
Delivery receipts/events logged; opt-outs respected; correct tenant branding; failed deliveries retry safely; no cross-tenant messages.

Location-based tax acceptance: representative stores in different jurisdictions select the correct rules; applicable taxable/exempt services, effective dates and rounding produce verified totals; receipts reconcile with saved order/payment amounts. Include missing-location/rate cases and negative cross-store/tenant tests. Synthetic fixture success must not be reported as verification of actual store tax configuration.

## Boundaries
- Target only mahendraek/FabClean-SaaS; never modify original FabClean.
- Maintain web and mobile support.
- Review the implementation and resolve the free-provider acceptance blocker before treating PR #11 as complete.
- Do not merge until implementation and explicit approval.
