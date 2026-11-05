# Tenant management audit

Date: 5 November 2026. Scope: read-only source review of FabClean-SaaS checkout `42d397f32052d7ff6f668fee6cd97ec3eb613f6b`, plus the existing decision-log working file. This is a documentation-only assessment, not a production security certification. No live database, permissions, subscriptions, branding, environment settings, or application code were changed. Tests were inspected, not executed or newly claimed as passing.

Documentation review: [PR #16](https://github.com/mahendraek/FabClean-SaaS/pull/16) · Future feature tracking: [issue #17](https://github.com/mahendraek/FabClean-SaaS/issues/17). Status: published for review, not merged; implementation remains unstarted.

The requested scenario and proposed implementation requirements are in [Tenant management requirements](TENANT_MANAGEMENT_REQUIREMENTS.md). Decision reasoning is recorded as DD-002 in [Design decisions](DESIGN_DECISIONS.md).

## Findings and existing evidence

| Area | Observed implementation | Gap or follow-up |
| --- | --- | --- |
| Tenant identity | `brands` is the business boundary; `stores.brand_id` groups stores. Operational ownership uses `business_id` and `location_id`. | Make Tenant = Brand explicit in terminology and UI; avoid a disruptive column rename merely for consistency. |
| Platform onboarding | `server.py` creates a brand, optional initial store and owner invitation transactionally; platform routes require SuperAdmin. | Present an understandable customer/brand onboarding wizard and three-store package, rather than exposing plan codes and override mechanics as the main workflow. |
| Licensed store count | `platform_management.py` supports plan limits and per-brand overrides. `usage()` counts active stores; `require_capacity()` rejects excess usage. Store creation/reactivation calls it while holding the brand lock. | The three-store limit is already representable. Add clearer allocation/usage UI and explicit concurrent 3rd/4th-store acceptance cases; do not rebuild this enforcement. |
| Lifecycle | Active/suspended brand state, invitation revocation and session restrictions exist. Downgrades below existing usage are rejected. | There is no explicit SaaS billing-period/renewal model in the reviewed platform plan schema. Document separately from feature access and laundry-customer subscriptions. |
| Memberships | `user_role_assignments` supports platform, brand and store scope. Owner invitation acceptance creates a brand-admin assignment. | Replace ambiguous owner/manager labels in administration with scope-aware labels and membership previews. Retain compatibility mapping during migration. |
| Store administration | `require_brand_admin_for()` gates store management. Creation/reactivation checks capacity; stores cannot be moved to another brand through update. | Make store setup accessible from the tenant overview. Current platform detail primarily shows stores, reactivation and initial-store recovery; it is not a complete store-management workspace. |
| Configuration | `configuration.py` has forced-RLS brand/store configuration, revision checks, defaults and explicit overrides. Licensed features constrain effective capabilities. | Add a clear Brand defaults / Store overrides interface, policy for which fields can be overridden, and previews before changes affect multiple stores. |
| Theme | `theme.ts` defines five presets; effective store settings drive the current UI theme. Brand/store configuration can set `brand_theme`. | A dedicated platform branding workflow, custom validated colors, branding locks/delegation and comprehensive surface coverage are not established by this review. |
| Brand name/logo | `brands.name`, `slug`, `legal_name` and `logo_url` exist. SuperAdmin profile APIs accept a logo URL. The inspected platform form does not expose logo/theme controls. | A logo field does not prove a secure upload, asset lifecycle, Brand Admin editor or consistent logo rendering. Define these as feature requirements. |
| Operational isolation | `tenant_scope.py` applies forced RLS to the original 21-table operational registry, configures scope per connection and rejects superuser/BYPASSRLS runtime roles. Related IDs have scoped foreign keys and legacy quarantine rules. | Inventory every later table too. Preserve existing protections; audit table-by-table scope coverage, connection reuse and all non-SQL data paths. Do not assume this registry is the entire schema. |
| Additional scoped data | Configuration, handoffs, notification and tax modules install additional scoped tables/policies. Handoffs deliberately grant participant-store visibility. | Document each exception explicitly. Keep cross-brand handoffs prohibited and do not replace participant rules with unrestricted brand-wide access. |
| Global control data | Identity, membership, brands/stores and platform control data are intentionally outside operational RLS; handlers perform authorization. | Review all global-table reads/writes independently. Operational RLS alone does not establish their isolation. |
| Reports | `reporting.py` allows authorized brand aggregation and restricts store users; explicit store selection is validated. | Keep brand-wide reporting explicit in the UI. A brand admin role must not silently broaden ordinary operational store queries. |
| Photos/assets | Order-photo metadata and bytes are persisted and fetched through order-scoped routes. | This is not a reusable brand-logo upload system. Review validation and ownership independently for private photos and deliberately public branding assets. |
| Context/UI | `ActiveContext.tsx` shows active brand/store, confirms switching and closes the previous screen; request generation guards invalidate stale work. | Separate platform management from tenant operations. Searchable pickers, capacity indicators and accessible context labels are needed as the customer count grows. |

These findings distinguish observed functionality from missing end-to-end product workflows. They do not establish an exploitable isolation flaw, prove that all routes are safe, or assert that previously released features are absent.

## Reviewed source references

- [Tenant scope, registry, RLS and ownership migration](../backend/tenant_scope.py).
- [Platform plans, entitlements, usage, invitation flow and audit](../backend/platform_management.py).
- [Brand/profile/store APIs, permissions, sessions, photos and runtime database handling](../backend/server.py).
- [Configuration inheritance and revisions](../backend/configuration.py).
- [Participant-scoped handoffs](../backend/store_operations.py).
- [Reporting scope](../backend/reporting.py), [notification scope](../backend/notifications.py), [tax scope](../backend/taxation.py).
- [Platform administration UI](../frontend/app/platform-admin.tsx), [store management UI](../frontend/app/brand-stores.tsx), [configuration UI](../frontend/app/configuration.tsx).
- [Active context](../frontend/src/ActiveContext.tsx), [request/session isolation](../frontend/src/api.ts), [theme handling](../frontend/src/theme.ts).

## Existing test evidence inspected

`backend/tests/test_postgres_isolation.py` covers foreign reads/mutations, scoped related IDs, missing scope, table-owner RLS, concurrent request scope and store switching. `test_platform_management.py` covers onboarding, invitation identity proof/single use, suspension, entitlement restrictions, store quota rejection, staff concurrency and plan downgrades. `test_configuration.py` covers inherited values, overrides/reset, stale revisions, foreign scope, forced RLS and new-store inheritance. Reporting, notification, store-operation and tax test modules provide additional feature-specific coverage.

These tests are useful starting points, not substitute evidence for a new multi-tenant acceptance run. In particular, the inspected quota test's concurrent operation is staff allocation; an explicit concurrent store-creation test at the three-store boundary is still required for the proposed acceptance scenario.

## Follow-up audit inventory before implementation

| Data class | Required ownership/access review |
| --- | --- |
| Platform plans and future SaaS subscription records | SuperAdmin write authority, brand-visible summary only, tenant-safe billing references and event processing. |
| Brand/store registry, identity and memberships | Global identity versus scoped memberships; no cross-brand staff/profile leakage, escalation, account reset or accidental reassignment. |
| Every operational table and new migration | Explicit owner, scoped related IDs, RLS read/write predicates, quarantine handling and appropriate unique/index scope. |
| Brand defaults, store overrides and versioned policies | Correct inheritance and permissions; immutable historical invoice/tax snapshots remain unchanged. |
| Reports, exports, search, metrics, barcodes, photos and audit feeds | Both list and object access; direct URLs/IDs, pagination, CSV, caches, error details and downloads. |
| Jobs, notifications and provider webhooks | Explicit saved scope at enqueue/execution; tenant-safe idempotency, retries, cancellation and provider account mapping. |
| Storage and caches | Separate private documents from public logos; tenant ownership on writes, deletion, cache keys and invalidation. |
| Privileged operations and recovery | Reviewed migration/maintenance credentials, connection reset, audit, scoped support, export/deletion/restore and backups. |

## Delivery boundaries

No implementation PR is assigned by this document. Proposed feature groups and acceptance criteria are in the requirements document. Detailed schema/endpoint designs and security review remain implementation prerequisites; live deployment verification and a full dynamic penetration review were outside this source audit.
