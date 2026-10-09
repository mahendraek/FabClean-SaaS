# Brand/Store switcher and active context

Status: IMPLEMENTED — validated locally; awaiting review and explicit merge approval.
Priority: P0 — selected after PR #4 by the user.

## Scope
Show active brand/store in a shared web/mobile header. Switch with a simple selector, not via administration. Refresh all relevant screens and retain selection across refresh/relogin.

## Acceptance criteria
Selected brand/store visible everywhere; switching is explicit and confirmed; no stale screens; switching works on web and mobile; unauthorized stores cannot be selected.

## Boundaries
- Target only mahendraek/FabClean-SaaS; never modify original FabClean.
- Maintain web and mobile support.
- Implement through a later reviewed code change; do not treat this planning PR as delivery.
- Do not merge until implementation and explicit approval.

## Implementation

Implementation commit: `ae6d1bb`, developed on `codex/pr-3-brand-store-switcher` from merged main `a800a73`. The original planning branch is retained in ancestry for a normal PR #3 head update.

- A shared header shows the active brand/store across signed-in screens, with an accessible modal listing only server-authorized brands and stores.
- Switching requires selecting a store and confirming the warning that unsaved changes will be discarded. Cancel makes no API change. Empty brands cannot be confirmed.
- The server validates and persists selection. Switching returns to the dashboard and remounts operational screens; prior-context responses are rejected. The old global dashboard cache and administration-only switch button are removed.
- Web sessions use local storage; native sessions use Expo SecureStore. Per-user preferred context is revalidated against the new session's permitted stores before relogin restoration. Revoked and malformed preferences cannot select unauthorized stores.
- Session changes and app resume/browser focus revalidate context. The selector shares the existing PostgreSQL isolation API; no RLS policies were weakened.

## Validation

- 27 backend tests passed, including disposable PostgreSQL and historical migration tests, without skips. The new context test checks authorized store lists, persisted selection through a fresh client, cross-store detail rejection and invalid brand/store combinations.
- 9 frontend session/selection tests passed: web/iOS/Android storage adapters, sign-out, late-response rejection, stale 401 protection, and authorized/revoked/corrupt preferences.
- Desktop and mobile-web Chromium checks passed with mocked local API responses: empty brand, cancellation, confirmation from an operational screen, navigation reset, refresh and relogin. No browser page errors were observed.
- Expo web export passed all 26 routes.
- TypeScript reports 34 errors on both the unchanged `a800a73` baseline and this implementation, with matching files/error codes. The tracker previously recorded 19; this current count includes typed-route errors. No new diagnostics were introduced and the typecheck is not reported as passing.

Run frontend unit tests with `npm run test:context`. After web export, run `npm run test:context:browser`; install Playwright Chromium first (`npx playwright install chromium`) or set `CHROMIUM_EXECUTABLE` to an existing Chromium binary. The browser suite serves local exported files and intercepts API traffic; it does not test production.

Native device/emulator and production authenticated smoke tests remain unperformed. Relogin preference is device-local; an already-active session uses its server-persisted context. Merge and deployment require explicit user approval.
