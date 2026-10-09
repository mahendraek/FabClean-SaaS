# Pre-PR #6 audit and fixes

9 October 2026. Branch: `codex/pre-pr6-fixes`, based on main `8e783a7`. This is a focused maintenance review after PR #5, before developing PR #6. Awaiting review; not merged or deployed.

## Confirmed issues fixed

- The homepage sign-out previously only removed local credentials, leaving the server token usable. It now revokes the server session before clearing credentials. A failed revocation shows an error and preserves the session for retry.
- Changing a session's active store in another tab could redirect a stale form's write to that store. Requests now include the displayed brand/store; the API rejects a mismatch with HTTP 409 before running the handler. Clients without these headers retain compatibility. Operational requests also use one authenticated staff snapshot, keeping handler authorization aligned with the PostgreSQL RLS scope even if the session changes during the request. Context/authentication routes continue reading the current session.
- The dedicated order-status endpoint bypassed the garment assembly check enforced by the general update endpoint. Both now share that check, rejecting ready/collected/completed transitions while existing garment tags remain unassembled. Existing custody guards remain intact.
- All 34 frontend TypeScript diagnostics were resolved: typed navigation parameters, duplicate style keys (keeping the previous last-value behavior), removed React Native absolute-fill API use, and a missing payment amount style. No compiler checks were suppressed.

## Validation

- 42 backend tests pass without skips on a disposable PostgreSQL database using a NOSUPERUSER/NOBYPASSRLS owner. New regressions cover stale/partial context headers, a session switch between middleware and handler authorization, server token revocation and assembly checks on both update endpoints. Existing negative authorization, forced RLS and custody concurrency checks pass.
- 15 frontend unit tests pass, including server revocation, retry on failure and context header/session reset behavior.
- `tsc --noEmit` passes with zero diagnostics; Expo web export passes all 27 routes.
- Desktop and mobile-web Chromium context checks pass, including assertions for scoped requests and the sign-out API call. Real local PostgreSQL-backed browser custody flows pass dispatch, receipt, return, completion and refresh.
- No production fixtures, merge or deployment were performed. Native iOS/Android devices were not exercised. This focused audit does not replace the broader security/load/performance work planned for PR #6.

## Review

Compare: https://github.com/mahendraek/FabClean-SaaS/compare/main...codex/pre-pr6-fixes

PR #6 remains paused until these maintenance fixes are reviewed and accepted. Future roadmap scopes and sequencing remain in [the tracker](DEVELOPMENT_TRACKER.md).
