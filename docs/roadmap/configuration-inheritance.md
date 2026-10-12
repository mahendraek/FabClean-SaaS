# Brand-to-store configuration inheritance

Status: VALIDATED — awaiting review; not merged or deployed.
Priority: P2 — current sequential roadmap item.
PR: https://github.com/mahendraek/FabClean-SaaS/pull/8
Implementation branch: `codex/pr-8-configuration-inheritance`, based on accepted main `be72979`.
Implemented: 12 October 2026.

## Delivered scope

Brand defaults and optional selected-store overrides for settings, service definitions and prices, offer templates, fulfillment rules and capabilities. Effective values/sources are deterministic; resets and removals require confirmation in the responsive web/mobile editor. Existing local values are preserved as explicit overrides; cross-brand inheritance and plan bypasses are denied. Store-specific promotion usage survives reset. Existing operational editors consume the same effective configuration.

See [design, migration, APIs and validation](../PR8_IMPLEMENTATION.md).

## Validation and boundaries

100 backend tests without skips, 26 frontend tests, clean TypeScript, 29-route web export, four desktop/mobile-web browser suites and local load gate pass. The three new tables use forced RLS; legacy operational/custody policies remain intact. Native-device and authenticated production acceptance remain unperformed; hosted GitHub CI/review flags cannot be verified because API access is Forbidden.

Only mahendraek/FabClean-SaaS changes. Production remains on PR #7. PR #9–#12 remain planned. This development authorization does not authorize merge/deployment of PR #8; explicit approval is required.
