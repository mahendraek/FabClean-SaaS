# PR #10 — OpenStreetMap delivery coverage

Implemented on 13 October 2026, based on accepted main `be01ff3`. Development branch: `codex/pr-10-service-area-maps`. Awaiting review; not merged or deployed. The running release remains PR #9 (`9e68ce3`). PR #11 and later work remains unstarted.

## Coverage and address source

Each selected service store owns one versioned coverage policy. Administrators enable enforcement and choose a radius or a union of simple polygon zones. Radius uses great-circle distance with an Earth radius of 6371.0088 km; miles convert at 1.609344 km. Units can change without changing the physical radius. A radius boundary and polygon edges/vertices are inside. Radius is bounded to 0.1–500 km. The reported distance is straight-line distance, not driving distance or a route estimate.

Store latitude/longitude come from the persisted store record, with brand-admin coordinate inputs in Brand & Stores. Coverage cannot be enabled until both valid coordinates exist. Customer addresses are explicitly typed and paired with a staff-confirmed map pin or numeric coordinates. Device/IP location and UI-provided store IDs cannot select the store or its policy. The system checks the pin against coverage; it does not independently geocode or verify that the textual address corresponds to that pin. The UI makes that confirmation explicit. Tax jurisdiction remains governed by PR #9, not the delivery pin.

Up to 20 zones per store support individual pickup, delivery and active flags. Each polygon has 3–100 unique, ordered vertices. Empty/zero-area, repeated closing vertices, intersecting/overlapping edges and date-line-spanning polygons are rejected. Concave polygons work; holes and driving-route buffers are out of scope. Combined pickup/delivery requires eligibility for both operations, which may be supplied by overlapping zones. Store capabilities and brand plan restrictions still apply.

## Isolation, migration and rollout

`store_delivery_coverage` has explicit brand/store ownership, a compound store/brand foreign key, a scoped primary key and forced PostgreSQL RLS, including for the table owner. Writes require admin permission and the selected authorized operational scope. Brand-before-order/store lock ordering serializes coverage writes with order creation/address updates; optimistic revisions prevent stale editor overwrites. Configuration writes append a scoped platform audit event. The demo policy map uses the same geometry and separate scope buckets; enabling coverage still requires a saved store origin, so normal map administration requires PostgreSQL.

Migrations add the coverage table and nullable pin columns to the already isolated `customer_subscriptions` table. Initialization is repeatable, runs with a NOSUPERUSER/NOBYPASSRLS owner and does not backfill or reclassify unknown historical addresses/orders.

Enforcement is opt-in per store. Unconfigured or explicitly disabled coverage returns `eligible: null`, labeled as the legacy scheduling workflow, rather than pretending an address is inside. Existing service-area postal filters, prices and fee rules remain available and are not automatically converted to polygons. Once enforcement is enabled, new non-walk-in orders require a valid service address and pin and are checked again by the server. Outside pins, missing coordinates or disabled requested capabilities block creation before customer writes.

Orders store the server-generated assessment: policy/revision, store origin, matched zones, submitted address/pin, fulfillment operation, straight-line distance and timestamp. Clients cannot supply an authoritative snapshot. Unrelated note/status/pricing changes preserve that assessment. Address, coordinate or fulfillment changes recheck current coverage; failures roll back. Policy or store-origin changes do not silently rewrite past orders. Changing to walk-in clears the current coverage assessment.

Recurring subscriptions can retain validated coordinate pairs through their existing scoped create/update APIs; enrollment includes optional coordinate inputs. Generation carries those pins into the order and checks current coverage again. Missing/outside scheduled pins block generation without advancing the next-pickup date or recording a run. The existing plan-only/walk-in fallback remains unchanged for subscriptions without a complete pickup schedule.

## API and web/mobile flows

- GET `/api/coverage`: selected-store policy, revision, saved origin and effective pickup/delivery capabilities.
- PUT `/api/coverage`: complete policy plus the expected revision; admin only.
- POST `/api/coverage/check`: address, latitude/longitude and requested fulfillment; returns inside/outside/not-enforced feedback. No caller-supplied jurisdiction/store/policy is accepted.
- Order create/update: optional `service_latitude` / `service_longitude`; server-only `coverage_snapshot` in responses.
- Existing subscription create/update: optional coordinate pairs for recurring pickup orders.

The responsive `/coverage` editor shows the saved store, radius or polygon overlays, units, polygon drawing/manual vertices, edit/undo/activation/removal confirmation, revision conflict handling and a saved-policy address preview. Counter pickup/delivery flows capture a confirmed address pin, invalidate it when inputs change, show eligibility feedback and submit coordinates. Order detail and printed receipts expose the recorded coverage assessment.

The map uses existing React Native Image/SVG dependencies on web/native, with visible raster tiles from `https://tile.openstreetmap.org/{z}/{x}/{y}.png`, zoom/pan/recenter controls and tap-to-select. Only the current viewport loads; there is no tile scraping, offline download or prefetch. Browser/native image HTTP caching is retained. Native requests identify FabClean with its repository URL. The map always displays linked © OpenStreetMap contributors / ODbL attribution. Tiles can fail without disabling coordinate entry, overlays or server checks. No public Nominatim geocoder, address autocomplete, API key or location permission is required.

## Validation and limits

The final common `scripts/validate.sh` gate passed: 136 backend tests without skips (119 baseline plus 17 coverage tests), 31 frontend tests, TypeScript, 31-route export, load gate and all six desktop/mobile browser suites. Geometry tests cover boundary/concavity/date-line behaviour, units, invalid policies, origin checks, scope isolation, direct API bypasses, snapshots, concurrent revisions, RLS/repeatable migration and recurring pin enforcement. Browser coverage includes radius/zone editing, units, stale revisions, validation/removal cancel, map taps, changed-pin invalidation, scheduled counter creation and direct API enforcement.

The load gate completed with zero errors and 216.93 requests/second; retained results are in [performance/pr10-load.json](performance/pr10-load.json). The mobile editor was visually inspected.

Browser tests use deterministic tile images on desktop and explicit tile failures on mobile while all coverage/order requests use the real disposable PostgreSQL API. Actual OpenStreetMap tile access was denied by the cloud proxy (CONNECT 403); this provider check is not a passing mocked network check. A saved environment draft adds `tile.openstreetmap.org` and `www.openstreetmap.org`, preserving Render access. Save/publish that draft to enable live tile checks in this cloud environment. This does not configure customers' own browser networks or change Render services. Native devices, live provider tiles and authenticated production coverage execution remain unverified. No production fixtures or operational writes were used.

## Publication evidence

Implementation SHA, verified remote refs and final validation outcome are recorded after the combined gate completes. GitHub hosted CI/review/open/closed state must be reported separately from Git publication. Explicit approval is required before merge and deployment; the earlier PR #9 release approval does not authorize PR #10.
