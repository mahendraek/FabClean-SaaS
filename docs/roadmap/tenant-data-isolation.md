# Tenant and store data isolation

Status: PLANNING ONLY — not implemented.
Priority: P0 (proposed; pending user prioritization)

## Scope
Scope orders, customers, garments, barcodes, payments, services, search, exports and related API reads/writes by authorized active brand/store; fail closed; audit shared/legacy identifiers.

## Acceptance criteria
Cross-tenant access denied for list/detail/search/update endpoints; store-level roles see authorized stores only; admin aggregation explicit; isolation integration tests pass.

## Boundaries
- Target only mahendraek/FabClean-SaaS; never modify original FabClean.
- Maintain web and mobile support.
- Implement through a later reviewed code change; do not treat this planning PR as delivery.
- Do not merge until implementation and explicit approval.
