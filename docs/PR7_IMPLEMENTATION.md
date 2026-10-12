# PR #7 — Platform administration and tenant onboarding

Prepared/implemented: 12 October 2026. Branch: `codex/pr-7-platform-onboarding`, based on accepted main `76b1bea` (live application `dd031a7`). Status: validated, awaiting review. No merge, deployment, production configuration changes or real invitation delivery were performed.

## Delivered flows

SuperAdmin can onboard a brand with an initial active root store, a platform plan and an owner invitation in one transaction. Invalid input or invitation failure rolls back the brand/store/invitation together. Existing API callers can still create brand metadata separately, then create a store and issue an invitation. The platform page supports this recovery path and reactivating a missing/inactive initial store without switching the administrator's operational context.

The administration page shows platform/database readiness and aggregate brand/store/invitation counts, brand onboarding readiness, plan assignment, per-brand feature and resource-limit overrides, owner invitation status, suspension/reactivation and brand audit history. Platform controls remain SuperAdmin-only; brand owners retain existing brand/store administration permissions. No global customer, order or financial records are added to platform health.

SaaS plans are separate from customer laundry subscriptions. The initial editable catalogue has Starter, Growth and Enterprise; it sets no prices and performs no payment or billing operations. SuperAdmin can add/edit/archive catalogue plans. Archived plans remain effective for existing bindings but cannot be newly assigned. Plan codes are immutable. Shared plan changes affect every assigned brand and validate all affected brand usage before commit.

| Initial plan | Features | Active-store limit | Active-staff limit |
| --- | --- | --- | --- |
| Existing brands (`legacy`) | All current optional features | Unlimited | Unlimited |
| Starter | Core orders/customers plus financial reports | 1 | 5 |
| Growth | Optional features below, except AI | 10 | 100 |
| Enterprise | All optional features | Unlimited | Unlimited |

These are configurable implementation defaults for review, not commercial pricing commitments. The compatibility catalogue entry is read-only; existing brands can receive explicit overrides or move to an editable plan.

Optional feature keys: offers, rewards, referrals, recurring subscriptions, pickup, delivery, store handoffs, AI and financial reports. Core orders/customer workflows remain available. Effective access combines the plan and brand overrides with existing store configuration; setting a store preference cannot enable an unentitled feature. Feature endpoints enforce the platform policy server-side, including direct API requests. Pickup/delivery entitlement checks also apply to order booking. The active brand's effective plan metadata is returned in context discovery.

Store/staff creation, store reactivation, staff activation and active role assignment check quotas under ordered brand locks. Staff seats count active accounts with a home brand or active role assignment in that brand; distinct live owner invitations reserve seats for identities not already counted. Expired/revoked invites release reservations, and replacing an invite does not consume another seat. Downgrades below usage/reservations return conflict. Handoffs cannot be disabled while open custody exists; dispatch/action rechecks lifecycle/licence state under the custody lock to prevent a waiting request bypassing a downgrade.

## Owner invitation security

- Invitations are fixed to one email, brand and initial store. Tokens have 256-bit randomness, are stored only as SHA-256 digests, expire after 48 hours and can be accepted once. Creation returns the sharing link once; listing, audit and health never return token/digest values.
- Reissuing a pending invitation revokes the prior token; SuperAdmin can revoke it explicitly. Expired/revoked/accepted tokens fail preview/acceptance. Suspended brands and inactive stores/accounts cannot accept invitations.
- The new account owner chooses their own password. Acceptance grants only BrandAdmin for the invited brand, never platform administration. An existing account must prove its identity using its current password or a still-valid matching session; its password/profile is never reset by invitation acceptance.
- Reservations, owner creation/role grant, token consumption and audit append commit together. Brand/email locks serialize simultaneous acceptance and quota changes. Invitation endpoints use the existing bounded shared authentication budget.
- Share links carry the token in a URL fragment, so it is not sent in the initial HTTP request. The acceptance screen captures it in memory, cleans navigation/history parameters and clears the buffer after acceptance or leaving the screen. Tokens/passwords are never written to preference storage. Native users can open an app route or paste the invitation code; native universal-link association is not claimed.
- Optional `PUBLIC_WEB_URL` chooses an explicit web origin; its default is the existing FabClean Render web URL. Production requires HTTPS and rejects credentials, paths, queries or fragments in that configured origin. Generated links are shared through the administrator's explicit Share action; automatic email/SMS delivery is outside this implementation. No real messages were sent during development.
- Failed invitation/password proof does not clear a different valid browser session; expired operational sessions still clear credentials normally.

## Lifecycle and audit

Suspension retains all tenant data and pending work, blocks new operational/store-admin access, and revokes non-platform sessions currently scoped to that brand. Platform administrators retain recovery access. Other brands' selected sessions are unaffected. Reactivation requires a reason and does not restore revoked tokens; staff sign in again. Sign-in and lifecycle changes share ordered locks so an overlapping login cannot resurrect a revoked brand session. A multi-brand account can sign in to an accessible active brand when its home brand is suspended; current session scope and the displayed header match the chosen active brand.

Lifecycle, plan assignment/overrides, catalogue edits and invitation creation/revocation/acceptance append authenticated audit events in the same transaction as their mutation. The existing platform audit table is now append-only through a database trigger. Invitation tokens/passwords are excluded from audit metadata and structured request logs.

## Migration and isolation

Additive migration `platform-onboarding-v1` runs inside the existing initialization transaction/advisory lock after tenant/store migrations. It creates global control/authentication tables `platform_plans` and `owner_invitations`, adds a plan binding/overrides to brands and seeds the compatibility catalogue. All existing brands bind to `legacy`, preserving current features and unlimited resources. It adds NOT VALID plan/status constraints to preserve unknown historical rows, rather than deleting/reclassifying data. A composite invitation store/brand FK prevents foreign-store binding. Repeated startup preserves existing catalogue edits and bindings.

These tables are deliberate global platform/authentication control state, alongside brands/staff/roles. They expose no operational customer data and have no tenant-operational API. Access is SuperAdmin-gated or restricted to one cryptographically proven invitation. Existing 21 operational-table forced RLS policies and participant-scoped custody RLS remain unchanged; operational requests keep one selected brand/store and one request-local entitlement snapshot.

## Validation

- 80 backend tests pass without skips on disposable PostgreSQL 16 with a NOSUPERUSER/NOBYPASSRLS owner. Includes the 61-test PR #6 baseline, repeatable migration, legacy compatibility, platform permission denial, atomic onboarding, token redaction/digests/replacement/expiry/replay, identity proof, suspension/revocation/reactivation, concurrent sign-in, quota races/reservations, role/activation bypass protection, shared plan updates, custody downgrade protection, onboarding readiness and immutable audit.
- 23 frontend unit tests pass, including limit parsing, override resolution, nested navigation token cleanup and preserving an unrelated valid session after failed invitation proof. TypeScript has zero diagnostics.
- Expo exports 28 routes, including `/accept-invite`. Existing context and real-API handoff desktop/mobile browser suites pass. Real-local-API platform browser checks pass onboarding, fragment cleanup, owner acceptance/sign-in, entitlement override, lifecycle cancellation/suspension/reactivation, fresh login, custom plan creation/assignment, store recovery and denial of platform access to a brand owner.
- The complete common gate is `scripts/validate.sh` (the older PR #6 entry point remains compatible). CI now runs it and includes private platform browser fixtures. The existing local load gate passes with zero errors; see [retained results](performance/pr7-load.json). This is in-process local measurement, not production performance.
- Native iOS/Android execution, real sharing/email delivery, public-domain deep links and production onboarding have not been exercised. GitHub API remains Forbidden, so hosted CI/review/branch-protection flags are unverified. Render automatic deployment remains off as recorded for PR #6; this branch has not changed services.

## API additions

- Platform plans: GET/POST `/api/platform/plans`, PUT `/api/platform/plans/{code}`.
- Brand detail: GET `/api/platform/brands/{brand_id}`; existing brand POST/PUT now handle atomic initial onboarding, plan/overrides and lifecycle reasons.
- Invitations: POST `/api/platform/brands/{brand_id}/owner-invitations`, POST `/api/platform/owner-invitations/{id}/revoke`.
- Invitation holder: POST `/api/auth/owner-invitations/preview` and `/accept`, with token in the JSON body.
- Health/audit: GET `/api/platform/health`, GET `/api/platform/audit` with optional brand filter and capped limit.

Before deployment, review plan defaults, run the common validation gate, verify PUBLIC_WEB_URL for any custom domain, retain non-bypass database ownership, and use the existing explicitly approved manual release procedure. Native staging acceptance should cover secure-session restart, invitation code entry/link cleanup, existing-account proof, OS sharing/cancel and lifecycle recovery. PR #8–#12 remain queued; settings inheritance, taxes, maps, receipts and consolidated reporting are outside this PR.
