# Brand/Store switcher and active context

Status: PLANNING ONLY — not implemented.
Priority: P0 (proposed; pending user prioritization)

## Scope
Show active brand/store in a shared web/mobile header. Switch with a simple selector, not via administration. Refresh all relevant screens and retain selection across refresh/relogin.

## Acceptance criteria
Selected brand/store visible everywhere; switching is explicit and confirmed; no stale screens; switching works on web and mobile; unauthorized stores cannot be selected.

## Boundaries
- Target only mahendraek/FabClean-SaaS; never modify original FabClean.
- Maintain web and mobile support.
- Implement through a later reviewed code change; do not treat this planning PR as delivery.
- Do not merge until implementation and explicit approval.
