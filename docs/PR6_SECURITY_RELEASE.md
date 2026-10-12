# PR #6 security and release review

12 October 2026. Implementation branch: `codex/pr-6-security-performance`, based on accepted main `d42f80f`. Implementation commit: `9ee0362`. Planning ancestry retained by `19c7742`; normal pushes update both the implementation branch and `roadmap/security-performance`. The PR #6 Git head was verified at `19c7742` before this publication-record follow-up. GitHub metadata editing remains Forbidden.

Awaiting review; no merge, deployment or production settings changes are authorized by this development request.

## Delivered behavior

- Sign-in consumes a shared PostgreSQL budget: 10 attempts per normalized account and 300 per network peer per five-minute window, including successful attempts. Concurrent workers use the same counters; HTTP 429 includes Retry-After. Expired entries are removed during reservations; at most 10,000 digest buckets are retained. Raw emails/IPs are not stored in the limiter. The memory demo uses a bounded, locked local limiter and is unavailable when production database configuration is missing.
- New passwords use versioned PBKDF2-SHA256 at 600,000 iterations and constant-time comparison. Existing 120,000-iteration hashes remain valid and upgrade on successful login. Failed legacy verification adds timing work to reduce account-version timing differences. Credential lengths are bounded. Password reset and staff deactivation revoke sessions; login locks the staff row so password reset cannot race a stale credential into a new session. Existing role/expiry checks are retained.
- Partial staff edits preserve omitted roles and explicit assignments. Changing to an already assigned role reuses that assignment rather than failing a unique constraint. Assembly override checks effective administrative permission instead of the legacy role string.
- Production (APP_ENV=production or Render runtime detection) requires DATABASE_URL and an explicit HTTPS origin allowlist. Wildcards, URL credentials and paths are rejected. CORS wraps authentication errors, so the browser can read 401/403/409 responses. The non-bypass database-role check still runs on every pool checkout and at startup through initialization.
- Structured access logs contain a server-generated request ID, route template, method, status, duration, authenticated operational actor and scope. They omit query strings, raw paths, headers and bodies. Raw Uvicorn access logging is disabled. Responses expose the request ID and use no-store. Login geolocation is disabled unless explicitly enabled; the application uses the server-provided peer address rather than parsing arbitrary forwarded headers.
- Each process has a bounded pool (default eight connections, maximum 32, bounded waiting). Tenant and maintenance settings reset before return to idle and are configured/validated on checkout. Operational requests reuse their validated staff/store snapshot, reducing repeated database work without caching permissions across requests. Exhausted capacity returns a controlled 503 with Retry-After.
- Order fields, status, payment recording, garment scanning and assembly changes share a scoped row lock and transaction, including nested database writes and event records. Invalid/non-finite payments return 400. New orders atomically allocate a store-local number and create customer/order/garment records. Overlapping recurring generation returns 409; order creation, recurring-run recording and next-date advancement commit together. Failed creation leaves no orphan customer.
- Order detail/barcode lookup returns one matching scoped payload from SQL instead of loading every order into Python. It retains RLS and explicit payload ownership checks.
- Frontend error handling preserves HTTP status for HTML gateway/unauthorized responses and exposes retry guidance. Permission removal during saved-store restoration clears the stale preference; restoration failures still notify the session provider. Desktop/mobile regression flows include rate-limit recovery.

The global `auth_rate_limits` table is authentication control state, deliberately shared across workers/accounts. It has no tenant/customer payload and is not exposed by any API. Its additive CREATE IF NOT EXISTS migration runs inside the existing initialization lock/transaction, including upgrades where the tenant migration already exists. Existing 21 operational-table isolation policies and participant-scoped handoff RLS are preserved.

## Permission matrix audited

| Role | Operational permissions | Administration boundary |
| --- | --- | --- |
| SuperAdmin | Admin, customers, orders, processing, delivery | Platform management; operational data still requires one selected store |
| BrandAdmin | Admin, customers, orders, processing, delivery | Assigned brand hierarchy and staff; no platform or foreign-brand grants |
| Store manager | Admin, customers, orders, processing, delivery | Assigned store; no brand hierarchy or staff-role escalation |
| Counter | Customers and orders | No administrative configuration or assembly override |
| Processing | Orders and processing | No customer-profile/admin permission or assembly override |
| Driver | Orders and delivery | No customer-profile/admin permission or assembly override |

Legacy owner/manager labels are compatibility metadata; loaded assignments decide database-mode permissions. Existing order permissions include order/payment endpoints; this PR preserves that product policy. Existing tests cover foreign detail/mutations, files/photos, financial/customer/AI aggregates, platform/brand administration and table-owner RLS. New tests cover revocation, role removal, CORS error responses and permission-based assembly override.

## Validation and performance

Run `scripts/validate_pr6.sh` with PYTHON_BIN, FABCLEAN_TEST_DATABASE_URL and optionally CHROMIUM_EXECUTABLE. It refuses non-local/non-test database URLs before any fixtures or migrations; then runs backend/PostgreSQL tests, a local load gate, frontend unit tests, Expo export, regenerated route types, TypeScript and desktop/mobile browser checks. It owns and cleans up its local API process and private fixture file. `npm ci` has been exercised from the committed lockfile.

Load artifacts and measured results are in [the performance report](performance/PR6_BASELINE.md). The local validation gate requires zero errors, at least 10 requests/second and p95 at most 1,000 ms per measured endpoint for the specified dataset/workload. This is a regression budget, not a production latency commitment.

Native-device execution remains outstanding. Browser mobile emulation does not establish native acceptance. On staging, test iOS and Android sign-in/restart persistence, expiry and sign-out, store switching/cancel/relogin, background resume, camera permission deny/retry for garment scanning/photos, and handoff confirmation/return after a network failure. Use staging fixtures and check that no secrets appear in logs.

## Before merge/deployment

1. Review this implementation and passing validation. The GitHub API is Forbidden in this environment; Git refs alone do not establish review decisions or hosted CI results.
2. Confirm GitHub Actions runs `PR validation / validation`; configure it as a required main-branch check through repository settings when permitted. The workflow uses PostgreSQL 16 and explicitly creates a NOSUPERUSER/NOBYPASSRLS database-owner role. Hosted execution and branch-protection enforcement have not been verified here.
3. Apply/verify the existing Render API service settings: APP_ENV=production, CORS_ALLOWED_ORIGINS=https://fabclean-saas-web.onrender.com (append approved custom origins as needed), existing secret DATABASE_URL with a non-bypass role, DB_POOL_MAX_SIZE=8, and Uvicorn with --no-access-log. Keep aggregate worker-count × pool-size within the database connection budget. Do not put secrets in render.yaml.
4. Render blueprint configuration now uses autoDeployTrigger=checksPass for both services. A read-only Render API check on 12 October verified that both existing services track main with autoDeploy=yes and autoDeployTrigger=commit. Change/verify them to checksPass before merging; editing a blueprint file does not update an unmanaged service. No settings were changed by this PR development task. Web build uses npm ci with Node 24 and the actual deployed API URL. If remote gates cannot be verified, turn off automatic deployment and deploy only a reviewed commit after the complete local validation script passes and explicit user approval is obtained.
5. After approval and merge, deploy both services and verify exact live application commit, health, authentication/CORS and the published bundle. Keep production operational data untouched during smoke checks. Native and notification-provider staging acceptance remain separate.

No native devices, production load tests, production database inspection or automatic remote guard enforcement is claimed. Scheduling availability remains the existing informational workflow; this PR adds no capacity-reservation policy. No scopes from PR #7–#12 are implemented.
