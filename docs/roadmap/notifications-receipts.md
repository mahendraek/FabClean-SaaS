# Email and SMS receipts and preferences

Status: PLANNING ONLY — not implemented.
Priority: P2 (proposed; pending user prioritization)

## Scope
Order and payment receipts and status notifications via email/SMS with brand templates, per-store sender options where supported, opt-in/preferences and retry/audit.

## Acceptance criteria
Delivery receipts/events logged; opt-outs respected; correct tenant branding; failed deliveries retry safely; no cross-tenant messages.

## Boundaries
- Target only mahendraek/FabClean-SaaS; never modify original FabClean.
- Maintain web and mobile support.
- Implement through a later reviewed code change; do not treat this planning PR as delivery.
- Do not merge until implementation and explicit approval.
