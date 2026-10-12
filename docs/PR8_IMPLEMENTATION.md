# PR #8 — Brand defaults and store overrides

Implemented: 12 October 2026. Branch: `codex/pr-8-configuration-inheritance`, based on accepted main `be72979`; current production application remains `43f3cbf`. Awaiting review, not merged or deployed.

## Delivered behavior

A selected brand has a default settings document, service catalogue (including pricing, variants, modifiers, turnaround and eligibility) and offer templates. Stores inherit defaults dynamically; no copied catalogue rows are needed when creating a new store. Store settings and catalogue overrides take precedence. Each settings value and service record shows its source in the responsive `/configuration` screen linked from Admin.

BrandAdmin for the selected brand and SuperAdmin can edit brand defaults. Store managers can inspect effective configuration and change only their selected store. Operational scope, active-store request headers, lifecycle checks and plan entitlements remain enforced. The screen supports capability toggles, business/fulfillment rules, default service/offer creation, copying the selected store's full service catalogue into defaults, pricing/offer overrides, disabling inherited records, confirmation/cancellation for removal/reset, refresh and server revision-conflict recovery.

Precedence is explicit: system settings < brand settings < persisted store settings; brand service < partial store template override < existing store-local service of the same ID. A local service shadows the default even when inactive. A price/flag edit of a matching legacy service preserves all its other local fields as explicit overrides. Reset of a matching service removes that local definition and its partial override; operational orders retain their historical snapshots. A local offer with the same code shadows a brand offer, including when inactive. Store-only offers remain in the existing offer editor; inherited offers have independent, store-specific identifiers and usage counters. Partial overrides preserve earlier overridden fields; reset removes the record override as a whole. Reset never clears promotion usage.

Existing `app_settings`, services, categories and offers are retained, including unknown historic settings. They remain explicit store configuration; there is no automatic reclassification or cross-brand copy. Settings saves persist only supplied overrides, rather than pinning every inherited value. Null removes a setting override. Existing service/offer editors can edit inherited records by creating store overrides; brand default editing uses the new screen/API. Store-only catalogue records without a brand counterpart remain editable through the existing Admin/retention flows.

Operational service lists, Admin overview, scheduling settings, offer validation and booking use the effective configuration. Template categories become available without writing local category rows; a same-name local category still controls its visibility. Brand defaults cannot bypass plan restrictions. Pricing defaults populate the existing service/pricing workflow; this PR preserves the existing manually entered order prices and immutable historical order item amounts. Scheduling areas, slots and blackouts remain store-local. Tax jurisdiction rules, map coverage logic, notification delivery and billing belong to later roadmap items.

## Persistence, validation and isolation

Additive migration `configuration-inheritance-v1` creates `brand_configuration`, `store_configuration` and `configuration_offer_usage` under the existing startup transaction/advisory lock. Every table has ENABLE/FORCE RLS with matching USING/WITH CHECK. Brand configuration is brand-scoped; store overrides and usage are brand/store-scoped with composite store/brand foreign keys. Initialization alone uses the existing maintenance path. The migration marker makes repeat startup preserve edits and legacy data.

The API derives all ownership from the authorized current scope, accepts supported fields only, validates prices/flags/fulfillment rules/offer dates and codes, and bounds catalogue/document sizes. Configuration writes use the existing ordered brand lock and commit settings, catalogue overrides, revision and audit together. Optimistic revisions reject stale configuration editors with 409. Existing settings and inherited-record editors advance the store revision. Brand changes validate effective definitions against overrides across the brand's stores through explicitly authorized, scoped RLS reads; they reject incompatible definitions rather than leaving another store with invalid effective settings. Effective offer codes must be unique. No HTTP handler requests maintenance access.

Inherited promotion usage commits with order creation in the existing store-serialized transaction. Counters remain local to a store and template, including after override/reset/removal and later restoration of that template ID. New configuration routes require Admin; BrandAdmin is additionally required for default writes. Metadata-only audit events contain actor, scope, revision and changed section names, with no operational customer records or credentials.

## API

- GET `/api/configuration`: brand/store documents and revisions, effective settings/services/offers, source metadata and brand-edit permission.
- PUT `/api/configuration/brand`: required current `revision`; supplied `settings`, `services` or `offers` sections replace those default sections. Omitted sections remain unchanged. Service and offer maps use stable template keys.
- PUT `/api/configuration/store`: required current `revision`; settings and template maps patch explicit overrides. Null resets a key/record. Templates must exist in the selected brand. Unknown ownership fields are rejected.
- Existing PUT `/api/settings` saves supplied store setting overrides (null resets) and advances revision. Existing inherited service and offer PUT routes create store overrides.

On 409, refresh configuration and reapply the intended edit. Store switching remounts the editor through the existing shared ActiveContext, preserving scope headers and discarding old-store drafts.

## Validation and release limits

100 backend tests pass without skips on disposable PostgreSQL with a NOSUPERUSER/NOBYPASSRLS owner. The 80-test accepted baseline is retained; 20 configuration tests cover defaults/legacy preservation, new-store inheritance, price/capability/offer execution, local usage, reset, inactive shadows, compatibility editors, partial updates, foreign scope, forced RLS, invalid-write rollback, concurrent/stale revisions, cross-store override conflicts and repeatable migration/audit.

26 frontend unit tests pass, TypeScript has zero diagnostics and Expo exports 29 routes. All four desktop/mobile-web browser suites pass: context, custody, platform onboarding, and real-local-API configuration creation/override/propagation/reset/cancel/disable/input/permission/isolation. Mobile layout was visually inspected. The common `scripts/validate.sh` gate includes private disposable configuration fixtures and the new browser suite; [local load evidence](performance/pr8-load.json) has zero errors. No production fixtures, authentication, messages or service changes were used.

Native iOS/Android devices, actual OS sharing and authenticated production inheritance remain unperformed. GitHub API access remains Forbidden, so hosted CI/review/open/closed metadata is unverified. Render deployment remains unchanged and automatic deployment remains off. Explicit approval is required before merging/deploying this PR. PR #9–#12 remain queued; their development has not started.
