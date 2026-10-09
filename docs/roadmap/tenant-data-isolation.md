# Tenant and store data isolation

Status: IMPLEMENTED — validated; awaiting review, not merged.
Priority: P0
PR: https://github.com/mahendraek/FabClean-SaaS/pull/4
Implementation branch: `codex/pr-4-tenant-isolation`

## Scope and resulting behavior

Operational reads and writes require a valid session, active brand and active store. The selected store must belong to the active brand and the user's valid role assignments. Missing selection returns 409; unauthorized selection returns 403; foreign detail identifiers return 404.

All operational data, including customers, orders, garments, photos, payments, service catalogs, settings, offers, rewards, referrals, scheduling, subscriptions, notifications and AI logs, is restricted to the selected store. Store managers cannot assign broader roles. SuperAdmin does not gain implicit all-store access to operational endpoints; platform brand management remains an explicit, separate path. Brand/store context discovery filters each brand's store memberships independently.

Cross-store customer sharing, transfers, inherited configuration and consolidated reporting are deliberately handled by later PRs #5, #8 and #12. Until those explicit workflows exist, new stores start with empty catalogs and safe default settings, and phone reuse is store-local.

## Storage and migration

`backend/tenant_scope.py` installs ownership columns and **forced PostgreSQL row-level security on 21 operational tables**. Every database connection receives the authenticated request scope; absent scope sees no operational rows. Role checks reject superuser/BYPASSRLS database connections, since PostgreSQL would otherwise bypass the policies even with FORCE enabled. Use a `NOSUPERUSER NOBYPASSRLS` database role that owns the application's schema for initialization.

Initialization runs in a transaction protected by an advisory lock. A schema-version marker makes repeated startup safe and prevents legacy seed/migration code from running globally after isolation is installed. Only initialization and controlled test fixtures use maintenance mode; HTTP handlers never accept maintenance settings or client-supplied database ownership.

- Original single-store configuration is assigned only to the baseline `fabclean/main`.
- Explicit historical order/customer ownership is preserved when consistent. Orders without resolvable ownership or with cross-store related records are quarantined; derived children inherit their parent's ownership. Unknown/unlinked logs remain hidden.
- Composite foreign keys reject new cross-store related records. Constraints are installed `NOT VALID` to preserve historical rows; new writes are still enforced. Inconsistent historical child references are quarantined during migration. Validate constraints after an operator audits/remediates historical data.
- Settings/service/category keys and order/item/garment barcode lookups are store-scoped. Identical barcodes can exist in separate stores and resolve only within the current store.
- Unscoped maintenance inspection requires a reviewed administrative script. Normal login must never assign legacy records to the current user. Back up a production database before applying schema changes; no production database was modified during development.
- The in-memory workflow keeps settings/catalogs in separate scope buckets and filters customer/order histories. It is a development demo with ephemeral data, not production persistence.

## Acceptance checks

Run from `backend`:

```sh
/workspace/.fabclean-venv/bin/python -m unittest discover -s tests -v
```

Without `FABCLEAN_TEST_DATABASE_URL`, PostgreSQL checks are explicitly skipped. To include them, securely set that variable to an isolated disposable PostgreSQL database owned by a non-superuser/non-BYPASSRLS role, then run the same command. The tests create unique fixtures and a temporary migration schema; they do not drop an existing database. Never point the test suite at production.

Validated on PostgreSQL 16 with a non-superuser table-owner role:

- 26 unit/API/integration/migration tests passed, with no skips when the test database was configured.
- Two stores in one brand and a second brand; shared service IDs and barcodes; scoped search, histories, financial totals and AI summaries.
- Foreign reads/writes and related-ID injection rejected; selected-scope permissions enforced; manager role escalation denied.
- RLS enforced for table owners and missing scopes; parallel request scopes do not bleed.
- Legacy upgrade and repeated initialization preserve legitimate rows and quarantine unknown/inconsistent ownership.
- Expo web production export passed for all 26 static routes.

The existing 19 frontend TypeScript errors predate this work and are tracked separately. Native iOS/Android execution was not performed; shared frontend source was not changed. Load/performance, broader session-hardening and deployment checks remain in PR #6, not unfinished isolation implementation.

## Boundaries

Target only `mahendraek/FabClean-SaaS`; never modify the original FabClean repository. Maintain web/mobile compatibility. Do not merge without explicit approval. Follow [the sequential development tracker](../DEVELOPMENT_TRACKER.md) for the next PR.
